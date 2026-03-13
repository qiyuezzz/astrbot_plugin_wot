from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from data.plugins.astrbot_plugin_wot.src.application.command_query_service import (
    build_basic_efficiency_text_component,
    resolve_report_component,
)
from data.plugins.astrbot_plugin_wot.src.application.command_service import (
    build_basic_efficiency_query_chain,
    build_report_chain,
    execute_bind,
)


async def handle_bind_command(event: AstrMessageEvent) -> AsyncIterator[dict]:
    """Handle player binding and yield AstrBot results."""
    message_chain = event.get_messages()
    logger.info(message_chain)
    msg = await execute_bind(event.get_sender_id(), event.message_str)
    yield event.plain_result(msg)


async def handle_basic_efficiency_query_command(
    event: AstrMessageEvent,
    commands: list[str],
    component_builder: Callable[[str, list, str | None], Comp.Plain] = (
        build_basic_efficiency_text_component
    ),
    message_text: str | None = None,
) -> AsyncIterator[list[Comp.At | Comp.Plain]]:
    """Build the plain-text efficiency response."""
    send_id = event.get_sender_id()
    message_chain = event.get_messages()
    logger.info(message_chain)
    chain = build_basic_efficiency_query_chain(
        send_id=send_id,
        message_str=event.message_str,
        message_chain=message_chain,
        commands=commands,
        component_builder=component_builder,
        message_text=message_text,
    )
    yield event.chain_result(chain)


async def handle_report_command(
    event: AstrMessageEvent,
    commands: list[str],
    report_fn: Callable[[str, str | None], None],
    report_component_resolver: Callable[
        [str, list, str | None, Callable[[str, str | None], None]],
        object,
    ] = resolve_report_component,
    message_text: str | None = None,
) -> AsyncIterator[list[Comp.At | Comp.Image | Comp.Plain]]:
    """Build the image/text report response."""
    send_id = event.get_sender_id()
    message_chain = event.get_messages()
    logger.info(message_chain)
    chain = await build_report_chain(
        send_id=send_id,
        message_str=event.message_str,
        message_chain=message_chain,
        commands=commands,
        report_fn=report_fn,
        report_component_resolver=report_component_resolver,
        message_text=message_text,
    )
    yield event.chain_result(chain)
