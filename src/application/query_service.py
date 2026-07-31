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
    parse_garage_query,
)
from data.plugins.astrbot_plugin_wot.src.application.message_parser import CommandInput
from data.plugins.astrbot_plugin_wot.src.application.moe_service import build_moe_text
from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
    error_message,
    resolve_player_account,
    resolve_player_name,
)
from data.plugins.astrbot_plugin_wot.src.application.report.text_report_renderer import (
    generate_text_report,
)
from data.plugins.astrbot_plugin_wot.src.application.single_vehicle_service import (
    build_single_vehicle_text,
    parse_single_vehicle_query,
)
from data.plugins.astrbot_plugin_wot.src.application.tank_info_service import (
    build_tank_comparison_report,
    build_tank_info_report,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import Tank
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    find_tank_candidates_by_name,
)

MessageChain = list[Comp.BaseMessageComponent]


def find_tank_info_candidates(tank_name: str) -> list[Tank]:
    """为坦克百科返回精确和模糊匹配的全部候选。"""
    return find_tank_candidates_by_name(tank_name)


def format_tank_info_candidates(tank_name: str, candidates: list[Tank]) -> str:
    """构建坦克候选列表，供会话控制器等待编号选择。"""
    lines = [f"坦克名称「{tank_name}」匹配到多个结果，请回复编号选择："]
    for index, tank in enumerate(candidates, start=1):
        tags = f"{tank.tier}级 · {tank.nation.display_name} · {tank.type.display_name}"
        if tank.role.display_name not in ("", "通用/无定位"):
            tags += f" · {tank.role.display_name}"
        lines.append(f"{index}. {tank.name}（{tags}）")
    lines.append("回复编号继续查询，回复“取消”退出（60秒内有效）")
    return "\n".join(lines)


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
    query = parse_garage_query(input.explicit_name)
    if query.error:
        return [Comp.At(qq=input.send_id), Comp.Plain(query.error)]
    player_name, account_id, err = await resolve_player_account(
        input.send_id, input.message_chain, query.player_name, input.self_id
    )
    if err:
        return _error_chain(input.send_id, err)
    try:
        text = await build_garage_text(
            player_name, account_id, query.tier, query.tank_type
        )
        image_url = await generate_text_report(
            input.send_id, "车库查询", text, layout="garage"
        )
        if not image_url:
            raise ValueError("生成车库图片失败")
    except Exception as exc:
        logger.exception(
            f"车库查询失败 (玩家={player_name}, 用户={input.send_id}): {exc}"
        )
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Image.fromURL(image_url)]


async def build_single_vehicle_response(input: CommandInput) -> MessageChain:
    """构建玩家单车详情响应。"""
    query = parse_single_vehicle_query(input.explicit_name)
    if not query:
        return [
            Comp.At(qq=input.send_id),
            Comp.Plain("请提供坦克名称，例如：单车 59式"),
        ]
    player_name, account_id, err = await resolve_player_account(
        input.send_id, input.message_chain, query.player_name, input.self_id
    )
    if err:
        return _error_chain(input.send_id, err)
    try:
        text = await build_single_vehicle_text(player_name, account_id, query.tank_name)
        image_url = await generate_text_report(input.send_id, "单车详情", text)
        if not image_url:
            raise ValueError("生成单车详情图片失败")
    except Exception as exc:
        logger.exception(
            f"单车查询失败 (玩家={player_name}, 坦克={query.tank_name}, 用户={input.send_id}): {exc}"
        )
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Image.fromURL(image_url)]


async def build_tank_info_response(input: CommandInput) -> MessageChain:
    """构建坦克百科响应。"""
    if not input.explicit_name:
        return [
            Comp.At(qq=input.send_id),
            Comp.Plain("请提供坦克名称，例如：坦克 59式"),
        ]
    try:
        report = await build_tank_info_report(input.explicit_name)
        image_url = await generate_text_report(
            input.send_id,
            "坦克信息查询",
            report.text,
            layout="tank_detail",
            hero_images=report.hero_images,
        )
        if not image_url:
            raise ValueError("生成坦克百科图片失败")
    except Exception as exc:
        logger.exception(f"坦克百科查询失败 (坦克={input.explicit_name}): {exc}")
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Image.fromURL(image_url)]


async def build_tank_comparison_response(input: CommandInput) -> MessageChain:
    """构建坦克对比响应。"""
    if not input.explicit_name:
        return [
            Comp.At(qq=input.send_id),
            Comp.Plain("请提供两辆坦克，例如：对比 59式 和 查狄伦 25t"),
        ]
    try:
        report = await build_tank_comparison_report(input.explicit_name)
        image_url = await generate_text_report(
            input.send_id,
            "坦克对比",
            report.text,
            layout="tank_compare",
            hero_images=report.hero_images,
        )
        if not image_url:
            raise ValueError("生成坦克对比图片失败")
    except Exception as exc:
        logger.exception(f"坦克对比失败 (参数={input.explicit_name}): {exc}")
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Image.fromURL(image_url)]


async def build_moe_response(input: CommandInput) -> MessageChain:
    """构建环线标伤查询的响应消息链"""
    if not input.explicit_name:
        return [
            Comp.At(qq=input.send_id),
            Comp.Plain("请提供坦克名称，例如：环线 鞭蛇"),
        ]
    try:
        text = await build_moe_text(input.explicit_name)
        image_url = await generate_text_report(
            input.send_id, "环线标伤", text, layout="moe"
        )
        if not image_url:
            raise ValueError("生成环线图片失败")
    except Exception as exc:
        logger.exception(f"环线查询失败 (坦克={input.explicit_name}): {exc}")
        return _error_chain(input.send_id, "查询失败，请稍后再试")
    return [Comp.At(qq=input.send_id), Comp.Image.fromURL(image_url)]
