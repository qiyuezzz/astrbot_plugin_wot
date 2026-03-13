from __future__ import annotations

from collections.abc import Callable

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
from data.plugins.astrbot_plugin_wot.src.domain.report import WotRenderContext, FinalSummary

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


def get_report_data_by_days(
    send_id: str,
    days: int,
    title: str,
    player_name_override: str | None = None,
) -> None:
    """Generate a report for the latest N days."""
    _generate_report_data(
        send_id=send_id,
        title=title,
        get_arena_list_func=get_arena_list_by_days,
        func_param=days,
        player_name_override=player_name_override,
    )


def get_report_data_by_times(
    send_id: str,
    times: int,
    title: str,
    player_name_override: str | None = None,
) -> None:
    """Generate a report for the latest N battles."""
    _generate_report_data(
        send_id=send_id,
        title=title,
        get_arena_list_func=get_arena_list_by_times,
        func_param=times,
        player_name_override=player_name_override,
    )


def get_record_today(send_id: str, player_name_override: str | None = None) -> None:
    get_report_data_by_days(
        send_id=send_id,
        days=1,
        title="今日战绩",
        player_name_override=player_name_override,
    )


def get_record_yesterday(send_id: str, player_name_override: str | None = None) -> None:
    get_report_data_by_days(
        send_id=send_id,
        days=-1,
        title="昨日战绩",
        player_name_override=player_name_override,
    )


def get_record_two_days(send_id: str, player_name_override: str | None = None) -> None:
    get_report_data_by_days(
        send_id=send_id,
        days=2,
        title="两日战绩",
        player_name_override=player_name_override,
    )


def get_record_three_days(
    send_id: str, player_name_override: str | None = None
) -> None:
    get_report_data_by_days(
        send_id=send_id,
        days=3,
        title="三日战绩",
        player_name_override=player_name_override,
    )


def get_record_hundred(send_id: str, player_name_override: str | None = None) -> None:
    get_report_data_by_times(
        send_id=send_id,
        times=100,
        title="百场战绩",
        player_name_override=player_name_override,
    )


def _generate_report_data(
    send_id: str,
    title: str,
    get_arena_list_func: Callable[[str, int], list],
    func_param: int,
    player_name_override: str | None = None,
) -> None:
    """Resolve target player, build render context, and generate report output."""
    try:
        player_name = player_name_override or read_binding_data(send_id)
        if not player_name:
            raise ValueError(f"用户{send_id}未绑定玩家名称，无法获取战绩数据")

        wot_render_context = build_wot_render_context(
            player_name=player_name,
            title=title,
            get_arena_list_func=get_arena_list_func,
            func_param=func_param,
        )
        generate_report(send_id, wot_render_context)
    except Exception as exc:
        logger.error(f"获取{title}数据失败（用户{send_id}）：{exc}", exc_info=True)
        raise


def build_wot_render_context(
    player_name: str,
    title: str,
    get_arena_list_func,
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

    def _build_uncached() -> WotRenderContext:
        wot_box_gateway = WotBoxService()
        player_stats = wot_box_gateway.get_player_stats(player_name)
        if not player_stats or len(player_stats) < 2:
            raise ValueError(f"获取玩家{player_name}基础统计信息失败，返回数据异常")

        arena_list = get_arena_list_func(player_name, func_param)
        if arena_list:
            detail_arena_list = get_detail_record_list(player_name, arena_list)
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

    return run_with_inflight_dedupe(cache_key, _build_uncached)
