import asyncio

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from data.plugins.astrbot_plugin_wot.src.application.command_handlers import (
    handle_basic_efficiency_query_command,
    handle_bind_command,
    handle_report_command,
)
from data.plugins.astrbot_plugin_wot.src.application.command_query_service import (
    build_basic_efficiency_text_component,
    resolve_report_component,
)
from data.plugins.astrbot_plugin_wot.src.application.command_service import (
    extract_arg_after_command,
    extract_player_name,
    extract_text_after_leading_at,
    resolve_player_name,
)
from data.plugins.astrbot_plugin_wot.src.application.report.report_service import (
    get_record_hundred,
    get_record_three_days,
    get_record_today,
    get_record_two_days,
    get_record_yesterday,
)
from data.plugins.astrbot_plugin_wot.src.application.tank_sync_service import (
    sync_all_tank_info,
)
from data.plugins.astrbot_plugin_wot.src.jobs.scheduler import start_timer_thread

_extract_player_name = extract_player_name
_extract_arg_after_command = extract_arg_after_command
_extract_text_after_leading_at = extract_text_after_leading_at
_resolve_player_name = resolve_player_name
_resolve_report_component = resolve_report_component
_build_basic_efficiency_text_component = build_basic_efficiency_text_component


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        start_timer_thread()
        await asyncio.to_thread(sync_all_tank_info)

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def command_router(self, event: AstrMessageEvent):
        """监听所有"""
        message_str = event.message_str.strip()
        routes = [
            (("效率", "盒子效率"), self.query_basic_efficiency),
            (("今日效率", "今日战绩"), self.get_today_performance),
            (("昨日效率", "昨日战绩"), self.get_yesterday_performance),
            (("两日效率", "两日战绩"), self.get_two_days_performance),
            (("三日效率", "三日战绩"), self.get_three_days_performance),
            (("百场效率", "百场战绩"), self.get_hundred_matches_performance),
        ]
        # 支持：@某人 + 命令
        at_followed_text = _extract_text_after_leading_at(event.get_messages())
        if at_followed_text:
            for commands, handler in routes:
                if at_followed_text.startswith(commands):
                    async for result in handler(event, message_text=at_followed_text):
                        yield result
                    return
        # 匹配触发词（必须命令和参数之间有分隔）
        for commands, handler in routes:
            for cmd in commands:
                if message_str.startswith(cmd):
                    # 要求命令后要么结束（查询自己），要么是空格分隔
                    if len(message_str) == len(cmd) or message_str[len(cmd)].isspace():
                        # 因为 handler 里面有 yield，所以需要异步迭代
                        async for result in handler(event):
                            yield result
                        return  # 触发后直接结束

    @filter.command("wot绑定")
    async def wot_bind_player_name(self, event: AstrMessageEvent):
        """绑定玩家游戏名称"""
        async for result in handle_bind_command(event):
            yield result

    @filter.command("效率", alias={"盒子效率"})
    async def query_basic_efficiency(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """只查询盒子页面并返回玩家基础效率数据（文本）"""
        async for result in handle_basic_efficiency_query_command(
            event,
            ["效率", "盒子效率"],
            component_builder=_build_basic_efficiency_text_component,
            message_text=message_text,
        ):
            yield result

    @filter.command("今日效率", alias={"今日战绩"})
    async def get_today_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询今日效率"""
        async for result in handle_report_command(
            event,
            ["今日效率", "今日战绩"],
            get_record_today,
            report_component_resolver=_resolve_report_component,
            message_text=message_text,
        ):
            yield result

    @filter.command("昨日效率", alias={"昨日战绩"})
    async def get_yesterday_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询昨日效率"""
        async for result in handle_report_command(
            event,
            ["昨日效率", "昨日战绩"],
            get_record_yesterday,
            report_component_resolver=_resolve_report_component,
            message_text=message_text,
        ):
            yield result

    @filter.command("两日效率", alias={"两日战绩"})
    async def get_two_days_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询两日效率"""
        async for result in handle_report_command(
            event,
            ["两日效率", "两日战绩"],
            get_record_two_days,
            report_component_resolver=_resolve_report_component,
            message_text=message_text,
        ):
            yield result

    @filter.command("三日效率", alias={"三日战绩"})
    async def get_three_days_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询三日效率"""
        async for result in handle_report_command(
            event,
            ["三日效率", "三日战绩"],
            get_record_three_days,
            report_component_resolver=_resolve_report_component,
            message_text=message_text,
        ):
            yield result

    @filter.command("百场效率", alias={"百场战绩"})
    async def get_hundred_matches_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询百场效率"""
        async for result in handle_report_command(
            event,
            ["百场效率", "百场战绩"],
            get_record_hundred,
            report_component_resolver=_resolve_report_component,
            message_text=message_text,
        ):
            yield result

    @filter.command("同步坦克", alias={"更新坦克"})
    async def sync_full_tank_info(self, event: AstrMessageEvent):
        """融合官网与 WotInspector 的坦克信息"""
        logger.info(event.get_messages())
        result = sync_all_tank_info()
        yield event.plain_result(result)

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
