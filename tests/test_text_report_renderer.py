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
        "玩家 的车库（共 1 辆，展示前 30 辆）\n"
        "1. 59式 VIII 中型坦克 100场 胜率55.5% 场均击毁0.53 "
        "场均伤害2000 场均经验771 2环\n"
        "数据来源：游戏官网",
        layout="garage",
    )

    assert "<table class=\"garage\">" in html
    assert "<th>场均伤害</th>" in html
    assert "<th>场均击毁</th>" in html
    assert "<td>59式</td>" in html
    assert "<td>55.5%</td>" in html


def test_render_garage_report_supports_unavailable_marks():
    html = render_text_report_html(
        "车库查询",
        "玩家 的车库（共 1 辆，展示前 30 辆）\n"
        "1. 59式 VIII 中型坦克 100场 胜率55.5% 场均击毁0.53 "
        "场均伤害2000 场均经验771 暂无\n"
        "数据来源：游戏官网",
        layout="garage",
    )

    assert '<table class="garage">' in html
    assert "<td>暂无</td>" in html


def test_render_career_report_as_cards():
    html = render_text_report_html(
        "玩家生涯统计",
        "总成绩\n"
        "总场次：100\n"
        "胜率：55.00%\n"
        "场均击毁：1.20\n\n"
        "战斗坦克分布（按坦克类型）\n"
        "重型坦克：60场 · 占比60.00% · 胜率55.00% · MB4\n\n"
        "数据来源：游戏官网",
        layout="career",
    )

    assert '<div class="career-grid career">' in html
    assert '<section class="career-dashboard">' not in html
    assert "总成绩" in html
    assert "按坦克类型" in html
    assert "career-chart" in html
    assert "career-chart-bar" in html
    assert "--bar-height: 100.00%" in html
    assert "60" in html
    assert "数据来源：游戏官网" in html


def test_render_help_as_wide_grouped_cards():
    html = render_text_report_html(
        "坦克世界插件帮助",
        "使用规则\n[] 内参数可选\n\n战绩报表\n今日、昨日、百场用法相同",
        layout="help",
        width=2200,
    )

    assert "width: 2200px" in html
    assert 'class="help-grid"' in html
    assert '<section class="help-section wide">' in html
    assert "font-size: 28px" in html


def test_render_career_dashboard_layout():
    html = render_text_report_html(
        "玩家生涯统计",
        "数据\n"
        "玩家名称：常威爆打来福\n"
        "账号创建于：2023年03月25日\n"
        "最后战斗时间：2026年07月25日 01:45\n"
        "军团标签：别急\n"
        "军团名称：FaZe Corps\n"
        "军团颜色：#e548b3\n"
        "军团职务：招募\n"
        "入团天数：682\n"
        "军团徽章：https://example.com/clan.png\n"
        "WTR评级：6712（王牌II）\n"
        "损伤记录：7313 · 场均1495\n"
        "获得经验：2403 · 场均817\n"
        "参战场次：7536 · 胜率52.24%\n"
        "击毁坦克：6191 · 记录7\n"
        "协助损伤：9395 · 场均430\n"
        "抵挡损伤：7200 · 场均582\n"
        "战斗勋章：特级M 22 / 173 · 独特 81 · 总计 5,710\n\n"
        "战斗勋章展示\n勇士：11|https://example.com/warrior.png\n\n"
        "总成绩\n场次：7536\n\n"
        "数据来源：游戏官网",
        layout="career",
    )

    assert "career-dashboard" in html
    assert "WTR评级" in html
    assert "6712" in html
    assert "数据" in html
    assert "常威爆打来福" in html
    assert "FaZe Corps" in html
    assert "career-profile" in html
    assert "career-achievement" in html
    assert "warrior.png" in html


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


def test_render_moe_report_hides_subtitle_and_uses_compact_header():
    html = render_text_report_html(
        "环线标伤",
        "59式 环线标伤（近7天）\n8级 中坦\n一环（65%）: 1314",
        layout="moe",
    )

    assert '<header class="header">' in html
    assert "坦克世界数据查询" not in html
    assert "padding: 20px 30px;" in html


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
