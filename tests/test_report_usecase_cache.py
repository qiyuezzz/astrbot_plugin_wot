import threading
import time

from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FinalSummary,
    PlayerStats,
    WotRenderContext,
)
from data.plugins.astrbot_plugin_wot.src.application.report import report_query_cache
from data.plugins.astrbot_plugin_wot.src.application.report.report_query_cache import (
    REPORT_CONTEXT_CACHE,
    clear_report_context_cache,
    clear_report_context_inflight,
    get_cached_report_context,
    run_with_inflight_dedupe,
    set_cached_report_context,
)


def _build_context(name: str) -> WotRenderContext:
    player_stats = PlayerStats(
        name=name,
        update_time="2026-03-13",
        power="1000",
        power_float="+0",
        win_rate="50%",
        total_count=100,
        win_count=50,
        lose_count=50,
        hit_rate="70%",
        avg_tier="8.0",
        avg_damage="1000",
        avg_exp="500",
        avg_kill="1.0",
        avg_occupy="0.5",
        avg_defense="0.5",
        avg_discovery="1.0",
        comment="",
        radar_data=[],
    )
    return WotRenderContext(
        player_stats=player_stats,
        frequent_tank=[],
        final_summary=FinalSummary(summary_title="今日战绩", tank_summary=[]),
    )


def test_report_context_cache_hit(monkeypatch):
    clear_report_context_cache()
    clear_report_context_inflight()
    monkeypatch.setattr(report_query_cache, "report_query_cache_ttl_seconds", 60)
    key = ("Tester", "今日战绩", "get_arena_list_by_days", 1)
    context = _build_context("Tester")
    set_cached_report_context(key, context)

    cached = get_cached_report_context(key)
    assert cached is context


def test_report_context_cache_expired(monkeypatch):
    clear_report_context_cache()
    clear_report_context_inflight()
    monkeypatch.setattr(report_query_cache, "report_query_cache_ttl_seconds", 1)
    key = ("Tester", "今日战绩", "get_arena_list_by_days", 1)
    context = _build_context("Tester")
    set_cached_report_context(key, context)

    # Force expiration by rewinding timestamp.
    timestamp, cached_ctx = REPORT_CONTEXT_CACHE[key]
    REPORT_CONTEXT_CACHE[key] = (timestamp - 2, cached_ctx)

    cached = get_cached_report_context(key)
    assert cached is None
    assert key not in REPORT_CONTEXT_CACHE


def test_report_context_cache_prunes_oldest(monkeypatch):
    clear_report_context_cache()
    clear_report_context_inflight()
    monkeypatch.setattr(report_query_cache, "report_query_cache_max_entries", 2)
    monkeypatch.setattr(report_query_cache, "report_query_cache_ttl_seconds", 60)

    key1 = ("P1", "今日战绩", "days", 1)
    key2 = ("P2", "今日战绩", "days", 1)
    key3 = ("P3", "今日战绩", "days", 1)

    set_cached_report_context(key1, _build_context("P1"))
    set_cached_report_context(key2, _build_context("P2"))
    # Ensure key1 is considered oldest.
    t1, c1 = REPORT_CONTEXT_CACHE[key1]
    t2, c2 = REPORT_CONTEXT_CACHE[key2]
    REPORT_CONTEXT_CACHE[key1] = (t1 - 10, c1)
    REPORT_CONTEXT_CACHE[key2] = (t2 - 5, c2)
    set_cached_report_context(key3, _build_context("P3"))

    assert key1 not in REPORT_CONTEXT_CACHE
    assert key2 in REPORT_CONTEXT_CACHE
    assert key3 in REPORT_CONTEXT_CACHE


def test_inflight_dedupe_builds_once_for_same_key(monkeypatch):
    clear_report_context_cache()
    clear_report_context_inflight()
    monkeypatch.setattr(
        report_query_cache, "report_query_inflight_wait_timeout_seconds", 5
    )

    key = ("Tester", "今日战绩", "days", 1)
    calls = {"count": 0}
    release_event = threading.Event()
    build_started = threading.Event()
    start_barrier = threading.Barrier(2)
    results: list = []
    errors: list[Exception] = []

    def _builder():
        calls["count"] += 1
        build_started.set()
        time.sleep(0.2)
        release_event.wait(timeout=2)
        return _build_context("Tester")

    def _worker():
        try:
            start_barrier.wait(timeout=2)
            results.append(run_with_inflight_dedupe(key, _builder))
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    assert build_started.wait(timeout=1)
    release_event.set()
    t1.join(timeout=3)
    t2.join(timeout=3)

    assert not errors
    assert calls["count"] == 1
    assert len(results) == 2
    assert results[0] is results[1]


def test_inflight_dedupe_propagates_build_error(monkeypatch):
    clear_report_context_cache()
    clear_report_context_inflight()
    monkeypatch.setattr(
        report_query_cache, "report_query_inflight_wait_timeout_seconds", 5
    )

    key = ("Tester", "今日战绩", "days", 1)
    start_barrier = threading.Barrier(2)
    errors: list[str] = []

    def _builder():
        raise RuntimeError("boom")

    def _worker():
        try:
            start_barrier.wait(timeout=2)
            run_with_inflight_dedupe(key, _builder)
        except Exception as exc:
            errors.append(str(exc))

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=3)
    t2.join(timeout=3)

    assert len(errors) == 2
    assert all("boom" in message for message in errors)
