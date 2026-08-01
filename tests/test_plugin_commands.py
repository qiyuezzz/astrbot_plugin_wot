from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import astrbot.api.message_components as Comp
from data.plugins.astrbot_plugin_wot import main as plugin_main
from data.plugins.astrbot_plugin_wot.main import MyPlugin
from data.plugins.astrbot_plugin_wot.src.application.efficiency_service import (
    get_basic_efficiency_text,
)
from data.plugins.astrbot_plugin_wot.src.application.message_parser import CommandInput
from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
    resolve_player_name,
)
from data.plugins.astrbot_plugin_wot.src.application.query_service import (
    build_career_response,
    build_efficiency_response,
    build_garage_response,
    build_moe_response,
    build_report_response,
    build_tank_comparison_response,
    build_tank_info_response,
)
from data.plugins.astrbot_plugin_wot.src.domain.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.domain.report import PlayerStats
from data.plugins.astrbot_plugin_wot.src.application.tank_info_service import TankReport


class DummyEvent:
    def __init__(
        self,
        sender_id: str,
        message_str: str,
        messages: list,
        is_at_or_wake_command: bool = False,
    ):
        self._sender_id = sender_id
        self.message_str = message_str
        self._messages = messages
        self.is_at_or_wake_command = is_at_or_wake_command
        self.unified_msg_origin = f"test:{sender_id}"
        self.sent = []
        self.stopped = False

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

    async def send(self, payload):
        self.sent.append(payload)

    def stop_event(self):
        self.stopped = True


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
async def test_bind_command_prompts_for_multiple_players_and_binds_selection(
    monkeypatch: pytest.MonkeyPatch,
):
    candidates = [
        AccountInfo("1", "Tester_One", 100, "A"),
        AccountInfo("2", "Tester_Two", 200, "B"),
    ]
    selection_event = DummyEvent("10001", "2", [Comp.Plain("2")])
    controller = MagicMock()

    def fake_session_waiter(*, timeout):
        assert timeout == 60

        def decorator(handler):
            async def wrapper(event, session_filter=None):
                await handler(controller, selection_event)

            return wrapper

        return decorator

    monkeypatch.setattr(
        plugin_main,
        "search_account_candidates",
        AsyncMock(return_value=candidates),
    )
    bind_account = AsyncMock(return_value=candidates[1])
    monkeypatch.setattr(plugin_main, "bind_account", bind_account)
    monkeypatch.setattr(plugin_main, "session_waiter", fake_session_waiter)

    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="/wot绑定 Tester",
        messages=[Comp.Plain("/wot绑定 Tester")],
    )

    results = [item async for item in plugin.wot_bind_player_name(event)]

    assert len(results) == 1
    assert "匹配到多个结果" in results[0]["plain"]
    assert "Tester_One" in results[0]["plain"]
    assert "Tester_Two" in results[0]["plain"]
    bind_account.assert_awaited_once_with("10001", candidates[1])
    assert event.sent == [
        {
            "plain": '绑定成功，玩家名称为"Tester_Two"\n军团:"B"\n玩家id:"2"'
        }
    ]
    assert event.stopped is True
    controller.stop.assert_called_once_with()


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

    class _MissingPath:
        def is_file(self):
            return False

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.prepare_tank_info_path",
        lambda: _MissingPath(),
    )
    plugin = MyPlugin(context=MagicMock())
    await plugin.initialize()
    assert called["started"] is True
    assert called["synced"] is True


@pytest.mark.asyncio
async def test_plugin_initialize_skips_sync_when_tank_data_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    called = {"synced": False}

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.start_timer_thread", lambda: None
    )

    async def _fake_sync_all_tank_info():
        called["synced"] = True
        return "ok"

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.sync_all_tank_info",
        _fake_sync_all_tank_info,
    )

    tank_info_path = tmp_path / "wot_tanks_full.json"
    tank_info_path.write_text(
        '{"59式": {"name": "59式", "vehicle_cd": 49}}', encoding="utf-8"
    )

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.prepare_tank_info_path",
        lambda: tank_info_path,
    )
    plugin = MyPlugin(context=MagicMock())
    await plugin.initialize()
    assert called["synced"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "{}", "not-json"])
