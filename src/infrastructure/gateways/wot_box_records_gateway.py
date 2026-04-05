from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    RecordsBasic,
    RecordsDetail,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_box_api import (
    fetch_arena_page,
    fetch_battle_detail,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    HttpClient,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.parsers.wot_box_records_parser import (
    parse_arena_list,
    parse_battle_detail,
)


async def _paginated_fetch(
    player_name: str,
    should_include: Callable[[RecordsBasic], bool],
    should_stop: Callable[[RecordsBasic], bool] | None = None,
    limit: int | None = None,
    *,
    http: HttpClient,
) -> list[RecordsBasic]:
    """通用分页获取战斗记录

    Args:
        player_name: 玩家名称
        should_include: 判断单条记录是否应包含的回调
        should_stop: 判断是否应停止翻页的回调（可选）
        limit: 最大返回数量限制（可选）
        http: 共享的 HTTP 客户端
    """
    all_records: list[RecordsBasic] = []
    seen_arena_ids: set[str] = set()
    page = 1

    while True:
        try:
            raw_json = await fetch_arena_page(player_name, page, http=http)
            raw_arenas = raw_json.get("data", {}).get("arenas", [])
            if not raw_arenas:
                break

            page_records = parse_arena_list(raw_json)
            if not page_records:
                page += 1
                await asyncio.sleep(0.2)
                continue

            page_has_new = False
            for record in page_records:
                if record.arena_id in seen_arena_ids:
                    continue
                if should_stop and should_stop(record):
                    return all_records
                if not should_include(record):
                    continue

                seen_arena_ids.add(record.arena_id)
                all_records.append(record)
                page_has_new = True
                if limit is not None and len(all_records) >= limit:
                    return all_records[:limit]

            if not page_has_new:
                break
            page += 1
            await asyncio.sleep(0.2)
        except Exception as exc:
            logger.error(f"Failed to fetch page {page}: {exc}")
            if page > 2:
                break
            page += 1
            await asyncio.sleep(0.5)

    return all_records


async def get_arena_list_by_times(player_name: str, times: int) -> list[RecordsBasic]:
    """获取最近N场标准战斗记录"""
    if times <= 0:
        return []

    async with HttpClient() as http:
        return await _paginated_fetch(
            player_name,
            should_include=lambda _: True,
            limit=times,
            http=http,
        )


async def get_arena_list_by_days(player_name: str, days: int = 1) -> list[RecordsBasic]:
    """获取N天内的标准战斗记录"""
    current_time = datetime.now()

    if days > 0:
        end_ts = int(current_time.timestamp())
        start_time = current_time - timedelta(days=days - 1)
    else:
        end_ts = int(
            current_time.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )
        start_time = current_time - timedelta(days=abs(days))

    start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(start_time.timestamp())

    def _should_include(record: RecordsBasic) -> bool:
        record_ts = int(record.start_time)
        return record_ts <= end_ts

    def _should_stop(record: RecordsBasic) -> bool:
        record_ts = int(record.start_time)
        if record_ts < start_ts:
            logger.info(f"发现早于 {days} 天的记录，停止翻页")
            return True
        return False

    async with HttpClient() as http:
        records = await _paginated_fetch(
            player_name,
            should_include=_should_include,
            should_stop=_should_stop,
            http=http,
        )
    records.sort(key=lambda x: int(x.start_time), reverse=True)
    return records


async def get_detail_record_single(
    player_name: str, arena: RecordsBasic, *, http: HttpClient
) -> RecordsDetail | None:
    """获取并解析单场战斗详情"""
    raw_text = await fetch_battle_detail(player_name, arena.arena_id, http=http)
    return parse_battle_detail(raw_text, arena)
