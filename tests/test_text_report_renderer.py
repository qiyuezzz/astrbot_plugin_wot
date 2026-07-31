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


def test_render_tank_detail_as_cards_with_vehicle_image():
    html = render_text_report_html(
        "坦克百科",
        "59式 坦克百科\n8级 · 中国 · 中坦\n\n"
        "【火力与炮控】\n移动扩圈：0.14\n射击俯角：-7°\n\n"
        "数据来源：坦克营地（基础配置）",
        layout="tank_detail",
        hero_images=(("59式", "https://example.com/type59.png"),),
    )

    assert '<div class="hero-gallery">' in html
    assert 'src="https://example.com/type59.png"' in html
    assert '<h2>59式 坦克百科</h2>' not in html
    assert 'class="data-row intro-meta"' in html
    assert '<span class="data-value">8级</span>' in html
    assert '<span class="data-value">中国</span>' in html
    assert "<h2>火力与炮控</h2>" in html
    assert '<span class="data-label">射击俯角</span>' in html
    assert '<span class="data-value">-7°</span>' in html
    assert "数据来源：坦克营地（基础配置）" in html


def test_render_tank_comparison_keeps_meta_with_each_vehicle_image():
    html = render_text_report_html(
        "坦克对比",
        "坦克对比：野牛 vs 59式\n"
        "3级 · 德国 · 火炮 | 8级 · 中国 · 中坦\n\n"
        "【火力与炮控】\n项目：野牛 | 59式\n伤害，HP：350 | 250\n\n"
        "数据来源：坦克营地（优选配置）",
        layout="tank_compare",
        hero_images=(
            ("野牛", "https://example.com/bison.png"),
            ("59式", "https://example.com/type59.png"),
        ),
    )

    assert 'class="hero-gallery compare-gallery"' in html
    assert html.count('class="compare-hero-meta"') == 2
    assert html.count('class="data-value">3级</span>') == 1
    assert html.count('class="data-value">8级</span>') == 1
    assert '<section class="tank-intro-info">' not in html
