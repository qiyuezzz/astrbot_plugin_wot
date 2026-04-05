from __future__ import annotations

from data.plugins.astrbot_plugin_wot.src.application.binding_service import (
    bind_user_name,
    player_exists,
)
from data.plugins.astrbot_plugin_wot.src.application.message_parser import (
    extract_at_target_id,
)
from data.plugins.astrbot_plugin_wot.src.domain.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.bindings_repository import (
    read_binding_data,
)
from data.plugins.astrbot_plugin_wot.src.settings.message import (
    CheckBindMsg,
    WotBindMsg,
)


async def resolve_player_name(
    send_id: str,
    message_chain: list,
    explicit_name: str | None,
    self_id: str | None = None,
) -> tuple[str | None, str | None]:
    """解析最终要查询的玩家名称

    优先级：显式名称 > @目标绑定 > 发送者自身绑定
    返回 (player_name, error_code)，error_code 为 None 表示成功
    """
    at_target = extract_at_target_id(message_chain, self_id)
    if explicit_name:
        if at_target:
            target_name = read_binding_data(at_target)
            if not target_name:
                return None, "target_unbound"
            return target_name, None
        if explicit_name.startswith("@"):
            return None, "at_text_only"
        if not await player_exists(explicit_name):
            return None, "player_not_found"
        return explicit_name, None

    if at_target:
        target_name = read_binding_data(at_target)
        if not target_name:
            return None, "target_unbound"
        return target_name, None

    self_name = read_binding_data(send_id)
    if not self_name:
        return None, "self_unbound"
    return self_name, None


def error_message(err: str) -> str:
    """根据错误码返回用户友好的提示文案"""
    if err == "at_text_only":
        return "未识别到有效@，请直接输入玩家名称或@已绑定用户"
    if err == "player_not_found":
        return "玩家不存在，请检查名称是否正确"
    if err == "target_unbound":
        return "对方未绑定游戏名称，请先绑定"
    if err == "self_unbound":
        return CheckBindMsg.failed()
    return "查询失败，请稍后再试"


async def execute_bind(send_id: str, message_str: str) -> str:
    """执行玩家绑定操作"""
    from data.plugins.astrbot_plugin_wot.src.application.message_parser import (
        extract_player_name,
    )

    player_name = extract_player_name(message_str)
    if not player_name:
        return WotBindMsg.invalid()

    account_info: AccountInfo | None = await bind_user_name(send_id, player_name)
    if account_info:
        return WotBindMsg.success(account_info)
    return WotBindMsg.fail(player_name)
