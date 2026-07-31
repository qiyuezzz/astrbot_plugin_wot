from __future__ import annotations

import json
import threading
from typing import Any

from data.plugins.astrbot_plugin_wot.src.domain.report import (
    Tank,
    TankNationEnum,
    TankRoleEnum,
    TankTypeEnum,
)
from data.plugins.astrbot_plugin_wot.src.settings.storage import prepare_tank_info_path

_tank_db_cache: dict[str, dict[str, Any]] | None = None
_tank_db_cache_mtime: float | None = None
_tank_db_lock = threading.Lock()


def _load_tank_db() -> dict[str, dict[str, Any]]:
    """按文件 mtime 缓存全量坦克数据，避免每次查询都读取大 JSON 文件。"""
    global _tank_db_cache, _tank_db_cache_mtime

    tank_info_file = prepare_tank_info_path()
    try:
        mtime = tank_info_file.stat().st_mtime
    except OSError:
        return {}

    with _tank_db_lock:
        if _tank_db_cache is not None and _tank_db_cache_mtime == mtime:
            return _tank_db_cache
        try:
            with tank_info_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        _tank_db_cache = data
        _tank_db_cache_mtime = mtime
        return data


def invalidate_tank_db_cache() -> None:
    """清空坦克数据缓存（坦克数据同步后调用）。"""
    global _tank_db_cache, _tank_db_cache_mtime
    with _tank_db_lock:
        _tank_db_cache = None
        _tank_db_cache_mtime = None


def get_tank_info_by_name(tank_name: str) -> Tank:
    try:
        tanks_full_info = _load_tank_db()
        tank_full_info = tanks_full_info.get(tank_name)
        if not tank_full_info:
            raise KeyError(tank_name)
        return Tank(
            name=tank_full_info.get("name", tank_name),
            vehicle_cd=int(tank_full_info.get("vehicle_cd") or 0),
            tier=int(tank_full_info.get("tier") or 0),
            premium=int(tank_full_info.get("premium") or 0),
            nation=TankNationEnum.from_code(tank_full_info.get("nation", "")),
            type=TankTypeEnum.from_code(tank_full_info.get("type", "")),
            role=TankRoleEnum.from_code(tank_full_info.get("role", "")),
        )
    except Exception:
        return Tank(
            name=tank_name or "Unknown",
            vehicle_cd=0,
            tier=0,
            premium=0,
            nation=TankNationEnum.UNKNOWN,
            type=TankTypeEnum.UNKNOWN,
            role=TankRoleEnum.NONE,
        )
