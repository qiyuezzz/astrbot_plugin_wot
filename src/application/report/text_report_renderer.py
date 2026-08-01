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

ReportLayout = Literal[
    "text", "help", "garage", "career", "moe", "tank_detail", "tank_compare"
]

_GARAGE_ROW_PATTERN = re.compile(
    r"^(?P<rank>\d+)\.\s+(?P<tank>.+?)\s+(?P<tier>\S+)\s+(?P<type>\S+)\s+"
    r"(?P<battles>\d+)场\s+胜率(?P<win_rate>[\d.]+)%\s+"
    r"场均击毁(?P<avg_frags>[\d.]+)\s+场均伤害(?P<damage>[\d.]+)\s+"
    r"场均经验(?P<xp>\d+)\s+"
    r"(?P<marks>无环|暂无|\d+环)$"
)
_MOE_TITLE_PATTERN = re.compile(r"^(?P<tank>.+?) 环线标伤（近7天）$")
_MOE_META_PATTERN = re.compile(r"^(?P<tier>\d+)级\s+(?P<type>.+)$")
_MOE_VALUE_PATTERN = re.compile(
    r"^(?P<label>[一二三]环)（\d+%）:\s*(?P<value>\d+)$"
)
_CAREER_DISTRIBUTION_PATTERN = re.compile(
    r"^(?P<label>.+?)：(?P<battles>[\d,.]+)场 · 占比(?P<percent>[\d,.]+)% · "
    r"胜率(?P<win_rate>[\d,.]+)% · MB(?P<master_count>[\d,.]+)$"
)
_CAREER_ACHIEVEMENT_PATTERN = re.compile(
    r"^(?P<label>.+?)：(?P<value>[\d,]+)\|(?P<icon>https?://.+)$"
)
_TIER_ROMAN_NAMES = {
    "1级": "I",
    "2级": "II",
    "3级": "III",
    "4级": "IV",
    "5级": "V",
    "6级": "VI",
    "7级": "VII",
    "8级": "VIII",
    "9级": "IX",
    "10级": "X",
    "11级": "XI",
}

_CAREER_STAT_ICONS = {
    "损伤记录": "damage.svg",
    "获得经验": "exp.svg",
    "参战场次": "battles.svg",
    "击毁坦克": "frags.svg",
    "协助损伤": "assist.svg",
    "抵挡损伤": "block.svg",
}
_CAREER_ASSET_ROOT = (
    "https://static-cdn.wotgame.cn/static/6.15.1_aca52e/"
    "wotp_static/img/user_profile/frontend/scss/img/"
)
_WTR_ICON_CODES = {
    "青铜I": "bronze_1",
    "青铜II": "bronze_2",
    "青铜III": "bronze_3",
    "白银I": "silver_1",
    "白银II": "silver_2",
    "白银III": "silver_3",
    "黄金I": "gold_1",
    "黄金II": "gold_2",
    "黄金III": "gold_3",
    "王牌I": "ace_1",
    "王牌II": "ace_2",
    "王牌III": "ace_3",
    "传奇I": "legend_1",
    "传奇II": "legend_2",
    "传奇III": "legend_3",
}


async def generate_text_report(
    send_id: str,
    title: str,
    text: str,
    layout: ReportLayout = "text",
    hero_images: tuple[tuple[str, str], ...] = (),
    width: int | None = None,
) -> str:
    """将文本查询结果渲染为图片并返回远程 URL。"""
    html_output = render_text_report_html(title, text, layout, hero_images, width)
    report_dir = Path(report_dir_path).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    safe_send_id = re.sub(r"[^0-9A-Za-z_-]", "_", send_id)
    html_file_path = report_dir / f"{safe_send_id}_text.html"
    html_file_path.write_text(html_output, encoding="utf-8")

    line_count = max(1, len(text.splitlines()))
    image_width = width or (
        2200
        if layout.startswith("tank_")
        else 2200
        if layout == "help"
        else 1800
        if layout in ("garage", "career")
        else 1200
    )
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
    hero_images: tuple[tuple[str, str], ...] = (),
    width: int | None = None,
) -> str:
    sections = [section.strip() for section in text.split("\n\n") if section.strip()]
    table = _build_table(layout, sections)
    cards, card_footer = _build_cards(layout, sections)
    intro_groups = _build_intro_groups(layout, cards)
    card_columns = _distribute_card_columns(
        cards[1:] if cards else [], 4 if layout == "tank_detail" else 3
    )
    report_width = width or (
        2200
        if layout.startswith("tank_")
        else 2200
        if layout == "help"
        else 1800
        if layout in ("garage", "career")
        else 1200
    )
    return get_text_report_template().render(
        title=title,
        layout=layout,
        width=report_width,
        sections=sections,
        table=table,
        cards=cards,
        card_columns=card_columns,
        card_footer=card_footer,
        intro_groups=intro_groups,
        hero_images=hero_images,
    )


