import json

from astrbot.core import  logger
from data.plugins.astrbot_plugin_wot.src.config.constants import tank_info_path
from data.plugins.astrbot_plugin_wot.src.http.http_client import HttpClient
from data.plugins.astrbot_plugin_wot.src.http.request_context import wot_account_search_config, \
    wot_game_tank_info_config
from data.plugins.astrbot_plugin_wot.src.model.player import AccountInfo

"""官方接口"""

def wot_account_search(player_name:str):
    """根据玩家名称查询账户信息"""

    client=HttpClient()
    params = wot_account_search_config.build_params()
    params['name'] = player_name
    params['name_gt'] = ""
    resp = client.send_get(wot_account_search_config, params)
    return resp


def get_all_tank_info():
    client = HttpClient ()
    try:
        logger.info('正在获取全量坦克数据...')
        resp =client.send_post(config=wot_game_tank_info_config,data=wot_game_tank_info_config.data)
        return resp
    except Exception as e:
        logger.error(f"运行失败: {e}")
        return '更新失败'