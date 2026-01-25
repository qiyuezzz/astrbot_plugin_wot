import json
from dataclasses import asdict

from html2image import Html2Image
from jinja2 import FileSystemLoader,Environment

from model.player_info import WotRenderContext
from player_stats import get_player_stats_wot_box
from record import get_arena_list_by_days, get_detail_record_list, get_final_summary


def format_wot_time(seconds):
    if not seconds: return "0'0\""
    m, s = divmod(round(float(seconds)), 60)
    return f"{m}分{s:02d}秒"




if __name__ == '__main__':
    # 常威爆打来福
    # 小小嘚粽子
    player_name = "小小嘚粽子"
    days=1
    # 根据玩家名称从偶游盒子页面获取战斗力统计页面,
    data_stats = get_player_stats_wot_box(player_name)
    #获取近期对局列表
    arena_list = get_arena_list_by_days(player_name,days)
    #获取近期对局列表详细数据
    detail_arena_list = get_detail_record_list(player_name,arena_list)
    #统计汇总近期详细数据
    final_summary = get_final_summary(detail_arena_list)

    wot_render_context = WotRenderContext(
        player_stats=data_stats[0],
        frequent_tank=data_stats[1],
        final_summary=final_summary
    )
    print(wot_render_context)


    #生成图片
    env = Environment(loader=FileSystemLoader('.'))
    env.filters['wot_time'] = format_wot_time
    output_dir = 'static'
    template = env.get_template('static/template/report_template.j2')
    html_output = template.render(ctx=wot_render_context)
    with open('static/output.html', 'w', encoding='utf-8') as f:
        f.write(html_output)
    hti = Html2Image(output_path=output_dir,custom_flags=['--no-sandbox', '--disable-gpu'])
    hti.screenshot(html_file='static/output.html', save_as='report.png', size=(2560, 2800))


