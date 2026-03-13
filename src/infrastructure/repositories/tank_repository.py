from __future__ import annotations

import json
from pathlib import Path

from data.plugins.astrbot_plugin_wot.src.domain.enums import (
    TankNationEnum,
    TankRoleEnum,
    TankTypeEnum,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import Tank
from data.plugins.astrbot_plugin_wot.src.settings.constants import tank_info_path


def get_tank_info_by_name(tank_name: str) -> Tank:
    try:
        with Path(tank_info_path).open("r", encoding="utf-8") as f:
            tanks_full_info = json.load(f)
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
