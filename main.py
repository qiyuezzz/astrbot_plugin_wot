import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from data.plugins.astrbot_plugin_wot.src.application.bind_usecase import bind_user_name
from data.plugins.astrbot_plugin_wot.src.application.report_usecase import (
    get_record_hundred,
    get_record_three_days,
    get_record_today,
    get_record_two_days,
    get_record_yesterday,
)
from data.plugins.astrbot_plugin_wot.src.application.tank_sync_usecase import (
    sync_all_tank_info,
)
from data.plugins.astrbot_plugin_wot.src.config.constants import report_dir_path
from data.plugins.astrbot_plugin_wot.src.config.message import CheckBindMsg, WotBindMsg
from data.plugins.astrbot_plugin_wot.src.domain.models.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.infrastructure.storage.bindings_repo import (
    read_binding_data,
)
from data.plugins.astrbot_plugin_wot.src.services.bindings_service import player_exists
from data.plugins.astrbot_plugin_wot.src.tasks.scheduler import start_timer_thread


def _extract_player_name(message_str: str) -> str:
    normalized = message_str.lstrip("/").strip()
    command_bind_prefix = "wot绑定 "
    if not normalized.startswith(command_bind_prefix):
        return ""
    parts = normalized.split(command_bind_prefix, maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _extract_arg_after_command(message_str: str, commands: list[str]) -> str:
    normalized = message_str.lstrip("/").strip()
    for cmd in commands:
        if normalized.startswith(cmd):
            return normalized[len(cmd) :].strip()
    return ""


def _extract_at_target_id(message_chain: list) -> str:
    for item in message_chain:
        if isinstance(item, Comp.At):
            target = str(item.qq)
            if target and target != "all":
                return target
    return ""


def _extract_text_after_leading_at(message_chain: list) -> str:
    parts: list[str] = []
    seen_at = False
    for item in message_chain:
        if isinstance(item, Comp.At):
            if not seen_at:
                seen_at = True
                continue
        if not seen_at:
            continue
        if isinstance(item, Comp.Plain):
            parts.append(item.text)
    return "".join(parts).strip()


def _resolve_player_name(
    send_id: str,
    message_chain: list,
    explicit_name: str | None,
) -> tuple[str | None, str | None]:
    at_target = _extract_at_target_id(message_chain)
    if explicit_name:
        # 如果带参数且有真实 @ 目标，则优先按 @ 目标查询
        if at_target:
            target_name = read_binding_data(at_target)
            if not target_name:
                return None, "target_unbound"
            return target_name, None
        # 纯文本 @xxx 但无 @ 组件，提示用正确的 @ 或直接输入玩家名
        if explicit_name.startswith("@"):
            return None, "at_text_only"
        if not player_exists(explicit_name):
            return None, "player_not_found"
        return explicit_name, None

    if at_target:
        target_name = read_binding_data(at_target)
        if not target_name:
            return None, "target_unbound"
        return target_name, None

    self_name = read_binding_data(send_id)
    if not self_name:
        return None, "self_unbound"
    return self_name, None


def _error_message(err: str) -> str:
    if err == "at_text_only":
        return "未识别到有效@，请直接输入玩家名称或@已绑定用户"
    if err == "player_not_found":
        return "玩家不存在，请检查名称是否正确"
    if err == "target_unbound":
        return "对方未绑定游戏名称，请先绑定"
    if err == "self_unbound":
        return CheckBindMsg.failed()
    return "查询失败，请稍后再试"


def _build_report_result(send_id: str, report_fn, player_name: str | None = None):
    try:
        report_fn(send_id, player_name)
        return Comp.Image.fromFileSystem(str(report_dir_path / f"{send_id}.png"))
    except Exception as exc:
        logger.exception(f"Failed to build report for {send_id}: {exc}")
        return Comp.Plain("查询失败，请稍后再试")


def _resolve_report_component(
    send_id: str,
    message_chain: list,
    explicit_name: str | None,
    report_fn,
) -> Comp.Image | Comp.Plain:
    player_name, err = _resolve_player_name(send_id, message_chain, explicit_name)
    if err:
        return Comp.Plain(_error_message(err))
    return _build_report_result(send_id, report_fn, player_name)


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        start_timer_thread()

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def command_router(self, event: AstrMessageEvent):
        """监听所有"""
        message_str = event.message_str.strip()
        if message_str.startswith("/"):
            return
        routes = [
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
        # 匹配触发词（允许不带/和带参数）
        for commands, handler in routes:
            if message_str.startswith(commands):
                # 因为 handler 里面有 yield，所以需要异步迭代
                async for result in handler(event):
                    yield result
                return  # 触发后直接结束

    @filter.command("wot绑定")
    async def wot_bind_player_name(self, event: AstrMessageEvent):
        """绑定玩家游戏名称"""
        message_chain = event.get_messages()
        player_name = _extract_player_name(event.message_str)
        logger.info(message_chain)
        if not player_name:
            yield event.plain_result(WotBindMsg.invalid())
            return
        account_info: AccountInfo | None = await bind_user_name(
            event.get_sender_id(), player_name
        )
        if account_info:
            msg = WotBindMsg.success(account_info)
        else:
            msg = WotBindMsg.fail(player_name)
        yield event.plain_result(msg)

    @filter.command("今日效率", alias={"今日战绩"})
    async def get_today_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询今日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        explicit_name = _extract_arg_after_command(
            message_text or event.message_str, ["今日效率", "今日战绩"]
        )
        res = _resolve_report_component(
            send_id, message_chain, explicit_name, get_record_today
        )
        chain: list[Comp.At | Comp.Image | Comp.Plain] = [Comp.At(qq=send_id), res]
        yield event.chain_result(chain)

    @filter.command("昨日效率", alias={"昨日战绩"})
    async def get_yesterday_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询昨日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        explicit_name = _extract_arg_after_command(
            message_text or event.message_str, ["昨日效率", "昨日战绩"]
        )
        res = _resolve_report_component(
            send_id, message_chain, explicit_name, get_record_yesterday
        )
        chain: list[Comp.At | Comp.Image | Comp.Plain] = [Comp.At(qq=send_id), res]
        yield event.chain_result(chain)

    @filter.command("两日效率", alias={"两日战绩"})
    async def get_two_days_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询两日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        explicit_name = _extract_arg_after_command(
            message_text or event.message_str, ["两日效率", "两日战绩"]
        )
        res = _resolve_report_component(
            send_id, message_chain, explicit_name, get_record_two_days
        )
        chain: list[Comp.At | Comp.Image | Comp.Plain] = [Comp.At(qq=send_id), res]
        yield event.chain_result(chain)

    @filter.command("三日效率", alias={"三日战绩"})
    async def get_three_days_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询三日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        explicit_name = _extract_arg_after_command(
            message_text or event.message_str, ["三日效率", "三日战绩"]
        )
        res = _resolve_report_component(
            send_id, message_chain, explicit_name, get_record_three_days
        )
        chain: list[Comp.At | Comp.Image | Comp.Plain] = [Comp.At(qq=send_id), res]
        yield event.chain_result(chain)

    @filter.command("百场效率", alias={"百场战绩"})
    async def get_hundred_matches_performance(
        self, event: AstrMessageEvent, message_text: str | None = None
    ):
        """查询百场效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        explicit_name = _extract_arg_after_command(
            message_text or event.message_str, ["百场效率", "百场战绩"]
        )
        res = _resolve_report_component(
            send_id, message_chain, explicit_name, get_record_hundred
        )
        chain: list[Comp.At | Comp.Image | Comp.Plain] = [Comp.At(qq=send_id), res]
        yield event.chain_result(chain)

    @filter.command("同步坦克", alias={"更新坦克"})
    async def sync_full_tank_info(self, event: AstrMessageEvent):
        """融合官网与 WotInspector 的坦克信息"""
        message_chain = event.get_messages()
        logger.info(message_chain)
        result = sync_all_tank_info()
        yield event.plain_result(result)

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
