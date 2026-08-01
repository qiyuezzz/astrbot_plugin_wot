from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wotbox_camp_api import (
    fetch_user_search,
)

_SEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60
_SEARCH_CACHE_MAX_ENTRIES = 2048
_search_cache: dict[str, tuple[float, "AccountLookup | None"]] = {}
_search_lock = threading.Lock()


@dataclass(frozen=True)
class AccountLookup:
    """玩家名称与账号 ID 的解析结果。"""

    player_name: str
    account_id: str


async def search_player_account(player_name: str) -> AccountLookup | None:
    """通过坦克营地搜索玩家，返回账号信息；未找到返回 None。

    网络/接口异常会向上抛出，由调用方决定错误提示。结果缓存 24 小时。
    """
    now = time.time()
    with _search_lock:
        cached = _search_cache.get(player_name)
        if cached and now - cached[0] < _SEARCH_CACHE_TTL_SECONDS:
            return cached[1]

    users = await fetch_user_search(player_name)
    normalized_name = player_name.casefold()
    exact = next(
        (
            user
            for user in users
            if str(user.get("nickname") or "").casefold() == normalized_name
        ),
        None,
    )
    if exact is not None:
        result = AccountLookup(
            player_name=str(exact.get("nickname") or player_name),
            account_id=str(exact.get("account_id") or ""),
        )
        if not result.account_id:
            logger.warning(f"坦克营地搜索结果缺少 account_id: {exact}")
            result = None
    else:
        result = None

    with _search_lock:
        if len(_search_cache) >= _SEARCH_CACHE_MAX_ENTRIES:
            _search_cache.clear()
        _search_cache[player_name] = (time.time(), result)
    return result
