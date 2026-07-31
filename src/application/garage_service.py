from __future__ import annotations

import threading
import time

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wotbox_camp_api import (
    fetch_garage_all,
)

_GARAGE_CACHE_TTL_SECONDS = 5 * 60
_GARAGE_CACHE_MAX_ENTRIES = 128
_garage_cache: dict[str, tuple[float, str]] = {}
_garage_lock = threading.Lock()

_GARAGE_TOP_N = 15


def _clean_name(name: str) -> str:
    for quote in '"“”‘’\'"':
        name = name.replace(quote, "")
    return name.strip()


def _format_garage(nick_name: str, entries: list[dict], total: int) -> str:
    sorted_entries = sorted(
        entries, key=lambda entry: int(entry.get("battles") or 0), reverse=True
    )
    lines = [f"{_clean_name(nick_name)} 的车库（共 {total} 辆，展示前 {_GARAGE_TOP_N} 辆）"]
    for index, entry in enumerate(sorted_entries[:_GARAGE_TOP_N], start=1):
        name = _clean_name(entry.get("vehicle_name") or entry.get("name") or "未知")
        level = entry.get("vlevel") or ""
        vtype = entry.get("vtype") or ""
        battles = int(entry.get("battles") or 0)
        win_rate = entry.get("win_rate") or 0
        wn8 = float(entry.get("WN8") or 0)
        damage_avg = float(entry.get("damage_avg") or 0)
        marks = int(entry.get("vehicle_mastery") or 0)
        marks_text = "无环" if marks <= 0 else f"{marks}环"
        lines.append(
            f"{index}. {name} {level} {vtype} {battles}场 "
            f"胜率{win_rate}% WN8 {wn8:.0f} 场均伤害{damage_avg:.0f} {marks_text}"
        )
    lines.append("数据来源：坦克营地")
    return "\n".join(lines)


async def build_garage_text(player_name: str, account_id: str) -> str:
    """查询玩家车库并格式化为文本（结果缓存 5 分钟）。"""
    now = time.time()
    with _garage_lock:
        cached = _garage_cache.get(account_id)
        if cached and now - cached[0] < _GARAGE_CACHE_TTL_SECONDS:
            return cached[1]

    nick_name, entries, total = await fetch_garage_all(account_id)
    if not entries:
        text = f"{_clean_name(nick_name or player_name)} 的车库为空"
    else:
        text = _format_garage(nick_name or player_name, entries, total)

    with _garage_lock:
        if len(_garage_cache) >= _GARAGE_CACHE_MAX_ENTRIES:
            _garage_cache.clear()
        _garage_cache[account_id] = (time.time(), text)
    logger.info(f"车库查询完成：{nick_name or player_name}（{len(entries)}辆）")
    return text
