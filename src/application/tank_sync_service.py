from __future__ import annotations

import asyncio
import json
import os
import tempfile

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_game_api import (
    fetch_all_tank_info,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wotinspector_tanks_api import (
    build_nation_map,
    build_wotinspector_tanks,
    fetch_tank_db_js,
    parse_tank_db,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    invalidate_tank_db_cache,
)
from data.plugins.astrbot_plugin_wot.src.settings.storage import prepare_tank_info_path

_MIN_OFFICIAL_TANK_COUNT = 100
_sync_lock = asyncio.Lock()


def _parse_official_tanks(result: object) -> tuple[list[str], dict[str, dict]]:
    """校验并解析官方坦克数据，拒绝空响应和明显不完整的数据集。"""
    if not isinstance(result, dict):
        raise ValueError("官方坦克接口返回格式无效")
    inner_data = result.get("data")
    if not isinstance(inner_data, dict):
        raise ValueError("官方坦克接口缺少 data")

    params = inner_data.get("parameters")
    tank_rows = inner_data.get("data")
    if not isinstance(params, list) or not isinstance(tank_rows, list):
        raise ValueError("官方坦克接口缺少字段定义或坦克列表")
    required_fields = {"name", "vehicle_cd", "tier"}
    if not required_fields.issubset(params):
        raise ValueError("官方坦克接口缺少必要字段")

    library: dict[str, dict] = {}
    for row in tank_rows:
        if not isinstance(row, list) or len(row) < len(params):
            continue
        tank_details = dict(zip(params, row))
        tank_name = tank_details.get("name")
        if tank_name and tank_details.get("vehicle_cd"):
            library[str(tank_name)] = tank_details

    if len(library) < _MIN_OFFICIAL_TANK_COUNT:
        raise ValueError(
            f"官方坦克数据仅有 {len(library)} 辆，低于安全阈值 "
            f"{_MIN_OFFICIAL_TANK_COUNT}"
        )
    return [str(param) for param in params], library


def _atomic_write_tank_library(path, library: dict[str, dict]) -> None:
    """在同一目录写入临时文件，完整落盘后原子替换正式数据库。"""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name
            json.dump(library, temp_file, ensure_ascii=False, indent=4)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def sync_all_tank_info():
    """Sync full tank info with official + WotInspector."""
    async with _sync_lock:
        try:
            resp = await fetch_all_tank_info()
            if resp is None:
                raise ValueError("官方坦克接口无响应")
            if getattr(resp, "status", 200) != 200:
                raise ValueError(f"官方坦克接口 HTTP {resp.status}")
            params, name_indexed_library = _parse_official_tanks(await resp.json())

            wotinspector_count = 0
            try:
                tank_db_js = await fetch_tank_db_js()
                tank_db = parse_tank_db(tank_db_js)
                nation_map = build_nation_map(name_indexed_library)
                wotinspector_tanks = build_wotinspector_tanks(tank_db, nation_map)
                for name, payload in wotinspector_tanks.items():
                    if name not in name_indexed_library:
                        name_indexed_library[name] = payload
                        wotinspector_count += 1
            except Exception as exc:
                logger.warning(f"WotInspector 坦克信息合并失败: {exc}")

            tank_info_file = prepare_tank_info_path()
            _atomic_write_tank_library(tank_info_file, name_indexed_library)
            invalidate_tank_db_cache()
        except Exception as exc:
            logger.error(f"同步坦克数据失败，保留现有数据库: {exc}")
            return f"更新失败：{exc}"

    logger.info(
        f"成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息，"
        f"WotInspector 追加 {wotinspector_count} 辆。"
    )
    logger.info(f"包含字段: {', '.join(params[:10])} ... 等共 {len(params)} 个字段")
    return f"更新成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息。"
