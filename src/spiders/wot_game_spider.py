
from data.plugins.astrbot_plugin_wot.src.http.http_client import HttpClient
from data.plugins.astrbot_plugin_wot.src.http.request_context import wot_account_search_config
from data.plugins.astrbot_plugin_wot.src.model.player import AccountInfo


def wot_account_search(player_name:str):
    """根据玩家名称查询账户信息"""

    client=HttpClient()
    params = wot_account_search_config.build_params()
    params['name'] = player_name
    params['name_gt'] = ""
    resp = client.send_get(wot_account_search_config, params)
    return resp
