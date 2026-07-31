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


def _normalize_tank_name(name: str) -> str:
    """去引号、折叠空白并转小写，用于容错匹配坦克名。"""
    if not name:
        return ""
    for quote in '"“”‘’\'"':
        name = name.replace(quote, "")
    return " ".join(name.strip().lower().split())


def _tank_name_aliases(name: str) -> set[str]:
    """生成可用于精确匹配的名称别名。"""
    normalized = _normalize_tank_name(name)
    if not normalized:
        return set()
    aliases = {normalized}
    if normalized.endswith("式"):
        aliases.add(normalized[:-1])
    return aliases


def find_tanks_by_name(tank_name: str) -> list[Tank]:
    """按坦克名查找所有候选，精确名称和别名优先于部分匹配。"""
    if not tank_name:
        return []
    tank_db = _load_tank_db()
    if tank_name in tank_db:
        return [get_tank_info_by_name(tank_name)]

    normalized = _normalize_tank_name(tank_name)
    if not normalized:
        return []

    normalized_names: dict[str, set[str]] = {}
    exact_matches: list[str] = []
    for candidate, payload in tank_db.items():
        payload_name = payload.get("name", "") if isinstance(payload, dict) else ""
        canonical_names = {
            name
            for name in (
                _normalize_tank_name(candidate),
                _normalize_tank_name(payload_name),
            )
            if name
        }
        names = _tank_name_aliases(candidate) | _tank_name_aliases(payload_name)
        if normalized in canonical_names:
            exact_matches.append(candidate)
        normalized_names[candidate] = names

    if exact_matches:
        return [get_tank_info_by_name(candidate) for candidate in exact_matches]

    contains_matches = [
        candidate
        for candidate, names in normalized_names.items()
        if any(normalized in name for name in names)
    ]
    return [get_tank_info_by_name(candidate) for candidate in contains_matches]


def find_tank_candidates_by_name(tank_name: str) -> list[Tank]:
    """返回精确名称和部分匹配的全部候选，精确匹配排在最前。"""
    if not tank_name:
        return []
    tank_db = _load_tank_db()
    normalized = _normalize_tank_name(tank_name)
    if not normalized:
        return []

    exact_matches: list[str] = []
    partial_matches: list[str] = []
    for candidate, payload in tank_db.items():
        payload_name = payload.get("name", "") if isinstance(payload, dict) else ""
        canonical_names = {
            name
            for name in (
                _normalize_tank_name(candidate),
                _normalize_tank_name(payload_name),
            )
            if name
        }
        aliases = _tank_name_aliases(candidate) | _tank_name_aliases(payload_name)
        if normalized in canonical_names:
            exact_matches.append(candidate)
        elif any(normalized in name for name in aliases):
            partial_matches.append(candidate)

    return [
        get_tank_info_by_name(candidate)
        for candidate in (*exact_matches, *partial_matches)
    ]


def find_tank_by_name(tank_name: str) -> Tank | None:
    """兼容单结果调用；多候选时返回 None。"""
    matches = find_tanks_by_name(tank_name)
    return matches[0] if len(matches) == 1 else None


def get_tank_full_info(tank: Tank) -> dict[str, Any]:
    """按车辆 ID 读取同步后的完整字段，避免名称引号/别名导致查找失败。"""
    for payload in _load_tank_db().values():
        if not isinstance(payload, dict):
            continue
        try:
            vehicle_cd = int(payload.get("vehicle_cd") or 0)
        except (TypeError, ValueError):
            continue
        if tank.vehicle_cd and vehicle_cd == tank.vehicle_cd:
            return dict(payload)
    return {}
