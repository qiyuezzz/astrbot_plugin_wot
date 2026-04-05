from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FrequentTank,
    PlayerStats,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_box_api import (
    fetch_player_stats_html,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.parsers.wot_box_stats_parser import (
    WotBoxStatsParser,
)


class WotBoxService:
    """获取 WotBox 页面数据并解析为领域模型"""

    def __init__(self):
        self.parser = WotBoxStatsParser()

    async def get_player_stats(
        self, player_name: str
    ) -> tuple[PlayerStats, list[FrequentTank]]:
        raw_html = await fetch_player_stats_html(player_name)
        return self.parser.parse_player_stats(raw_html, player_name)
