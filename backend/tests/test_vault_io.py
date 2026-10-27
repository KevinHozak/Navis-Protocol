"""Real read-only handles, short reads and fail-closed budget configuration."""
from contextlib import contextmanager
import io
import os

import pytest

from services import vault_io
from services.vault_access import VaultAccessError, _snapshot
from services.vault_limits import scan_timeout_seconds
from test_vault_mcp import config
from services.vault_access import VaultPolicy


def test_read_handle_preserves_bytes_is_readonly_and_never_creates(tmp_path):
    path = tmp_path / "café 雪.md"
    raw = b"\xef\xbb\xbf# Fixture\r\n" + "Unicode café 雪\r\n".encode()
    path.write_bytes(raw)
    with vault_io.read_binary(path) as stream:
        assert stream.read() == raw
        with pytest.raises((io.UnsupportedOperation, OSError)):
            stream.write(b"overwrite")
    assert path.read_bytes() == raw
    missing = tmp_path / "missing.md"
    with pytest.raises(FileNotFoundError):
        with vault_io.read_binary(missing):
            pass
    assert not missing.exists()


def test_snapshot_consumes_short_raw_reads_and_rejects_premature_eof(tmp_path):
    directory = tmp_path / "Documentation"
    directory.mkdir()
    raw = "# Fixture\r\nUnicode café 雪\r\n".encode()
    path = directory / "short.md"
    path.write_bytes(raw)
    policy = VaultPolicy.from_env(config(tmp_path))

    @contextmanager
    def short(path):
        with vault_io.read_binary(path) as stream:
            class Reader:
                def fileno(self):
                    return stream.fileno()
                def read(self, size):
                    return stream.read(min(size, 3))
            yield Reader()

    assert _snapshot(policy, "Documentation/short.md", opener=short)[1] == raw.decode()

    @contextmanager
    def premature(path):
        with vault_io.read_binary(path) as stream:
            class Reader:
                def fileno(self):
                    return stream.fileno()
                def read(self, size):
                    return b""
            yield Reader()

    with pytest.raises(VaultAccessError, match="source_changed"):
        _snapshot(policy, "Documentation/short.md", opener=premature)


@pytest.mark.skipif(os.name != "nt", reason="Windows handle semantics")
def test_native_open_failure_and_descriptor_conversion_release_handles(tmp_path, monkeypatch):
    import ctypes
    path = tmp_path / "fixture.md"
    path.write_bytes(b"fixture")
    closed = []
    close = vault_io._close_handle
    def track(handle):
        closed.append(handle)
        return close(handle)
    with monkeypatch.context() as patch:
        patch.setattr(vault_io, "_close_handle", track)
        def conversion_failed(*args):
            raise OSError("synthetic descriptor failure")
        patch.setattr(vault_io.msvcrt, "open_osfhandle", conversion_failed)
        with pytest.raises(OSError):
            with vault_io.read_binary(path):
                pass
    assert len(closed) == 1
    def denied(*args):
        ctypes.set_last_error(5)
        return vault_io._INVALID
    monkeypatch.setattr(vault_io, "_create_file", denied)
    with pytest.raises(PermissionError):
        with vault_io.read_binary(path):
            pass


def test_default_and_explicit_scan_budget():
    assert scan_timeout_seconds({}) == 10
    assert scan_timeout_seconds({"NAVIS_MCP_SCAN_TIMEOUT_SECONDS": "60"}) == 60
    assert scan_timeout_seconds({"NAVIS_MCP_SCAN_TIMEOUT_SECONDS": "120"}) == 120


@pytest.mark.parametrize("value", ["0", "121", "-1", "nan", "1.5", " 60", "9999", "６０", 60])
def test_invalid_scan_budget_is_rejected(value):
    with pytest.raises(VaultAccessError, match="invalid_configuration"):
        scan_timeout_seconds({"NAVIS_MCP_SCAN_TIMEOUT_SECONDS": value})
