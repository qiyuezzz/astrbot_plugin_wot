from __future__ import annotations

import aiohttp

from data.plugins.astrbot_plugin_wot.src.infrastructure.network.request_context import (
    BaseConfig,
)


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
    """基于 aiohttp 的异步 HTTP 客户端（复用 Session）"""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None
        self._timeout = aiohttp.ClientTimeout(total=BaseConfig.DEFAULT_TIMEOUT)

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
            self._session = None
        return False

    async def _prepare_headers(self, config: BaseConfig) -> dict:
        headers = config.build_headers()

        if config.warmup_url:
            if not getattr(config, "_warmed", False):
                await self._session.get(
                    config.warmup_url,
                    timeout=self._timeout,
                    ssl=False,
                )
                config._warmed = True

        if config.need_csrf:
            await self._session.get(
                config.warmup_url,
                timeout=self._timeout,
                ssl=False,
            )
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
            ssl=False,
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
            ssl=False,
        ) as resp:
            body = await resp.read()
            return HttpResponse(resp.status, dict(resp.headers), body)
