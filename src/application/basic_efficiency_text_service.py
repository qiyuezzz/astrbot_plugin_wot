from __future__ import annotations

from data.plugins.astrbot_plugin_wot.src.domain.report import PlayerStats
from data.plugins.astrbot_plugin_wot.src.infrastructure.gateways.wot_box_gateway import (
    WotBoxService,
)


def get_basic_efficiency_text(player_name: str) -> str:
    """Return plain text for the basic efficiency query command."""
    if not player_name:
        raise ValueError("玩家名称不能为空")

    wot_box_gateway = WotBoxService()
    player_stats, _ = wot_box_gateway.get_player_stats(player_name)
    if not player_stats:
        raise ValueError(f"获取玩家{player_name}基础统计信息失败")
    return format_basic_efficiency_text(player_stats)


def format_basic_efficiency_text(stats: PlayerStats) -> str:
    lines = [
        f"玩家：{stats.name}",
        f"更新时间：{stats.update_time or '未知'}",
        f"效率：{stats.power}（浮动：{stats.power_float or '0'}）",
        f"胜率：{stats.win_rate}",
        f"总场次：{stats.total_count}",
        f"命中率：{stats.hit_rate}",
        f"场均等级：{stats.avg_tier}",
        f"场均伤害：{stats.avg_damage}",
    ]
    return "\n".join(lines)
