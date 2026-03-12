# service/wot_box_service.py
from data.plugins.astrbot_plugin_wot.src.domain.models.report import FrequentTank, PlayerStats
from data.plugins.astrbot_plugin_wot.src.infrastructure.crawlers.wot_box_api import (
    fetch_player_stats_html,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.parsers.wot_box_stats import WotBoxStatsParser

class WotBoxService:
    """偶游盒子服务层：负责解析原始HTML、转换为Model对象"""

    def __init__(self):
        self.parser = WotBoxStatsParser()

    def get_player_stats(self, player_name: str) -> tuple[PlayerStats, list[FrequentTank]]:
        """对外提供的核心方法：获取玩家统计数据和常用坦克列表"""
        raw_html = fetch_player_stats_html(player_name)
        return self.parser.parse_player_stats(raw_html, player_name)
