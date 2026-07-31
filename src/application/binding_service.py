from __future__ import annotations

import threading
import time

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_game_api import (
    fetch_account_search,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.bindings_repository import (
    write_binding_data,
)

_EXISTS_CACHE_TTL_SECONDS = 24 * 60 * 60
_EXISTS_CACHE_MAX_ENTRIES = 2048
_player_exists_cache: dict[str, tuple[float, bool]] = {}
_player_exists_lock = threading.Lock()


async def bind_user_name(send_id: str, player_name: str) -> AccountInfo | None:
    """绑定玩家名称到用户ID"""
    if len(player_name) > 14 or len(player_name) < 4:
        logger.info("用户名必须在 4 和 14 个字符之间")
        return None

    try:
        resp = await fetch_account_search(player_name)
        resp_dict = await resp.json()
        if resp_dict.get("response"):
            data = resp_dict["response"][0]
            filtered_data = {
                key: value
                for key, value in data.items()
                if key in AccountInfo.__annotations__
            }
            account_info = AccountInfo(**filtered_data)
            logger.info(account_info.__str__())
            await write_binding_data(send_id, account_info.account_name)
            return account_info

        logger.info("未找到该用户")
        return None
    except Exception as exc:
        logger.error(f"绑定玩家失败: {exc}")
        return None


async def player_exists(player_name: str) -> bool | None:
    """检查玩家名称是否存在于游戏中

    返回 True/False 表示校验结果；返回 None 表示网络异常、结果未知。
    校验结果缓存 24 小时，避免每次查询都额外发起一次官网搜索请求。
    """
    if len(player_name) > 14 or len(player_name) < 4:
        return False

    now = time.time()
    with _player_exists_lock:
        cached = _player_exists_cache.get(player_name)
        if cached and now - cached[0] < _EXISTS_CACHE_TTL_SECONDS:
            return cached[1]

    try:
        resp = await fetch_account_search(player_name)
        resp_dict = await resp.json()
        exists = bool(resp_dict.get("response"))
    except Exception as exc:
        logger.info(f"玩家存在性校验失败: {exc}")
        return None

    with _player_exists_lock:
        if len(_player_exists_cache) >= _EXISTS_CACHE_MAX_ENTRIES:
            _player_exists_cache.clear()
        _player_exists_cache[player_name] = (time.time(), exists)
    return exists
