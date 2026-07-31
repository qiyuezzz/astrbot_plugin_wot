from __future__ import annotations

import asyncio
import threading
import time

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.report import Tank, TankTypeEnum
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wotbox_camp_api import (
    fetch_moe_ranking,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    find_tanks_by_name,
)

_MOE_CACHE_TTL_SECONDS = 6 * 60 * 60
_MOE_CACHE_MAX_ENTRIES = 512
_moe_cache: dict[int, tuple[float, str]] = {}
_moe_lock = threading.Lock()

_PERCENTILES = (65, 85, 95)
_PERCENTILE_LABELS = {65: "一环", 85: "二环", 95: "三环"}


def _clean_name(name: str) -> str:
    for quote in '"“”‘’\'"':
        name = name.replace(quote, "")
    return name.strip()


def _format_moe(tank: Tank, values: dict[int, int]) -> str:
    lines = [
        f"{_clean_name(tank.name)} 环线标伤（近7天）",
        f"{tank.tier}级 {tank.type.display_name}",
    ]
    for percentile in _PERCENTILES:
        lines.append(f"{_PERCENTILE_LABELS[percentile]}（{percentile}%）: {values[percentile]}")
    lines.append("数据来源：坦克营地")
    return "\n".join(lines)


async def _build_moe_text(tank: Tank) -> str:
    if tank.type is TankTypeEnum.UNKNOWN or not tank.tier or not tank.vehicle_cd:
        return f"坦克「{_clean_name(tank.name)}」数据不完整，请先执行 同步坦克"

    cache_key = tank.vehicle_cd
    now = time.time()
    with _moe_lock:
        cached = _moe_cache.get(cache_key)
        if cached and now - cached[0] < _MOE_CACHE_TTL_SECONDS:
            return cached[1]

    results = await asyncio.gather(
        *(
            fetch_moe_ranking(tank.type.code, str(tank.tier), percentile)
            for percentile in _PERCENTILES
        ),
        return_exceptions=True,
    )

    values: dict[int, int] = {}
    for ranking, percentile in zip(results, _PERCENTILES):
        if isinstance(ranking, BaseException):
            logger.warning(f"获取环线数据失败（{percentile}%）: {ranking}")
            continue
        entry = next(
            (item for item in ranking if int(item.get("tank_id") or 0) == cache_key),
            None,
        )
        if entry is not None and entry.get("mastery") is not None:
            values[percentile] = int(entry["mastery"])

    if len(values) < len(_PERCENTILES):
        tank_display_name = _clean_name(tank.name)
        logger.warning(f"未查询到坦克「{tank_display_name}」的完整环线数据")
        return f"{tank_display_name}：暂无完整环线数据（近7天）"

    text = _format_moe(tank, values)
    with _moe_lock:
        if len(_moe_cache) >= _MOE_CACHE_MAX_ENTRIES:
            _moe_cache.clear()
        _moe_cache[cache_key] = (time.time(), text)
    return text


async def build_moe_text(tank_name: str) -> str:
    """查询名称匹配的坦克环线，多个候选之间用空行分隔。"""
    tanks = find_tanks_by_name(tank_name)
    if not tanks:
        return f"未找到坦克「{tank_name}」，请检查名称是否正确"

    texts = await asyncio.gather(*(_build_moe_text(tank) for tank in tanks))
    return "\n\n".join(texts)
