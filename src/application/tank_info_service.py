from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.report import Tank
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wotbox_camp_api import (
    fetch_tank_wiki_profile,
    fetch_tank_wiki_summary,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    find_tank_candidates_by_name,
    find_tanks_by_name,
    get_tank_full_info,
)

_WIKI_CACHE_TTL_SECONDS = 24 * 60 * 60
_wiki_cache: dict[int, tuple[float, dict, dict]] = {}
_wiki_cache_lock = threading.Lock()

_CATEGORY_TITLES = {
    "装备": "火力与炮控",
    "护甲": "生存与防护",
    "移动": "机动性能",
    "视野和隐蔽": "视野与隐蔽",
}

_FITTING_TYPES = {
    "gun": "火炮",
    "turret": "炮塔",
    "engine": "发动机",
    "suspension": "悬挂",
    "radio": "电台",
}

_MODULE_UNIQUE_FIELDS = {
    "gun": ("口径，毫米", "伤害，HP", "穿透，毫米"),
    "turret": ("炮塔生命值，HP",),
    "engine": ("起火几率，%",),
    "suspension": (),
    "radio": (),
}

_PREFERRED_DEPLOY_NAMES = {"高级配置", "顶级配置", "完全体", "满配"}
_GUN_SUMMARY_DUPLICATE_KEYS = {"ammo_damage", "ammo_penetration"}


@dataclass(frozen=True)
class TankReport:
    text: str
    hero_images: tuple[tuple[str, str], ...] = ()


def _clean_name(name: str) -> str:
    for quote in '"“”‘’\'':
        name = name.replace(quote, "")
    return name.strip()


def _fmt(value, digits: int = 0) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.{digits}f}"


def _pretty_value(value) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _tank_label(tank: Tank) -> str:
    tags = [f"{tank.tier}级", tank.nation.display_name, tank.type.display_name]
    if tank.role.display_name not in ("", "通用/无定位"):
        tags.append(tank.role.display_name)
    if tank.premium:
        tags.append("金币/特种")
    return " · ".join(tags)


def _ambiguous_text(query: str, matches: list[Tank]) -> str:
    names = "、".join(_clean_name(tank.name) for tank in matches[:12])
    return f"坦克名称「{_clean_name(query)}」匹配到多个结果：{names}\n请使用更完整的名称"


def _detail_lines(tank: Tank) -> list[str]:
    info = get_tank_full_info(tank)
    return [
        f"{_clean_name(tank.name)} 坦克百科",
        _tank_label(tank),
        f"生命值：{_fmt(info.get('max_health'))}",
        f"单发伤害：{_fmt(info.get('damage1'))}",
        f"每分钟伤害：{_fmt(info.get('damage_per_minute'))}",
        "穿深："
        + "/".join(
            _fmt(info.get(key)) for key in ("piercing1", "piercing2", "piercing3")
        ),
        f"精度：{_fmt(info.get('shot_dispersion_radius'), 2)}",
        f"瞄准时间：{_fmt(info.get('aiming_time'), 2)} 秒",
        f"前进极速：{_fmt(info.get('speed_forward_kmh'))} km/h",
        f"功重比：{_fmt(info.get('power_weight_ratio'), 2)} hp/t",
        f"车体转速：{_fmt(info.get('chassis_rotation_speed_deg'))} 度/秒",
        f"炮塔转速：{_fmt(info.get('turret_rotation_speed_deg'))} 度/秒",
        f"视野：{_fmt(info.get('circular_vision_radius'))} 米",
    ]


def build_tank_info_text(tank_name: str) -> str:
    """从每日同步的完整坦克库构建百科文本。"""
    matches = find_tanks_by_name(tank_name)
    if not matches:
        return f"未找到坦克「{_clean_name(tank_name)}」，请检查名称是否正确"
    if len(matches) > 1:
        return _ambiguous_text(tank_name, matches)
    lines = _detail_lines(matches[0])
    lines.append("数据来源：游戏官方/WotInspector 同步资料")
    return "\n".join(lines)


