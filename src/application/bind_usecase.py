from __future__ import annotations

from data.plugins.astrbot_plugin_wot.src.domain.models.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.services.bindings_service import account_bind


async def bind_user_name(send_id: str, player_name: str) -> AccountInfo | None:
    """Bind a player name to a user id."""
    return await account_bind(send_id, player_name)
