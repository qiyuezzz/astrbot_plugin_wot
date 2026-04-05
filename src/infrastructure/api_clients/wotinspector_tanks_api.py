from __future__ import annotations

import json
import re
from typing import Any

import aiohttp

TANK_DB_PC_URL = "https://armor.wotinspector.com/static/armorinspector/tank_db_pc.js"

TYPE_TAGS = ("lightTank", "mediumTank", "heavyTank", "AT-SPG", "SPG")
TYPE_BY_ID = {
    0: "lightTank",
    1: "mediumTank",
    2: "heavyTank",
    3: "AT-SPG",
    4: "SPG",
}


async def fetch_tank_db_js(url: str = TANK_DB_PC_URL, timeout: int = 30) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            resp.raise_for_status()
            return await resp.text()


def parse_tank_db(js_text: str) -> dict[str, dict[str, Any]]:
    object_text = _extract_js_object(js_text, "TANK_DB")
    json_text = _normalize_js_object(object_text)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Failed to parse TANK_DB payload.") from exc


def build_nation_map(full_tank_data: dict[str, dict[str, Any]]) -> dict[str, str]:
    nation_map: dict[str, str] = {}
    for key, payload in full_tank_data.items():
        nation = payload.get("nation")
        if not nation:
            continue
        for candidate in (key, payload.get("name"), payload.get("short_mark")):
            if candidate:
                nation_map[candidate] = nation
                normalized = normalize_name(candidate)
                nation_map.setdefault(normalized, nation)
    return nation_map


def build_wotinspector_tanks(
    tank_db: dict[str, dict[str, Any]],
    nation_map: dict[str, str],
) -> dict[str, dict[str, Any]]:
    tanks: dict[str, dict[str, Any]] = {}
    for vehicle_id, payload in tank_db.items():
        name = payload.get("zh_Hans") or payload.get("en") or payload.get("ru")
        if not name:
            continue
        tags = {tag for tag in payload.get("tags", "").split(",") if tag}
        tank_type = next((tag for tag in TYPE_TAGS if tag in tags), None)
        if tank_type is None:
            tank_type = TYPE_BY_ID.get(payload.get("type"))
        role = next((tag for tag in tags if tag.startswith("role_")), "")
        nation = _find_nation(name, nation_map)
        tanks[name] = {
            "nation": nation,
            "type": tank_type or "",
            "role": role,
            "tier": int(payload.get("tier") or 0),
            "name": name,
            "vehicle_cd": int(vehicle_id),
            "premium": int(payload.get("premium") or 0),
            "collector_vehicle": 1 if "collectorVehicle" in tags else 0,
        }
    return tanks


def normalize_name(name: str) -> str:
    normalized = name.strip()
    normalized = normalized.strip("\"'''")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _find_nation(name: str, nation_map: dict[str, str]) -> str:
    if name in nation_map:
        return nation_map[name]
    normalized = normalize_name(name)
    return nation_map.get(normalized, "")


def _extract_js_object(js_text: str, variable_name: str) -> str:
    match = re.search(rf"{re.escape(variable_name)}\s*=\s*\{{", js_text)
    if not match:
        raise ValueError(f"Missing {variable_name} declaration.")
    start = match.end() - 1
    depth = 0
    end = None
    for idx in range(start, len(js_text)):
        char = js_text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        raise ValueError(f"Unterminated {variable_name} object.")
    return js_text[start:end]


def _normalize_js_object(object_text: str) -> str:
    text = re.sub(r"(?m)(\s*)(\d+)\s*:", r'\1"\2":', object_text)
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text