async def _get_wiki_data(tank: Tank) -> tuple[dict, dict]:
    """读取坦克营地百科数据并缓存 24 小时。"""
    now = time.time()
    with _wiki_cache_lock:
        cached = _wiki_cache.get(tank.vehicle_cd)
        if cached and now - cached[0] < _WIKI_CACHE_TTL_SECONDS:
            return cached[1], cached[2]

    summary_result, profile_result = await asyncio.gather(
        fetch_tank_wiki_summary(tank.vehicle_cd),
        fetch_tank_wiki_profile(tank.vehicle_cd),
        return_exceptions=True,
    )
    summary = summary_result if isinstance(summary_result, dict) else {}
    profile = profile_result if isinstance(profile_result, dict) else {}
    if isinstance(summary_result, Exception):
        logger.warning(f"坦克百科图片查询失败 (tank_id={tank.vehicle_cd}): {summary_result}")
    if isinstance(profile_result, Exception):
        logger.warning(f"坦克百科详情查询失败 (tank_id={tank.vehicle_cd}): {profile_result}")

    # 部分成功通常只是瞬时网络故障，不将缺失的一半长期缓存。
    if summary and profile:
        with _wiki_cache_lock:
            _wiki_cache[tank.vehicle_cd] = (time.time(), summary, profile)
    return summary, profile


def _format_parameter(parameter: dict) -> str:
    key = str(parameter.get("key") or "")
    name = str(parameter.get("name") or key or "未知参数")
    value = parameter.get("current")
    if key == "gun_move_down_arc":
        return f"射击俯角：-{_pretty_value(abs(float(value or 0)))}°"
    if key == "gun_move_up_arc":
        return f"射击仰角：+{_pretty_value(value)}°"
    return f"{name}：{_pretty_value(value)}"


def _preferred_deploy(item: dict) -> dict | None:
    deploys = [deploy for deploy in item.get("deploy_list") or [] if isinstance(deploy, dict)]
    if not deploys:
        return None
    return max(
        enumerate(deploys),
        key=lambda pair: (
            1 if str(pair[1].get("name") or "").strip() in _PREFERRED_DEPLOY_NAMES else 0,
            pair[0],
        ),
    )[1]


def _profile_groups(profile: dict) -> list[tuple[str, list[dict]]]:
    groups: list[tuple[str, list[dict]]] = []
    for item in profile.get("tank_info_list") or []:
        raw_title = str(item.get("name") or "其他参数")
        title = _CATEGORY_TITLES.get(raw_title, raw_title)
        deploy = _preferred_deploy(item)
        parameters = list(deploy.get("parameter_list") or []) if deploy else []
        if raw_title == "装备" and _find_fitting(profile, "gun"):
            parameters = [
                parameter
                for parameter in parameters
                if str(parameter.get("key") or "")
                not in _GUN_SUMMARY_DUPLICATE_KEYS
            ]
        if parameters:
            groups.append((title, parameters))
    return groups


def _find_fitting(profile: dict, fitting_type: str) -> dict | None:
    for item in profile.get("tank_info_list") or []:
        deploy = _preferred_deploy(item)
        for fitting in (deploy or {}).get("fittings") or []:
            if str(fitting.get("type") or "") == fitting_type:
                return fitting
    return None


def _gun_module_lines(profile: dict) -> list[str]:
    fitting = _find_fitting(profile, "gun")
    if not fitting:
        return []
    lines = [f"火炮型号：{_clean_name(str(fitting.get('title') or '未知'))}"]
    tier = str(fitting.get("tier") or "")
    if tier:
        lines.append(f"火炮等级：{tier}")
    for detail in fitting.get("fit_list") or []:
        detail_name = str(detail.get("name") or "")
        if detail_name not in _MODULE_UNIQUE_FIELDS["gun"]:
            continue
        lines.append(f"{detail_name}：{_pretty_value(detail.get('value'))}")
    return lines


