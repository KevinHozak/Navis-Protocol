"""Guarded append acceptance uses disposable Vaults only."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from services import journal_entry as service
from services.vault_access import VaultAccessError, VaultPolicy


@pytest.fixture
def target(tmp_path):
    path = tmp_path / "Journal/2026/10/2026-10-26.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Day\n## 🏰 The Sanctum\n- [ ] Before\n\n## 🏠 The Domestic Breach\nunchanged\n", encoding="utf-8")
    return tmp_path, path


def request(path, **extra):
    return {"date": "2026-10-26", "section": "sanctum", "entry": "Completed fixture work",
            "request_id": "fixture-request-00001", "expected_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **extra}


def noop(*args):
    pass


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_preserves_all_original_bytes_and_replays(target, bom, newline):
    root, path = target
    original = bom + path.read_text(encoding="utf-8").replace("\n", newline).encode()
    path.write_bytes(original)
    args = request(path, entry="Unicode café 🌟")
    saved = service.append(root, args, guarded=True, award=noop)
    first = path.read_bytes()
    addition = (newline + "- [x] Unicode café 🌟" + newline).encode()
    assert first.replace(addition, b"", 1) == original
    assert saved["sha256"] == hashlib.sha256(first).hexdigest()
    again = service.append(root, args, guarded=True, award=noop)
    assert again["replayed"] and path.read_bytes() == first


def test_conflicts_duplicates_and_invalid_arguments_are_nonmutating(target):
    root, path = target
    args = request(path)
    path.write_bytes(path.read_bytes() + b"editor change\n")
    with pytest.raises(service.JournalError, match="source_changed"):
        service.append(root, args, guarded=True, award=noop)
    args = request(path)
    service.append(root, args, guarded=True, award=noop)
    original = path.read_bytes()
    for changed, code in (({**args, "entry": "different"}, "request_id_conflict"),
                          (request(path, request_id="fixture-request-00002"), "duplicate_entry"),
                          ({**args, "entry": "item\n## injected"}, "invalid_argument"),
                          ({**args, "date": "2026-02-30"}, "invalid_argument"),
                          ({**args, "section": "other"}, "invalid_argument"),
                          ({**args, "overwrite": True}, "invalid_argument")):
        with pytest.raises(service.JournalError, match=code):
            service.append(root, changed, guarded=True, award=noop)
        assert path.read_bytes() == original


def test_concurrent_distinct_requests_with_same_hash_only_one_saves(target):
    root, path = target
    a = request(path)
    b = {**a, "request_id": "fixture-request-00002", "entry": "Other completed item"}
    def run(args):
        try:
            return service.append(root, args, guarded=True, award=noop)["saved"]
        except service.JournalError as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(run, [a, b]))
    assert outcomes.count(True) == 1 and outcomes.count("source_changed") == 1
    assert path.read_text(encoding="utf-8").count("- [x]") == 1


@pytest.mark.parametrize("point", ["before_replace", "after_replace", "before_ack"])
def test_interrupted_write_recovers_exactly_once(target, monkeypatch, point):
    root, path = target
    args = request(path)
    original_atomic, original_record = service.atomic_bytes, service.atomic_json
    def interrupted(path_arg, data):
        if point == "before_replace":
            raise OSError("synthetic interruption")
        original_atomic(path_arg, data)
        raise OSError("synthetic interruption")
    def record(path_arg, data):
        if point == "before_ack" and data["phase"] == "saved":
            raise OSError("synthetic interruption")
        original_record(path_arg, data)
    with monkeypatch.context() as patch:
        patch.setattr(service, "atomic_json", record)
        if point != "before_ack":
            patch.setattr(service, "atomic_bytes", interrupted)
        with pytest.raises(OSError):
            service.append(root, args, guarded=True, award=noop)
    result = service.append(root, args, guarded=True, award=noop)
    assert result["saved"] and path.read_text(encoding="utf-8").count("- [x]") == 1


def test_xp_pending_retries_only_sync_and_preserves_later_edits(target):
    root, path = target
    args = request(path)
    def fail(*args):
        raise RuntimeError("synthetic projection unavailable")
    assert service.append(root, args, guarded=True, award=fail)["status"] == "saved_xp_pending"
    path.write_bytes(path.read_bytes() + b"later editor text\n")
    current = path.read_bytes()
    seen = []
    result = service.append(root, args, guarded=True, award=lambda *v: seen.append(v[2]))
    assert result["xp_status"] == "complete" and "later editor text" in seen[0]
    assert path.read_bytes() == current


def test_missing_unavailable_denied_and_invalid_encoding_never_create_journal(target):
    root, path = target
    args = request(path)
    policy = VaultPolicy.from_env({"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "UTC", "NAVIS_MCP_ALLOWED_ROOTS": '["Documentation"]'})
    with pytest.raises(VaultAccessError, match="not_found"):
        service.append(root, args, policy=policy, guarded=True, award=noop)
    assert not (root / "Battle").exists()
    path.write_bytes(b"\xffunsupported")
    with pytest.raises(VaultAccessError):
        service.append(root, args, guarded=True, award=noop)
    path.unlink()
    with pytest.raises(VaultAccessError, match="not_found"):
        service.append(root, args, guarded=True, award=noop)
    assert not path.exists()
    with pytest.raises(OSError):
        service.append(root / "unavailable", args, guarded=True, award=noop)


def test_real_ledger_projection_retry_does_not_duplicate_xp(target, monkeypatch):
    from services import progression_db as db, rpg_engine
    root, path = target
    monkeypatch.setattr(db, "NAVIS_ROOT", str(root))
    monkeypatch.setattr(db, "DB_PATH", str(root / "Keeper/navis_progression.db"))
    monkeypatch.setattr(rpg_engine, "NAVIS_ROOT", str(root))
    (root / "Bridge").mkdir()
    (root / "Bridge/status.json").write_text(json.dumps({"squad": [], "last_updated": "2026-10-26"}), encoding="utf-8")
    (root / "Bridge/CompanionStats.json").write_text(json.dumps({"companions": {"Keeper": {}}}), encoding="utf-8")
    args = request(path)
    with monkeypatch.context() as patch:
        patch.setattr(db, "_project_entity", lambda *a, **k: (_ for _ in ()).throw(OSError("synthetic projection failure")))
        assert service.append(root, args, guarded=True)["xp_status"] == "pending"
    total = db.get_total_xp("keeper")
    assert total == 12
    assert service.append(root, args, guarded=True)["xp_status"] == "complete"
    assert db.get_total_xp("keeper") == total
    assert "12 XP" in (root / "Keeper/XP.md").read_text(encoding="utf-8-sig")
    assert path.read_text(encoding="utf-8").count("- [x]") == 1


def test_desktop_bridge_uses_shared_service(target):
    root, path = target
    args = request(path)
    script = Path(__file__).parents[1] / "native_journal_entry.py"
    for _ in range(2):
        result = subprocess.run([sys.executable, str(script)], input=json.dumps({"path": "/api/journal/entry", "body": args}),
                                env={**os.environ, "NAVIS_ROOT": str(root)}, text=True, encoding="utf-8", capture_output=True, timeout=20)
        envelope = json.loads(result.stdout)
        assert envelope["status"] == 200 and envelope["body"]["xp_status"] == "pending"
        assert result.stderr == ""
    assert path.read_text(encoding="utf-8").count("- [x]") == 1


def test_external_edit_before_replace_is_rejected(target, monkeypatch):
    root, path = target
    args = request(path)
    original = service.atomic_json
    def edit_after_intent(record_path, record):
        original(record_path, record)
        path.write_bytes(path.read_bytes() + b"external edit\n")
    monkeypatch.setattr(service, "atomic_json", edit_after_intent)
    with pytest.raises(service.JournalError, match="source_changed"):
        service.append(root, args, guarded=True, award=noop)
    assert b"external edit" in path.read_bytes() and b"- [x]" not in path.read_bytes()


def test_ambiguous_crash_recovery_never_guesses_or_reappends(target, monkeypatch):
    root, path = target
    args = request(path)
    original = service.atomic_bytes
    def saved_then_crashed(target, raw):
        original(target, raw)
        raise OSError("synthetic crash")
    with monkeypatch.context() as patch:
        patch.setattr(service, "atomic_bytes", saved_then_crashed)
        with pytest.raises(OSError):
            service.append(root, args, guarded=True, award=noop)
    path.write_bytes(path.read_bytes() + b"changed after crash\n")
    current = path.read_bytes()
    with pytest.raises(service.JournalError, match="recovery_required"):
        service.append(root, args, guarded=True, award=noop)
    assert path.read_bytes() == current


def test_atomic_replace_failure_cleans_only_own_temp(target, monkeypatch):
    from services import combat_completion
    root, path = target
    args = request(path)
    original = path.read_bytes()
    unrelated = path.parent / ".other-editor.tmp"
    unrelated.write_bytes(b"preserve")
    real_replace = combat_completion.os.replace
    def fail_replace(source, destination):
        if Path(destination) == path:
            raise OSError("synthetic Drive interruption")
        return real_replace(source, destination)
    with monkeypatch.context() as patch:
        patch.setattr(combat_completion.os, "replace", fail_replace)
        with pytest.raises(OSError):
            service.append(root, args, guarded=True, award=noop)
    assert path.read_bytes() == original and unrelated.read_bytes() == b"preserve"
    assert list(path.parent.glob(".2026-10-26.md.*")) == []
    assert service.append(root, args, guarded=True, award=noop)["saved"]


def test_opt_in_mcp_stdio_append_and_exact_retry(target):
    from test_vault_mcp import Wire
    root, path = target
    args = request(path)
    wire = Wire({"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "UTC", "NAVIS_MCP_ENABLE_JOURNAL_APPEND": "1"})
    try:
        wire.start()
        tools = wire.call("tools/list")["result"]["tools"]
        tool = next(t for t in tools if t["name"] == "append_journal_entry")
        assert tool["annotations"]["readOnlyHint"] is False
        assert tool["annotations"]["idempotentHint"] is True
        for _ in range(2):
            reply = wire.call("tools/call", {"name": "append_journal_entry", "arguments": args})["result"]
            assert not reply["isError"]
            assert reply["structuredContent"]["data"]["saved"]
            assert reply["structuredContent"]["data"]["xp_status"] == "pending"
            assert "content" not in reply["structuredContent"]["data"]
        assert path.read_text(encoding="utf-8").count("- [x]") == 1
    finally:
        assert wire.close() == ""


def test_fenced_fake_sections_and_unclosed_fences_are_not_append_targets(target):
    root, path = target
    for source in ("```md\n## 🏰 The Sanctum\n```\n", "## 🏰 The Sanctum\n```md\nunfinished\n"):
        path.write_text(source, encoding="utf-8")
        before = path.read_bytes()
        with pytest.raises(service.JournalError, match="section_"):
            service.append(root, request(path), guarded=True, award=noop)
        assert path.read_bytes() == before


def test_no_source_growth_past_shared_read_limit(target):
    root, path = target
    original = "## 🏰 The Sanctum\n".encode()
    path.write_bytes(original + b"a" * (service.MAX_FILE_BYTES - len(original)))
    before = path.read_bytes()
    with pytest.raises(service.JournalError, match="source_too_large"):
        service.append(root, request(path), guarded=True, award=noop)
    assert path.read_bytes() == before
