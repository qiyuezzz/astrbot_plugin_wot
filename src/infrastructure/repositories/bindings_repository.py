from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.settings.storage import prepare_bind_data_path

BINDINGS_LOCK = threading.Lock()

_bindings_cache: dict[str, Any] | None = None
_bindings_cache_mtime: float | None = None


@dataclass
class BindingInfo:
    """玩家绑定信息。"""

    name: str
    account_id: str | None = None


def _read_bindings() -> dict[str, Any]:
    """按文件 mtime 缓存绑定数据，避免每次命令都读取 JSON 文件。"""
    global _bindings_cache, _bindings_cache_mtime

    bind_path = prepare_bind_data_path()
    try:
        mtime = bind_path.stat().st_mtime
    except OSError:
        return {}

    with BINDINGS_LOCK:
        if _bindings_cache is not None and _bindings_cache_mtime == mtime:
            return _bindings_cache
        try:
            with bind_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        _bindings_cache = data
        _bindings_cache_mtime = mtime
        return data


def read_binding_data(send_id: str) -> str | None:
    """读取单个用户的绑定数据"""
    info = read_binding_info(send_id)
    return info.name if info else None


def read_binding_info(send_id: str) -> BindingInfo | None:
    """读取绑定信息，兼容旧版 {qq: 玩家名} 和新的 {qq: {name, account_id}} 格式。"""
    try:
        bind_data = _read_bindings()
        value = bind_data.get(send_id)
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.error(f"Failed to read binding data: {exc}")
        return None

    if isinstance(value, dict):
        name = value.get("name") or value.get("player_name")
        if not name:
            return None
        return BindingInfo(name=name, account_id=value.get("account_id"))
    if isinstance(value, str) and value:
        return BindingInfo(name=value)
    return None


def binding_exists(send_id: str) -> bool:
    return read_binding_info(send_id) is not None


def _write_binding_data_sync(
    qq_id: str, player_name: str, account_id: str | None = None
) -> bool:
    global _bindings_cache, _bindings_cache_mtime
    bind_path = prepare_bind_data_path()
    bind_data: dict[str, Any] = {}
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

        entry: dict[str, str] = {"name": player_name}
        if account_id:
            entry["account_id"] = account_id
        bind_data[qq_id] = entry

        with bind_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(bind_data, ensure_ascii=False, indent=4))
        try:
            _bindings_cache = bind_data
            _bindings_cache_mtime = bind_path.stat().st_mtime
        except OSError:
            _bindings_cache = None
            _bindings_cache_mtime = None
    return True


async def write_binding_data(
    qq_id: str, player_name: str, account_id: str | None = None
) -> bool:
    """写入或更新绑定数据"""
    try:
        return await asyncio.to_thread(
            _write_binding_data_sync, qq_id, player_name, account_id
        )
    except Exception as exc:
        logger.error(f"Failed to write binding data: {exc}")
        return False
