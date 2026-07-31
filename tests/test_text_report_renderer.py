from data.plugins.astrbot_plugin_wot.src.application.report.text_report_renderer import (
    render_text_report_html,
)


def test_render_text_report_html_preserves_sections_and_escapes_content():
    html = render_text_report_html(
        "环线标伤",
        "59式\n一环：1314\n\n<script>alert(1)</script>",
    )

    assert "59式\n一环：1314" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_render_garage_report_as_table():
    html = render_text_report_html(
        "车库查询",
        "玩家 的车库（共 1 辆，展示前 15 辆）\n"
        "1. 59式 VIII 中型坦克 100场 胜率55.5% WN8 1800 场均伤害2000 2环\n"
        "数据来源：坦克营地",
        layout="garage",
    )

    assert "<table class=\"garage\">" in html
    assert "<th>场均伤害</th>" in html
    assert "<td>59式</td>" in html
    assert "<td>55.5%</td>" in html


def test_render_multiple_moe_results_as_table():
    html = render_text_report_html(
        "环线标伤",
        "59式 环线标伤（近7天）\n8级 中坦\n"
        "一环（65%）: 1314\n二环（85%）: 1949\n三环（95%）: 2460\n"
        "数据来源：坦克营地\n\n"
        "黄金59式 环线标伤（近7天）\n8级 中坦\n"
        "一环（65%）: 1500\n二环（85%）: 2200\n三环（95%）: 2951\n"
        "数据来源：坦克营地",
        layout="moe",
    )

    assert "<table class=\"moe\">" in html
    assert "<th>三环（95%）</th>" in html
    assert "<td>59式</td>" in html
    assert "<td>黄金59式</td>" in html
    assert "<td>2951</td>" in html
