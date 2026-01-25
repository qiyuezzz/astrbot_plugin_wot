import json

from data.plugins.astrbot_plugin_wot.model.player_info import WotRenderContext
from data.plugins.astrbot_plugin_wot.player_stats import get_player_stats_wot_box
from data.plugins.astrbot_plugin_wot.record import get_arena_list_by_days, get_detail_record_list, get_final_summary
from data.plugins.astrbot_plugin_wot.util.get_tank_list import fetch_all_tank_data
from data.plugins.astrbot_plugin_wot.util.utils import write_binding_data, read_binding_data, general_image


def get_record_by_days(player_name:str,days:int) ->WotRenderContext:
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
    return wot_render_context

#获取全部坦克信息
def get_all_tank_info():
    fetch_all_tank_data()

def bind_user_name(qq_id:str,msg:str):
    write_binding_data(qq_id,msg)

#查询今日效率
def get_record_today(send_id:str):
    player_name = read_binding_data(send_id)
    wot_render_context =  get_record_by_days(player_name,15)
    general_image(send_id,wot_render_context)

#查询两日效率
def get_record_two_days(player_name) ->WotRenderContext:
    return get_record_by_days(player_name,1)

#查询三日效率
def get_record_three_days(player_name) ->WotRenderContext:
    return get_record_by_days(player_name,3)