def _engine_module_lines(profile: dict) -> list[str]:
    fitting = _find_fitting(profile, "engine")
    if not fitting:
        return []
    lines: list[str] = []
    tier = str(fitting.get("tier") or "")
    if tier:
        lines.append(f"发动机等级：{tier}")
    for detail in fitting.get("fit_list") or []:
        detail_name = str(detail.get("name") or "")
        if detail_name not in _MODULE_UNIQUE_FIELDS["engine"]:
            continue
        lines.append(f"{detail_name}：{_pretty_value(detail.get('value'))}")
    return lines


def _build_detailed_text(tank: Tank, profile: dict) -> str:
    name = _clean_name(str(profile.get("name") or tank.name))
    sections = [f"{name} 坦克百科\n{_tank_label(tank)}"]
    rendered_titles: set[str] = set()
    for title, parameters in _profile_groups(profile):
        rendered_titles.add(title)
        lines = [f"【{title}】"]
        if title == "火力与炮控":
            lines.extend(_gun_module_lines(profile))
        elif title == "机动性能":
            lines.extend(_engine_module_lines(profile))
        lines.extend(_format_parameter(parameter) for parameter in parameters)
        sections.append("\n".join(lines))
    if "机动性能" not in rendered_titles:
        engine_lines = _engine_module_lines(profile)
        if engine_lines:
            sections.append("\n".join(["【机动性能】", *engine_lines]))
    sections.append("数据来源：坦克营地（优选配置）")
    return "\n\n".join(sections)


async def build_tank_info_report(tank_name: str) -> TankReport:
    """构建带车辆图片的完整坦克百科；外部接口失败时使用本地简版。"""
    matches = find_tanks_by_name(tank_name)
    if not matches:
        return TankReport(f"未找到坦克「{_clean_name(tank_name)}」，请检查名称是否正确")
    if len(matches) > 1:
        return TankReport(_ambiguous_text(tank_name, matches))

    tank = matches[0]
    summary, profile = await _get_wiki_data(tank)
    image_url = str(summary.get("tanke_image") or "")
    images = ((_clean_name(tank.name), image_url),) if image_url else ()
    if profile.get("tank_info_list"):
        return TankReport(_build_detailed_text(tank, profile), images)
    return TankReport(build_tank_info_text(tank_name), images)


