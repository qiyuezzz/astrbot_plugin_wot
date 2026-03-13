from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.application.basic_efficiency_text_service import (
    get_basic_efficiency_text,
)
from data.plugins.astrbot_plugin_wot.src.application.command_service import (
    error_message,
    resolve_player_name,
)
from data.plugins.astrbot_plugin_wot.src.settings.constants import report_dir_path


def build_basic_efficiency_text_component(
    send_id: str,
    message_chain: list,
    explicit_name: str | None,
) -> Comp.Plain:
    player_name, err = resolve_player_name(send_id, message_chain, explicit_name)
    if err:
        return Comp.Plain(error_message(err))
    try:
        return Comp.Plain(get_basic_efficiency_text(player_name))
    except Exception as exc:
        logger.exception(f"Failed to query player stats for {send_id}: {exc}")
        return Comp.Plain("查询失败，请稍后再试")


async def resolve_report_component(
    send_id: str,
    message_chain: list,
    explicit_name: str | None,
    report_fn: Callable[[str, str | None], None],
) -> Comp.Image | Comp.Plain:
    player_name, err = resolve_player_name(send_id, message_chain, explicit_name)
    if err:
        return Comp.Plain(error_message(err))
    return await build_report_result(send_id, report_fn, player_name)


async def build_report_result(
    send_id: str,
    report_fn: Callable[[str, str | None], None],
    player_name: str | None = None,
) -> Comp.Image | Comp.Plain:
    try:
        report_fn(send_id, player_name)
        return Comp.Image.fromFileSystem(str(Path(report_dir_path) / f"{send_id}.png"))
    except Exception as exc:
        logger.exception(f"Failed to build report for {send_id}: {exc}")
        return Comp.Plain("查询失败，请稍后再试")
