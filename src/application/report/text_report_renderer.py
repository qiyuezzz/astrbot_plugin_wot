from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from astrbot.api import logger
from astrbot.core import html_renderer
from data.plugins.astrbot_plugin_wot.src.settings.constants import (
    report_dir_path,
    template_dir_path,
)

_IMAGE_MIN_HEIGHT = 500
_IMAGE_MAX_HEIGHT = 8000
_IMAGE_BASE_HEIGHT = 280
_IMAGE_PER_LINE_HEIGHT = 76

ReportLayout = Literal["text", "garage", "moe"]

_GARAGE_ROW_PATTERN = re.compile(
    r"^(?P<rank>\d+)\.\s+(?P<tank>.+?)\s+(?P<tier>\S+)\s+(?P<type>\S+)\s+"
    r"(?P<battles>\d+)场\s+胜率(?P<win_rate>[\d.]+)%\s+WN8\s+"
    r"(?P<wn8>[\d.]+)\s+场均伤害(?P<damage>[\d.]+)\s+"
    r"(?P<marks>无环|\d+环)$"
)
_MOE_TITLE_PATTERN = re.compile(r"^(?P<tank>.+?) 环线标伤（近7天）$")
_MOE_META_PATTERN = re.compile(r"^(?P<tier>\d+)级\s+(?P<type>.+)$")
_MOE_VALUE_PATTERN = re.compile(
    r"^(?P<label>[一二三]环)（\d+%）:\s*(?P<value>\d+)$"
)


async def generate_text_report(
    send_id: str,
    title: str,
    text: str,
    layout: ReportLayout = "text",
) -> str:
    """将文本查询结果渲染为图片并返回远程 URL。"""
    html_output = render_text_report_html(title, text, layout)
    report_dir = Path(report_dir_path).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    safe_send_id = re.sub(r"[^0-9A-Za-z_-]", "_", send_id)
    html_file_path = report_dir / f"{safe_send_id}_text.html"
    html_file_path.write_text(html_output, encoding="utf-8")

    line_count = max(1, len(text.splitlines()))
    image_width = 1800 if layout == "garage" else 1200
    height = max(
        _IMAGE_MIN_HEIGHT,
        min(_IMAGE_MAX_HEIGHT, _IMAGE_BASE_HEIGHT + line_count * _IMAGE_PER_LINE_HEIGHT),
    )
    image_url = await html_renderer.render_custom_template(
        html_output,
        {},
        return_url=True,
        options={
            "full_page": True,
            "type": "jpeg",
            "quality": 95,
            "width": image_width,
            "height": height,
            "device_scale_factor": 1,
        },
    )
    logger.info(f"{title}图片已生成：{image_url}")
    return image_url


@lru_cache(maxsize=1)
def get_text_report_template():
    template_dir = Path(template_dir_path).resolve()
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("text_report_template.j2")


def render_text_report_html(
    title: str,
    text: str,
    layout: ReportLayout = "text",
) -> str:
    sections = [section.strip() for section in text.split("\n\n") if section.strip()]
    table = _build_table(layout, sections)
    return get_text_report_template().render(
        title=title,
        layout=layout,
        width=1800 if layout == "garage" else 1200,
        sections=sections,
        table=table,
    )


def _build_table(layout: ReportLayout, sections: list[str]) -> dict | None:
    if layout == "garage":
        return _build_garage_table(sections)
    if layout == "moe":
        return _build_moe_table(sections)
    return None


def _build_garage_table(sections: list[str]) -> dict | None:
    if len(sections) != 1:
        return None
    lines = sections[0].splitlines()
    if len(lines) < 3:
        return None

    rows: list[list[str]] = []
    for line in lines[1:-1]:
        match = _GARAGE_ROW_PATTERN.match(line)
        if not match:
            return None
        rows.append(
            [
                match["rank"],
                match["tank"],
                match["tier"],
                match["type"],
                match["battles"],
                f'{match["win_rate"]}%',
                match["wn8"],
                match["damage"],
                match["marks"],
            ]
        )
    if not rows:
        return None
    return {
        "summary": lines[0],
        "headers": [
            "排名",
            "坦克",
            "等级",
            "类型",
            "场次",
            "胜率",
            "WN8",
            "场均伤害",
            "环数",
        ],
        "rows": rows,
        "footer": lines[-1],
        "notices": [],
    }


def _build_moe_table(sections: list[str]) -> dict | None:
    rows: list[list[str]] = []
    notices: list[str] = []
    for section in sections:
        lines = section.splitlines()
        if len(lines) < 5:
            notices.append(section)
            continue
        title_match = _MOE_TITLE_PATTERN.match(lines[0])
        meta_match = _MOE_META_PATTERN.match(lines[1])
        values = {}
        for line in lines[2:]:
            if value_match := _MOE_VALUE_PATTERN.match(line):
                values[value_match["label"]] = value_match["value"]
        if not title_match or not meta_match or len(values) != 3:
            notices.append(section)
            continue
        rows.append(
            [
                title_match["tank"],
                meta_match["tier"],
                meta_match["type"],
                values["一环"],
                values["二环"],
                values["三环"],
            ]
        )
    if not rows:
        return None
    return {
        "summary": "近7天环线标伤阈值",
        "headers": ["坦克", "等级", "类型", "一环（65%）", "二环（85%）", "三环（95%）"],
        "rows": rows,
        "footer": "数据来源：坦克营地",
        "notices": notices,
    }
