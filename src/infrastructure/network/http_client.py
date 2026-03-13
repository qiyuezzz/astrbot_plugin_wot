import requests

from data.plugins.astrbot_plugin_wot.src.infrastructure.network.request_context import (
    BaseConfig,
)


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

    # =========================
    # 公共准备逻辑
    # =========================
    def _prepare_request(self, config: BaseConfig):
        # 1️⃣ requester
        if config.use_session:
            key = config.base_url.split("/")[2]
            requester = self.ctx.get_session(key)
        else:
            requester = requests

        # 2️⃣ warmup
        if config.use_session and config.warmup_url:
            if not getattr(config, "_warmed", False):
                requester.get(config.warmup_url)
                config._warmed = True

        # 3️⃣ headers
        headers = config.build_headers()

        # 4️⃣ csrf
        if config.need_csrf and requester is not requests:
            csrf = requester.cookies.get("csrftoken")
            if csrf:
                headers.setdefault("X-CSRFToken", csrf)

        return requester, headers

    # =========================
    # GET
    # =========================
    def send_get(
        self, config: BaseConfig, params: dict | None = None
    ) -> requests.Response | None:

        requester, headers = self._prepare_request(config)

        resp = requester.get(
            url=config.base_url,
            headers=headers,
            params=params,
            timeout=config.DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp

    # =========================
    # POST
    # =========================
    def send_post(
        self,
        config: BaseConfig,
        *,
        params: dict | None = None,
        data: dict | None = None,
        json: dict | None = None,
    ) -> requests.Response | None:

        requester, headers = self._prepare_request(config)

        resp = requester.post(
            url=config.base_url,
            headers=headers,
            params=params,  # url 参数（少见，但留着）
            data=data,  # form
            json=json,  # json body
            timeout=config.DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp
