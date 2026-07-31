import pytest

from data.plugins.astrbot_plugin_wot.src.application import garage_service
from data.plugins.astrbot_plugin_wot.src.application.garage_service import (
    build_garage_text,
)


def _entry(name: str, battles: int, wn8: float, win_rate: float) -> dict:
    return {
        "vehicle_name": name,
        "vlevel": "X",
        "vtype": "中型坦克",
        "battles": battles,
        "win_rate": win_rate,
        "WN8": wn8,
        "damage_avg": 2500.0,
        "vehicle_mastery": 2,
    }


@pytest.mark.asyncio
async def test_build_garage_text_formats_top_tanks(monkeypatch):
    entries = [
        _entry("“豹”I", 58, 2235.02, 56.9),
        _entry('"战鳄"', 22, 1979.3, 63.64),
        _entry("DBV-152", 117, 2090.48, 60.68),
    ]

    async def _fake_fetch(*_args, **_kwargs):
        return "常威爆打来福", entries, 173

    monkeypatch.setattr(garage_service, "fetch_garage_all", _fake_fetch)
    garage_service._garage_cache.clear()

    text = await build_garage_text("常威爆打来福", "7059354392")
    assert "共 173 辆" in text
    assert "1. DBV-152" in text
    assert "胜率60.68%" in text
    assert "WN8 2090" in text
    assert "2环" in text
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
