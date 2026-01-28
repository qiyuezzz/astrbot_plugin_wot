import requests
from typing import Optional

from data.plugins.astrbot_plugin_wot.src.http.request_context import BaseConfig

class RequestContext:
    def __init__(self):
        self.session_map: dict[str, requests.Session] = {}

    def get_session(self, key: str) -> requests.Session:
        if key not in self.session_map:
            self.session_map[key] = requests.Session()
        return self.session_map[key]

class HttpClient:

    def __init__(self):
        self.ctx = RequestContext()

    def send_get(self, config: BaseConfig,params=None) -> Optional[requests.Response]:

        # 1️⃣ 确定 requester
        if config.use_session:
            key = config.base_url.split("/")[2]
            session = self.ctx.get_session(key)
            requester = session
        else:
            requester = requests

        # 2️⃣ 预热（只做一次）
        if config.use_session and config.warmup_url:
            if not getattr(config, "_warmed", False):
                requester.get(config.warmup_url)
                config._warmed = True

        # 3️⃣ 构造 headers / params
        headers = config.build_headers()
        params = params

        # 4️⃣ 自动注入 CSRF
        if config.need_csrf and requester is not requests:
            csrf = requester.cookies.get("csrftoken")
            if csrf:
                headers.setdefault("X-CSRFToken", csrf)

        # 5️⃣ 发送请求
        resp = requester.get(
            url=config.base_url,
            headers=headers,
            params=params,
            timeout=config.DEFAULT_TIMEOUT,
        )

        resp.raise_for_status()
        return resp
