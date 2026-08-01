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
    candidates = await search_account_candidates(player_name)
    if len(candidates) != 1:
        return None
    return await bind_account(send_id, candidates[0])


def _parse_account_candidates(payload: object) -> list[AccountInfo]:
    """将官网搜索响应转换为可供用户选择的账号列表。"""
    if not isinstance(payload, dict):
        return []
    response = payload.get("response")
    if not isinstance(response, list):
        return []

    candidates: list[AccountInfo] = []
    seen_ids: set[str] = set()
    for item in response:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("account_id") or "").strip()
        account_name = str(item.get("account_name") or "").strip()
        if not account_id or not account_name or account_id in seen_ids:
            continue
        seen_ids.add(account_id)
        candidates.append(
            AccountInfo(
                account_id=account_id,
                account_name=account_name,
                account_battles=int(item.get("account_battles") or 0),
                clan_tag=str(item.get("clan_tag") or "无"),
            )
        )
    return candidates


async def search_account_candidates(player_name: str) -> list[AccountInfo]:
    """搜索官网玩家账号；多个模糊结果交由命令层让用户选择。"""
    if len(player_name) > 14 or len(player_name) < 4:
        logger.info("用户名必须在 4 和 14 个字符之间")
        return []

    try:
        resp = await fetch_account_search(player_name)
        if getattr(resp, "status", 200) != 200:
            raise ValueError(f"账号搜索接口 HTTP {resp.status}")
        resp_dict = await resp.json()
        return _parse_account_candidates(resp_dict)
    except Exception as exc:
        logger.error(f"搜索绑定玩家失败: {exc}")
        return []


async def bind_account(send_id: str, account_info: AccountInfo) -> AccountInfo:
    """写入用户明确选择的玩家账号。"""
    await write_binding_data(
        send_id, account_info.account_name, account_info.account_id
    )
    logger.info(account_info.__str__())
    return account_info


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
        candidates = _parse_account_candidates(resp_dict)
        normalized_name = player_name.casefold()
        exists = any(
            candidate.account_name.casefold() == normalized_name
            for candidate in candidates
        )
    except Exception as exc:
        logger.info(f"玩家存在性校验失败: {exc}")
        return None

    with _player_exists_lock:
        if len(_player_exists_cache) >= _EXISTS_CACHE_MAX_ENTRIES:
            _player_exists_cache.clear()
        _player_exists_cache[player_name] = (time.time(), exists)
    return exists
