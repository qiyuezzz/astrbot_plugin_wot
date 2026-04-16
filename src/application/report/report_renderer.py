from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.application.report.h2i_renderer import (
    H2IRenderer,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import WotRenderContext
from data.plugins.astrbot_plugin_wot.src.settings.constants import (
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

# 全局 H2I 渲染器实例
_h2i_renderer = H2IRenderer()


async def generate_report(
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

    # 使用 H2I 渲染器（优先本地渲染，失败时降级到 T2I）
    options = {
        "full_page": True,
        "type": "jpeg",
        "quality": 100,
        "width": 2560,
        "height": 2560,
        "device_scale_factor": 1,
    }
    image_url = await _h2i_renderer.render_report(
        send_id, html_output, report_dir, options
    )
    logger.info(f"生成的图片 URL: {image_url}")


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
    template = get_report_template()
    return template.render(ctx=wot_render_context)


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
