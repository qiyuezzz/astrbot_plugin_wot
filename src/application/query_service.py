from __future__ import annotations

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from data.plugins.astrbot_plugin_wot.src.application.efficiency_service import (
    get_basic_efficiency_text,
)
from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
    error_message,
    resolve_player_name,
)
from data.plugins.astrbot_plugin_wot.src.application.message_parser import CommandInput
from data.plugins.astrbot_plugin_wot.src.settings.constants import report_dir_path


async def handle_bind_command(event: AstrMessageEvent):
    """处理玩家绑定命令"""
    from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
        execute_bind,
    )

    msg = await execute_bind(event.get_sender_id(), event.message_str)
    return event.plain_result(msg)


def _error_chain(send_id: str, err: str) -> list[Comp.At | Comp.Plain]:
    """构建错误响应消息链"""
    return [Comp.At(qq=send_id), Comp.Plain(error_message(err))]


async def _with_player(
    input: CommandInput,
    fn: Callable[[str], Coroutine[Any, Any, list[Comp.At | Comp.Plain | Comp.Image]]],
    fallback_msg: str = "查询失败，请稍后再试",
) -> list[Comp.At | Comp.Image | Comp.Plain]:
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


async def build_efficiency_response(input: CommandInput) -> list[Comp.At | Comp.Plain]:
    """构建效率文本查询的响应消息链"""

    async def _query(name: str) -> list[Comp.At | Comp.Plain]:
        text = await get_basic_efficiency_text(name)
        return [Comp.At(qq=input.send_id), Comp.Plain(text)]

    return await _with_player(input, _query)


async def build_report_response(
    input: CommandInput, report_fn: Callable[[str, str | None], Coroutine[Any, Any, None]]
) -> list[Comp.At | Comp.Image | Comp.Plain]:
    """构建报表图片查询的响应消息链"""

    async def _query(name: str) -> list[Comp.At | Comp.Image]:
        await report_fn(input.send_id, name)
        return [
            Comp.At(qq=input.send_id),
            Comp.Image.fromFileSystem(
                str(Path(report_dir_path) / f"{input.send_id}.png")
            ),
        ]

    return await _with_player(input, _query)