def _build_table(layout: ReportLayout, sections: list[str]) -> dict | None:
    if layout == "garage":
        return _build_garage_table(sections)
    if layout == "moe":
        return _build_moe_table(sections)
    return None


def _build_cards(
    layout: ReportLayout, sections: list[str]
) -> tuple[list[dict[str, object]] | None, str]:
    if layout == "career":
        return _build_career_cards(sections)
    if layout not in ("tank_detail", "tank_compare"):
        return None, ""
    cards: list[dict[str, object]] = []
    footer = ""
    for section in sections:
        if section.startswith("数据来源："):
            footer = section
            continue
        lines = section.splitlines()
        title = lines[0].strip().strip("【】")
        rows: list[dict[str, str]] = []
        for line in lines[1:]:
            stripped = line.strip()
            if "：" in stripped:
                label, value = stripped.split("：", 1)
                kind = "sub" if line.startswith("  ") else "normal"
                if label == "项目":
                    kind = "comparison-head"
                rows.append(
                    {"label": label.strip(), "value": value.strip(), "kind": kind}
                )
            elif stripped:
                rows.append({"label": "", "value": stripped, "kind": "full"})
        cards.append({"title": title, "rows": rows})
    if cards:
        if layout != "tank_compare":
            cards[0]["rows"] = _split_intro_meta_rows(cards[0]["rows"])
    return cards, footer


