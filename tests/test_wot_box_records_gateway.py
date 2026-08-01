import pytest

from data.plugins.astrbot_plugin_wot.src.domain.report import RecordsBasic
from data.plugins.astrbot_plugin_wot.src.infrastructure.gateways import (
    wot_box_records_gateway,
)


@pytest.mark.asyncio
async def test_paginated_fetch_continues_when_first_page_has_only_excluded_records(
    monkeypatch,
):
    pages = {
        1: [RecordsBasic("today-1", "1", "random", "200")],
        2: [RecordsBasic("yesterday-1", "1", "random", "90")],
        3: [],
    }
    visited = []

    async def _fetch(_player_name, page, *, http):
        visited.append(page)
        return {"page": page, "data": {"arenas": [1] if pages[page] else []}}

    monkeypatch.setattr(wot_box_records_gateway, "fetch_arena_page", _fetch)
    monkeypatch.setattr(
        wot_box_records_gateway,
        "parse_arena_list",
        lambda payload: pages[payload["page"]],
    )
    monkeypatch.setattr(wot_box_records_gateway.asyncio, "sleep", lambda _delay: _noop())

    records = await wot_box_records_gateway._paginated_fetch(
        "Tester",
        should_include=lambda record: int(record.start_time) <= 100,
        http=object(),
    )

    assert visited == [1, 2, 3]
    assert [record.arena_id for record in records] == ["yesterday-1"]


async def _noop():
    return None