def split_comparison_query(argument: str) -> tuple[str, str] | None:
    """将两个允许包含空格的坦克名称拆开；坦克名之间必须有分隔。"""
    argument = argument.strip()
    if "和" in argument and " 和 " not in argument:
        return None
    for separator in (" 和 ", " vs ", " VS ", " / ", " 对比 "):
        if separator in argument:
            left, right = argument.split(separator, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()

    parts = argument.split()
    candidates: list[tuple[str, str]] = []
    for index in range(1, len(parts)):
        left = " ".join(parts[:index])
        right = " ".join(parts[index:])
        if (find_tanks_by_name(left) or find_tank_candidates_by_name(left)) and (
            find_tanks_by_name(right) or find_tank_candidates_by_name(right)
        ):
            candidates.append((left, right))
    return candidates[0] if len(candidates) == 1 else None


def build_tank_comparison_text(argument: str) -> str:
    pair = split_comparison_query(argument)
    if not pair:
        return "请提供两辆坦克，名称之间保留空格，例如：坦克对比 59式 查狄伦 25t"
    left_name, right_name = pair
    left_matches = find_tanks_by_name(left_name)
    right_matches = find_tanks_by_name(right_name)
    if not left_matches:
        return f"未找到坦克「{_clean_name(left_name)}」"
    if not right_matches:
        return f"未找到坦克「{_clean_name(right_name)}」"
    if len(left_matches) > 1:
        return _ambiguous_text(left_name, left_matches)
    if len(right_matches) > 1:
        return _ambiguous_text(right_name, right_matches)

    left, right = left_matches[0], right_matches[0]
    left_info, right_info = get_tank_full_info(left), get_tank_full_info(right)
    rows = [
        ("等级", left.tier, right.tier, 0),
        ("生命值", left_info.get("max_health"), right_info.get("max_health"), 0),
        ("单发伤害", left_info.get("damage1"), right_info.get("damage1"), 0),
        ("每分钟伤害", left_info.get("damage_per_minute"), right_info.get("damage_per_minute"), 0),
        ("标准弹穿深", left_info.get("piercing1"), right_info.get("piercing1"), 0),
        ("精度", left_info.get("shot_dispersion_radius"), right_info.get("shot_dispersion_radius"), 2),
        ("瞄准时间", left_info.get("aiming_time"), right_info.get("aiming_time"), 2),
        ("前进极速", left_info.get("speed_forward_kmh"), right_info.get("speed_forward_kmh"), 0),
        ("功重比", left_info.get("power_weight_ratio"), right_info.get("power_weight_ratio"), 2),
        ("车体转速", left_info.get("chassis_rotation_speed_deg"), right_info.get("chassis_rotation_speed_deg"), 0),
        ("视野", left_info.get("circular_vision_radius"), right_info.get("circular_vision_radius"), 0),
    ]
    lines = [
        f"坦克对比：{_clean_name(left.name)} vs {_clean_name(right.name)}",
        f"类型：{_tank_label(left)} | {_tank_label(right)}",
    ]
    lines.extend(
        f"{label}：{_fmt(left_value, digits)} | {_fmt(right_value, digits)}"
        for label, left_value, right_value, digits in rows
    )
    lines.append("数据来源：游戏官方/WotInspector 同步资料")
    return "\n".join(lines)


def _parameter_map(profile: dict) -> dict[str, tuple[str, list[str], dict[str, object]]]:
    result: dict[str, tuple[str, list[str], dict[str, object]]] = {}
    for title, parameters in _profile_groups(profile):
        order: list[str] = []
        values: dict[str, object] = {}
        for parameter in parameters:
            key = str(parameter.get("key") or parameter.get("name") or "")
            if not key:
                continue
            order.append(key)
            values[key] = parameter
        result[title] = (title, order, values)
    return result


def _comparison_parameter_value(parameter: dict | None) -> str:
    if not parameter:
        return "-"
    key = str(parameter.get("key") or "")
    value = parameter.get("current")
    if key == "gun_move_down_arc":
        return f"-{_pretty_value(abs(float(value or 0)))}°"
    if key == "gun_move_up_arc":
        return f"+{_pretty_value(value)}°"
    return _pretty_value(value)


def _comparison_parameter_label(parameter: dict, key: str) -> str:
    if key == "gun_move_down_arc":
        return "射击俯角"
    if key == "gun_move_up_arc":
        return "射击仰角"
    return str(parameter.get("name") or key)


def _gun_comparison_lines(left_profile: dict, right_profile: dict) -> list[str]:
    left = _find_fitting(left_profile, "gun") or {}
    right = _find_fitting(right_profile, "gun") or {}
    lines = [
        "火炮型号："
        f"{_clean_name(str(left.get('title') or '-'))} | "
        f"{_clean_name(str(right.get('title') or '-'))}",
        f"火炮等级：{left.get('tier') or '-'} | {right.get('tier') or '-'}",
    ]
    left_details = {
        str(detail.get("name") or ""): detail.get("value")
        for detail in left.get("fit_list") or []
    }
    right_details = {
        str(detail.get("name") or ""): detail.get("value")
        for detail in right.get("fit_list") or []
    }
    for label in _MODULE_UNIQUE_FIELDS["gun"]:
        lines.append(
            f"{label}：{_pretty_value(left_details.get(label))} | "
            f"{_pretty_value(right_details.get(label))}"
        )
    return lines


def _engine_comparison_lines(left_profile: dict, right_profile: dict) -> list[str]:
    left = _find_fitting(left_profile, "engine") or {}
    right = _find_fitting(right_profile, "engine") or {}
    lines = [
        f"发动机等级：{left.get('tier') or '-'} | {right.get('tier') or '-'}",
    ]
    left_details = {
        str(detail.get("name") or ""): detail.get("value")
        for detail in left.get("fit_list") or []
    }
    right_details = {
        str(detail.get("name") or ""): detail.get("value")
        for detail in right.get("fit_list") or []
    }
    for label in _MODULE_UNIQUE_FIELDS["engine"]:
        lines.append(
            f"{label}：{_pretty_value(left_details.get(label))} | "
            f"{_pretty_value(right_details.get(label))}"
        )
    return lines


def _build_detailed_comparison(
    left: Tank, right: Tank, left_profile: dict, right_profile: dict
) -> str:
    left_name, right_name = _clean_name(left.name), _clean_name(right.name)
    sections = [
        f"坦克对比：{left_name} vs {right_name}\n"
        f"{_tank_label(left)} | {_tank_label(right)}"
    ]
    left_groups = _parameter_map(left_profile)
    right_groups = _parameter_map(right_profile)
    group_order = list(left_groups)
    group_order.extend(title for title in right_groups if title not in left_groups)
    if (
        "机动性能" not in group_order
        and (_find_fitting(left_profile, "engine") or _find_fitting(right_profile, "engine"))
    ):
        group_order.append("机动性能")
    for title in group_order:
        left_group = left_groups.get(title, (title, [], {}))
        right_group = right_groups.get(title, (title, [], {}))
        keys = list(left_group[1])
        keys.extend(key for key in right_group[1] if key not in keys)
        lines = [f"【{title}】", f"项目：{left_name} | {right_name}"]
        if title == "火力与炮控":
            lines.extend(_gun_comparison_lines(left_profile, right_profile))
        elif title == "机动性能":
            lines.extend(_engine_comparison_lines(left_profile, right_profile))
        for key in keys:
            left_parameter = left_group[2].get(key)
            right_parameter = right_group[2].get(key)
            source = left_parameter or right_parameter or {}
            label = _comparison_parameter_label(source, key)
            lines.append(
                f"{label}：{_comparison_parameter_value(left_parameter)} | "
                f"{_comparison_parameter_value(right_parameter)}"
            )
        sections.append("\n".join(lines))

    sections.append("数据来源：坦克营地（优选配置）")
    return "\n\n".join(sections)


async def build_tank_comparison_report(argument: str) -> TankReport:
    """构建带双车图片的完整参数对比。"""
    pair = split_comparison_query(argument)
    if not pair:
        return TankReport(
            "请提供两辆坦克，名称之间保留空格，例如：坦克对比 59式 查狄伦 25t"
        )
    left_matches = find_tanks_by_name(pair[0])
    right_matches = find_tanks_by_name(pair[1])
    if not left_matches or not right_matches or len(left_matches) != 1 or len(right_matches) != 1:
        return TankReport(build_tank_comparison_text(argument))

    left, right = left_matches[0], right_matches[0]
    (left_summary, left_profile), (right_summary, right_profile) = await asyncio.gather(
        _get_wiki_data(left), _get_wiki_data(right)
    )
    images = tuple(
        (label, url)
        for label, url in (
            (_clean_name(left.name), str(left_summary.get("tanke_image") or "")),
            (_clean_name(right.name), str(right_summary.get("tanke_image") or "")),
        )
        if url
    )
    if left_profile.get("tank_info_list") and right_profile.get("tank_info_list"):
        return TankReport(
            _build_detailed_comparison(left, right, left_profile, right_profile),
            images,
        )
    return TankReport(build_tank_comparison_text(argument), images)
