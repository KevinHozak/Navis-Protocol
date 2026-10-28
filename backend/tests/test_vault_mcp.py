"""Disposable-file policy tests and real stdio process acceptance for S017."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import pytest

from services.vault_access import MAX_FILE_BYTES, VaultAccessError, VaultPolicy, read_markdown_source, read_note


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "fixture-vault"
    root.mkdir()
    (root / "Journal").mkdir()
    (root / "Documentation").mkdir()
    (root / "Documentation" / "fixture.md").write_bytes(b"\xef\xbb\xbf# Fixture\r\nalpha\r\n## Detail\r\nbeta\r\n")
    return root


def config(root, **extra):
    return {"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "America/Chicago", **extra}


def error_code(policy, args):
    with pytest.raises(VaultAccessError) as found:
        read_note(policy, args)
    return found.value.code


def test_read_is_live_source_linked_and_does_not_mutate(vault):
    path = vault / "Documentation" / "fixture.md"
    before = path.read_bytes()
    policy = VaultPolicy.from_env(config(vault))
    got = read_note(policy, {"path": "Documentation/fixture.md", "max_lines": 2})
    assert got["data"]["content"] == "# Fixture\r\nalpha\r\n"
    assert (got["data"]["start_line"], got["data"]["end_line"]) == (1, 2)
    assert got["data"]["sha256"] == hashlib.sha256(before).hexdigest()
    assert got["data"]["path"] == "Documentation/fixture.md"
    assert got["data"]["heading"] == "Fixture"
    assert got["continuation"] == {"start_line": 3, "start_column": 0}
    assert got["coverage"]["missing_roots"] == ["Operations", "Codex"]
    assert path.read_bytes() == before
    path.write_text("changed", encoding="utf-8")
    assert read_note(policy, {"path": "Documentation/fixture.md"})["data"]["content"] == "changed"


@pytest.mark.parametrize("path", [
    "../outside.md", "%2e%2e/outside.md", "Documentation/%2e%2e/Bridge/status.md",
    "/etc/private.md", "C:/private.md", "C:private.md", r"\\host\share\private.md",
    "Documentation/fixture.md:stream", "Documentation/fixture.md.", "Documentation/fixture.md ",
    "Documentation/NUL.md", "Documentation/COM1.md", "Documentation/.hidden.md",
    "Documentation/.git/fixture.md", "Documentation/credentials.md", "Documentation/secret.md",
    "Documentation/fixture.backup.md", "Documentation/config.md", "Bridge/status.md",
    "Documentation/fixture.json", "Documentation/fi\x00xture.md", "Documentation/fi\nxture.md",
    "Documentation/PRIVATE~1/note.md", "Documentation/CONIN$.md",
    "Documentation//fixture.md", "Documentation/./fixture.md", "Documentation/missing.md",
])
def test_denied_and_missing_paths_are_indistinguishable(vault, path):
    assert error_code(VaultPolicy.from_env(config(vault)), {"path": path}) == "not_found"


@pytest.mark.parametrize("args", [
    {"path": "Documentation/fixture.md", "overwrite": True},
    {"path": "Documentation/fixture.md", "max_lines": 201},
    {"path": "Documentation/fixture.md", "max_lines": True},
    {"path": "Documentation/fixture.md", "start_line": "1"},
    {"path": "Documentation/fixture.md", "start_column": -1}, {},
])
def test_arguments_fail_closed(vault, args):
    assert error_code(VaultPolicy.from_env(config(vault)), args) == "invalid_argument"


def test_custom_allowlist_and_denied_subtree(vault):
    policy = VaultPolicy.from_env(config(vault, NAVIS_MCP_ALLOWED_ROOTS='["Documentation"]',
                                       NAVIS_MCP_DENIED_PATHS='["Documentation/fixture.md"]'))
    assert error_code(policy, {"path": "Documentation/fixture.md"}) == "not_found"
    policy = VaultPolicy.from_env(config(vault, NAVIS_MCP_ALLOWED_ROOTS='["Journal"]'))
    assert error_code(policy, {"path": "Documentation/fixture.md"}) == "not_found"


@pytest.mark.parametrize("change", [
    {"NAVIS_ROOT": ""}, {"NAVIS_ROOT": "relative"}, {"NAVIS_MCP_TIMEZONE": ""},
    {"NAVIS_MCP_TIMEZONE": "Not/AZone"}, {"NAVIS_MCP_ALLOWED_ROOTS": "[]"},
    {"NAVIS_MCP_ALLOWED_ROOTS": '["../escape"]'}, {"NAVIS_MCP_ALLOWED_ROOTS": '"Journal"'},
    {"NAVIS_MCP_ALLOWED_ROOTS": "not json"},
])
def test_invalid_configuration(vault, change):
    with pytest.raises(VaultAccessError, match="invalid_configuration"):
        VaultPolicy.from_env(config(vault, **change))


def test_vault_unavailable_before_start_and_between_calls(vault):
    policy = VaultPolicy.from_env(config(vault))
    moved = vault.with_name("moved-vault")
    vault.rename(moved)
    assert error_code(policy, {"path": "Documentation/fixture.md"}) == "vault_unavailable"
    with pytest.raises(VaultAccessError, match="vault_unavailable"):
        VaultPolicy.from_env(config(vault))
    moved.rename(vault)
    assert read_note(policy, {"path": "Documentation/fixture.md"})["status"] == "ok"


def _link(directory, target):
    try:
        directory.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi
        _winapi.CreateJunction(str(target), str(directory))


def test_links_and_junctions_are_denied_inside_and_outside_root(vault, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "fixture.md").write_text("outside synthetic", encoding="utf-8")
    policy = VaultPolicy.from_env(config(vault))
    for name, target in (("out", outside), ("inside", vault / "Documentation")):
        link = vault / "Journal" / name
        _link(link, target)
        try:
            assert error_code(policy, {"path": f"Journal/{name}/fixture.md"}) == "not_found"
        finally:
            if link.is_symlink():
                link.unlink()
            else:
                link.rmdir()  # Only the disposable junction, never its target.
    assert (outside / "fixture.md").read_text(encoding="utf-8") == "outside synthetic"
    alias = tmp_path / "alias-root"
    _link(alias, vault)
    try:
        with pytest.raises(VaultAccessError, match="vault_unavailable"):
            VaultPolicy.from_env(config(alias))
    finally:
        if alias.is_symlink():
            alias.unlink()
        else:
            alias.rmdir()


def test_large_encoding_changed_and_deadline_errors(vault, monkeypatch):
    path = vault / "Documentation" / "fixture.md"
    policy = VaultPolicy.from_env(config(vault))
    path.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    assert error_code(policy, {"path": "Documentation/fixture.md"}) == "file_too_large"
    path.write_bytes(b"\xff")
    assert error_code(policy, {"path": "Documentation/fixture.md"}) == "unsupported_encoding"
    path.write_text("old", encoding="utf-8")
    original = Path.open

    def changing(file, *args, **kwargs):
        if file == path and args == ("rb",):
            file.write_text("changed longer", encoding="utf-8")
        return original(file, *args, **kwargs)

    monkeypatch.setattr(Path, "open", changing)
    assert error_code(policy, {"path": "Documentation/fixture.md"}) == "source_changed"
    with pytest.raises(VaultAccessError, match="deadline_exceeded"):
        read_note(policy, {"path": "Documentation/fixture.md"}, deadline=time.monotonic() - 1)


def test_sections_and_lossless_long_line_continuation(vault):
    path = vault / "Documentation" / "fixture.md"
    policy = VaultPolicy.from_env(config(vault))
    assert read_note(policy, {"path": "Documentation/fixture.md", "section": "Detail"})["data"]["content"] == "## Detail\r\nbeta\r\n"
    assert error_code(policy, {"path": "Documentation/fixture.md", "section": "Absent"}) == "section_not_found"
    text = '\\"🐱' * 14000 + "\r\nnext\r\n"
    path.write_text(text, encoding="utf-8", newline="")
    args, pieces = {"path": "Documentation/fixture.md"}, []
    from navis_vault_mcp import _result
    for _ in range(30):
        result = read_note(policy, args)
        assert len(_result(result).model_dump_json(by_alias=True).encode("utf-8")) < 64 * 1024
        pieces.append(result["data"]["content"])
        if result["continuation"] is None:
            break
        args.update(result["continuation"])
    else:
        pytest.fail("continuation did not make progress")
    assert "".join(pieces) == text
    assert read_note(policy, {"path": "Documentation/fixture.md", "start_line": 100})["continuation"] is None


def test_empty_notes_unicode_physical_lines_and_duplicate_headings(vault):
    path = vault / "Documentation" / "fixture.md"
    policy = VaultPolicy.from_env(config(vault))
    path.write_bytes(b"")
    empty = read_note(policy, {"path": "Documentation/fixture.md"})
    assert empty["data"]["start_line"] is empty["data"]["end_line"] is empty["continuation"] is None
    path.write_text("a\u2028b\n# Twice\n# Twice\n", encoding="utf-8", newline="")
    assert read_note(policy, {"path": "Documentation/fixture.md", "max_lines": 1})["data"]["content"] == "a\u2028b\n"
    assert error_code(policy, {"path": "Documentation/fixture.md", "section": "Twice"}) == "invalid_argument"


def test_timeout_returns_error_and_server_stays_responsive(vault, monkeypatch):
    import anyio
    from mcp import Client
    import navis_vault_mcp as adapter

    def stalled(*args, **kwargs):
        time.sleep(0.1)
        raise RuntimeError("synthetic private error must not escape")

    monkeypatch.setattr(adapter, "read_note", stalled)
    monkeypatch.setattr(adapter, "CALL_TIMEOUT_SECONDS", 0.02)

    async def exercise():
        async with Client(adapter.create_server(VaultPolicy.from_env(config(vault)))) as client:
            got = await client.call_tool("read_note", {"path": "Documentation/fixture.md"})
            assert got.is_error and got.structured_content["error"]["code"] == "deadline_exceeded"
            assert (await client.list_tools()).tools[0].name == "read_note"

    anyio.run(exercise)


def test_exhaustive_scan_budget_does_not_extend_note_deadlines(vault, monkeypatch):
    import anyio
    from mcp import Client
    import navis_vault_mcp as adapter

    def scan(*args, **kwargs):
        assert kwargs["deadline"] - time.monotonic() > 0.5
        time.sleep(0.04)
        return {"status": "ok", "data": {"matches": []}}

    def note(*args, **kwargs):
        time.sleep(0.04)
        return {"status": "ok", "data": {}}

    monkeypatch.setenv("NAVIS_MCP_SCAN_TIMEOUT_SECONDS", "1")
    monkeypatch.setattr(adapter, "CALL_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(adapter, "search_vault", scan)
    monkeypatch.setattr(adapter, "read_note", note)

    async def exercise():
        async with Client(adapter.create_server(VaultPolicy.from_env(config(vault)))) as client:
            assert not (await client.call_tool("search_vault", {"query": "fixture"})).is_error
            result = await client.call_tool("read_note", {"path": "Documentation/fixture.md"})
            assert result.is_error and result.structured_content["error"]["code"] == "deadline_exceeded"

    anyio.run(exercise)


class Wire:
    """Raw stdio peer with bounded waits; protocol stdout is parsed, never printed."""
    def __init__(self, env):
        self.proc = subprocess.Popen([sys.executable, str(Path(__file__).parents[1] / "navis_vault_mcp.py")],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", env={**os.environ, **env})
        self.messages = queue.Queue()
        self.seen = []
        self.counter = 0

        def reader():
            for line in self.proc.stdout:
                self.messages.put(line)
            self.messages.put(None)

        threading.Thread(target=reader, daemon=True).start()

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def call(self, method, params=None):
        self.counter += 1
        self.send({"jsonrpc": "2.0", "id": self.counter, "method": method, **({"params": params} if params is not None else {})})
        for _ in range(20):
            line = self.messages.get(timeout=15)
            assert line is not None, "stdio child ended before responding"
            result = json.loads(line)
            self.seen.append(result)
            if result.get("id") == self.counter:
                return result
        raise AssertionError("missing response")

    def start(self):
        result = self.call("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                         "clientInfo": {"name": "synthetic-fixture", "version": "1"}})
        assert "error" not in result
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
            raise AssertionError("stdio child did not exit after EOF")
        return self.proc.stderr.read()


def test_stdio_handshake_read_unknown_args_unavailable_reconnect_no_logs(vault):
    sentinel = "SYNTHETIC_PRIVATE_SENTINEL"
    note = vault / "Documentation" / "fixture.md"
    note.write_text(sentinel, encoding="utf-8")
    original = {p.relative_to(vault): p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    for attempt in range(2):
        wire = Wire(config(vault, NAVIS_API_KEY="synthetic-test-credential", LOG_LEVEL="DEBUG"))
        try:
            init = wire.start()
            assert set(init["result"]["capabilities"]) == {"tools"}
            tools = wire.call("tools/list")["result"]["tools"]
            assert [t["name"] for t in tools] == ["read_note", "search_vault", "get_journal_range", "get_mission"]
            assert tools[0]["annotations"]["readOnlyHint"] is True
            assert tools[0]["inputSchema"]["additionalProperties"] is False
            result = wire.call("tools/call", {"name": "read_note", "arguments": {"path": "Documentation/fixture.md"}})["result"]
            assert result["structuredContent"]["data"]["content"] == sentinel
            assert not result["isError"]
            for name, args, code in (
                ("append_journal_entry", {}, "unknown_tool"),
                ("read_note", {"path": "Documentation/fixture.md", "overwrite": sentinel}, "invalid_argument"),
                ("read_note", {"path": "../outside.md"}, "not_found"),
            ):
                denied = wire.call("tools/call", {"name": name, "arguments": args})["result"]
                assert denied["isError"] and denied["structuredContent"]["error"]["code"] == code
                assert sentinel not in json.dumps(denied)
            if attempt == 0:
                moved = vault.with_name("temporarily-unavailable")
                vault.rename(moved)
                try:
                    got = wire.call("tools/call", {"name": "read_note", "arguments": {"path": "Documentation/fixture.md"}})
                    assert got["result"]["structuredContent"]["error"]["code"] == "vault_unavailable"
                finally:
                    moved.rename(vault)
            assert "error" not in wire.call("ping")
            wire.proc.stdin.write('{"private_synthetic_payload":"' + sentinel + '"\n')
            wire.proc.stdin.flush()
            assert "error" not in wire.call("ping")
            for frame in wire.seen:
                if "error" in frame:
                    assert sentinel not in json.dumps(frame)
        finally:
            logs = wire.close()
            assert wire.proc.returncode == 0
            assert sentinel not in logs and str(vault) not in logs and "synthetic-test-credential" not in logs
        assert {p.relative_to(vault): p.read_bytes() for p in vault.rglob("*") if p.is_file()} == original


def test_stdio_note_read_uses_shared_bounded_source_reader(vault):
    relative = "Documentation/fixture.md"
    note = vault / relative
    note.write_bytes(b"\xef\xbb\xbf# Shared\r\nFixture source\r\n")
    expected = read_markdown_source(VaultPolicy.from_env(config(vault)), relative)
    before = {p.relative_to(vault): p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    wire = Wire(config(vault))
    try:
        wire.start()
        result = wire.call("tools/call", {"name": "read_note", "arguments": {"path": relative}})["result"]
        assert not result["isError"]
        assert result["structuredContent"]["data"]["content"] == expected["content"]
        assert result["structuredContent"]["data"]["sha256"] == expected["sha256"]
    finally:
        logs = wire.close()
        assert wire.proc.returncode == 0 and logs == "", (wire.proc.returncode, logs)
    assert {p.relative_to(vault): p.read_bytes() for p in vault.rglob("*") if p.is_file()} == before


def test_stdio_invalid_startup_sanitizes_paths(vault):
    env = {**os.environ, **config(vault / "missing")}
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / "navis_vault_mcp.py")],
                            input="", text=True, encoding="utf-8", capture_output=True, env=env, timeout=15)
    assert result.returncode == 2 and result.stdout == ""
    assert result.stderr.strip() == "navis-vault-mcp: vault_unavailable"


def test_import_does_not_start_portal_or_create_files(vault):
    code = "import sys; import navis_vault_mcp; assert 'main' not in sys.modules; assert 'services.sync_engine' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1],
                            env={**os.environ, **config(vault)}, capture_output=True, timeout=15)
    assert result.returncode == 0 and result.stdout == result.stderr == b""