async def test_plugin_initialize_syncs_when_tank_data_file_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    content: str,
):
    called = {"synced": False}

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.start_timer_thread", lambda: None
    )

    async def _fake_sync_all_tank_info():
        called["synced"] = True
        return "ok"

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.sync_all_tank_info",
        _fake_sync_all_tank_info,
    )
    tank_info_path = tmp_path / "wot_tanks_full.json"
    tank_info_path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.prepare_tank_info_path",
        lambda: tank_info_path,
    )

    plugin = MyPlugin(context=MagicMock())
    await plugin.initialize()

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
async def test_resolve_player_name_returns_target_unbound(
    monkeypatch: pytest.MonkeyPatch,
):
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


@pytest.mark.asyncio
async def test_build_report_response_uses_returned_image_url(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.resolve_player_name",
        AsyncMock(return_value=("Tester", None)),
    )

    async def _fake_report(_send_id: str, _name: str | None) -> str:
        return "https://example.com/report.jpg"

    input = CommandInput("10001", [], None)
    result = await build_report_response(input, _fake_report)
    assert len(result) == 2
    assert isinstance(result[0], Comp.At)
    assert isinstance(result[1], Comp.Image)
    assert result[1].file == "https://example.com/report.jpg"


@pytest.mark.asyncio
async def test_build_garage_response_returns_image(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.resolve_player_account",
        AsyncMock(return_value=("Tester", "123", None)),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.build_garage_text",
        AsyncMock(return_value="Tester 的车库"),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.generate_text_report",
        AsyncMock(return_value="https://example.com/garage.jpg"),
    )

    result = await build_garage_response(CommandInput("10001", [], None))

    assert isinstance(result[1], Comp.Image)
    assert result[1].file == "https://example.com/garage.jpg"


@pytest.mark.asyncio
async def test_build_garage_response_separates_player_and_filters(
    monkeypatch: pytest.MonkeyPatch,
):
    resolver = AsyncMock(return_value=("Tester", "123", None))
    builder = AsyncMock(return_value="筛选后的车库")
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.resolve_player_account",
        resolver,
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.build_garage_text",
        builder,
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.generate_text_report",
        AsyncMock(return_value="https://example.com/garage.jpg"),
    )

    await build_garage_response(CommandInput("10001", [], "Tester 10级 重坦"))

    assert resolver.await_args.args[2] == "Tester"
    builder.assert_awaited_once_with("Tester", "123", 10, "重坦")


@pytest.mark.asyncio
async def test_build_career_response_returns_image(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.resolve_player_account",
        AsyncMock(return_value=("Tester", "123", None)),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.build_career_text",
        AsyncMock(return_value="标准模式总览"),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.generate_text_report",
        AsyncMock(return_value="https://example.com/career.jpg"),
    )

    result = await build_career_response(CommandInput("10001", [], None))

    assert isinstance(result[1], Comp.Image)
    assert result[1].file == "https://example.com/career.jpg"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("builder_name", "response_fn", "argument", "title"),
    [
        (
            "build_tank_info_report",
            build_tank_info_response,
            "59式",
            "坦克信息查询",
        ),
        (
            "build_tank_comparison_report",
            build_tank_comparison_response,
            "59式 查狄伦 25t",
            "坦克对比",
        ),
    ],
)
async def test_tank_reference_responses_render_images(
    monkeypatch: pytest.MonkeyPatch,
    builder_name,
    response_fn,
    argument,
    title,
):
    monkeypatch.setattr(
        f"data.plugins.astrbot_plugin_wot.src.application.query_service.{builder_name}",
        AsyncMock(
            return_value=TankReport(
                "坦克资料", (("59式", "https://example.com/tank.png"),)
            )
        ),
    )
    renderer = AsyncMock(return_value="https://example.com/tank.jpg")
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.generate_text_report",
        renderer,
    )

    result = await response_fn(CommandInput("10001", [], argument))

    assert isinstance(result[1], Comp.Image)
    assert renderer.await_args.args[1] == title
    assert renderer.await_args.kwargs["hero_images"][0][0] == "59式"


