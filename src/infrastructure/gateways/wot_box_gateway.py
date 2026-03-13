from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FrequentTank,
    PlayerStats,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.clients.wot_box_api import (
    fetch_player_stats_html,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.parsers.wot_box_stats_parser import (
    WotBoxStatsParser,
)


class WotBoxService:
    """Fetch WotBox HTML and parse it into domain models."""

    def __init__(self):
        self.parser = WotBoxStatsParser()

    def get_player_stats(
        self, player_name: str
    ) -> tuple[PlayerStats, list[FrequentTank]]:
        raw_html = fetch_player_stats_html(player_name)
        return self.parser.parse_player_stats(raw_html, player_name)
