import pytest
from unittest.mock import AsyncMock

from data.plugins.astrbot_plugin_wot.src.application import player_resolver
from data.plugins.astrbot_plugin_wot.src.application.player_resolver import (
    resolve_player_account,
)
from data.plugins.astrbot_plugin_wot.src.application.wotbox_account_service import (
    AccountLookup,
)
from data.plugins.astrbot_plugin_wot.src.application import wotbox_account_service


@pytest.mark.asyncio
async def test_resolve_player_account_explicit_name(monkeypatch):
    monkeypatch.setattr(
        player_resolver,
        "search_player_account",
        AsyncMock(return_value=AccountLookup("Tester", "12345")),
    )
    name, account_id, err = await resolve_player_account("10001", [], "Tester")
    assert (name, account_id, err) == ("Tester", "12345", None)


@pytest.mark.asyncio
async def test_resolve_player_account_bound_uses_stored_account_id(monkeypatch):
    class _Info:
        name = "已绑定玩家"
        account_id = "999"

    monkeypatch.setattr(player_resolver, "read_binding_info", lambda _sid: _Info())
    name, account_id, err = await resolve_player_account("10001", [], None)
    assert (name, account_id, err) == ("已绑定玩家", "999", None)


@pytest.mark.asyncio
async def test_resolve_player_account_bound_without_account_id_searches(
    monkeypatch,
):
    class _LegacyInfo:
        name = "老绑定"
        account_id = None

    monkeypatch.setattr(player_resolver, "read_binding_info", lambda _sid: _LegacyInfo())
    monkeypatch.setattr(
        player_resolver,
        "search_player_account",
        AsyncMock(return_value=AccountLookup("老绑定", "888")),
    )
    name, account_id, err = await resolve_player_account("10001", [], None)
    assert (name, account_id, err) == ("老绑定", "888", None)


@pytest.mark.asyncio
async def test_resolve_player_account_network_error(monkeypatch):
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(player_resolver, "search_player_account", _raise)
    name, account_id, err = await resolve_player_account("10001", [], "Tester")
    assert (name, account_id, err) == (None, None, "network_error")


@pytest.mark.asyncio
async def test_resolve_player_account_not_found(monkeypatch):
    monkeypatch.setattr(
        player_resolver, "search_player_account", AsyncMock(return_value=None)
    )
    name, account_id, err = await resolve_player_account("10001", [], "Nobody")
    assert (name, account_id, err) == (None, None, "player_not_found")


@pytest.mark.asyncio
async def test_resolve_player_account_self_unbound(monkeypatch):
    monkeypatch.setattr(player_resolver, "read_binding_info", lambda _sid: None)
    name, account_id, err = await resolve_player_account("10001", [], None)
    assert (name, account_id, err) == (None, None, "self_unbound")


@pytest.mark.asyncio
async def test_wotbox_search_does_not_fall_back_to_first_fuzzy_result(monkeypatch):
    async def _fake_search(_name):
        return [{"nickname": "Tester_One", "account_id": "123"}]

    monkeypatch.setattr(wotbox_account_service, "fetch_user_search", _fake_search)
    wotbox_account_service._search_cache.clear()

    assert await wotbox_account_service.search_player_account("Tester") is None
    wotbox_account_service._search_cache.clear()
