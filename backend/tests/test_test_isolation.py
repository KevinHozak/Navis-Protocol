"""Ensure accidental local/cloud requests fail while async tests still work."""
import asyncio
import socket

import pytest


@pytest.mark.parametrize("method", ["connect", "connect_ex"])
@pytest.mark.parametrize("address", [("127.0.0.1", 8000), ("192.0.2.1", 443)])
def test_socket_guard_blocks_local_and_external_services(method, address):
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="network access is disabled"):
            getattr(connection, method)(address)


def test_asyncio_internal_socketpair_remains_available():
    async def synthetic_operation():
        await asyncio.sleep(0)
        return "fixture"

    assert asyncio.run(synthetic_operation()) == "fixture"
