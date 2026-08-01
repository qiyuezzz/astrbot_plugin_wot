from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_game_api import (
    fetch_garage_all,
)

_GARAGE_CACHE_TTL_SECONDS = 5 * 60
_GARAGE_CACHE_MAX_ENTRIES = 128
_garage_cache: dict[str, tuple[float, str, list[dict], int]] = {}
_garage_lock = threading.Lock()

_GARAGE_TOP_N = 30
_GARAGE_MIN_TIER = 7
_GARAGE_MAX_TIER = 11

_TIER_ALIASES = {
    **{f"{tier}级": tier for tier in range(1, 11)},
    "一级": 1,
    "二级": 2,
    "三级": 3,
    "四级": 4,
    "五级": 5,
    "六级": 6,
    "七级": 7,
    "八级": 8,
    "九级": 9,
    "十级": 10,
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "I级": 1,
    "II级": 2,
    "III级": 3,
    "IV级": 4,
    "V级": 5,
    "VI级": 6,
    "VII级": 7,
    "VIII级": 8,
    "IX级": 9,
    "X级": 10,
    "XI": 11,
    "XI级": 11,
    "11级": 11,
}

_TYPE_ALIASES = {
    "轻坦": "轻坦",
    "轻型": "轻坦",
    "轻型坦克": "轻坦",
    "中坦": "中坦",
    "中型": "中坦",
    "中型坦克": "中坦",
    "重坦": "重坦",
    "重型": "重坦",
    "重型坦克": "重坦",
    "坦歼": "坦歼",
    "反坦": "坦歼",
    "反坦克歼击车": "坦歼",
    "火炮": "火炮",
    "自行火炮": "火炮",
}


@dataclass(frozen=True)
class GarageQuery:
    player_name: str | None = None
    tier: int | None = None
    tank_type: str | None = None
    error: str | None = None


def parse_garage_query(argument: str | None) -> GarageQuery:
    """从“玩家名 10级 重坦”中分离玩家名和车库筛选条件。"""
    if not argument:
        return GarageQuery()

    player_parts: list[str] = []
    tier: int | None = None
    tank_type: str | None = None
    for token in argument.split():
        normalized_tier = _TIER_ALIASES.get(token.upper())
        normalized_type = _TYPE_ALIASES.get(token)
        if normalized_tier is not None:
            if not _GARAGE_MIN_TIER <= normalized_tier <= _GARAGE_MAX_TIER:
                return GarageQuery(error="车库仅统计7-11级坦克")
            if tier is not None and tier != normalized_tier:
                return GarageQuery(error="一次只能筛选一个等级")
            tier = normalized_tier
        elif normalized_type is not None:
            if tank_type is not None and tank_type != normalized_type:
                return GarageQuery(error="一次只能筛选一种坦克类型")
            tank_type = normalized_type
        else:
            player_parts.append(token)

    return GarageQuery(" ".join(player_parts) or None, tier, tank_type)


def _clean_name(name: str) -> str:
    for quote in '"“”‘’\'"':
        name = name.replace(quote, "")
    return name.strip()


def _entry_tier(entry: dict) -> int:
    raw = str(entry.get("vlevel") or entry.get("tier") or "").strip().upper()
    if raw.isdigit():
        return int(raw)
    return _TIER_ALIASES.get(raw, 0)


def _entry_type(entry: dict) -> str:
    raw = str(entry.get("vtype") or entry.get("type") or "").strip()
    if raw in _TYPE_ALIASES:
        return _TYPE_ALIASES[raw]
    code_map = {
        "lightTank": "轻坦",
        "mediumTank": "中坦",
        "heavyTank": "重坦",
        "AT-SPG": "坦歼",
        "SPG": "火炮",
    }
    return code_map.get(raw, raw)


def _entry_gun_marks(entry: dict) -> int | None:
    """读取炮管环数，不要将 vehicle_mastery（熟练度徽章）当作环数。"""
    for key in ("marksOnGun", "marks_on_gun", "gun_marks"):
        value = entry.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _format_garage(
    nick_name: str,
    entries: list[dict],
    total: int,
    tier: int | None = None,
    tank_type: str | None = None,
) -> str:
    filtered_entries = [
        entry
        for entry in entries
        if (tier is None or _entry_tier(entry) == tier)
        and (tank_type is None or _entry_type(entry) == tank_type)
    ]
    filters = [value for value in (f"{tier}级" if tier else "", tank_type or "") if value]
    filter_text = f"（筛选：{'、'.join(filters)}）" if filters else ""
    if not filtered_entries:
        return f"{_clean_name(nick_name)} 的车库中没有符合条件的坦克{filter_text}"

    sorted_entries = sorted(
        filtered_entries,
        key=lambda entry: int(entry.get("battles") or 0),
        reverse=True,
    )
    if filters:
        summary = (
            f"{_clean_name(nick_name)} 的车库{filter_text}（匹配 {len(filtered_entries)} 辆，"
            f"共 {total} 辆，统计7-11级，展示前 {_GARAGE_TOP_N} 辆）"
        )
    else:
        summary = (
            f"{_clean_name(nick_name)} 的车库（共 {total} 辆，统计7-11级，"
            f"展示前 {_GARAGE_TOP_N} 辆）"
        )
    lines = [summary]
    for index, entry in enumerate(sorted_entries[:_GARAGE_TOP_N], start=1):
        name = _clean_name(entry.get("vehicle_name") or entry.get("name") or "未知")
        level = entry.get("vlevel") or ""
        vtype = _entry_type(entry)
        battles = int(entry.get("battles") or 0)
        win_rate = entry.get("win_rate") or 0
        avg_frags = float(entry.get("avg_frags") or 0)
        damage_avg = float(entry.get("damage_avg") or 0)
        xp_avg = float(entry.get("xp_per_battle_average") or 0)
        marks = _entry_gun_marks(entry)
        marks_text = "暂无" if marks is None else "无环" if marks <= 0 else f"{marks}环"
        lines.append(
            f"{index}. {name} {level} {vtype} {battles}场 "
            f"胜率{win_rate}% 场均击毁{avg_frags:.2f} "
            f"场均伤害{damage_avg:.0f} 场均经验{xp_avg:.0f} {marks_text}"
        )
    lines.append("数据来源：游戏官网")
    return "\n".join(lines)


async def get_garage_data(account_id: str) -> tuple[str, list[dict], int]:
    """读取并缓存玩家完整车库，供车库列表查询使用。"""
    now = time.time()
    with _garage_lock:
        cached = _garage_cache.get(account_id)
        if cached and now - cached[0] < _GARAGE_CACHE_TTL_SECONDS:
            return cached[1], cached[2], cached[3]

    nick_name, entries, total = await fetch_garage_all(account_id)
    with _garage_lock:
        if len(_garage_cache) >= _GARAGE_CACHE_MAX_ENTRIES:
            _garage_cache.clear()
        _garage_cache[account_id] = (time.time(), nick_name, entries, total)
    return nick_name, entries, total


async def build_garage_text(
    player_name: str,
    account_id: str,
    tier: int | None = None,
    tank_type: str | None = None,
) -> str:
    """查询玩家车库，可按等级和类型筛选。"""
    nick_name, entries, total = await get_garage_data(account_id)
    display_name = nick_name or player_name
    if not entries:
        text = f"{_clean_name(display_name)} 的车库为空"
    else:
        text = _format_garage(display_name, entries, total, tier, tank_type)

    logger.info(f"车库查询完成：{display_name}（{len(entries)}辆）")
    return text