def _build_career_cards(
    sections: list[str],
) -> tuple[list[dict[str, object]] | None, str]:
    cards: list[dict[str, object]] = []
    footer = ""
    for section in sections:
        if section.startswith("数据来源："):
            footer = section
            continue
        lines = section.splitlines()
        if not lines:
            continue
        if lines[0].strip() == "数据":
            dashboard = {
                "wtr_score": "0",
                "wtr_title": "",
                "wtr_icon": "",
                "left": [],
                "right": [],
                "medals": "",
                "profile": {},
            }
            for line in lines[1:]:
                if "：" not in line:
                    continue
                label, value = line.split("：", 1)
                label = label.strip()
                value = value.strip()
                if label == "WTR评级":
                    match = re.match(r"^(?P<score>[\d,.]+)（(?P<title>.+)）$", value)
                    if match:
                        dashboard["wtr_score"] = match["score"]
                        dashboard["wtr_title"] = match["title"]
                        code = _WTR_ICON_CODES.get(match["title"], "default")
                        dashboard["wtr_icon"] = f"{_CAREER_ASSET_ROOT}wtr_icons/{code}.png"
                    continue
                if label == "战斗勋章":
                    dashboard["medals"] = value
                    continue
                profile_keys = {
                    "玩家名称": "name",
                    "账号创建于": "registered_at",
                    "最后战斗时间": "last_battle_at",
                    "军团标签": "clan_tag",
                    "军团名称": "clan_name",
                    "军团颜色": "clan_color",
                    "军团职务": "clan_role",
                    "入团天数": "clan_days",
                    "军团徽章": "clan_emblem",
                }
                if label in profile_keys:
                    dashboard["profile"][profile_keys[label]] = value
                    continue
                parts = [part.strip() for part in value.split("·", 1)]
                item = {
                    "label": label,
                    "primary": parts[0],
                    "secondary": parts[1] if len(parts) > 1 else "",
                    "icon": f"{_CAREER_ASSET_ROOT}stats/{_CAREER_STAT_ICONS.get(label, '')}",
                }
                if label in {"损伤记录", "获得经验", "参战场次"}:
                    dashboard["left"].append(item)
                else:
                    dashboard["right"].append(item)
            cards.append({"title": "数据", "rows": [], "dashboard": dashboard})
            continue
        rows: list[dict[str, str]] = []
        is_distribution = lines[0].startswith("战斗坦克分布")
        is_achievements = lines[0] == "战斗勋章展示"
        for line in lines[1:]:
            stripped = line.strip()
            if is_achievements and (match := _CAREER_ACHIEVEMENT_PATTERN.match(stripped)):
                rows.append(
                    {
                        "label": match["label"],
                        "value": match["value"],
                        "kind": "achievement",
                        "icon": match["icon"],
                    }
                )
                continue
            if is_distribution and (match := _CAREER_DISTRIBUTION_PATTERN.match(stripped)):
                battles = float(match["battles"].replace(",", ""))
                label = match["label"]
                if "按等级" in lines[0]:
                    label = _TIER_ROMAN_NAMES.get(label, label)
                rows.append(
                    {
                        "label": label,
                        "value": f"{int(battles):,}",
                        "kind": "chart",
                        "bar_height": "0%",
                    }
                )
                continue
            if "：" in stripped:
                label, value = stripped.split("：", 1)
                rows.append(
                    {"label": label.strip(), "value": value.strip(), "kind": "normal"}
                )
            elif stripped:
                rows.append({"label": "", "value": stripped, "kind": "full"})
        if is_distribution and rows:
            max_battles = max(
                int(str(row.get("value") or "0").replace(",", "")) for row in rows
            )
            if max_battles:
                for row in rows:
                    battles = int(str(row.get("value") or "0").replace(",", ""))
                    row["bar_height"] = f"{battles * 100 / max_battles:.2f}%"
        cards.append(
            {
                "title": lines[0].strip(),
                "rows": rows,
                "chart": is_distribution,
                "achievements": is_achievements,
            }
        )
    return cards or None, footer


def _split_intro_meta_rows(rows: object) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        return []
    split_rows: list[dict[str, str]] = []
    for row in rows:
        value = str(row.get("value") or "")
        if not row.get("label") and " · " in value:
            split_rows.extend(
                {
                    "label": "",
                    "value": item.strip(),
                    "kind": "intro-meta",
                }
                for item in value.split(" · ")
                if item.strip()
            )
        else:
            split_rows.append(row)
    return split_rows


def _build_intro_groups(
    layout: ReportLayout,
    cards: list[dict[str, object]] | None,
) -> list[list[dict[str, str]]]:
    if not cards:
        return []
    rows = cards[0].get("rows")
    if layout != "tank_compare" or not isinstance(rows, list):
        return [rows] if isinstance(rows, list) else []
    if not rows:
        return []
    value = str(rows[0].get("value") or "")
    if " | " not in value:
        return [_split_intro_meta_rows(rows)]
    left, right = value.split(" | ", 1)
    return [
        _split_intro_meta_rows([{"label": "", "value": left, "kind": "full"}]),
        _split_intro_meta_rows([{"label": "", "value": right, "kind": "full"}]),
    ]


def _distribute_card_columns(
    cards: list[dict[str, object]], column_count: int
) -> list[list[dict[str, object]]]:
    """按卡片行数贪心分栏，避免 CSS 网格短卡片下方出现大块留白。"""
    if not cards:
        return []
    columns: list[list[dict[str, object]]] = [[] for _ in range(column_count)]
    weights = [0] * column_count
    ordered_cards = sorted(
        cards,
        key=lambda card: len(card.get("rows") or []) + 2,
        reverse=True,
    )
    for card in ordered_cards:
        target = min(range(column_count), key=weights.__getitem__)
        columns[target].append(card)
        weights[target] += len(card.get("rows") or []) + 2
    return [column for column in columns if column]


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
                match["avg_frags"],
                match["damage"],
                match["xp"],
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
            "场均击毁",
            "场均伤害",
            "场均经验",
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
