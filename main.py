from __future__ import annotations

import re
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.session_waiter import SessionController, SessionFilter, session_waiter
from data.plugins.astrbot_plugin_wot.src.application.message_parser import (
    CommandInput,
    extract_text_after_leading_at,
)
from data.plugins.astrbot_plugin_wot.src.application.query_service import (
    build_efficiency_response,
    build_garage_response,
    build_moe_response,
    build_report_response,
    build_single_vehicle_response,
    build_tank_comparison_response,
    build_tank_info_response,
    find_tank_comparison_candidates,
    find_tank_info_candidates,
    format_tank_info_candidates,
    handle_bind_command,
)
from data.plugins.astrbot_plugin_wot.src.application.report.report_service import (
    REPORT_CONFIGS,
    query_report,
)
from data.plugins.astrbot_plugin_wot.src.application.tank_sync_service import (
    sync_all_tank_info,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    close_shared_session,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import Tank
from data.plugins.astrbot_plugin_wot.src.settings.storage import (
    prepare_tank_info_path,
)
from data.plugins.astrbot_plugin_wot.src.tasks.scheduler import (
    start_timer_thread,
    stop_timer_thread,
)

EFFICIENCY_COMMANDS = ["效率", "盒子效率"]

_REPORT_HANDLERS = [
    ("query_today_report", 0),
    ("query_yesterday_report", 1),
    ("query_two_days_report", 2),
    ("query_three_days_report", 3),
    ("query_hundred_report", 4),
]


class _TankSelectionSessionFilter(SessionFilter):
    """按消息来源和发送人隔离坦克候选选择会话。"""

    def filter(self, event: AstrMessageEvent) -> str:
        return f"{event.unified_msg_origin}:{event.get_sender_id()}"


async def _wait_for_tank_selection(
    event: AstrMessageEvent, candidates: list[Tank]
) -> Tank | None:
    selected: list[Tank] = []

    @session_waiter(timeout=60)
    async def _selection_waiter(
        controller: SessionController,
        waiting_event: AstrMessageEvent,
    ) -> None:
        try:
            choice = waiting_event.message_str.strip().lstrip("/").strip()
            if choice in {"取消", "退出"}:
                await waiting_event.send(waiting_event.plain_result("已取消坦克查询。"))
                controller.stop()
                return
            if not choice.isdigit():
                await waiting_event.send(
                    waiting_event.plain_result("请输入列表中的编号，或回复“取消”退出。")
                )
                controller.keep(timeout=60, reset_timeout=True)
                return
            index = int(choice) - 1
            if not 0 <= index < len(candidates):
                await waiting_event.send(
                    waiting_event.plain_result(
                        f"编号无效，请输入 1-{len(candidates)}，或回复“取消”退出。"
                    )
                )
                controller.keep(timeout=60, reset_timeout=True)
                return
            selected.append(candidates[index])
            controller.stop()
        finally:
            waiting_event.stop_event()

    try:
        await _selection_waiter(event, session_filter=_TankSelectionSessionFilter())
    except TimeoutError:
        await event.send(event.plain_result("选择已超时，请重新输入坦克名称查询。"))
    return selected[0] if selected else None


def _load_plugin_version() -> str:
    """从 metadata.yaml 读取插件版本，避免与注册信息重复维护。"""
    metadata_path = Path(__file__).resolve().parent / "metadata.yaml"
    try:
        match = re.search(
            r"^version:\s*(\S+)", metadata_path.read_text(encoding="utf-8"), re.M
        )
        if match:
            return match.group(1)
    except OSError:
        pass
    return "v0.0.0"


def _make_report_handler(config, plugin_instance):
    """生成报表查询处理器"""

    async def _handler(event: AstrMessageEvent, message_text: str | None = None):
        plugin_instance._load_config()
        input = CommandInput.from_event(event, config.aliases, message_text)
        chain = await build_report_response(
            input, lambda sid, name: query_report(sid, config, name)
        )
        yield event.chain_result(chain)

    return _handler


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", _load_plugin_version())
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._load_config()

    def _load_config(self):
        """加载插件配置"""
        from astrbot.core.star.star import star_map
        from data.plugins.astrbot_plugin_wot.src.settings.constants import (
            set_plugin_config,
        )

        metadata = star_map.get(__name__)
        config = {}
        if metadata and metadata.config:
            config = dict(metadata.config)
        set_plugin_config(config)
        logger.info(f"插件配置已加载: {config}")

    async def initialize(self):
        """插件初始化：启动定时任务；首次使用（无坦克数据文件）时同步坦克数据"""
        start_timer_thread()
        if prepare_tank_info_path().exists():
            logger.info("坦克数据文件已存在，跳过启动同步，由每日定时任务更新")
            return
        try:
            result = await sync_all_tank_info()
            logger.info(f"坦克数据初始化: {result}")
        except Exception as exc:
            logger.warning(f"坦克数据初始化失败（将在后台重试）: {exc}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def command_router(self, event: AstrMessageEvent):
        """监听群消息，处理不带 / 前缀的命令"""
        message_str = event.message_str.strip()
        if event.is_at_or_wake_command:
            return

        routes = [
            *[
                (REPORT_CONFIGS[idx].aliases, getattr(self, method))
                for method, idx in _REPORT_HANDLERS
            ],
            ([*EFFICIENCY_COMMANDS], self.query_basic_efficiency),
            (["wot绑定"], self.wot_bind_player_name),
            (["车库"], self.query_garage),
            (["单车"], self.query_single_vehicle),
            (["坦克"], self.query_tank_info),
            (["对比"], self.query_tank_comparison),
            (["环线", "标伤"], self.query_moe),
            (["同步坦克", "更新坦克"], self.sync_full_tank_info),
            (["帮助"], self.show_help),
        ]

        at_text = extract_text_after_leading_at(event.get_messages())
        if at_text:
            for cmds, handler in routes:
                for c in cmds:
                    if at_text == c:
                        async for result in handler(event):
                            yield result
                        return
            return

        for cmds, handler in routes:
            if any(
                message_str == c
                or (message_str.startswith(c) and message_str[len(c)].isspace())
                for c in cmds
            ):
                async for result in handler(event):
                    yield result
                return

    @filter.command("wot绑定")
    async def wot_bind_player_name(self, event: AstrMessageEvent):
        """绑定玩家游戏名称"""
        result = await handle_bind_command(event)
        yield result

    @filter.command("效率", alias={"盒子效率"})
    async def query_basic_efficiency(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询盒子页面基础效率数据（文本返回）"""
        input = CommandInput.from_event(event, EFFICIENCY_COMMANDS, message_text)
        chain = await build_efficiency_response(input)
        yield event.chain_result(chain)

    @filter.command("今日效率", alias={"今日战绩"})
    async def query_today_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[0], self)(
            event, message_text
        ):
            yield ret

    @filter.command("昨日效率", alias={"昨日战绩"})
    async def query_yesterday_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[1], self)(
            event, message_text
        ):
            yield ret

    @filter.command("两日效率", alias={"两日战绩"})
    async def query_two_days_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[2], self)(
            event, message_text
        ):
            yield ret

    @filter.command("三日效率", alias={"三日战绩"})
    async def query_three_days_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[3], self)(
            event, message_text
        ):
            yield ret

    @filter.command("百场效率", alias={"百场战绩"})
    async def query_hundred_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[4], self)(
            event, message_text
        ):
            yield ret

    @filter.command("同步坦克", alias={"更新坦克"})
    async def sync_full_tank_info(self, event: AstrMessageEvent):
        """融合官网与 WotInspector 的坦克信息"""
        result = await sync_all_tank_info()
        yield event.plain_result(result)

    @filter.command("车库")
    async def query_garage(self, event: AstrMessageEvent, message_text: str | None = None):
        """查询玩家车库坦克战绩"""
        input = CommandInput.from_event(event, ["车库"], message_text)
        chain = await build_garage_response(input)
        yield event.chain_result(chain)

    @filter.command("单车")
    async def query_single_vehicle(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询玩家指定坦克的详细战绩"""
        input = CommandInput.from_event(event, ["单车"], message_text)
        chain = await build_single_vehicle_response(input)
        yield event.chain_result(chain)

    @filter.command("坦克")
    async def query_tank_info(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询坦克百科属性"""
        input = CommandInput.from_event(event, ["坦克"], message_text)
        if input.explicit_name:
            candidates = find_tank_info_candidates(input.explicit_name)
            if len(candidates) > 1:
                yield event.plain_result(
                    format_tank_info_candidates(input.explicit_name, candidates)
                )
                try:
                    selected = await _wait_for_tank_selection(event, candidates)
                except Exception as exc:
                    logger.exception(f"坦克候选选择失败 (坦克={input.explicit_name}): {exc}")
                    await event.send(event.plain_result("坦克查询失败，请重新输入坦克名称。"))
                    selected = None
                if selected:
                    selected_input = CommandInput(
                        input.send_id,
                        event.get_messages(),
                        selected.name,
                        input.self_id,
                    )
                    chain = await build_tank_info_response(selected_input)
                    await event.send(event.chain_result(chain))
                event.stop_event()
                return
        chain = await build_tank_info_response(input)
        yield event.chain_result(chain)

    @filter.command("对比")
    async def query_tank_comparison(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """对比两辆坦克的主要属性"""
        input = CommandInput.from_event(event, ["对比"], message_text)
        comparison_candidates = (
            find_tank_comparison_candidates(input.explicit_name or "")
            if input.explicit_name
            else None
        )
        if comparison_candidates:
            pair, left_candidates, right_candidates = comparison_candidates
            if left_candidates and right_candidates:
                had_session = False
                left = left_candidates[0]
                right = right_candidates[0]
                if len(left_candidates) > 1:
                    yield event.plain_result(
                        format_tank_info_candidates(
                            pair[0], left_candidates, subject="第一辆坦克"
                        )
                    )
                    had_session = True
                    selected_left = await _wait_for_tank_selection(event, left_candidates)
                    if not selected_left:
                        event.stop_event()
                        return
                    left = selected_left
                if len(right_candidates) > 1:
                    prompt = format_tank_info_candidates(
                        pair[1], right_candidates, subject="第二辆坦克"
                    )
                    if had_session:
                        await event.send(event.plain_result(prompt))
                    else:
                        yield event.plain_result(prompt)
                    had_session = True
                    selected_right = await _wait_for_tank_selection(event, right_candidates)
                    if not selected_right:
                        event.stop_event()
                        return
                    right = selected_right

                selected_input = CommandInput(
                    input.send_id,
                    event.get_messages(),
                    f"{left.name} 和 {right.name}",
                    input.self_id,
                )
                chain = await build_tank_comparison_response(selected_input)
                if had_session:
                    await event.send(event.chain_result(chain))
                    event.stop_event()
                else:
                    yield event.chain_result(chain)
                return
        chain = await build_tank_comparison_response(input)
        yield event.chain_result(chain)

    @filter.command("环线", alias={"标伤"})
    async def query_moe(self, event: AstrMessageEvent, message_text: str | None = None):
        """查询坦克一环/二环/三环标伤"""
        input = CommandInput.from_event(event, ["环线", "标伤"], message_text)
        chain = await build_moe_response(input)
        yield event.chain_result(chain)

    @filter.command("帮助")
    async def show_help(self, event: AstrMessageEvent):
        """显示所有可用命令及其说明"""
        help_text = "坦克世界插件命令列表：\n\n"
        help_text += "基础命令：\n"
        help_text += "- wot绑定 [玩家名称]：绑定玩家游戏名称到当前QQ账号\n"
        help_text += (
            "- 效率/盒子效率 [玩家名称]：查询盒子页面基础效率数据（文本返回）\n\n"
        )
        help_text += "战绩报表：\n"
        help_text += "- 今日效率/今日战绩 [玩家名称]：查询今日效率和战绩\n"
        help_text += "- 昨日效率/昨日战绩 [玩家名称]：查询昨日效率和战绩\n"
        help_text += "- 两日效率/两日战绩 [玩家名称]：查询两日效率和战绩\n"
        help_text += "- 三日效率/三日战绩 [玩家名称]：查询三日效率和战绩\n"
        help_text += "- 百场效率/百场战绩 [玩家名称]：查询百场效率和战绩\n\n"
        help_text += "- 车库 [玩家名称] [等级] [类型]：查询并筛选玩家车库\n"
        help_text += "  示例：车库 10级 重坦、车库 玩家名 8级 中坦\n"
        help_text += "- 单车 [玩家名称] [坦克名称]：查询指定坦克的详细战绩\n"
        help_text += "- 坦克 [坦克名称]：查询坦克百科属性\n"
        help_text += "  名称匹配到多辆坦克时会返回编号列表，回复编号选择（60秒内有效）\n"
        help_text += "- 对比 [坦克A] 和 [坦克B]：对比两辆坦克的属性\n"
        help_text += "  两辆坦克分别匹配到多个结果时，会依次返回编号列表供选择\n"
        help_text += "- 环线 [坦克名称]：查询坦克一环/二环/三环标伤阈值\n\n"
        help_text += "管理命令：\n"
        help_text += "- 同步坦克/更新坦克：融合官网与 WotInspector 的坦克信息\n\n"
        help_text += "使用说明：\n"
        help_text += "- 所有命令都支持带/和不带/两种方式，例如：/效率 或 效率\n"
        help_text += "- 对于官方QQ机器人，需要先@机器人，然后再输入命令\n"
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁时的清理逻辑：停止定时任务并关闭共享 HTTP Session"""
        stop_timer_thread()
        await close_shared_session()
