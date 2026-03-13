from __future__ import annotations

import json
import re
from collections.abc import Iterable

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    RecordsBasic,
    RecordsDetail,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    get_tank_info_by_name,
)


def parse_arena_list(raw_json: dict) -> list[RecordsBasic]:
    arena_list: list[RecordsBasic] = []
    required_keys = {"arena_id", "is_win", "gui_type", "start_time"}

    data = raw_json.get("data", {}).get("arenas", [])
    for record in data:
        if record.get("gui_type") != "1":
            continue
        filtered_record = {k: v for k, v in record.items() if k in required_keys}
        arena_list.append(RecordsBasic(**filtered_record))
    return arena_list


def parse_battle_detail(raw_text: str, arena: RecordsBasic) -> RecordsDetail | None:
    json_match = re.search(r"\{.*\}", raw_text)
    if not json_match:
        logger.error("Failed to locate JSON in battle detail response")
        return None

    data = json.loads(json_match.group()).get("result", {})
    player_id = int(data.get("player_id", 0))
    player_data_list: Iterable[dict] = data.get("team_a", [])
    player_data = next(
        (
            p
            for p in player_data_list
            if p.get("vehicle", {}).get("accountDBID") == player_id
        ),
        None,
    )
    if not player_data:
        logger.error("Failed to locate player record in battle detail response")
        return None

    vehicle = player_data["vehicle"]
    tank_info = get_tank_info_by_name(player_data.get("tank_title", ""))
    return RecordsDetail(
        tank_info=tank_info,
        records_basic=arena,
        exp=vehicle["xp"],
        power=round(player_data["combat"], 2),
        death_count=vehicle["deathCount"],
        damage_dealt=vehicle["damageDealt"],
        assist_radio=vehicle["damageAssistedRadio"],
        assist_track=vehicle["damageAssistedTrack"],
        assist_stun=vehicle["damageAssistedStun"],
        kills=vehicle["kills"],
        shots=vehicle["shots"],
        hits=vehicle["directHits"],
        hit_received=vehicle["directHitsReceived"],
        piercings=vehicle["piercings"],
        piercings_received=vehicle["piercingsReceived"],
        blocked=vehicle["damageBlockedByArmor"],
        marks_on_gun=vehicle["marksOnGun"],
        credits=vehicle["credits"],
        life_time=vehicle["lifeTime"],
    )
