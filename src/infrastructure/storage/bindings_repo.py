from __future__ import annotations

import json
from pathlib import Path

import aiofiles
from astrbot.api import logger

from data.plugins.astrbot_plugin_wot.src.config.constants import bind_data_path


def read_binding_data(send_id: str) -> str | None:
    """Read binding data for one user."""
    try:
        with Path(bind_data_path).open("r", encoding="utf-8") as f:
            bind_data = json.load(f)
            player_name = bind_data[send_id]
        return player_name if player_name else None
    except Exception as exc:
        logger.error(f"Failed to read binding data: {exc}")
        return None


def binding_exists(send_id: str) -> bool:
    return bool(read_binding_data(send_id))


async def write_binding_data(qq_id: str, player_name: str) -> bool:
    """Upsert binding data."""
    try:
        bind_data: dict[str, str] = {}
        try:
            async with aiofiles.open(Path(bind_data_path), "r", encoding="utf-8") as f:
                content = await f.read()
                if content.strip():
                    bind_data = json.loads(content)
        except FileNotFoundError:
            bind_data = {}

        bind_data[qq_id] = player_name

        async with aiofiles.open(Path(bind_data_path), "w", encoding="utf-8") as f:
            await f.write(json.dumps(bind_data, ensure_ascii=False, indent=4))
        return True
    except Exception as exc:
        logger.error(f"Failed to write binding data: {exc}")
        return False