@pytest.mark.asyncio
async def test_build_moe_response_returns_image(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.build_moe_text",
        AsyncMock(return_value="59式 环线标伤"),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.query_service.generate_text_report",
        AsyncMock(return_value="https://example.com/moe.jpg"),
    )

    result = await build_moe_response(CommandInput("10001", [], "59式"))

    assert isinstance(result[1], Comp.Image)
    assert result[1].file == "https://example.com/moe.jpg"


@pytest.mark.asyncio
async def test_command_router_handles_zh_help_only(monkeypatch: pytest.MonkeyPatch):
    async def _fake_show_help(_event):
        yield "help-ok"

    plugin = MyPlugin(context=MagicMock())
    monkeypatch.setattr(plugin, "show_help", _fake_show_help)

    zh_event = DummyEvent(
        sender_id="10001",
        message_str="帮助",
        messages=[Comp.Plain("帮助")],
    )
    zh_results = [item async for item in plugin.command_router(zh_event)]
    assert zh_results == ["help-ok"]

    en_event = DummyEvent(
        sender_id="10001",
        message_str="help",
        messages=[Comp.Plain("help")],
    )
    en_results = [item async for item in plugin.command_router(en_event)]
    assert en_results == []


@pytest.mark.asyncio
async def test_show_help_returns_command_list_as_image(monkeypatch: pytest.MonkeyPatch):
    generate_text_report = AsyncMock(return_value="https://example.com/help.jpg")
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.generate_text_report",
        generate_text_report,
    )
    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="帮助",
        messages=[Comp.Plain("帮助")],
    )

    results = [item async for item in plugin.show_help(event)]

    assert len(results) == 1
    assert isinstance(results[0][1], Comp.Image)
    assert results[0][1].file == "https://example.com/help.jpg"
    help_text = generate_text_report.call_args.args[2]
    for command in (
        "wot绑定",
        "效率 / 盒子效率",
        "今日效率 / 今日战绩",
        "昨日效率 / 昨日战绩",
        "两日效率 / 两日战绩",
        "三日效率 / 三日战绩",
        "百场效率 / 百场战绩",
        "车库",
        "坦克生涯",
        "坦克信息",
        "坦克对比",
        "环线 / 标伤",
        "同步坦克 / 更新坦克",
        "帮助",
    ):
        assert command in help_text
    assert "单车" not in help_text
    assert "坦克 [坦克名称]" not in help_text
    assert "\n对比 [坦克A]" not in help_text
    assert "参数可单独或组合使用，顺序不限" in help_text
    assert "车库 玩家名 10级 重坦" in help_text
    assert "不支持无空格连写" in help_text
    assert "分别查询今日、昨日、近两日、近三日或最近百场战绩；用法相同" in help_text
    assert generate_text_report.call_args.kwargs["layout"] == "help"
    assert generate_text_report.call_args.kwargs["width"] == 2200


