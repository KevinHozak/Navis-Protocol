import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from services import operation_outcomes as ops
from services import sync_engine


def test_receipt_write_retries_only_bounded_windows_sharing_failures(tmp_path, monkeypatch):
    original = ops._atomic_json
    calls = []
    error = PermissionError("synthetic Windows sharing lock")
    error.winerror = 32

    def transient(path, value):
        calls.append(1)
        if len(calls) < 3:
            raise error
        return original(path, value)

    monkeypatch.setattr(ops, "_atomic_json", transient)
    monkeypatch.setattr(ops.time, "sleep", lambda _: None)
    path = tmp_path / "receipt.json"
    ops.atomic_json(path, {"status": "partial"})
    assert len(calls) == 3
    assert json.loads(path.read_text(encoding="utf-8-sig"))["status"] == "partial"

    def permanent(*args):
        calls.append(1)
        raise error

    calls.clear()
    monkeypatch.setattr(ops, "_atomic_json", permanent)
    with pytest.raises(PermissionError):
        ops.atomic_json(path, {})
    assert len(calls) == 8
    error.winerror = None
    calls.clear()
    with pytest.raises(PermissionError):
        ops.atomic_json(path, {})
    assert len(calls) == 1


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / "Bridge").mkdir()
    (tmp_path / "Journal").mkdir()
    monkeypatch.setenv("NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(tmp_path))
    return tmp_path


def fake_backup(root, fail=False, crash=False):
    def backup(log_callback=None):
        ops.step("work")
        latest = json.loads((root / "Bridge/.navis_operations/latest.json").read_text(encoding="utf-8-sig"))["job_id"]
        record = json.loads((root / f"Bridge/.navis_operations/{latest}.json").read_text(encoding="utf-8-sig"))
        if record:
            assert record["steps"][0]["status"] == "running"
        marker = root / "Journal/synthetic.md"
        marker.write_text(marker.read_text() + "saved\n" if marker.exists() else "saved\n")
        ops.committed()
        if crash:
            raise KeyboardInterrupt("synthetic interrupted process")
        if fail:
            ops.failure()
        ops.step("xp")
        ops.step("watch")
        ops.note("FIXTURE MODE: integration disabled")
        ops.step("backup")
    return backup


def test_completed_report_and_duplicate_identity_never_replays(root, monkeypatch):
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root))
    result = ops.run_operation(root, "sync", "job")
    assert result["status"] == "completed"
    assert result["steps"][0]["persistence"] == "confirmed"
    assert result["steps"][2]["status"] == "skipped"
    saved = (root / "Journal/synthetic.md").read_bytes()
    assert ops.run_operation(root, "sync", "job") == result
    assert (root / "Journal/synthetic.md").read_bytes() == saved
    assert ops.read_operation(root, "job")["status"] == "completed"


def test_partial_work_is_retained_and_rollover_not_started(root, monkeypatch):
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root, fail=True))
    monkeypatch.setattr(sync_engine, "run_midnight_rollover", lambda **kwargs: pytest.fail("must not start rollover"))
    result = ops.run_operation(root, "rollover", "job")
    assert result["status"] == "partial"
    assert result["steps"][0]["status"] == "failed"
    assert result["steps"][0]["persistence"] == "confirmed"
    assert result["changes_may_have_committed"]
    assert result["recovery"] == "review_saved_changes"
    assert any(s["id"] == "journals" and s["status"] == "not_run" for s in result["steps"])
    assert ops.run_operation(root, "rollover", "job")["status"] == "partial"
    with pytest.raises(ops.OperationBusy):
        ops.run_operation(root, "sync", "next")
    before = (root / "Journal/synthetic.md").read_bytes()
    ops.acknowledge(root, "job")
    assert (root / "Journal/synthetic.md").read_bytes() == before
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root))
    assert ops.run_operation(root, "sync", "next")["status"] == "completed"


def test_restart_exposes_uncertain_commit_and_blocks_automatic_replay(root, monkeypatch):
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root, crash=True))
    with pytest.raises(KeyboardInterrupt):
        ops.run_operation(root, "sync", "job")
    result = ops.read_operation(root, "job")
    assert result["status"] == "interrupted"
    assert result["steps"][0]["status"] == "unknown"
    assert result["steps"][0]["persistence"] == "confirmed"
    assert ops.run_operation(root, "sync", "job")["status"] == "interrupted"
    assert (root / "Journal/synthetic.md").read_text().count("saved") == 1


def test_operation_lock_prevents_cross_process_overlap(root):
    script = "from services.operation_outcomes import operation_lock; import sys;\nwith operation_lock(sys.argv[1]): pass"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    with ops.operation_lock(root):
        with pytest.raises(ops.OperationBusy):
            with ops.operation_lock(root):
                pytest.fail("overlap allowed")
        result = subprocess.run([sys.executable, "-c", script, str(root)], env=env, capture_output=True, timeout=10)
        assert result.returncode != 0
        assert b"OperationBusy" in result.stderr


