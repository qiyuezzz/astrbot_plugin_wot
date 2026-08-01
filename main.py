from __future__ import annotations

import re
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.session_waiter import SessionController, SessionFilter, session_waiter
from data.plugins.astrbot_plugin_wot.src.application.message_parser import (
    CommandInput,
    extract_text_after_leading_at,
)
from data.plugins.astrbot_plugin_wot.src.application.query_service import (
    build_career_response,
    build_efficiency_response,
    build_garage_response,
    build_moe_response,
    build_report_response,
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
from data.plugins.astrbot_plugin_wot.src.application.report.text_report_renderer import (
    generate_text_report,
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
    invalid_prompt_sent = False

    @session_waiter(timeout=60)
    async def _selection_waiter(
        controller: SessionController,
        waiting_event: AstrMessageEvent,
    ) -> None:
        nonlocal invalid_prompt_sent
        try:
            choice = waiting_event.message_str.strip().lstrip("/").strip()
            if choice in {"取消", "退出"}:
                await waiting_event.send(waiting_event.plain_result("已取消坦克查询。"))
                controller.stop()
                return
            if not choice.isdigit():
                if not invalid_prompt_sent:
                    await waiting_event.send(
                        waiting_event.plain_result(
                            "请输入列表中的编号，或回复“取消”退出。"
                        )
                    )
                    invalid_prompt_sent = True
                controller.keep(timeout=60, reset_timeout=False)
                return
            index = int(choice) - 1
            if not 0 <= index < len(candidates):
                if not invalid_prompt_sent:
                    await waiting_event.send(
                        waiting_event.plain_result(
                            f"编号无效，请输入 1-{len(candidates)}，或回复“取消”退出。"
                        )
                    )
                    invalid_prompt_sent = True
                controller.keep(timeout=60, reset_timeout=False)
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
            (["坦克生涯"], self.query_career),
            (["坦克信息"], self.query_tank_info),
            (["坦克对比"], self.query_tank_comparison),
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

    @filter.command("坦克生涯")
    async def query_career(self, event: AstrMessageEvent, message_text: str | None = None):
        """查询玩家官网标准模式生涯统计"""
        input = CommandInput.from_event(event, ["坦克生涯"], message_text)
        chain = await build_career_response(input)
        yield event.chain_result(chain)

    @filter.command("坦克信息")
    async def query_tank_info(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询坦克百科属性"""
        input = CommandInput.from_event(event, ["坦克信息"], message_text)
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

    @filter.command("坦克对比")
    async def query_tank_comparison(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """对比两辆坦克的主要属性"""
        input = CommandInput.from_event(event, ["坦克对比"], message_text)
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
        help_text = (
            "使用规则\n"
            "[] 内参数可选；参数可单独或组合使用，顺序不限。\n"
            "省略玩家名称时使用已绑定玩家；命令支持带 / 和不带 / 两种方式。\n"
            "官方 QQ 机器人需要先 @机器人，再输入命令。\n\n"
            "玩家查询\n"
            "wot绑定 玩家名称：绑定当前 QQ 账号\n"
            "效率 / 盒子效率 [玩家名称]：查询基础效率\n"
            "坦克生涯 [玩家名称]：查询官网生涯数据与坦克分布\n"
            "示例：效率、效率 玩家名称、坦克生涯 玩家名称\n\n"
            "战绩报表\n"
            "今日效率 / 今日战绩、昨日效率 / 昨日战绩、两日效率 / 两日战绩、三日效率 / 三日战绩、百场效率 / 百场战绩 [玩家名称]\n"
            "分别查询今日、昨日、近两日、近三日或最近百场战绩；用法相同。\n"
            "示例：今日战绩、三日效率 玩家名称、百场战绩\n\n"
            "车库\n"
            "车库 [玩家名称] [等级] [类型]：查询并筛选玩家车辆战绩\n"
            "玩家名称、等级、类型均可选且顺序不限；仅统计 7-11 级，展示前 30 辆。\n"
            "示例：车库、车库 10级、车库 重坦、车库 玩家名 10级 重坦\n\n"
            "坦克百科\n"
            "坦克信息 [坦克名称]：查询坦克百科属性\n"
            "坦克对比 [坦克A] [坦克B]：对比两辆坦克的属性\n"
            "环线 / 标伤 坦克名称：查询一环、二环、三环标伤阈值\n"
            "两辆坦克名称之间需保留空格，不支持无空格连写；多结果时回复编号选择。\n"
            "示例：坦克信息 59式、坦克对比 59式 查狄伦 25t、标伤 野牛\n\n"
            "管理与其他\n"
            "同步坦克 / 更新坦克：同步坦克资料\n"
            "帮助：显示本帮助图片"
        )
        try:
            image_url = await generate_text_report(
                event.get_sender_id(),
                "坦克世界插件帮助",
                help_text,
                layout="help",
                width=2200,
            )
            if not image_url:
                raise ValueError("生成帮助图片失败")
        except Exception as exc:
            logger.exception(f"生成帮助图片失败（用户={event.get_sender_id()}）：{exc}")
            yield event.chain_result(
                [Comp.At(qq=event.get_sender_id()), Comp.Plain("帮助图片生成失败，请稍后再试")]
            )
            return
        yield event.chain_result(
            [Comp.At(qq=event.get_sender_id()), Comp.Image.fromURL(image_url)]
        )

    async def terminate(self):
        """插件销毁时的清理逻辑：停止定时任务并关闭共享 HTTP Session"""
        stop_timer_thread()
        await close_shared_session()
