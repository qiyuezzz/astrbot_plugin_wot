from __future__ import annotations

import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_game_api import (
    fetch_player_career,
)

_CAREER_CACHE_TTL_SECONDS = 5 * 60
_CAREER_CACHE_MAX_ENTRIES = 128
_career_cache: dict[str, tuple[float, dict]] = {}
_career_lock = threading.Lock()

_WTR_LEVELS = (
    (0, "青铜I"),
    (400, "青铜II"),
    (1000, "青铜III"),
    (1400, "白银I"),
    (1900, "白银II"),
    (2700, "白银III"),
    (3200, "黄金I"),
    (3900, "黄金II"),
    (4800, "黄金III"),
    (5400, "王牌I"),
    (6200, "王牌II"),
    (7300, "王牌III"),
    (8000, "传奇I"),
    (8800, "传奇II"),
    (9900, "传奇III"),
)

_CLAN_ROLE_NAMES = {
    "commander": "指挥官",
    "executive_officer": "副指挥官",
    "personnel_officer": "人事官",
    "combat_officer": "作战官",
    "intelligence_officer": "情报官",
    "quartermaster": "后勤官",
    "recruitment_officer": "征兵官",
    "junior_officer": "初级军官",
    "private": "士兵",
    "recruit": "招募",
    "reservist": "预备役",
}


def _number(value: object, digits: int = 0) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    if digits:
        return f"{number:,.{digits}f}"
    return f"{number:,.0f}"


def _date(value: object, include_time: bool = False) -> str:
    try:
        timestamp = int(float(value or 0))
    except (TypeError, ValueError):
        return "—"
    if timestamp <= 0:
        return "—"
    date = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Shanghai"))
    return date.strftime("%Y年%m月%d日 %H:%M" if include_time else "%Y年%m月%d日")


def _format_distribution(title: str, entries: list[dict]) -> str:
    lines = [title]
    for entry in entries:
        lines.append(
            f"{entry.get('name') or entry.get('code') or '未知'}："
            f"{_number(entry.get('battles'))}场 · "
            f"占比{_number(entry.get('battle_percent'), 2)}% · "
            f"胜率{_number(entry.get('win_rate'), 2)}% · "
            f"MB{_number(entry.get('master_count'))}"
        )
    return "\n".join(lines)


def _format_stats_section(title: str, values: list[tuple[str, str]]) -> str:
    return "\n".join([title, *(f"{label}：{value}" for label, value in values)])


def _wtr_title(value: object) -> str:
    try:
        score = float(value or 0)
    except (TypeError, ValueError):
        score = 0
    title = _WTR_LEVELS[0][1]
    for threshold, level in _WTR_LEVELS:
        if score >= threshold:
            title = level
    return title


