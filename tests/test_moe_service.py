import pytest

from data.plugins.astrbot_plugin_wot.src.application import moe_service
from data.plugins.astrbot_plugin_wot.src.application.moe_service import build_moe_text
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    Tank,
    TankNationEnum,
    TankRoleEnum,
    TankTypeEnum,
)


def _tank() -> Tank:
    return Tank(
        name='"鞭蛇"',
        tier=9,
        premium=1,
        vehicle_cd=53665,
        nation=TankNationEnum.ITALY,
        type=TankTypeEnum.MEDIUM_TANK,
        role=TankRoleEnum.NONE,
    )


def _ranking(percentile: int, mastery: int) -> list[dict]:
    return [
        {
            "tank_id": 53665,
            "tank_name": '"鞭蛇"',
            "mastery": mastery,
            "percentile": str(percentile),
        }
    ]


@pytest.mark.asyncio
async def test_build_moe_text_queries_three_percentiles(monkeypatch):
    calls: list[int] = []

    async def _fake_fetch(tank_type, tier, percentile, **kwargs):
        calls.append(percentile)
        values = {65: 2729, 85: 3751, 95: 4542}
        return _ranking(percentile, values[percentile])

    monkeypatch.setattr(moe_service, "find_tanks_by_name", lambda _name: [_tank()])
    monkeypatch.setattr(moe_service, "fetch_moe_ranking", _fake_fetch)
    moe_service._moe_cache.clear()

    text = await build_moe_text("鞭蛇")
    assert "鞭蛇 环线标伤" in text
    assert "一环（65%）: 2729" in text
    assert "二环（85%）: 3751" in text
    assert "三环（95%）: 4542" in text
    assert sorted(calls) == [65, 85, 95]
    moe_service._moe_cache.clear()


@pytest.mark.asyncio
async def test_build_moe_text_caches_result(monkeypatch):
    calls = {"count": 0}

    async def _fake_fetch(*_args, **_kwargs):
        calls["count"] += 1
        return _ranking(65, 2729)

    monkeypatch.setattr(moe_service, "find_tanks_by_name", lambda _name: [_tank()])
    monkeypatch.setattr(moe_service, "fetch_moe_ranking", _fake_fetch)
    moe_service._moe_cache.clear()

    await build_moe_text("鞭蛇")
    # 缓存命中，不再发起请求
    await build_moe_text("鞭蛇")
    assert calls["count"] == 3
    moe_service._moe_cache.clear()


@pytest.mark.asyncio
async def test_build_moe_text_unknown_tank(monkeypatch):
    monkeypatch.setattr(moe_service, "find_tanks_by_name", lambda _name: [])
    text = await build_moe_text("不存在的坦克")
    assert "未找到坦克" in text


@pytest.mark.asyncio
async def test_build_moe_text_incomplete_data(monkeypatch):
    incomplete = Tank(
        name="未知",
        tier=0,
        premium=0,
        vehicle_cd=0,
        nation=TankNationEnum.UNKNOWN,
        type=TankTypeEnum.UNKNOWN,
        role=TankRoleEnum.NONE,
    )
    monkeypatch.setattr(moe_service, "find_tanks_by_name", lambda _name: [incomplete])
    text = await build_moe_text("未知")
    assert "数据不完整" in text


@pytest.mark.asyncio
async def test_build_moe_text_returns_all_matching_tanks(monkeypatch):
    second_tank = Tank(
        name="野牛 C46",
        tier=10,
        premium=1,
        vehicle_cd=53666,
        nation=TankNationEnum.ITALY,
        type=TankTypeEnum.MEDIUM_TANK,
        role=TankRoleEnum.NONE,
    )
    calls = {"count": 0}

    async def _fake_fetch(_tank_type, _tier, percentile, **_kwargs):
        calls["count"] += 1
        mastery = {65: 2729, 85: 3751, 95: 4542}[percentile]
        ranking = [{"tank_id": 53666, "mastery": mastery + 100}]
        if percentile != 95:
            ranking.append({"tank_id": 53665, "mastery": mastery})
        return ranking

    monkeypatch.setattr(
        moe_service, "find_tanks_by_name", lambda _name: [_tank(), second_tank]
    )
    monkeypatch.setattr(moe_service, "fetch_moe_ranking", _fake_fetch)
    moe_service._moe_cache.clear()

    text = await build_moe_text("野牛")

    assert "鞭蛇：暂无完整环线数据" in text
    assert "野牛 C46 环线标伤" in text
    assert calls["count"] == 6
    moe_service._moe_cache.clear()