@pytest.mark.asyncio
async def test_command_router_uses_renamed_tank_commands(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _fake_tank_info(_event):
        yield "tank-info-ok"

    async def _fake_tank_comparison(_event):
        yield "tank-comparison-ok"

    plugin = MyPlugin(context=MagicMock())
    monkeypatch.setattr(plugin, "query_tank_info", _fake_tank_info)
    monkeypatch.setattr(plugin, "query_tank_comparison", _fake_tank_comparison)

    info_event = DummyEvent(
        sender_id="10001",
        message_str="坦克信息 59式",
        messages=[Comp.Plain("坦克信息 59式")],
    )
    comparison_event = DummyEvent(
        sender_id="10001",
        message_str="坦克对比 59式 查狄伦 25t",
        messages=[Comp.Plain("坦克对比 59式 查狄伦 25t")],
    )
    old_info_event = DummyEvent(
        sender_id="10001",
        message_str="坦克 59式",
        messages=[Comp.Plain("坦克 59式")],
    )
    old_comparison_event = DummyEvent(
        sender_id="10001",
        message_str="对比 59式 查狄伦 25t",
        messages=[Comp.Plain("对比 59式 查狄伦 25t")],
    )

    assert [item async for item in plugin.command_router(info_event)] == ["tank-info-ok"]
    assert [item async for item in plugin.command_router(comparison_event)] == [
        "tank-comparison-ok"
    ]
    assert [item async for item in plugin.command_router(old_info_event)] == []
    assert [item async for item in plugin.command_router(old_comparison_event)] == []


@pytest.mark.asyncio
async def test_command_router_handles_garage(monkeypatch: pytest.MonkeyPatch):
    async def _fake_query_garage(_event):
        yield "garage-ok"

    plugin = MyPlugin(context=MagicMock())
    monkeypatch.setattr(plugin, "query_garage", _fake_query_garage)
    event = DummyEvent(
        sender_id="10001",
        message_str="车库",
        messages=[Comp.Plain("车库")],
    )
    results = [item async for item in plugin.command_router(event)]
    assert results == ["garage-ok"]


@pytest.mark.asyncio
async def test_command_router_handles_career(monkeypatch: pytest.MonkeyPatch):
    async def _fake_query_career(_event):
        yield "career-ok"

    plugin = MyPlugin(context=MagicMock())
    monkeypatch.setattr(plugin, "query_career", _fake_query_career)
    event = DummyEvent(
        sender_id="10001",
        message_str="坦克生涯",
        messages=[Comp.Plain("坦克生涯")],
    )
    results = [item async for item in plugin.command_router(event)]
    assert results == ["career-ok"]


@pytest.mark.asyncio
async def test_query_garage_command_returns_chain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.build_garage_response",
        AsyncMock(return_value=[Comp.At(qq="10001"), Comp.Plain("车库文本")]),
    )
    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="/车库",
        messages=[Comp.Plain("/车库")],
    )
    results = [item async for item in plugin.query_garage(event)]
    assert len(results) == 1
    assert isinstance(results[0][1], Comp.Plain)
    assert results[0][1].text == "车库文本"


@pytest.mark.asyncio
async def test_query_moe_command_returns_chain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.main.build_moe_response",
        AsyncMock(return_value=[Comp.At(qq="10001"), Comp.Plain("环线文本")]),
    )
    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="/环线 鞭蛇",
        messages=[Comp.Plain("/环线 鞭蛇")],
    )
    results = [item async for item in plugin.query_moe(event)]
    assert len(results) == 1
    assert results[0][1].text == "环线文本"


@pytest.mark.asyncio
async def test_query_tank_info_uses_session_for_ambiguous_name(
    monkeypatch: pytest.MonkeyPatch,
):
    candidates = [
        SimpleNamespace(name="野牛"),
        SimpleNamespace(name="野牛 C45"),
    ]
    for candidate in candidates:
        candidate.tier = 8
        candidate.nation = SimpleNamespace(display_name="德国")
        candidate.type = SimpleNamespace(display_name="重坦")
        candidate.role = SimpleNamespace(display_name="通用/无定位")

    selection_event = DummyEvent(
        sender_id="10001",
        message_str="2",
        messages=[Comp.Plain("2")],
    )
    controller = MagicMock()

    def fake_session_waiter(*, timeout):
        assert timeout == 60

        def decorator(handler):
            async def wrapper(event, session_filter=None):
                await handler(controller, selection_event)

            return wrapper

        return decorator

    monkeypatch.setattr(plugin_main, "find_tank_info_candidates", lambda _name: candidates)
    monkeypatch.setattr(
        plugin_main,
        "format_tank_info_candidates",
        lambda _name, _candidates: "候选列表",
    )
    builder = AsyncMock(return_value=[Comp.Plain("精确百科")])
    monkeypatch.setattr(plugin_main, "build_tank_info_response", builder)
    monkeypatch.setattr(plugin_main, "session_waiter", fake_session_waiter)

    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="坦克信息 野牛",
        messages=[Comp.Plain("坦克信息 野牛")],
    )

    results = [item async for item in plugin.query_tank_info(event)]

    assert results == [{"plain": "候选列表"}]
    assert builder.await_args.args[0].explicit_name == "野牛 C45"
    assert len(event.sent) == 1
    assert event.sent[0][0].text == "精确百科"
    controller.stop.assert_called_once_with()


