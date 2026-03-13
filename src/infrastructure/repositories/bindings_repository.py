from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.settings.constants import bind_data_path

BINDINGS_LOCK = threading.Lock()


def read_binding_data(send_id: str) -> str | None:
    """Read binding data for one user."""
    try:
        with BINDINGS_LOCK:
            with Path(bind_data_path).open("r", encoding="utf-8") as f:
                bind_data = json.load(f)
        player_name = bind_data.get(send_id)
        return player_name if player_name else None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to decode binding data JSON: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Failed to read binding data: {exc}")
        return None


def binding_exists(send_id: str) -> bool:
    return bool(read_binding_data(send_id))


def _write_binding_data_sync(qq_id: str, player_name: str) -> bool:
    Path(bind_data_path).parent.mkdir(parents=True, exist_ok=True)
    bind_data: dict[str, str] = {}
    with BINDINGS_LOCK:
        try:
            with Path(bind_data_path).open("r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    bind_data = json.loads(content)
        except FileNotFoundError:
            bind_data = {}
        except json.JSONDecodeError:
            bind_data = {}

        bind_data[qq_id] = player_name

        with Path(bind_data_path).open("w", encoding="utf-8") as f:
            f.write(json.dumps(bind_data, ensure_ascii=False, indent=4))
    return True


async def write_binding_data(qq_id: str, player_name: str) -> bool:
    """Upsert binding data."""
    try:
        return await asyncio.to_thread(_write_binding_data_sync, qq_id, player_name)
    except Exception as exc:
        logger.error(f"Failed to write binding data: {exc}")
        return False
