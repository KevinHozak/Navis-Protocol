"""Cross-transport contract checks for shared Vault Markdown reads."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from io import StringIO

from fastapi.testclient import TestClient
import pytest

import main
from services.vault_access import (
    VaultAccessError,
    VaultPolicy,
    application_note_policy,
    read_markdown_source,
    read_note,
)
import native_vault_note


def _files(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_http_native_and_mcp_read_one_unchanged_fixture_through_shared_service(tmp_path, monkeypatch):
    root = tmp_path
    source = root / "Journal/2026/10/2026-10-27.md"
    source.parent.mkdir(parents=True)
    original = b"\xef\xbb\xbf# Fixture\r\nShared source caf\xc3\xa9\r\n"
    source.write_bytes(original)
    relative = "Journal/2026/10/2026-10-27.md"
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    env = {"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "UTC"}
    policy = VaultPolicy.from_env(env)
    before = _files(root)

    shared = read_markdown_source(policy, relative)
    assert shared["content"] == "# Fixture\r\nShared source café\r\n"
    assert shared["sha256"] == hashlib.sha256(original).hexdigest()

    http = TestClient(main.app).get("/api/vault/" + relative)
    assert http.status_code == 200
    assert http.json() == {
        "content": "# Fixture\r\nShared source café\r\n",
        "source_content": "# Fixture\r\nShared source café\r\n",
        "path": relative,
    }

    backend = Path(__file__).resolve().parents[1]
    native_env = os.environ.copy()
    native_env.update(env)
    native_env["PYTHONPATH"] = str(backend)
    native = subprocess.run(
        [sys.executable, "-B", "native_vault_note.py"],
        cwd=backend,
        env=native_env,
        input=json.dumps({"path": "/api/vault/" + relative}),
        text=True,
        capture_output=True,
        check=True,
    )
    native_result = json.loads(native.stdout)
    assert native_result == {
        "status": 200,
        "body": {"content": shared["content"], "path": relative},
    }

    mcp = read_note(policy, {"path": relative, "max_lines": 20})
    assert mcp["status"] == "ok"
    assert mcp["data"]["content"] == shared["content"]
    assert mcp["data"]["sha256"] == shared["sha256"]
    assert _files(root) == before


def test_shared_read_keeps_mcp_scope_and_leaves_other_app_markdown_on_existing_path(tmp_path, monkeypatch):
    root = tmp_path
    shared = root / "Journal/2026/10/2026-10-27.md"
    outside = root / "Companions/Fixture/Profile.md"
    shared.parent.mkdir(parents=True)
    outside.parent.mkdir(parents=True)
    shared.write_text("Shared fixture", encoding="utf-8")
    outside.write_text("App-only fixture", encoding="utf-8")
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))

    app_only = TestClient(main.app).get("/api/vault/Companions/Fixture/Profile.md")
    assert app_only.status_code == 200
    assert app_only.json()["source_content"] == "App-only fixture"

    env = {"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "UTC"}
    policy = VaultPolicy.from_env(env)
    with pytest.raises(VaultAccessError) as error:
        read_note(policy, {"path": "Companions/Fixture/Profile.md"})
    assert error.value.code == "not_found"


def test_missing_shared_note_keeps_each_transport_not_found_behavior(tmp_path, monkeypatch):
    root = tmp_path
    (root / "Journal").mkdir()
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    relative = "Journal/missing.md"

    with pytest.raises(VaultAccessError) as missing:
        read_markdown_source(application_note_policy(root), relative)
    assert missing.value.code == "not_found"
    assert TestClient(main.app).get("/api/vault/" + relative).status_code == 404

    native_env = os.environ.copy()
    native_env["NAVIS_ROOT"] = str(root)
    native_env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    native = subprocess.run(
        [sys.executable, "-B", "native_vault_note.py"],
        cwd=Path(__file__).resolve().parents[1], env=native_env,
        input=json.dumps({"path": "/api/vault/" + relative}),
        text=True, capture_output=True, check=True,
    )
    assert json.loads(native.stdout)["status"] == 404

    with pytest.raises(VaultAccessError) as mcp_missing:
        read_note(VaultPolicy.from_env({"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "UTC"}), {"path": relative})
    assert mcp_missing.value.code == "not_found"


def test_unreadable_shared_note_maps_to_each_transport_error(tmp_path, monkeypatch):
    root = tmp_path
    note = root / "Journal/2026/10/note.md"
    note.parent.mkdir(parents=True)
    note.write_text("synthetic fixture", encoding="utf-8")
    relative = "Journal/2026/10/note.md"
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    original_open = Path.open

    def deny_fixture(path, *args, **kwargs):
        if path == note:
            raise PermissionError("synthetic unreadable fixture")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_fixture)
    http = TestClient(main.app).get("/api/vault/" + relative)
    assert http.status_code == 500
    assert http.json() == {"detail": "Resource unavailable"}

    monkeypatch.setattr(sys, "stdin", StringIO(json.dumps({"path": "/api/vault/" + relative})))
    native_output = StringIO()
    monkeypatch.setattr(sys, "stdout", native_output)
    native_vault_note.main()
    assert json.loads(native_output.getvalue()) == {
        "status": 500, "body": {"detail": "Resource unavailable"}
    }

    with pytest.raises(VaultAccessError) as mcp_unreadable:
        read_note(
            VaultPolicy.from_env({"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "UTC"}),
            {"path": relative},
        )
    assert mcp_unreadable.value.code == "source_unreadable"
