import pytest

from data.plugins.astrbot_plugin_wot.src.application import garage_service
from data.plugins.astrbot_plugin_wot.src.application.garage_service import (
    build_garage_text,
    parse_garage_query,
)


def _entry(name: str, battles: int, win_rate: float) -> dict:
    return {
        "vehicle_name": name,
        "vlevel": "X",
        "vtype": "中型坦克",
        "battles": battles,
        "win_rate": win_rate,
        "avg_frags": 0.53,
        "damage_avg": 2500.0,
        "xp_per_battle_average": 771,
        "vehicle_mastery": 2,
    }


@pytest.mark.asyncio
async def test_build_garage_text_formats_top_tanks(monkeypatch):
    entries = [
        _entry("“豹”I", 58, 56.9),
        _entry('"战鳄"', 22, 63.64),
        _entry("DBV-152", 117, 60.68),
    ]

    async def _fake_fetch(*_args, **_kwargs):
        return "常威爆打来福", entries, 173

    monkeypatch.setattr(garage_service, "fetch_garage_all", _fake_fetch)
    garage_service._garage_cache.clear()

    text = await build_garage_text("常威爆打来福", "7059354392")
    assert "共 173 辆" in text
    assert "1. DBV-152" in text
    assert "胜率60.68%" in text
    assert "场均击毁0.53" in text
    assert "场均伤害2500" in text
    assert "场均经验771" in text
    assert "WN8" not in text
    assert "数据来源：游戏官网" in text
    assert "暂无" in text
    assert "1环" not in text
    assert "豹I" in text
    assert "“豹”I" not in text
    garage_service._garage_cache.clear()


@pytest.mark.asyncio
async def test_build_garage_text_empty(monkeypatch):
    async def _fake_fetch(*_args, **_kwargs):
        return "玩家", [], 0

    monkeypatch.setattr(garage_service, "fetch_garage_all", _fake_fetch)
    garage_service._garage_cache.clear()

    text = await build_garage_text("玩家", "1")
    assert "车库为空" in text
    garage_service._garage_cache.clear()


def test_parse_garage_query_separates_player_and_filters():
    query = parse_garage_query("Tester 10级 重型坦克")
    assert query.player_name == "Tester"
    assert query.tier == 10
    assert query.tank_type == "重坦"
    assert query.error is None


def test_parse_garage_query_accepts_filter_only():
    query = parse_garage_query("VIII 中坦")
    assert query.player_name is None
    assert query.tier == 8
    assert query.tank_type == "中坦"


def test_parse_garage_query_limits_garage_tiers_to_seven_through_eleven():
    assert parse_garage_query("XI级").tier == 11
    assert parse_garage_query("6级").error == "车库仅统计7-11级坦克"


def test_format_garage_uses_gun_marks_field():
    text = garage_service._format_garage(
        "玩家",
        [{**_entry("有环坦克", 10, 50), "vehicle_mastery": 1, "marksOnGun": 3}],
        1,
    )

    assert "3环" in text
    assert "1环" not in text


@pytest.mark.asyncio
async def test_build_garage_text_filters_by_tier_and_type(monkeypatch):
    entries = [
        _entry("十级中坦", 100, 55),
        {**_entry("十级重坦", 80, 54), "vtype": "重型坦克"},
        {**_entry("八级中坦", 60, 53), "vlevel": "VIII"},
    ]

    async def _fake_fetch(*_args, **_kwargs):
        return "玩家", entries, 3

    monkeypatch.setattr(garage_service, "fetch_garage_all", _fake_fetch)
    garage_service._garage_cache.clear()

    text = await build_garage_text("玩家", "1", tier=10, tank_type="中坦")
    assert "匹配 1 辆" in text
    assert "十级中坦" in text
    assert "十级重坦" not in text
    assert "八级中坦" not in text
    garage_service._garage_cache.clear()
