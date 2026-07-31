from __future__ import annotations

from dataclasses import dataclass

from data.plugins.astrbot_plugin_wot.src.application.garage_service import (
    get_garage_data,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    find_tanks_by_name,
)


def _clean_name(name: str) -> str:
    for quote in '"“”‘’\'':
        name = name.replace(quote, "")
    return " ".join(name.strip().split())


def _normalize_name(name: str) -> str:
    return _clean_name(name).lower()


@dataclass(frozen=True)
class SingleVehicleQuery:
    player_name: str | None
    tank_name: str


def parse_single_vehicle_query(argument: str | None) -> SingleVehicleQuery | None:
    """解析“坦克名”或“玩家名 坦克名”，坦克名允许包含空格。"""
    if not argument or not argument.strip():
        return None
    argument = argument.strip()
    if find_tanks_by_name(argument):
        return SingleVehicleQuery(None, argument)

    parts = argument.split()
    for index in range(1, len(parts)):
        tank_name = " ".join(parts[index:])
        if len(find_tanks_by_name(tank_name)) == 1:
            return SingleVehicleQuery(" ".join(parts[:index]), tank_name)
    return SingleVehicleQuery(None, argument)


def _find_entries(entries: list[dict], tank_name: str) -> list[dict]:
    query = _normalize_name(tank_name)
    exact = [
        entry
        for entry in entries
        if _normalize_name(str(entry.get("vehicle_name") or entry.get("name") or ""))
        == query
    ]
    if exact:
        return exact
    return [
        entry
        for entry in entries
        if query
        in _normalize_name(str(entry.get("vehicle_name") or entry.get("name") or ""))
    ]


def _number(entry: dict, *keys: str, default=0):
    for key in keys:
        value = entry.get(key)
        if value not in (None, ""):
            return value
    return default


def _format_single_vehicle(nick_name: str, entry: dict) -> str:
    name = _clean_name(str(entry.get("vehicle_name") or entry.get("name") or "未知"))
    tier = _number(entry, "vlevel", "tier", default="-")
    tank_type = _number(entry, "vtype", "type", default="未知")
    battles = int(_number(entry, "battles"))
    wins = int(_number(entry, "wins", "win"))
    win_rate = float(_number(entry, "win_rate"))
    wn8 = float(_number(entry, "WN8", "wn8"))
    damage = float(_number(entry, "damage_avg", "avg_damage"))
    marks = int(_number(entry, "vehicle_mastery", "marks_on_gun"))
    marks_text = "无环" if marks <= 0 else f"{marks}环"

    lines = [
        f"{_clean_name(nick_name)} · {name}",
        f"{tier}级 {tank_type}",
        f"场次：{battles}",
        f"胜率：{win_rate:.2f}%",
        f"WN8：{wn8:.0f}",
        f"场均伤害：{damage:.0f}",
        f"环数：{marks_text}",
    ]
    if wins:
        lines.insert(3, f"胜场：{wins}")
    lines.append("数据来源：坦克营地")
    return "\n".join(lines)


async def build_single_vehicle_text(
    player_name: str, account_id: str, tank_name: str
) -> str:
    """从玩家完整车库中提取一辆坦克的统计详情。"""
    nick_name, entries, _total = await get_garage_data(account_id)
    matches = _find_entries(entries, tank_name)
    display_name = nick_name or player_name
    if not matches:
        return f"{_clean_name(display_name)} 的车库中未找到坦克「{_clean_name(tank_name)}」"
    if len(matches) > 1:
        candidates = "、".join(
            _clean_name(str(item.get("vehicle_name") or item.get("name") or "未知"))
            for item in matches[:10]
        )
        return f"匹配到多辆坦克：{candidates}\n请使用更完整的坦克名称"
    return _format_single_vehicle(display_name, matches[0])
