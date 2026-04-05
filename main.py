from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from data.plugins.astrbot_plugin_wot.src.application.message_parser import (
    CommandInput,
    extract_text_after_leading_at,
)
from data.plugins.astrbot_plugin_wot.src.application.query_service import (
    build_efficiency_response,
    build_report_response,
    handle_bind_command,
)
from data.plugins.astrbot_plugin_wot.src.application.report.report_service import (
    REPORT_CONFIGS,
    query_report,
)
from data.plugins.astrbot_plugin_wot.src.application.tank_sync_service import (
    sync_all_tank_info,
)
from data.plugins.astrbot_plugin_wot.src.tasks.scheduler import start_timer_thread

EFFICIENCY_COMMANDS = ["效率", "盒子效率"]

_REPORT_HANDLERS = [
    ("query_today_report", 0),
    ("query_yesterday_report", 1),
    ("query_two_days_report", 2),
    ("query_three_days_report", 3),
    ("query_hundred_report", 4),
]


def _make_report_handler(config):
    """生成报表查询处理器"""

    async def _handler(event: AstrMessageEvent, message_text: str | None = None):
        input = CommandInput.from_event(event, config.aliases, message_text)
        chain = await build_report_response(
            input, lambda sid, name: query_report(sid, config, name)
        )
        yield event.chain_result(chain)

    return _handler


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """插件初始化：启动定时任务并尝试同步坦克数据"""
        start_timer_thread()
        try:
            result = await sync_all_tank_info()
            logger.info(f"坦克数据初始化: {result}")
        except Exception as exc:
            logger.warning(f"坦克数据初始化失败（将在后台重试）: {exc}")

    @filter.event_message_type(filter.EventMessageType.ALL)
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
        ]

        at_text = extract_text_after_leading_at(event.get_messages())
        if at_text:
            for cmds, handler in routes:
                if any(at_text.startswith(c) for c in cmds):
                    async for result in handler(event, message_text=at_text):
                        yield result
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
        async for ret in _make_report_handler(REPORT_CONFIGS[0])(event, message_text):
            yield ret

    @filter.command("昨日效率", alias={"昨日战绩"})
    async def query_yesterday_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[1])(event, message_text):
            yield ret

    @filter.command("两日效率", alias={"两日战绩"})
    async def query_two_days_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[2])(event, message_text):
            yield ret

    @filter.command("三日效率", alias={"三日战绩"})
    async def query_three_days_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[3])(event, message_text):
            yield ret

    @filter.command("百场效率", alias={"百场战绩"})
    async def query_hundred_report(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        async for ret in _make_report_handler(REPORT_CONFIGS[4])(event, message_text):
            yield ret

    @filter.command("同步坦克", alias={"更新坦克"})
    async def sync_full_tank_info(self, event: AstrMessageEvent):
        """融合官网与 WotInspector 的坦克信息"""
        result = await sync_all_tank_info()
        yield event.plain_result(result)

    async def terminate(self):
        """插件销毁时的清理逻辑"""
