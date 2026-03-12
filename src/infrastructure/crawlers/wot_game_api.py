from __future__ import annotations

from astrbot.core import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.http.http_client import HttpClient
from data.plugins.astrbot_plugin_wot.src.infrastructure.http.request_context import (
    wot_account_search_config,
    wot_game_tank_info_config,
)


def fetch_account_search(player_name: str):
    """Fetch account search response from official WOT site."""
    client = HttpClient()
    params = wot_account_search_config.build_params()
    params["name"] = player_name
    params["name_gt"] = ""
    return client.send_get(wot_account_search_config, params)


def fetch_all_tank_info():
    """Fetch full tank data from official WOT site."""
    client = HttpClient()
    try:
        logger.info("Fetching full tank data...")
        return client.send_post(config=wot_game_tank_info_config, data=wot_game_tank_info_config.data)
    except Exception as exc:
        logger.error(f"Failed to fetch full tank data: {exc}")
        return None
