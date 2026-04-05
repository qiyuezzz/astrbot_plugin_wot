from __future__ import annotations

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    HttpClient,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.request_context import (
    wot_account_search_config,
    wot_game_tank_info_config,
)


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
                data=wot_game_tank_info_config.data,
            )
        except Exception as exc:
            logger.error(f"Failed to fetch full tank data: {exc}")
            return None
