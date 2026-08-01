from __future__ import annotations

import asyncio
import json
import re

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    HttpClient,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.request_context import (
    wot_account_search_config,
    wot_game_tank_info_config,
    wot_player_vehicles_config,
    wot_player_statistics_config,
    wot_player_summary_config,
    wot_player_achievements_config,
    wot_player_profile_config,
)

_ACHIEVEMENT_MEDIA_ROOT = "https://static-cdn.wotgame.cn/dcont/"


async def fetch_account_search(player_name: str):
    """从WOT官网获取账号搜索结果"""
    async with HttpClient() as client:
        params = wot_account_search_config.build_params()
        params["name"] = player_name
        params["name_gt"] = ""
        return await client.send_get(wot_account_search_config, params)


async def fetch_all_tank_info():
    """从WOT官网获取全量坦克数据"""
    async with HttpClient() as client:
        try:
            logger.info("Fetching full tank data...")
            return await client.send_post(
                config=wot_game_tank_info_config,
                data=dict(wot_game_tank_info_config.data),
            )
        except Exception as exc:
            logger.error(f"Failed to fetch full tank data: {exc}")
            return None


def normalize_player_vehicles(payload: dict) -> list[dict]:
    """将官方车辆接口的参数数组转换为车库服务使用的字典列表。"""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []

    parameters = data.get("parameters") or []
    rows = data.get("data") or []
    if not parameters or not rows:
        return []

    entries: list[dict] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        raw = dict(zip(parameters, row))
        entries.append(
            {
                "vehicle_cd": raw.get("vehicle_cd"),
                "vehicle_name": raw.get("name") or "未知",
                "vlevel": raw.get("tier") or "",
                "vtype": raw.get("type") or "",
                "battles": raw.get("battles_count") or 0,
                "win_rate": raw.get("wins_ratio") or 0,
                "avg_frags": raw.get("frags_per_battle_average") or 0,
                "damage_avg": raw.get("damage_per_battle_average") or 0,
                "xp_per_battle_average": raw.get("xp_per_battle_average") or 0,
                "frags_per_battle_average": raw.get("frags_per_battle_average") or 0,
                "marksOnGun": raw.get("marksOnGun"),
                "markOfMastery": raw.get("markOfMastery"),
            }
        )
    return entries


async def fetch_garage_all(account_id: str) -> tuple[str, list[dict], int]:
    """获取官方玩家页面中的车辆战绩列表。"""
    request_data = {
        "battle_type": "random",
        "only_in_garage": [0, 1],
        "spa_id": int(account_id),
        "premium": [0, 1],
        "collector_vehicle": [0, 1],
        "nation": [],
        "role": [],
        "type": [],
        "tier": [7, 8, 9, 10, 11],
        "language": "zh-cn",
    }

    async with HttpClient() as client:
        response = await client.send_post(
            config=wot_player_vehicles_config,
            json_data=request_data,
        )
        if response.status != 200:
            raise ValueError(f"官方车辆接口 HTTP {response.status}")
        payload = await response.json()

    if payload.get("status") != "ok":
        raise ValueError(f"官方车辆接口错误: {payload.get('status')}")

    entries = normalize_player_vehicles(payload)
    # 官方车辆接口不返回昵称，调用方使用已解析出的玩家名称展示。
    return "", entries, len(entries)


_NATION_NAMES = {
    "china": "C系",
    "ussr": "S系",
    "germany": "D系",
    "usa": "M系",
    "france": "F系",
    "uk": "Y系",
    "japan": "R系",
    "czech": "J系",
    "sweden": "V系",
    "poland": "B系",
    "italy": "I系",
}

_TYPE_NAMES = {
    "lightTank": "轻型坦克",
    "mediumTank": "中型坦克",
    "heavyTank": "重型坦克",
    "AT-SPG": "自行反坦克炮",
    "SPG": "自行火炮",
}


