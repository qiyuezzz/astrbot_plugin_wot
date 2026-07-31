from __future__ import annotations

import asyncio
import threading

import aiohttp

from data.plugins.astrbot_plugin_wot.src.infrastructure.network.request_context import (
    BaseConfig,
)

_session_lock = threading.Lock()
_shared_sessions: dict[asyncio.AbstractEventLoop, aiohttp.ClientSession] = {}
_session_warmups: dict[aiohttp.ClientSession, set[str]] = {}


def get_shared_session() -> aiohttp.ClientSession:
    """返回当前事件循环共享的 aiohttp Session，复用连接池。"""
    loop = asyncio.get_running_loop()
    with _session_lock:
        session = _shared_sessions.get(loop)
        if session is None or session.closed:
            session = aiohttp.ClientSession()
            _shared_sessions[loop] = session
            _session_warmups[session] = set()
        return session


async def close_shared_session() -> None:
    """关闭当前事件循环共享的 Session。"""
    loop = asyncio.get_running_loop()
    with _session_lock:
        session = _shared_sessions.pop(loop, None)
        if session is not None:
            _session_warmups.pop(session, None)
    if session and not session.closed:
        await session.close()


class HttpResponse:
    """封装 HTTP 响应，确保数据在上下文退出后仍可访问"""

    def __init__(self, status: int, headers: dict, body: bytes):
        self.status = status
        self.headers = headers
        self._body = body

    async def text(self) -> str:
        return self._body.decode("utf-8", errors="replace")

    async def json(self):
        import json

        return json.loads(self._body)

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=None,
                history=(),
                status=self.status,
                message=f"HTTP {self.status}",
            )


class HttpClient:
    """基于 aiohttp 的异步 HTTP 客户端（按事件循环复用 Session）"""

    def __init__(self, timeout: float | None = None):
        self._session: aiohttp.ClientSession | None = None
        self._timeout = aiohttp.ClientTimeout(
            total=timeout if timeout is not None else BaseConfig.DEFAULT_TIMEOUT
        )

    async def __aenter__(self):
        self._session = get_shared_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Session 由所属事件循环在退出时统一关闭
        return False

    async def _prepare_headers(self, config: BaseConfig) -> dict:
        headers = config.build_headers()

        if config.warmup_url:
            with _session_lock:
                warmed = config.warmup_url in _session_warmups.get(
                    self._session, set()
                )
            if not warmed:
                async with self._session.get(
                    config.warmup_url,
                    timeout=self._timeout,
                    ssl=config.verify_ssl,
                ) as response:
                    await response.read()
                with _session_lock:
                    _session_warmups.setdefault(self._session, set()).add(
                        config.warmup_url
                    )

        if config.need_csrf:
            async with self._session.get(
                config.warmup_url,
                timeout=self._timeout,
                ssl=config.verify_ssl,
            ) as response:
                await response.read()
            csrf = self._session.cookie_jar.filter_cookies(config.warmup_url).get(
                "csrftoken"
            )
            if csrf:
                headers.setdefault("X-CSRFToken", csrf.value)

        return headers

    async def send_get(self, config: BaseConfig, params: dict | None = None):
        headers = await self._prepare_headers(config)
        async with self._session.get(
            url=config.base_url,
            headers=headers,
            params=params,
            timeout=self._timeout,
            ssl=config.verify_ssl,
        ) as resp:
            body = await resp.read()
            return HttpResponse(resp.status, dict(resp.headers), body)

    async def send_post(
        self,
        config: BaseConfig,
        *,
        params: dict | None = None,
        data: dict | None = None,
        json_data: dict | None = None,
    ):
        headers = await self._prepare_headers(config)
        async with self._session.post(
            url=config.base_url,
            headers=headers,
            params=params,
            data=data,
            json=json_data,
            timeout=self._timeout,
            ssl=config.verify_ssl,
        ) as resp:
            body = await resp.read()
            return HttpResponse(resp.status, dict(resp.headers), body)
