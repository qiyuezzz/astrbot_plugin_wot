from __future__ import annotations

import json
from pathlib import Path

from astrbot.core import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.clients.wot_game_api import (
    fetch_all_tank_info,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.clients.wotinspector_tanks_api import (
    build_nation_map,
    build_wotinspector_tanks,
    fetch_tank_db_js,
    parse_tank_db,
)
from data.plugins.astrbot_plugin_wot.src.settings.constants import tank_info_path


def sync_all_tank_info():
    """Sync full tank info with official + WotInspector."""
    resp = fetch_all_tank_info()
    if resp is None:
        return "更新失败"
    resp.raise_for_status()
    result = resp.json()
    inner_data = result.get("data", {})

    params = inner_data.get("parameters", [])
    tank_rows = inner_data.get("data", [])

    name_indexed_library = {}
    for row in tank_rows:
        tank_details = {params[i]: row[i] for i in range(len(params))}
        tank_name = tank_details.get("name")
        if tank_name:
            name_indexed_library[tank_name] = tank_details

    wotinspector_count = 0
    try:
        tank_db_js = fetch_tank_db_js()
        tank_db = parse_tank_db(tank_db_js)
        nation_map = build_nation_map(name_indexed_library)
        wotinspector_tanks = build_wotinspector_tanks(tank_db, nation_map)
        for name, payload in wotinspector_tanks.items():
            if name not in name_indexed_library:
                name_indexed_library[name] = payload
                wotinspector_count += 1
    except Exception as exc:
        logger.warning(f"WotInspector 坦克信息合并失败: {exc}")

    with Path(tank_info_path).open("w", encoding="utf-8") as f:
        json.dump(name_indexed_library, f, ensure_ascii=False, indent=4)

    logger.info(
        f"成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息，"
        f"WotInspector 追加 {wotinspector_count} 辆。"
    )
    logger.info(f"包含字段: {', '.join(params[:10])} ... 等共 {len(params)} 个字段")
    return f"更新成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息。"
