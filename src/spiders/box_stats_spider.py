import re
from bs4 import BeautifulSoup

from astrbot.core import logger
from data.plugins.astrbot_plugin_wot.src.http.request_context import wot_box_config
from data.plugins.astrbot_plugin_wot.src.model.report import FrequentTank, PlayerStats
from data.plugins.astrbot_plugin_wot.src.util.data_utils import get_tank_info_by_name, clean_number
from data.plugins.astrbot_plugin_wot.src.http.http_client import HttpClient

class WotBoxSpider:
    def __init__(self):
        self.client = HttpClient()

    def get_player_raw_html(self,player_name: str) -> str:
        """
        获取玩家盒子页面的原始HTML内容
        :param player_name: 玩家游戏名称
        :return: 原始HTML字符串，失败返回空字符串
        """
        if not player_name or not player_name.strip():
            logger.error(f"错误：玩家名称不能为空")
            return ""

        params = wot_box_config.build_params()
        params['pn'] = player_name

        try:
            res = self.client.send_get(wot_box_config, params)
            return res.text if res and res.text else ""
        except Exception as e:
            logger.exception(f"爬取玩家{player_name}原始页面失败：{e}")
            return ""