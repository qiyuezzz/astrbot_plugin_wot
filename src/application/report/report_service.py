from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.application.report.report_query_cache import (
    get_cached_report_context,
    make_report_context_cache_key,
    run_with_inflight_dedupe,
    set_cached_report_context,
)
from data.plugins.astrbot_plugin_wot.src.application.report.report_renderer import (
    generate_report,
)
from data.plugins.astrbot_plugin_wot.src.application.report.report_summary_service import (
    get_detail_record_list,
    get_final_summary,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FinalSummary,
    WotRenderContext,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.gateways.wot_box_gateway import (
    WotBoxService,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.gateways.wot_box_records_gateway import (
    get_arena_list_by_days,
    get_arena_list_by_times,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.bindings_repository import (
    read_binding_data,
)


@dataclass(frozen=True)
class ReportConfig:
    """报表命令配置"""

    aliases: list[str]
    title: str
    func: Callable
    param: int


REPORT_CONFIGS = [
    ReportConfig(["今日效率", "今日战绩"], "今日战绩", get_arena_list_by_days, 1),
    ReportConfig(["昨日效率", "昨日战绩"], "昨日战绩", get_arena_list_by_days, -1),
    ReportConfig(["两日效率", "两日战绩"], "两日战绩", get_arena_list_by_days, 2),
    ReportConfig(["三日效率", "三日战绩"], "三日战绩", get_arena_list_by_days, 3),
    ReportConfig(["百场效率", "百场战绩"], "百场战绩", get_arena_list_by_times, 100),
]


async def query_report(
    send_id: str,
    config: ReportConfig,
    player_name_override: str | None = None,
) -> None:
    """根据配置生成对应报表"""
    await _generate_report_data(
        send_id=send_id,
        title=config.title,
        get_arena_list_func=config.func,
        func_param=config.param,
        player_name_override=player_name_override,
    )


async def _generate_report_data(
    send_id: str,
    title: str,
    get_arena_list_func: Callable,
    func_param: int,
    player_name_override: str | None = None,
) -> None:
    """解析目标玩家，构建渲染上下文并生成报表"""
    try:
        player_name = player_name_override or read_binding_data(send_id)
        if not player_name:
            raise ValueError(f"用户{send_id}未绑定玩家名称，无法获取战绩数据")

        wot_render_context = await build_wot_render_context(
            player_name=player_name,
            title=title,
            get_arena_list_func=get_arena_list_func,
            func_param=func_param,
        )
        generate_report(send_id, wot_render_context)
    except Exception as exc:
        logger.error(f"获取{title}数据失败（用户{send_id}）：{exc}", exc_info=True)
        raise


async def build_wot_render_context(
    player_name: str,
    title: str,
    get_arena_list_func: Callable,
    func_param: int,
) -> WotRenderContext:
    cache_key = make_report_context_cache_key(
        player_name=player_name,
        title=title,
        get_arena_list_func=get_arena_list_func,
        func_param=func_param,
    )
    if cached := get_cached_report_context(cache_key):
        logger.info(f"命中报表缓存：{cache_key}")
        return cached

    async def _build_uncached() -> WotRenderContext:
        wot_box_gateway = WotBoxService()
        player_stats = await wot_box_gateway.get_player_stats(player_name)
        if not player_stats or len(player_stats) < 2:
            raise ValueError(f"获取玩家{player_name}基础统计信息失败，返回数据异常")

        arena_list = await get_arena_list_func(player_name, func_param)
        if arena_list:
            detail_arena_list = await get_detail_record_list(player_name, arena_list)
            if detail_arena_list:
                final_summary = get_final_summary(detail_arena_list, title)
            else:
                logger.warning(f"玩家{player_name}未查询到{title}对应的详细对局数据")
                final_summary = FinalSummary(summary_title=title)
        else:
            logger.warning(f"玩家{player_name}未查询到{title}对应的对局数据")
            final_summary = FinalSummary(summary_title=title)

        wot_render_context = WotRenderContext(
            player_stats=player_stats[0],
            frequent_tank=player_stats[1],
            final_summary=final_summary,
        )
        logger.info(f"成功生成{title}渲染上下文：{wot_render_context}")
        set_cached_report_context(cache_key, wot_render_context)
        return wot_render_context

    return await run_with_inflight_dedupe(cache_key, _build_uncached)
