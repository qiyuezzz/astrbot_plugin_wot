import pytest

from data.plugins.astrbot_plugin_wot.src.application import single_vehicle_service
from data.plugins.astrbot_plugin_wot.src.application.single_vehicle_service import (
    build_single_vehicle_text,
    parse_single_vehicle_query,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    Tank,
    TankNationEnum,
    TankRoleEnum,
    TankTypeEnum,
)


def _tank(name: str) -> Tank:
    return Tank(
        name=name,
        tier=8,
        premium=1,
        vehicle_cd=49,
        nation=TankNationEnum.CHINA,
        type=TankTypeEnum.MEDIUM_TANK,
        role=TankRoleEnum.ROLE_MT_UNIVERSAL,
    )


def test_parse_single_vehicle_query_with_player(monkeypatch):
    monkeypatch.setattr(
        single_vehicle_service,
        "find_tanks_by_name",
        lambda name: [_tank(name)] if name == "查狄伦 25t" else [],
    )
    query = parse_single_vehicle_query("Tester 查狄伦 25t")
    assert query is not None
    assert query.player_name == "Tester"
    assert query.tank_name == "查狄伦 25t"


@pytest.mark.asyncio
async def test_build_single_vehicle_text(monkeypatch):
    entry = {
        "vehicle_name": '"59式"',
        "vlevel": "VIII",
        "vtype": "中型坦克",
        "battles": 100,
        "wins": 56,
        "win_rate": 56,
        "WN8": 2100,
        "damage_avg": 1800,
        "vehicle_mastery": 2,
    }

    async def _fake_garage(_account_id):
        return "Tester", [entry], 1

    monkeypatch.setattr(single_vehicle_service, "get_garage_data", _fake_garage)
    text = await build_single_vehicle_text("Tester", "123", "59式")
    assert "Tester · 59式" in text
    assert "场次：100" in text
    assert "胜场：56" in text
    assert "WN8：2100" in text
    assert "环数：2环" in text
