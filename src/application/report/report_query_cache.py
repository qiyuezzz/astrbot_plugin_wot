from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.settings.constants import (
    report_query_cache_max_entries,
    report_query_cache_ttl_seconds,
    report_query_inflight_wait_timeout_seconds,
)

ReportCacheKey = tuple[str, str, str, int]

REPORT_CONTEXT_CACHE: dict[ReportCacheKey, tuple[float, Any]] = {}
REPORT_CONTEXT_INFLIGHT: dict[ReportCacheKey, _InFlightContext] = {}
REPORT_CONTEXT_CACHE_LOCK = threading.Lock()
REPORT_CONTEXT_INFLIGHT_LOCK = threading.Lock()


@dataclass
class _InFlightContext:
    event: asyncio.Event | threading.Event
    result: Any = None
    error: Exception | None = None


def make_report_context_cache_key(
    player_name: str,
    title: str,
    get_arena_list_func,
    func_param: int,
) -> ReportCacheKey:
    return (
        player_name,
        title,
        getattr(get_arena_list_func, "__name__", str(get_arena_list_func)),
        func_param,
    )


def get_cached_report_context(cache_key: ReportCacheKey):
    with REPORT_CONTEXT_CACHE_LOCK:
        item = REPORT_CONTEXT_CACHE.get(cache_key)
        if not item:
            return None

        timestamp, context = item
        if time.time() - timestamp > report_query_cache_ttl_seconds:
            REPORT_CONTEXT_CACHE.pop(cache_key, None)
            return None
        return context


def set_cached_report_context(cache_key: ReportCacheKey, context) -> None:
    with REPORT_CONTEXT_CACHE_LOCK:
        REPORT_CONTEXT_CACHE[cache_key] = (time.time(), context)
        if len(REPORT_CONTEXT_CACHE) <= report_query_cache_max_entries:
            return

        oldest_key = min(REPORT_CONTEXT_CACHE.items(), key=lambda item: item[1][0])[0]
        REPORT_CONTEXT_CACHE.pop(oldest_key, None)


async def run_with_inflight_dedupe(
    cache_key: ReportCacheKey,
    build_func,
):
    owner = False
    with REPORT_CONTEXT_INFLIGHT_LOCK:
        inflight = REPORT_CONTEXT_INFLIGHT.get(cache_key)
        if inflight is None:
            inflight = _InFlightContext(event=asyncio.Event())
            REPORT_CONTEXT_INFLIGHT[cache_key] = inflight
            owner = True

    if not owner:
        try:
            finished = await asyncio.wait_for(
                inflight.event.wait(),
                timeout=max(1, report_query_inflight_wait_timeout_seconds),
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning(f"等待同 key 渲染超时，退化为独立构建：{cache_key}")
            return await build_func()
        if not finished:
            logger.warning(f"等待同 key 渲染超时，退化为独立构建：{cache_key}")
            return await build_func()
        if inflight.error:
            raise inflight.error
        if inflight.result is not None:
            return inflight.result
        if cached := get_cached_report_context(cache_key):
            return cached
        return await build_func()

    try:
        result = await build_func()
        inflight.result = result
        return result
    except Exception as exc:
        inflight.error = exc
        raise
    finally:
        inflight.event.set()
        with REPORT_CONTEXT_INFLIGHT_LOCK:
            REPORT_CONTEXT_INFLIGHT.pop(cache_key, None)


def clear_report_context_cache() -> None:
    with REPORT_CONTEXT_CACHE_LOCK:
        REPORT_CONTEXT_CACHE.clear()


def clear_report_context_inflight() -> None:
    with REPORT_CONTEXT_INFLIGHT_LOCK:
        REPORT_CONTEXT_INFLIGHT.clear()
