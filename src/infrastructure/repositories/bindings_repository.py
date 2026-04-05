from __future__ import annotations

import asyncio
import json
import threading

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.settings.storage import prepare_bind_data_path

BINDINGS_LOCK = threading.Lock()


def read_binding_data(send_id: str) -> str | None:
    """读取单个用户的绑定数据"""
    try:
        bind_path = prepare_bind_data_path()
        with BINDINGS_LOCK:
            with bind_path.open("r", encoding="utf-8") as f:
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
    bind_path = prepare_bind_data_path()
    bind_data: dict[str, str] = {}
    with BINDINGS_LOCK:
        try:
            with bind_path.open("r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    bind_data = json.loads(content)
        except FileNotFoundError:
            bind_data = {}
        except json.JSONDecodeError:
            bind_data = {}

        bind_data[qq_id] = player_name

        with bind_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(bind_data, ensure_ascii=False, indent=4))
    return True


async def write_binding_data(qq_id: str, player_name: str) -> bool:
    """写入或更新绑定数据"""
    try:
        return await asyncio.to_thread(_write_binding_data_sync, qq_id, player_name)
    except Exception as exc:
        logger.error(f"Failed to write binding data: {exc}")
        return False
