from __future__ import annotations

from data.plugins.astrbot_plugin_wot.src.services.tank_sync_service import sync_tank_info


def sync_all_tank_info():
    """Sync full tank info with official + WotInspector."""
    return sync_tank_info()