def _normalize_distribution(
    values: object,
    names: dict[str, str] | None = None,
) -> list[dict]:
    if not isinstance(values, dict):
        return []
    result: list[dict] = []
    for code, value in values.items():
        if not isinstance(value, dict):
            continue
        result.append(
            {
                "code": code,
                "name": (names or {}).get(str(code), str(code)),
                "battles": value.get("battles_count") or 0,
                "battle_percent": value.get("battles_count_percent") or 0,
                "wins": value.get("wins_count") or 0,
                "win_rate": value.get("wins_count_percent") or 0,
                "master_count": value.get("master_count") or 0,
            }
        )
    return result


def _normalize_profile_page(html: str) -> dict:
    marker = "USER_DATA ="
    marker_index = html.find(marker)
    user_data: dict = {}
    if marker_index >= 0:
        object_index = html.find("{", marker_index + len(marker))
        if object_index >= 0:
            try:
                decoded, _ = json.JSONDecoder().raw_decode(html[object_index:])
                if isinstance(decoded, dict):
                    user_data = decoded
            except (json.JSONDecodeError, TypeError):
                pass

    clan = user_data.get("clan_info") or {}
    emblem_match = re.search(
        r"clan-box_img[^>]+background-image:url\((?P<url>[^)]+)\)", html
    )
    emblem_url = emblem_match.group("url").strip("'\"") if emblem_match else ""
    if emblem_url.startswith("//"):
        emblem_url = f"https:{emblem_url}"
    return {
        "nickname": user_data.get("nickname") or "",
        "registered_at": user_data.get("reg_timestamp") or 0,
        "last_battle_at": (user_data.get("summary") or {}).get("last_battle_at") or 0,
        "clan": {
            "tag": clan.get("tag") or "",
            "name": clan.get("name") or "",
            "color": clan.get("color") or "#d8d3c6",
            "role": clan.get("role") or "",
            "days": clan.get("days_in_clan") or 0,
            "emblem_url": emblem_url,
        },
    }


