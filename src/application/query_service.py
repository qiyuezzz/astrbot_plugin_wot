from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from data.plugins.astrbot_plugin_wot.src.application.efficiency_service import (
    get_basic_efficiency_text,
)
from data.plugins.astrbot_plugin_wot.src.application.garage_service import (
    build_garage_text,
)
from data.plugins.astrbot_plugin_wot.src.application.message_parser import CommandInput
from data.plugins.astrbot_plugin_wot.src.application.moe_service import build_moe_text
from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
    error_message,
    resolve_player_account,
    resolve_player_name,
)

MessageChain = list[Comp.BaseMessageComponent]


async def handle_bind_command(event: AstrMessageEvent):
    """处理玩家绑定命令"""
    from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
        execute_bind,
    )

    msg = await execute_bind(event.get_sender_id(), event.message_str)
    return event.plain_result(msg)


def _error_chain(send_id: str, err: str) -> MessageChain:
    """构建错误响应消息链"""
    return [Comp.At(qq=send_id), Comp.Plain(error_message(err))]


async def _with_player(
    input: CommandInput,
    fn: Callable[[str], Coroutine[Any, Any, MessageChain]],
    fallback_msg: str = "查询失败，请稍后再试",
) -> MessageChain:
    """统一解析玩家名称并执行查询，自动处理错误"""
    player_name, err = await resolve_player_name(
        input.send_id, input.message_chain, input.explicit_name, input.self_id
    )
    if err:
        return _error_chain(input.send_id, err)
    assert player_name is not None
    try:
        return await fn(player_name)
    except Exception as exc:
        logger.exception(f"查询失败 (玩家={player_name}, 用户={input.send_id}): {exc}")
        return _error_chain(input.send_id, fallback_msg)


async def build_efficiency_response(input: CommandInput) -> MessageChain:
    """构建效率文本查询的响应消息链"""

    async def _query(name: str) -> MessageChain:
        text = await get_basic_efficiency_text(name)
        return [Comp.At(qq=input.send_id), Comp.Plain(text)]

    return await _with_player(input, _query)


async def build_report_response(
    input: CommandInput,
    report_fn: Callable[[str, str | None], Coroutine[Any, Any, str]],
) -> MessageChain:
    """构建报表图片查询的响应消息链"""

    async def _query(name: str) -> MessageChain:
        image_url = await report_fn(input.send_id, name)
        if not image_url:
            logger.error(f"生成图片失败，未返回图片 URL（用户={input.send_id}）")
            raise ValueError("生成图片失败，请稍后再试")

        logger.info(f"使用 T2I 远程图片 URL: {image_url}")
        return [
            Comp.At(qq=input.send_id),
            Comp.Image.fromURL(image_url),
        ]

    return await _with_player(input, _query)


async def build_garage_response(input: CommandInput) -> MessageChain:
    """构建车库查询的响应消息链"""
    player_name, account_id, err = await resolve_player_account(
        input.send_id, input.message_chain, input.explicit_name, input.self_id
    )
    if err:
        return _error_chain(input.send_id, err)
    try:
        text = await build_garage_text(player_name, account_id)
    except Exception as exc:
        logger.exception(
            f"车库查询失败 (玩家={player_name}, 用户={input.send_id}): {exc}"
        )
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Plain(text)]


async def build_moe_response(input: CommandInput) -> MessageChain:
    """构建环线标伤查询的响应消息链"""
    if not input.explicit_name:
        return [
            Comp.At(qq=input.send_id),
            Comp.Plain("请提供坦克名称，例如：环线 鞭蛇"),
        ]
    try:
        text = await build_moe_text(input.explicit_name)
    except Exception as exc:
        logger.exception(f"环线查询失败 (坦克={input.explicit_name}): {exc}")
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Plain(text)]
