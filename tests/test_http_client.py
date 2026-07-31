import asyncio

from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    close_shared_session,
    get_shared_session,
)


def test_shared_session_is_isolated_by_event_loop():
    first_loop = asyncio.new_event_loop()
    second_loop = asyncio.new_event_loop()

    async def _get_session():
        return get_shared_session()

    try:
        first_session = first_loop.run_until_complete(_get_session())
        second_session = second_loop.run_until_complete(_get_session())

        assert first_session is not second_session
        assert first_session is first_loop.run_until_complete(_get_session())
        assert second_session is second_loop.run_until_complete(_get_session())
    finally:
        first_loop.run_until_complete(close_shared_session())
        second_loop.run_until_complete(close_shared_session())
        first_loop.close()
        second_loop.close()
