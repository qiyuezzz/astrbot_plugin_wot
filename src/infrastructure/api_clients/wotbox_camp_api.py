from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time

import aiohttp
from Crypto.Cipher import DES

from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    get_shared_session,
)

# 坦克营地（WoT Box）主 API，算法来自对 APK 的逆向分析：
# sign = MD5(排序参数 + API_SECRET)，响应使用 DES/CBC 加密
API_SECRET = "1q7gdwugf283rfh9u3hr982"
DES_IV = "85631247"
BASE_URL = "https://tbox.wot.360.cn"
USER_AGENT = "okhttp/3.10.0"

_PUBLIC_PARAMS = {
    "platform": "1",
    "v": "259002",
    "ch": "ch_oppo",
    "sk": "35",
    "md": "SM-S9110",
    "brand": "Samsung",
    "m1": "06e70fdce2c29d6f61c7686111fa1890",
    "m2": "06e70fdce2c29d6f61c7686111fa1890",
    "m3": "06e70fdce2c29d6f61c7686111fa1890",
    "nt": "1",
    "oaid": "",
}

# 限制对营地 API 的总并发，避免请求过于集中
_CAMP_SEMAPHORE = asyncio.Semaphore(4)


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _generate_sign(params: dict) -> str:
    """按 key 升序拼接参数并追加 API_SECRET 后取 MD5。"""
    filtered = {
        key: value
        for key, value in params.items()
        if key not in ("sign", "_callback") and value not in (None, "")
    }
    raw = "&".join(f"{key}={filtered[key]}" for key in sorted(filtered))
    return _md5(raw + API_SECRET)


def build_signed_params(extra: dict | None = None) -> dict:
    """构造带公共参数和 sign 的请求参数。"""
    params = dict(_PUBLIC_PARAMS)
    params["_t"] = str(int(time.time() * 1000))
    if extra:
        params.update(extra)
    params["sign"] = _generate_sign(params)
    return params


def _des_decrypt(encrypted_b64: str, sign: str) -> str:
    """DES/CBC/PKCS5 解密，密钥为 MD5(sign)[6:14]。"""
    key = _md5(sign)[6:14].encode("ascii")
    raw = base64.b64decode(encrypted_b64)
    decrypted = DES.new(key, DES.MODE_CBC, DES_IV.encode("ascii")).decrypt(raw)
    pad_len = decrypted[-1]
    return decrypted[:-pad_len].decode("utf-8", errors="replace")


def parse_response(body: str, sign: str) -> dict:
    """解析响应：部分接口返回明文 JSON，部分返回 DES 加密的 Base64。"""
    stripped = body.strip()
    if stripped.startswith(("{", "[")):
        return json.loads(stripped)
    try:
        return json.loads(_des_decrypt(stripped, sign))
    except Exception:
        # 兜底：明文 JSON（例如带 BOM 或前后空白的情况）
        return json.loads(stripped)


async def _request(path: str, params: dict) -> dict:
    async with _CAMP_SEMAPHORE:
        signed_params = build_signed_params(params)
        session = get_shared_session()
        async with session.get(
            BASE_URL + path,
            params=signed_params,
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            body = await resp.text()

    if resp.status != 200:
        raise ValueError(f"坦克营地接口 HTTP {resp.status}")

    payload = parse_response(body, signed_params["sign"])
    if payload.get("errno") != 0:
        raise ValueError(
            f"坦克营地接口错误 {payload.get('errno')}: {payload.get('errmsg')}"
        )
    return payload.get("data") or {}


async def fetch_user_search(nickname: str) -> list[dict]:
    """搜索玩家，返回 [{account_id, nickname, ...}]。"""
    data = await _request("/user/search", {"nickname": nickname, "size": "10"})
    return data.get("list") or []


async def fetch_garage(account_id: str, page: int = 1, page_size: int = 200) -> dict:
    """获取玩家车库单页数据（不带 tankid 时返回全部坦克）。"""
    return await _request(
        "/tank/singleVehicleStat",
        {"accountId": account_id, "pn": str(page), "psize": str(page_size)},
    )


async def fetch_garage_all(
    account_id: str, max_pages: int = 5
) -> tuple[str, list[dict], int]:
    """分页拉取玩家全部坦克，返回 (昵称, 坦克列表, 总场次)。"""
    entries: list[dict] = []
    nick_name = ""
    total = 0
    page = 1
    while page <= max_pages:
        data = await fetch_garage(account_id, page=page)
        user_info = data.get("userInfo") or {}
        nick_name = user_info.get("nick_name") or nick_name
        v_battles = data.get("vBattles") or {}
        total = int(v_battles.get("total") or len(entries))
        entries.extend(v_battles.get("list") or [])
        if not v_battles.get("next"):
            break
        page += 1
    return nick_name, entries, total


async def fetch_moe_ranking(
    tank_type: str,
    tier: str,
    percentile: int,
    page: int = 1,
    size: int = 100,
    max_pages: int = 10,
) -> list[dict]:
    """获取完整环线排行榜，percentile: 65=一环, 85=二环, 95=三环。"""
    ranking: list[dict] = []
    current_page = page
    for _ in range(max_pages):
        data = await _request(
            "/rank/more",
            {
                "rank_type": "mastery",
                "type": tank_type,
                "tier": str(tier),
                "size": str(size),
                "page": str(current_page),
                "sort": "mastery",
                "percentile": str(percentile),
            },
        )
        ranking.extend(data.get("ranking") or [])
        if not data.get("next"):
            break
        current_page += 1
    return ranking


async def fetch_tank_wiki_summary(tank_id: int | str) -> dict:
    """获取坦克百科摘要（名称、等级、类型和车辆图片）。"""
    data = await _request(
        "/wiki/app_vehicles",
        {"page_no": "1", "length": "10", "tankId": str(tank_id)},
    )
    vehicles = data.get("data") or []
    return vehicles[0] if vehicles else {}


async def fetch_tank_wiki_profile(tank_id: int | str) -> dict:
    """获取坦克营地完整百科参数。"""
    return await _request("/wiki/app_vehiclesprofile", {"tankId": str(tank_id)})