def _normalize_achievements(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return {}
    parameters = data.get("parameters") or []
    achievements = []
    for row in data.get("data") or []:
        if not isinstance(row, list):
            continue
        item = dict(zip(parameters, row))
        icon = str(item.get("icon") or "")
        if icon and not icon.startswith(("http://", "https://")):
            icon = f"{_ACHIEVEMENT_MEDIA_ROOT}{icon.lstrip('/')}"
        achievements.append(
            {
                "name": item.get("mark") or item.get("name") or "",
                "value": item.get("value") or 0,
                "icon_url": icon,
            }
        )
    mastery = data.get("mastery") or {}
    return {
        "mastery_count": mastery.get("mastery_count") or 0,
        "vehicles_count": mastery.get("vehicles_count") or 0,
        "unique_count": data.get("unique_achievements_count") or 0,
        "total_count": data.get("total_achievements_count") or 0,
        "items": achievements,
    }


def normalize_player_career(
    summary_payload: dict,
    statistics_payload: dict,
    profile: dict | None = None,
    achievements: dict | None = None,
) -> dict:
    """将官网生涯接口响应转换为统一的标准模式统计结构。"""
    summary_data = summary_payload.get("data") if isinstance(summary_payload, dict) else None
    statistics_data = (
        statistics_payload.get("data") if isinstance(statistics_payload, dict) else None
    )
    if not isinstance(summary_data, dict):
        summary_data = {}
    if not isinstance(statistics_data, dict):
        statistics_data = {}

    return {
        "profile": profile or {},
        "achievements": achievements or {},
        "summary": {
            "battles": statistics_data.get("battles_count")
            or summary_data.get("battles_count")
            or 0,
            "wins": statistics_data.get("wins_count") or 0,
            "losses": statistics_data.get("losses_count") or 0,
            "win_rate": statistics_data.get("wins_count_percent")
            or summary_data.get("wins_ratio")
            or 0,
            "losses_rate": statistics_data.get("losses_count_percent") or 0,
            "survived": statistics_data.get("survived_battles") or 0,
            "survived_rate": statistics_data.get("survived_battles_percent") or 0,
            "damage_ratio": statistics_data.get("damage_coefficient") or 0,
            "frags_deaths_ratio": statistics_data.get("frags_count_coefficient") or 0,
            "armor_ratio": statistics_data.get("damage_blocked_coefficient") or 0,
            "capture_points": statistics_data.get("capture_points") or 0,
            "defense_points": statistics_data.get("dropped_capture_points") or 0,
            "frags_total": summary_data.get("frags_count") or 0,
            "max_assisted": summary_data.get("assisted_max") or 0,
            "max_blocked": summary_data.get("blocked_max") or 0,
            "wtr": summary_data.get("wtr") or 0,
        },
        "average": {
            "xp": statistics_data.get("xp_amount_avg")
            or summary_data.get("xp_per_battle_average")
            or 0,
            "damage": statistics_data.get("damage_dealt_avg")
            or summary_data.get("damage_per_battle_average")
            or 0,
            "damage_received": statistics_data.get("damage_received_avg") or 0,
            "stun": statistics_data.get("stun_num_avg") or 0,
            "assisted_damage": statistics_data.get("damage_assisted_avg")
            or summary_data.get("battle_avg_assisted")
            or 0,
            "assisted_stun_damage": statistics_data.get("damage_assisted_stun_avg")
            or 0,
            "blocked_damage": summary_data.get("battle_avg_blocked") or 0,
            "spotted": statistics_data.get("spotted_count_avg") or 0,
            "frags": statistics_data.get("frags_count_avg") or 0,
        },
        "records": {
            "max_frags": statistics_data.get("frags_max")
            or summary_data.get("frags_max")
            or 0,
            "max_xp": statistics_data.get("xp_max") or summary_data.get("xp_max") or 0,
            "max_damage": statistics_data.get("damage_max")
            or summary_data.get("damage_max")
            or 0,
        },
        "master_levels": [
            {
                "name": name,
                "count": (statistics_data.get("master_level_counts") or {}).get(
                    str(code), 0
                ),
            }
            for code, name in ((4, "特级"), (3, "I级"), (2, "II级"), (1, "III级"))
        ],
        "tiers": _normalize_distribution(statistics_data.get("tiers"), {
            str(tier): f"{tier}级" for tier in range(1, 12)
        }),
        "nations": _normalize_distribution(statistics_data.get("nations"), _NATION_NAMES),
        "types": _normalize_distribution(statistics_data.get("types"), _TYPE_NAMES),
    }


async def fetch_player_career(account_id: str) -> dict:
    """获取官网玩家页面的标准模式生涯统计。"""
    params = {"spa_id": int(account_id), "battle_type": "random"}
    async with HttpClient() as client:
        profile_config = type(wot_player_profile_config)()
        profile_config.base_url = (
            f"https://wotgame.cn/zh-cn/community/accounts/{int(account_id)}/"
        )
        summary_response, statistics_response, profile_response, achievements_response = await asyncio.gather(
            client.send_get(wot_player_summary_config, params),
            client.send_get(wot_player_statistics_config, params),
            client.send_get(profile_config),
            client.send_get(wot_player_achievements_config, params),
        )
        if summary_response.status != 200:
            raise ValueError(f"官方玩家总览接口 HTTP {summary_response.status}")
        if statistics_response.status != 200:
            raise ValueError(f"官方玩家统计接口 HTTP {statistics_response.status}")
        if profile_response.status != 200:
            raise ValueError(f"官方玩家主页 HTTP {profile_response.status}")
        summary_payload, statistics_payload = await asyncio.gather(
            summary_response.json(), statistics_response.json()
        )
        profile_html = await profile_response.text()
        achievements_payload = (
            await achievements_response.json()
            if achievements_response.status == 200
            else {}
        )

    if summary_payload.get("status") != "ok":
        raise ValueError(f"官方玩家总览接口错误: {summary_payload.get('status')}")
    if statistics_payload.get("status") != "ok":
        raise ValueError(f"官方玩家统计接口错误: {statistics_payload.get('status')}")
    return normalize_player_career(
        summary_payload,
        statistics_payload,
        _normalize_profile_page(profile_html),
        _normalize_achievements(achievements_payload),
    )
