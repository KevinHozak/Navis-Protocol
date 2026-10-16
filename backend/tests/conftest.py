"""Set a disposable default Vault before service imports and deny real sockets."""
import os
import socket
import tempfile
import threading
from pathlib import Path

import pytest


_vault = tempfile.TemporaryDirectory(prefix="navis-pytest-vault-")
_previous_root = os.environ.get("NAVIS_ROOT")
os.environ["NAVIS_ROOT"] = _vault.name
for directory in ("Bridge", "Journal", "Keeper", "Companions"):
    (Path(_vault.name) / directory).mkdir()


def pytest_unconfigure(config):
    if _previous_root is None:
        os.environ.pop("NAVIS_ROOT", None)
    else:
        os.environ["NAVIS_ROOT"] = _previous_root
    _vault.cleanup()


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    # TestClient uses an in-process ASGI transport. Providers must use fakes.
    local = threading.local()
    original_pair = socket.socketpair
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def pair(*args, **kwargs):
        # Windows implements asyncio's private wakeup socketpair with loopback.
        local.creating_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            local.creating_pair = False

    def guard(original):
        def blocked(*args, **kwargs):
            if getattr(local, "creating_pair", False):
                return original(*args, **kwargs)
            raise AssertionError("Real network access is disabled in the test suite")
        return blocked

    monkeypatch.setattr(socket, "socketpair", pair)
    monkeypatch.setattr(socket.socket, "connect", guard(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(original_connect_ex))