@pytest.mark.parametrize("message", ["⚠️ XP ERROR: secret content", "❌ GIT ERROR", "Error: missing settings", "Missing state"])
def test_legacy_error_strings_fail_without_persisting_content(root, monkeypatch, message):
    def backup(log_callback=None):
        ops.step("work")
        ops.note(message)
    monkeypatch.setattr(sync_engine, "execute_git_backup", backup)
    result = ops.run_operation(root, "sync", "job")
    assert result["status"] == "partial"
    assert message not in json.dumps(result)


def test_conflicting_kind_corrupt_record_and_invalid_paths_fail_closed(root, monkeypatch):
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root))
    ops.run_operation(root, "sync", "job")
    with pytest.raises(ValueError):
        ops.run_operation(root, "rollover", "job")
    with pytest.raises(ValueError):
        ops.read_operation(root, "../outside")
    (root / "Bridge/.navis_operations/latest.json").write_text("broken")
    with pytest.raises(ValueError):
        ops.run_operation(root, "sync", "next")


def test_native_status_bridge_and_http_survive_memory_loss(root, monkeypatch):
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root, fail=True))
    ops.run_operation(root, "sync", "job")
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(backend / "native_operation_status.py")],
                            input=json.dumps({"path": "/api/ops/jobs/job"}), text=True,
                            env=os.environ.copy(), capture_output=True, timeout=10)
    envelope = json.loads(result.stdout)
    assert envelope["status"] == 200 and envelope["body"]["status"] == "partial"
    import main
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    monkeypatch.setattr(main, "active_jobs", {})
    assert asyncio.run(main.get_ops_job_status("job"))["status"] == "partial"


def test_async_duplicate_request_does_not_queue_again(root, monkeypatch):
    from fastapi import BackgroundTasks
    import main
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    monkeypatch.setattr(main, "active_jobs", {})
    tasks = BackgroundTasks()
    first = asyncio.run(main.execute_sync(True, tasks, "same"))
    second = asyncio.run(main.execute_sync(True, tasks, "same"))
    assert first == second
    assert len(tasks.tasks) == 1


def test_unavailable_vault_has_no_mutation(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        ops.run_operation(missing, "sync", "job")
    assert not missing.exists()


def test_reserved_identity_and_runtime_root_mismatch(root, monkeypatch):
    with pytest.raises(ValueError):
        ops.run_operation(root, "sync", "LATEST")
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(root / "other"))
    result = ops.run_operation(root, "sync", "job")
    assert result["status"] == "failed"
    assert not result["changes_may_have_committed"]


def test_saved_identity_kind_conflict_rejected_before_queue_after_restart(root, monkeypatch):
    from fastapi import BackgroundTasks, HTTPException
    import main
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root))
    ops.run_operation(root, "sync", "job")
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    monkeypatch.setattr(main, "active_jobs", {})
    tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.journal_rollover(True, tasks, "job"))
    assert error.value.status_code == 409 and not tasks.tasks
    asyncio.run(main.execute_sync(True, tasks, "job"))
    assert not tasks.tasks


def test_real_work_merge_reports_retained_unmerged_items(root, monkeypatch):
    work = root / "work.md"
    work.write_text("## 2026-10-01\n- Unmerged synthetic item\n", encoding="utf-8")
    (root / "Bridge/settings.json").write_text(json.dumps({"paths": {"office_work_log": str(work)}}))
    (root / "Bridge/status.json").write_text(json.dumps({"last_updated": "2026-10-01"}))
    monkeypatch.setattr(sync_engine, "SETTINGS_FILE", str(root / "Bridge/settings.json"))
    original = sync_engine.sync_work_journal
    def backup(log_callback=None):
        ops.step("work")
        original()
    monkeypatch.setattr(sync_engine, "execute_git_backup", backup)
    result = ops.run_operation(root, "sync", "job")
    assert result["status"] == "partial"
    assert result["steps"][0]["status"] == "failed"
    assert "Unmerged synthetic item" in work.read_text()


def test_review_cannot_acknowledge_active_write_and_never_replays(root, monkeypatch):
    import main
    monkeypatch.setattr(sync_engine, "execute_git_backup", fake_backup(root, fail=True))
    ops.run_operation(root, "sync", "job")
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    before = (root / "Journal/synthetic.md").read_bytes()
    with ops.operation_lock(root):
        with pytest.raises(ops.OperationBusy):
            ops.acknowledge(root, "job")
    reviewed = asyncio.run(main.review_ops_job("job"))
    assert reviewed["reviewed"] and reviewed["status"] == "partial"
    assert ops.read_latest(root)["job_id"] == "job"
    assert (root / "Journal/synthetic.md").read_bytes() == before
