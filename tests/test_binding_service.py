import pytest

from data.plugins.astrbot_plugin_wot.src.application import binding_service
from data.plugins.astrbot_plugin_wot.src.application.binding_service import (
    player_exists,
)


@pytest.mark.asyncio
async def test_player_exists_returns_false_for_invalid_length():
    assert await player_exists("ab") is False
    assert await player_exists("x" * 20) is False


@pytest.mark.asyncio
async def test_player_exists_returns_none_on_network_error(monkeypatch):
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(binding_service, "fetch_account_search", _raise)
    assert await player_exists("Tester") is None


@pytest.mark.asyncio
async def test_player_exists_caches_result(monkeypatch):
    calls = {"count": 0}

    class _FakeResponse:
        async def json(self):
            return {"response": [{"account_name": "Tester"}]}

    async def _fake_search(_player_name: str):
        calls["count"] += 1
        return _FakeResponse()

    monkeypatch.setattr(binding_service, "fetch_account_search", _fake_search)
    binding_service._player_exists_cache.clear()

    assert await player_exists("Tester") is True
    assert await player_exists("Tester") is True
    assert calls["count"] == 1
    binding_service._player_exists_cache.clear()


@pytest.mark.asyncio
async def test_player_exists_retries_after_cache_ttl_expiry(monkeypatch):
    calls = {"count": 0}

    class _FakeResponse:
        async def json(self):
            return {"response": [{"account_name": "Tester"}]}

    async def _fake_search(_player_name: str):
        calls["count"] += 1
        return _FakeResponse()

    monkeypatch.setattr(binding_service, "fetch_account_search", _fake_search)
    binding_service._player_exists_cache.clear()

    assert await player_exists("Tester") is True
    binding_service._player_exists_cache["Tester"] = (
        0.0,
        True,  # 模拟缓存过期
    )
    assert await player_exists("Tester") is True
    assert calls["count"] == 2
    binding_service._player_exists_cache.clear()