@pytest.mark.asyncio
async def test_tank_selection_only_prompts_once_for_invalid_choices(
    monkeypatch: pytest.MonkeyPatch,
):
    candidate = SimpleNamespace(name="59式")
    waiting_events = [
        DummyEvent("10001", "不是编号", [Comp.Plain("不是编号")]),
        DummyEvent("10001", "99", [Comp.Plain("99")]),
        DummyEvent("10001", "1", [Comp.Plain("1")]),
    ]
    controller = MagicMock()

    def fake_session_waiter(*, timeout):
        assert timeout == 60

        def decorator(handler):
            async def wrapper(event, session_filter=None):
                for waiting_event in waiting_events:
                    await handler(controller, waiting_event)

            return wrapper

        return decorator

    monkeypatch.setattr(plugin_main, "session_waiter", fake_session_waiter)

    selected = await plugin_main._wait_for_tank_selection(
        waiting_events[0], [candidate]
    )

    assert selected is candidate
    assert len(waiting_events[0].sent) == 1
    assert waiting_events[0].sent[0] == {
        "plain": "请输入列表中的编号，或回复“取消”退出。"
    }
    assert waiting_events[1].sent == []
    controller.keep.assert_not_called()


@pytest.mark.asyncio
async def test_query_tank_comparison_selects_both_ambiguous_names(
    monkeypatch: pytest.MonkeyPatch,
):
    left_candidates = [SimpleNamespace(name="野牛"), SimpleNamespace(name="C45 野牛")]
    right_candidates = [SimpleNamespace(name="59式"), SimpleNamespace(name="黄金59式")]
    selection_events = [
        DummyEvent("10001", "2", [Comp.Plain("2")]),
        DummyEvent("10001", "1", [Comp.Plain("1")]),
    ]
    controller = MagicMock()
    session_index = 0

    def fake_session_waiter(*, timeout):
        assert timeout == 60

        def decorator(handler):
            async def wrapper(event, session_filter=None):
                nonlocal session_index
                selection_event = selection_events[session_index]
                session_index += 1
                await handler(controller, selection_event)

            return wrapper

        return decorator

    monkeypatch.setattr(
        plugin_main,
        "find_tank_comparison_candidates",
        lambda _argument: (("野牛", "59"), left_candidates, right_candidates),
    )
    monkeypatch.setattr(
        plugin_main,
        "format_tank_info_candidates",
        lambda _name, _candidates, subject="": subject,
    )
    builder = AsyncMock(return_value=[Comp.Plain("对比结果")])
    monkeypatch.setattr(plugin_main, "build_tank_comparison_response", builder)
    monkeypatch.setattr(plugin_main, "session_waiter", fake_session_waiter)

    plugin = MyPlugin(context=MagicMock())
    event = DummyEvent(
        sender_id="10001",
        message_str="坦克对比 野牛 59",
        messages=[Comp.Plain("坦克对比 野牛 59")],
    )

    results = [item async for item in plugin.query_tank_comparison(event)]

    assert results == [{"plain": "第一辆坦克"}]
    assert event.sent[0] == {"plain": "第二辆坦克"}
    assert event.sent[1][0].text == "对比结果"
    assert builder.await_args.args[0].explicit_name == "C45 野牛 和 59式"
    assert controller.stop.call_count == 2
