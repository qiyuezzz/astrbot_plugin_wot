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


def fetch_player_stats_html(player_name: str) -> str:
    """Fetch raw player stats HTML from WotBox."""
    if not player_name or not player_name.strip():
        logger.error("Player name is empty")
        return ""

    params = wot_box_config.build_params()
    params["pn"] = player_name

    client = HttpClient()
    try:
        res = client.send_get(wot_box_config, params)
        return res.text if res and res.text else ""
    except Exception as exc:
        logger.exception(f"Failed to fetch WotBox HTML for {player_name}: {exc}")
        return ""


def fetch_arena_page(player_name: str, page_num: int) -> dict[str, Any]:
    """Fetch raw arena list JSON for one page."""
    client = HttpClient()
    params = wot_box_records_config.build_params()
    params["pn"] = player_name
    params["p"] = page_num
    res = client.send_get(wot_box_records_config, params)
    return res.json()


def fetch_battle_detail(player_name: str, arena_id: str) -> str:
    """Fetch raw battle detail response text."""
    client = HttpClient()
    params = wot_box_detail_record_config.build_params()
    params["pn"] = player_name
    params["arena_id"] = arena_id
    res = client.send_get(wot_box_detail_record_config, params)
    return res.text
