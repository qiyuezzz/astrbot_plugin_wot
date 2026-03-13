from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from html2image import Html2Image
from jinja2 import Environment, FileSystemLoader

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.report import WotRenderContext
from data.plugins.astrbot_plugin_wot.src.settings.constants import (
    font_path,
    report_dir_path,
    report_image_base_height,
    report_image_max_height,
    report_image_min_height,
    report_image_per_summary_row,
    report_image_retry_extra_height,
    report_image_retry_height_scale,
    report_image_retry_rows_threshold,
    report_image_width,
    template_dir_path,
    template_path,
)


def generate_report(
    send_id: str, wot_render_context: WotRenderContext, report_path=None
):
    """生成WOT战绩报告。"""
    report_dir = Path(report_dir_path).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    html_output = render_report_html(wot_render_context)

    html_file_path = report_dir / f"{send_id}.html"
    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(html_output)
    logger.info(f"HTML文件已保存：{html_file_path}")

    hti = Html2Image(
        output_path=str(report_dir), custom_flags=["--no-sandbox", "--disable-gpu"]
    )
    png_file_name = f"{send_id}.png"
    table_rows = count_table_rows(html_output)
    screenshot_size = estimate_screenshot_size(
        wot_render_context,
        table_rows=table_rows,
    )
    hti.screenshot(
        html_file=str(html_file_path), save_as=png_file_name, size=screenshot_size
    )
    retry_size = estimate_retry_screenshot_size(
        wot_render_context,
        screenshot_size,
        table_rows=table_rows,
    )
    if retry_size:
        logger.info(f"Retrying PNG render with larger size={retry_size}")
        hti.screenshot(
            html_file=str(html_file_path), save_as=png_file_name, size=retry_size
        )
        screenshot_size = retry_size
    png_file_path = report_dir / png_file_name
    logger.info(f"PNG报告生成成功：{png_file_path}，size={screenshot_size}")


def estimate_screenshot_size(
    wot_render_context: WotRenderContext,
    table_rows: int | None = None,
) -> tuple[int, int]:
    width = report_image_width
    base_height = report_image_base_height
    if table_rows is None:
        table_rows = len(wot_render_context.final_summary.tank_summary or [])
    estimated_height = base_height + table_rows * report_image_per_summary_row
    height = max(
        report_image_min_height, min(report_image_max_height, estimated_height)
    )
    return width, height


def estimate_retry_screenshot_size(
    wot_render_context: WotRenderContext,
    current_size: tuple[int, int],
    table_rows: int | None = None,
) -> tuple[int, int] | None:
    if table_rows is None:
        table_rows = len(wot_render_context.final_summary.tank_summary or [])
    if table_rows < report_image_retry_rows_threshold:
        return None

    width, current_height = current_size
    scaled_height = int(current_height * report_image_retry_height_scale)
    retry_height = min(
        report_image_max_height, scaled_height + report_image_retry_extra_height
    )
    if retry_height <= current_height:
        return None
    return width, retry_height


def count_table_rows(html_output: str) -> int:
    return len(re.findall(r"<tr\b", html_output, flags=re.IGNORECASE))


@lru_cache(maxsize=1)
def get_report_template():
    template_dir = Path(template_dir_path).resolve()
    template_file = Path(template_path).resolve()
    template_filename = template_file.name
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["wot_time"] = format_wot_time
    env.filters["win_rate"] = format_win_rate
    return env.get_template(template_filename)


def render_report_html(wot_render_context: WotRenderContext) -> str:
    font_file = Path(font_path).resolve()
    template = get_report_template()
    return template.render(
        ctx=wot_render_context,
        font_url=str(font_file),
    )


def format_wot_time(seconds):
    if not seconds:
        return "0分0秒"
    m, s = divmod(round(float(seconds)), 60)
    return f"{m}分{s:02d}秒"


def format_win_rate(win_rate: float | None) -> str:
    if win_rate is None or win_rate == 0:
        return "0%"
    formatted = f"{win_rate:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}%"
