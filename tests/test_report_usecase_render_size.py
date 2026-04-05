from data.plugins.astrbot_plugin_wot.src.application.report.report_renderer import (
    count_table_rows,
    estimate_retry_screenshot_size,
    estimate_screenshot_size,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FinalSummary,
    PlayerStats,
    WotRenderContext,
)
from data.plugins.astrbot_plugin_wot.src.settings.constants import (
    report_image_base_height,
    report_image_max_height,
    report_image_min_height,
    report_image_per_summary_row,
    report_image_retry_rows_threshold,
    report_image_width,
)


def _build_context(summary_rows: int) -> WotRenderContext:
    player_stats = PlayerStats(
        name="Tester",
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
    final_summary = FinalSummary(
        summary_title="今日战绩", tank_summary=[None] * summary_rows
    )
    return WotRenderContext(
        player_stats=player_stats,
        frequent_tank=[],
        final_summary=final_summary,
    )


def test_estimate_screenshot_size_uses_min_height_floor():
    context = _build_context(summary_rows=0)
    width, height = estimate_screenshot_size(context)
    assert width == report_image_width
    assert height == report_image_min_height


def test_estimate_screenshot_size_grows_with_rows():
    context = _build_context(summary_rows=40)
    width, height = estimate_screenshot_size(context)
    expected = report_image_base_height + 40 * report_image_per_summary_row
    expected = max(report_image_min_height, min(report_image_max_height, expected))
    assert width == report_image_width
    assert height == expected


def test_estimate_retry_size_returns_none_when_below_threshold():
    rows = max(0, report_image_retry_rows_threshold - 1)
    context = _build_context(summary_rows=rows)
    current = estimate_screenshot_size(context)
    assert estimate_retry_screenshot_size(context, current) is None


def test_estimate_retry_size_returns_larger_height_when_needed():
    context = _build_context(summary_rows=report_image_retry_rows_threshold + 8)
    current = estimate_screenshot_size(context, table_rows=report_image_retry_rows_threshold + 8)
    retry = estimate_retry_screenshot_size(context, current, table_rows=report_image_retry_rows_threshold + 8)
    assert retry is not None
    assert retry[0] == current[0]
    assert retry[1] > current[1]


def test_count_table_rows_from_html():
    html = "<table><tr><td>a</td></tr><tr><td>b</td></tr></table>"
    assert count_table_rows(html) == 2


def test_estimate_size_uses_html_row_count_when_provided():
    context = _build_context(summary_rows=0)
    width, height = estimate_screenshot_size(context, table_rows=60)
    expected = report_image_base_height + 60 * report_image_per_summary_row
    expected = max(report_image_min_height, min(report_image_max_height, expected))
    assert width == report_image_width
    assert height == expected
