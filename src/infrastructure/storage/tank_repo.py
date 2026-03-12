from __future__ import annotations

import json
from pathlib import Path

from data.plugins.astrbot_plugin_wot.src.config.constants import tank_info_path
from data.plugins.astrbot_plugin_wot.src.domain.models.enums import TankNationEnum, TankRoleEnum, TankTypeEnum
from data.plugins.astrbot_plugin_wot.src.domain.models.report import Tank


def get_tank_info_by_name(tank_name: str) -> Tank:
    with Path(tank_info_path).open("r", encoding="utf-8") as f:
        tanks_full_info = json.load(f)
    tank_full_info = tanks_full_info[tank_name]
    return Tank(
        name=tank_full_info["name"],
        vehicle_cd=tank_full_info["vehicle_cd"],
        tier=tank_full_info["tier"],
        premium=tank_full_info["premium"],
        nation=TankNationEnum.from_code(tank_full_info["nation"]),
        type=TankTypeEnum.from_code(tank_full_info["type"]),
        role=TankRoleEnum.from_code(tank_full_info["role"]),
    )
