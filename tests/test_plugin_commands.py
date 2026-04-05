from importlib import import_module
from unittest.mock import AsyncMock, MagicMock

import pytest

import astrbot.api.message_components as Comp
from data.plugins.astrbot_plugin_wot.main import MyPlugin
from data.plugins.astrbot_plugin_wot.src.application.efficiency_service import (
    get_basic_efficiency_text,
)
from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
    resolve_player_name,
)
from data.plugins.astrbot_plugin_wot.src.application.message_parser import CommandInput
from data.plugins.astrbot_plugin_wot.src.application.query_service import (
    build_efficiency_response,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import PlayerStats


class DummyEvent:
    def __init__(self, sender_id: str, message_str: str, messages: list):
        self._sender_id = sender_id
        self.message_str = message_str
        self._messages = messages

    def get_sender_id(self):
        return self._sender_id

    def get_self_id(self):
        return "bot_123"

    def get_messages(self):
        return self._messages

    def chain_result(self, chain):
        return chain

    def plain_result(self, text: str):
        return {"plain": text}


def _sample_player_stats(comment: str = "stable output") -> PlayerStats:
    return PlayerStats(
        name="Tester",
        update_time="2026-03-13",
        power="1234",
        power_float="+12",
        win_rate="55.5%",
        total_count=1000,
        win_count=555,
        lose_count=445,
        hit_rate="72.3%",
        avg_tier="8.2",
        avg_damage="2100",
        avg_exp="980",
        avg_kill="1.3",
        avg_occupy="0.4",
        avg_defense="0.6",
        avg_discovery="1.1",
        comment=comment,
        radar_data=[10, 20, 30],
    )


def test_plugin_module_can_load():
    module = import_module("data.plugins.astrbot_plugin_wot.main")
    assert module.MyPlugin is not None


@pytest.mark.asyncio
async def test_plugin_initialize_starts_scheduler_and_syncs_tanks(
    monkeypatch: pytest.MonkeyPatch,
):
    called = {"started": False, "synced": False}

    def _fake_start_timer_thread():
        called["started"] = True

    async def _fake_sync_all_tank_info():
        called["synced"] = True
        return "ok"

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.start_timer_thread",
        _fake_start_timer_thread,
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.sync_all_tank_info",
        _fake_sync_all_tank_info,
    )
    plugin = MyPlugin(context=MagicMock())
    await plugin.initialize()
    assert called["started"] is True
    assert called["synced"] is True


@pytest.mark.asyncio
async def test_get_basic_efficiency_text_uses_wot_box_gateway(
    monkeypatch: pytest.MonkeyPatch,
):
    stats = _sample_player_stats()

    class FakeWotBoxService:
        async def get_player_stats(self, player_name: str):
            assert player_name == "Tester"
            return stats, []

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.efficiency_service.WotBoxService",
        FakeWotBoxService,
    )

    text = await get_basic_efficiency_text("Tester")
    assert "玩家：Tester" in text
    assert "场均伤害：2100" in text


@pytest.mark.asyncio
async def test_resolve_player_name_with_explicit_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.player_resolver.player_exists",
        AsyncMock(return_value=True),
    )
    player_name, err = await resolve_player_name("10001", [], "Tester")
    assert player_name == "Tester"
    assert err is None


@pytest.mark.asyncio
async def test_resolve_player_name_returns_target_unbound(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.player_resolver.read_binding_data",
        lambda _sender_id: "",
    )
    message_chain = [Comp.At(qq="20002")]

    player_name, err = await resolve_player_name("10001", message_chain, None)
    assert player_name is None
    assert err == "target_unbound"


@pytest.mark.asyncio
async def test_build_efficiency_response_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.resolve_player_name",
        AsyncMock(return_value=("Tester", None)),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.get_basic_efficiency_text",
        AsyncMock(return_value="玩家：Tester\n效率：1234"),
    )

    input = CommandInput("10001", [], None)
    result = await build_efficiency_response(input)
    assert len(result) == 2
    assert isinstance(result[0], Comp.At)
    assert isinstance(result[1], Comp.Plain)
    assert "效率：1234" in result[1].text


@pytest.mark.asyncio
async def test_build_efficiency_response_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.resolve_player_name",
        AsyncMock(return_value=("Tester", None)),
    )

    async def _raise(_player_name: str):
        raise RuntimeError("network error")

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.get_basic_efficiency_text",
        _raise,
    )
    logger_exception = MagicMock()
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.logger.exception",
        logger_exception,
    )

    input = CommandInput("10001", [], None)
    result = await build_efficiency_response(input)
    assert len(result) == 2
    assert isinstance(result[0], Comp.At)
    assert isinstance(result[1], Comp.Plain)
    assert result[1].text == "查询失败，请稍后再试"
    logger_exception.assert_called_once()


@pytest.mark.asyncio
async def test_query_basic_efficiency_command_returns_plain_chain(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.build_efficiency_response",
        AsyncMock(
            return_value=[Comp.At(qq="10001"), Comp.Plain("玩家：Tester\n效率：1234")]
        ),
    )
    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="效率 Tester",
        messages=[Comp.Plain("效率 Tester")],
    )

    results = [item async for item in plugin.query_basic_efficiency(event)]
    assert len(results) == 1
    assert isinstance(results[0][0], Comp.At)
    assert str(results[0][0].qq) == "10001"
    assert isinstance(results[0][1], Comp.Plain)
    assert "效率：1234" in results[0][1].text


@pytest.mark.asyncio
async def test_get_today_performance_returns_report_chain(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _fake_build_report_response(*_args, **_kwargs):
        return [Comp.At(qq="10001"), Comp.Plain("report-ok")]

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.build_report_response",
        _fake_build_report_response,
    )
    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="/今日效率",
        messages=[Comp.Plain("/今日效率")],
    )

    results = [item async for item in plugin.query_today_report(event)]
    assert len(results) == 1
    assert isinstance(results[0][0], Comp.At)
    assert isinstance(results[0][1], Comp.Plain)
    assert results[0][1].text == "report-ok"
