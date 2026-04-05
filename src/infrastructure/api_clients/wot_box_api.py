from __future__ import annotations

from typing import Any

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    HttpClient,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.request_context import (
    wot_box_config,
    wot_box_detail_record_config,
    wot_box_records_config,
)


async def fetch_player_stats_html(player_name: str) -> str:
    """从WotBox获取玩家原始统计HTML"""
    if not player_name or not player_name.strip():
        logger.error("Player name is empty")
        return ""

    params = wot_box_config.build_params()
    params["pn"] = player_name

    async with HttpClient() as client:
        try:
            res = await client.send_get(wot_box_config, params)
            return await res.text() if res else ""
        except Exception as exc:
            logger.exception(f"Failed to fetch WotBox HTML for {player_name}: {exc}")
            return ""


async def fetch_arena_page(
    player_name: str, page_num: int, *, http: HttpClient | None = None
) -> dict[str, Any]:
    """获取单页战斗列表原始JSON"""
    _should_close = False
    if http is None:
        http = HttpClient()
        _should_close = True

    try:
        if _should_close:
            await http.__aenter__()
        params = wot_box_records_config.build_params()
        params["pn"] = player_name
        params["p"] = page_num
        res = await http.send_get(wot_box_records_config, params)
        return await res.json()
    finally:
        if _should_close:
            await http.__aexit__(None, None, None)


async def fetch_battle_detail(
    player_name: str, arena_id: str, *, http: HttpClient | None = None
) -> str:
    """获取单场战斗详情原始响应文本"""
    _should_close = False
    if http is None:
        http = HttpClient()
        _should_close = True

    try:
        if _should_close:
            await http.__aenter__()
        params = wot_box_detail_record_config.build_params()
        params["pn"] = player_name
        params["arena_id"] = arena_id
        res = await http.send_get(wot_box_detail_record_config, params)
        return await res.text()
    finally:
        if _should_close:
            await http.__aexit__(None, None, None)
