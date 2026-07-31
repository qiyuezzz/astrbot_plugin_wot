import base64
import hashlib
import json

import pytest
from Crypto.Cipher import DES

from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients import (
    wotbox_camp_api,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wotbox_camp_api import (
    API_SECRET,
    DES_IV,
    _generate_sign,
    parse_response,
)


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def test_generate_sign_sorts_params_and_appends_secret():
    sign = _generate_sign({"b": "2", "a": "1", "sign": "ignored", "empty": ""})
    assert sign == _md5("a=1&b=2" + API_SECRET)


def test_generate_sign_excludes_empty_values():
    sign = _generate_sign({"a": "", "b": "x"})
    assert sign == _md5("b=x" + API_SECRET)


def test_parse_response_accepts_plain_json():
    payload = parse_response('{"errno":0,"data":{"x":1}}', "whatever")
    assert payload == {"errno": 0, "data": {"x": 1}}


def test_parse_response_decrypts_des_body():
    payload = {"errno": 0, "errmsg": "ok", "data": {"list": [{"a": 1}]}}
    sign = _generate_sign({"nickname": "玩家", "size": "10"})
    key = _md5(sign)[6:14].encode("ascii")
    plain = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    pad_len = 8 - len(plain) % 8
    padded = plain + bytes([pad_len]) * pad_len
    encrypted = DES.new(key, DES.MODE_CBC, DES_IV.encode("ascii")).encrypt(padded)
    body = base64.b64encode(encrypted).decode("ascii")

    assert parse_response(body, sign) == payload


def test_build_signed_params_includes_sign_and_timestamp():
    params = wotbox_camp_api.build_signed_params({"nickname": "玩家"})
    assert params["nickname"] == "玩家"
    assert params["sign"] == _generate_sign(params)
    assert params["_t"].isdigit()


@pytest.mark.asyncio
async def test_fetch_moe_ranking_returns_ranking(monkeypatch):
    async def _fake_request(*_args, **_kwargs):
        return {"ranking": []}

    monkeypatch.setattr(wotbox_camp_api, "_request", _fake_request)
    ranking = await wotbox_camp_api.fetch_moe_ranking("mediumTank", "9", 95)
    assert ranking == []


@pytest.mark.asyncio
async def test_fetch_moe_ranking_fetches_all_pages(monkeypatch):
    requested_pages: list[str] = []

    async def _fake_request(_path, params):
        requested_pages.append(params["page"])
        if params["page"] == "1":
            return {"ranking": [{"tank_id": 1}], "next": 1}
        return {"ranking": [{"tank_id": 49, "mastery": 2460}], "next": 0}

    monkeypatch.setattr(wotbox_camp_api, "_request", _fake_request)

    ranking = await wotbox_camp_api.fetch_moe_ranking("mediumTank", "8", 95)

    assert requested_pages == ["1", "2"]
    assert ranking == [
        {"tank_id": 1},
        {"tank_id": 49, "mastery": 2460},
    ]


@pytest.mark.asyncio
async def test_fetch_tank_wiki_summary_returns_first_vehicle(monkeypatch):
    async def _fake_request(path, params):
        assert path == "/wiki/app_vehicles"
        assert params["tankId"] == "49"
        return {"data": [{"tank_id": 49, "tanke_image": "tank.png"}]}

    monkeypatch.setattr(wotbox_camp_api, "_request", _fake_request)
    summary = await wotbox_camp_api.fetch_tank_wiki_summary(49)
    assert summary == {"tank_id": 49, "tanke_image": "tank.png"}


@pytest.mark.asyncio
async def test_fetch_tank_wiki_profile_uses_profile_endpoint(monkeypatch):
    async def _fake_request(path, params):
        assert path == "/wiki/app_vehiclesprofile"
        assert params == {"tankId": "49"}
        return {"tank_id": 49, "tank_info_list": []}

    monkeypatch.setattr(wotbox_camp_api, "_request", _fake_request)
    profile = await wotbox_camp_api.fetch_tank_wiki_profile("49")
    assert profile["tank_id"] == 49
