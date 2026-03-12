from __future__ import annotations

import time
from datetime import datetime, timedelta

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.models.report import RecordsBasic, RecordsDetail
from data.plugins.astrbot_plugin_wot.src.infrastructure.crawlers.wot_box_api import (
    fetch_arena_page,
    fetch_battle_detail,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.parsers.wot_box_records import (
    parse_arena_list,
    parse_battle_detail,
)


def get_arena_list_by_times(player_name: str, times: int) -> list[RecordsBasic]:
    """Get latest N standard battles. Not implemented."""
    return []


def get_arena_list_by_days(player_name: str, days: int = 1) -> list[RecordsBasic]:
    """Get standard battles within N days."""
    current_time = datetime.now()

    if days > 0:
        end_timestamp_threshold = int(current_time.timestamp())
        time_threshold = current_time - timedelta(days=days - 1)
    else:
        end_timestamp_threshold = int(
            current_time.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        )
        time_threshold = current_time - timedelta(days=abs(days))

    time_threshold = time_threshold.replace(hour=0, minute=0, second=0, microsecond=0)
    start_timestamp_threshold = int(time_threshold.timestamp())

    all_valid_records: list[RecordsBasic] = []
    seen_arena_ids = set()
    page = 1
    stop_flag = False

    while not stop_flag:
        page_has_valid = False
        try:
            raw_json = fetch_arena_page(player_name, page)
            page_records = parse_arena_list(raw_json)

            if not page_records:
                break

            for record in page_records:
                record_timestamp = int(record.start_time)
                if record.arena_id in seen_arena_ids:
                    continue
                if end_timestamp_threshold < record_timestamp:
                    continue

                if record_timestamp < start_timestamp_threshold:
                    logger.info(f"Page {page} has records older than {days} days, stop")
                    stop_flag = True
                    break

                all_valid_records.append(record)
                seen_arena_ids.add(record.arena_id)
                page_has_valid = True

            if not page_has_valid and not stop_flag:
                break
            page += 1

        except Exception as exc:
            logger.error(f"Failed to fetch page {page}: {exc}")
            if page > 2 and not page_has_valid:
                break
            page += 1
            time.sleep(0.5)
            continue

    all_valid_records.sort(key=lambda x: int(x.start_time), reverse=True)
    return all_valid_records


def get_detail_record_single(player_name: str, arena: RecordsBasic) -> RecordsDetail | None:
    """Fetch and parse one battle detail."""
    raw_text = fetch_battle_detail(player_name, arena.arena_id)
    return parse_battle_detail(raw_text, arena)
