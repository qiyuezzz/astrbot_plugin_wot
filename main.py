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


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", "v1.1.1")
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
        logger.info(
            f"插件配置已加载: enable_h2i={config.get('enable_h2i')}, full_config={config}"
        )

    async def initialize(self):
        """插件初始化：启动定时任务并同步坦克数据"""
        start_timer_thread()
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
        help_text += "管理命令：\n"
        help_text += "- 同步坦克/更新坦克：融合官网与 WotInspector 的坦克信息\n\n"
        help_text += "使用说明：\n"
        help_text += "- 所有命令都支持带/和不带/两种方式，例如：/效率 或 效率\n"
        help_text += "- 对于官方QQ机器人，需要先@机器人，然后再输入命令\n"
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁时的清理逻辑"""
        from data.plugins.astrbot_plugin_wot.src.application.report.report_renderer import (
            _h2i_renderer,
        )

        await _h2i_renderer.close()
