from __future__ import annotations

from collections.abc import Callable

import astrbot.api.message_components as Comp
from data.plugins.astrbot_plugin_wot.src.application.binding_service import (
    bind_user_name,
    player_exists,
)
from data.plugins.astrbot_plugin_wot.src.domain.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.bindings_repository import (
    read_binding_data,
)
from data.plugins.astrbot_plugin_wot.src.settings.message import (
    CheckBindMsg,
    WotBindMsg,
)


def extract_player_name(message_str: str) -> str:
    normalized = message_str.lstrip("/").strip()
    command_bind_prefix = "wot绑定 "
    if not normalized.startswith(command_bind_prefix):
        return ""
    parts = normalized.split(command_bind_prefix, maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def extract_arg_after_command(message_str: str, commands: list[str]) -> str:
    normalized = message_str.lstrip("/").strip()
    for cmd in commands:
        if normalized.startswith(cmd):
            return normalized[len(cmd) :].strip()
    return ""


def extract_at_target_id(message_chain: list) -> str:
    for item in message_chain:
        if isinstance(item, Comp.At):
            target = str(item.qq)
            if target and target != "all":
                return target
    return ""


def extract_text_after_leading_at(message_chain: list) -> str:
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


def resolve_player_name(
    send_id: str,
    message_chain: list,
    explicit_name: str | None,
) -> tuple[str | None, str | None]:
    at_target = extract_at_target_id(message_chain)
    if explicit_name:
        if at_target:
            target_name = read_binding_data(at_target)
            if not target_name:
                return None, "target_unbound"
            return target_name, None
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


def error_message(err: str) -> str:
    if err == "at_text_only":
        return "未识别到有效@，请直接输入玩家名称或@已绑定用户"
    if err == "player_not_found":
        return "玩家不存在，请检查名称是否正确"
    if err == "target_unbound":
        return "对方未绑定游戏名称，请先绑定"
    if err == "self_unbound":
        return CheckBindMsg.failed()
    return "查询失败，请稍后再试"


async def execute_bind(send_id: str, message_str: str) -> str:
    player_name = extract_player_name(message_str)
    if not player_name:
        return WotBindMsg.invalid()

    account_info: AccountInfo | None = await bind_user_name(send_id, player_name)
    if account_info:
        return WotBindMsg.success(account_info)
    return WotBindMsg.fail(player_name)


def build_basic_efficiency_query_chain(
    send_id: str,
    message_str: str,
    message_chain: list,
    commands: list[str],
    component_builder: Callable[[str, list, str | None], Comp.Plain],
    message_text: str | None = None,
) -> list[Comp.At | Comp.Plain]:
    explicit_name = extract_arg_after_command(message_text or message_str, commands)
    res = component_builder(send_id, message_chain, explicit_name)
    return [Comp.At(qq=send_id), res]


async def build_report_chain(
    send_id: str,
    message_str: str,
    message_chain: list,
    commands: list[str],
    report_fn: Callable[[str, str | None], None],
    report_component_resolver: Callable[
        [str, list, str | None, Callable[[str, str | None], None]],
        object,
    ],
    message_text: str | None = None,
) -> list[Comp.At | Comp.Image | Comp.Plain]:
    explicit_name = extract_arg_after_command(message_text or message_str, commands)
    res = await report_component_resolver(
        send_id,
        message_chain,
        explicit_name,
        report_fn,
    )
    return [Comp.At(qq=send_id), res]