def _format_career(player_name: str, career: dict) -> str:
    profile = career.get("profile") or {}
    clan = profile.get("clan") or {}
    achievements = career.get("achievements") or {}
    summary = career.get("summary") or {}
    average = career.get("average") or {}
    records = career.get("records") or {}
    battles = int(float(summary.get("battles") or 0))
    if battles <= 0:
        return f"{player_name} 暂无标准模式生涯统计\n\n数据来源：游戏官网"

    master_levels = list(career.get("master_levels") or [])
    master_total = sum(int(float(entry.get("count") or 0)) for entry in master_levels)
    dashboard_section = "\n".join(
        [
            "数据",
            f"玩家名称：{profile.get('nickname') or player_name}",
            f"账号创建于：{_date(profile.get('registered_at'))}",
            f"最后战斗时间：{_date(profile.get('last_battle_at'), True)}",
            f"军团标签：{clan.get('tag') or ''}",
            f"军团名称：{clan.get('name') or ''}",
            f"军团颜色：{clan.get('color') or '#d8d3c6'}",
            f"军团职务：{_CLAN_ROLE_NAMES.get(str(clan.get('role') or ''), clan.get('role') or '')}",
            f"入团天数：{_number(clan.get('days')) if clan.get('days') else ''}",
            f"军团徽章：{clan.get('emblem_url') or ''}",
            f"WTR评级：{_number(summary.get('wtr'))}（{_wtr_title(summary.get('wtr'))}）",
            f"损伤记录：{_number(records.get('max_damage'))} · 场均{_number(average.get('damage'))}",
            f"获得经验：{_number(records.get('max_xp'))} · 场均{_number(average.get('xp'))}",
            f"参战场次：{_number(summary.get('battles'))} · 胜率{_number(summary.get('win_rate'), 2)}%",
            f"击毁坦克：{_number(summary.get('frags_total'))} · 记录{_number(records.get('max_frags'))}",
            f"协助损伤：{_number(summary.get('max_assisted'))} · 场均{_number(average.get('assisted_damage'))}",
            f"抵挡损伤：{_number(summary.get('max_blocked'))} · 场均{_number(average.get('blocked_damage'))}",
            "战斗勋章："
            f"特级M {_number(achievements.get('mastery_count') or next((entry.get('count') for entry in master_levels if entry.get('name') == '特级'), 0))}"
            f" / {_number(achievements.get('vehicles_count'))} · "
            f"独特 {_number(achievements.get('unique_count'))} · "
            f"总计 {_number(achievements.get('total_count') or master_total)}",
        ]
    )
    sections = [
        dashboard_section,
        _format_stats_section(
            "总成绩",
            [
                ("场次", _number(summary.get("battles"))),
                ("胜率", f"{_number(summary.get('wins'))}（{_number(summary.get('win_rate'), 2)}%）"),
                ("失败", f"{_number(summary.get('losses'))}（{_number(summary.get('losses_rate'), 2)}%）"),
                ("幸存率", f"{_number(summary.get('survived'))}（{_number(summary.get('survived_rate'), 2)}%）"),
                ("损伤率", _number(summary.get("damage_ratio"), 2)),
                ("战损比", _number(summary.get("frags_deaths_ratio"), 2)),
                ("装甲特性", _number(summary.get("armor_ratio"), 2)),
                ("占领基地点数", _number(summary.get("capture_points"))),
                ("防御基地点数", _number(summary.get("defense_points"))),
            ],
        ),
        _format_stats_section(
            "平均每场战斗数据",
            [
                ("经验", _number(average.get("xp"))),
                ("造成损伤", _number(average.get("damage"))),
                ("受到损伤", _number(average.get("damage_received"))),
                ("弹震效果数", _number(average.get("stun"))),
                ("由您协助造成的损伤", _number(average.get("assisted_damage"))),
                ("对受到您弹震影响的敌方坦克造成的损伤", _number(average.get("assisted_stun_damage"))),
                ("点亮的敌方坦克", _number(average.get("spotted"), 2)),
                ("每场战斗击毁的敌方坦克", _number(average.get("frags"), 2)),
            ],
        ),
        _format_stats_section(
            "成绩记录",
            [
                ("单次战斗最大击毁数量", _number(records.get("max_frags"))),
                ("单次战斗中获得的最多经验", _number(records.get("max_xp"))),
                ("单次战斗中造成的最多损伤", _number(records.get("max_damage"))),
            ],
        ),
        _format_stats_section(
            "MB",
            [
                (str(entry.get("name") or "未知"), _number(entry.get("count")))
                for entry in career.get("master_levels") or []
            ],
        ),
    ]
    achievement_items = achievements.get("items") or []
    if achievement_items:
        sections.insert(
            1,
            "\n".join(
                [
                    "战斗勋章展示",
                    *(
                        f"{item.get('name') or '勋章'}：{_number(item.get('value'))}|{item.get('icon_url') or ''}"
                        for item in achievement_items
                    ),
                ]
            ),
        )
    chart_orders = {
        "nations": {
            code: index
            for index, code in enumerate(
                ("china", "ussr", "germany", "usa", "france", "uk", "japan", "czech", "sweden", "poland", "italy")
            )
        },
        "types": {
            code: index
            for index, code in enumerate(
                ("lightTank", "mediumTank", "heavyTank", "AT-SPG", "SPG")
            )
        },
    }
    for title, key in (
        ("战斗坦克分布（按等级）", "tiers"),
        ("战斗坦克分布（按国家）", "nations"),
        ("战斗坦克分布（按坦克类型）", "types"),
    ):
        entries = list(career.get(key) or [])
        if key == "tiers":
            entries_by_tier = {
                int(entry.get("code") or 0): entry for entry in entries
            }
            entries = [
                entries_by_tier.get(
                    tier,
                    {
                        "code": str(tier),
                        "name": f"{tier}级",
                        "battles": 0,
                        "battle_percent": 0,
                        "win_rate": 0,
                        "master_count": 0,
                    },
                )
                for tier in range(1, 12)
            ]
            entries.sort(key=lambda entry: int(entry.get("code") or 0))
        else:
            order = chart_orders[key]
            entries.sort(key=lambda entry: order.get(str(entry.get("code")), 999))
        if entries:
            sections.append(_format_distribution(title, entries))
    sections.append("数据来源：游戏官网")
    return "\n\n".join(sections)


async def get_career_data(account_id: str) -> dict:
    now = time.time()
    with _career_lock:
        cached = _career_cache.get(account_id)
        if cached and now - cached[0] < _CAREER_CACHE_TTL_SECONDS:
            return cached[1]

    career = await fetch_player_career(account_id)
    with _career_lock:
        if len(_career_cache) >= _CAREER_CACHE_MAX_ENTRIES:
            _career_cache.clear()
        _career_cache[account_id] = (time.time(), career)
    return career


async def build_career_text(player_name: str, account_id: str) -> str:
    """查询玩家官网标准模式生涯统计。"""
    try:
        career = await get_career_data(account_id)
    except Exception as exc:
        logger.exception(f"获取玩家生涯统计失败（玩家={player_name}）：{exc}")
        raise
    return _format_career(player_name, career)
