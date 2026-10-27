import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[1]
ENTRYPOINT = BACKEND / "native_operations.py"


@pytest.fixture
def fixture_root(tmp_path):
    return tmp_path


@pytest.fixture
def fixture_vault(fixture_root):
    vault = fixture_root / "vault"
    (vault / "Bridge").mkdir(parents=True)
    (vault / "Journal" / "2026" / "09").mkdir(parents=True)
    (vault / "Operations").mkdir()
    (vault / "Companions").mkdir()
    office_log = vault / "Daily_Work.md"
    office_log.write_text("## 2026-09-28\n- Fixture work item\n", encoding="utf-8-sig")
    settings = {
        "paths": {
            "office_work_log": str(office_log),
            "operations_dir": str(vault / "Operations"),
            "journal_root": str(vault / "Journal"),
            "chronicle_db": str(vault / "Bridge" / "Chronicle.db"),
            "status_manifold": str(vault / "Bridge" / "status.json"),
        },
        "readiness_thresholds": {},
    }
    (vault / "Bridge" / "settings.json").write_text(json.dumps(settings), encoding="utf-8-sig")
    (vault / "Bridge" / "status.json").write_text(
        json.dumps({"last_updated": "2026-09-28", "current_realm": "Fixture Realm", "squad": []}),
        encoding="utf-8-sig",
    )
    (vault / "Bridge" / "ops_state.json").write_text(json.dumps({"tasks": []}), encoding="utf-8-sig")
    (vault / "Bridge" / "CompanionStats.json").write_text(
        json.dumps({"companions": {"Keeper": {"xp": 0, "level": 1}}}),
        encoding="utf-8-sig",
    )
    (vault / "Journal" / "daily_template.md").write_text(
        "# {{DATE}}\n\n- **🌀 Realm:** {{REALM}}\n## 🛡️ The High-Velocity Front\n{{COMMANDER_TASKS}}\n",
        encoding="utf-8-sig",
    )
    (vault / "Journal" / "2026" / "09" / "2026-09-28.md").write_text(
        "# 2026-09-28\n## 🥾 The Kinetic Outland\n- [x] Fixture XP marker\n"
        "## 🛡️ The High-Velocity Front\n\n",
        encoding="utf-8-sig",
    )
    return vault, office_log, fixture_root / "fixture-git"


def run_native(vault, git_dir, operation):
    env = os.environ.copy()
    env.update(
        NAVIS_ROOT=str(vault),
        NAVIS_FIXTURE_GIT_DIR=str(git_dir),
        NAVIS_NATIVE_FIXTURE_MODE="1",
        PYTHONPATH=str(BACKEND),
        PYTHONIOENCODING="utf-8",
        GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="remote.origin.url",
        GIT_CONFIG_VALUE_0="https://invalid.example/should-not-be-used",
    )
    return subprocess.run(
        [sys.executable, str(ENTRYPOINT), operation],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )


def test_disconnected_vault_fails_before_mutation(fixture_root):
    vault = fixture_root / "disconnected"
    env = os.environ.copy()
    env.update(NAVIS_ROOT=str(vault), PYTHONPATH=str(BACKEND), PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(ENTRYPOINT), "sync"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        check=False,
    )
    assert result.returncode == 1
    assert "NAVIS_ROOT is unavailable" in result.stdout
    assert "complete" not in result.stdout.lower()
    assert not vault.exists()


def test_missing_vault_git_fails_instead_of_reporting_sync_success(fixture_root):
    vault = fixture_root / "vault"
    (vault / "Bridge").mkdir(parents=True)
    (vault / "Journal").mkdir()
    (vault / "Bridge" / "settings.json").write_text(
        json.dumps({"paths": {"office_work_log": str(vault / "Daily_Work.md")}}),
        encoding="utf-8-sig",
    )
    env = os.environ.copy()
    env.update(
        NAVIS_ROOT=str(vault),
        NAVIS_NATIVE_FIXTURE_MODE="1",
        PYTHONPATH=str(BACKEND),
        PYTHONIOENCODING="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ENTRYPOINT), "sync"], cwd=BACKEND, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=10, check=False,
    )
    assert result.returncode == 1
    assert "isolated NAVIS_FIXTURE_GIT_DIR" in result.stdout
    assert "complete" not in result.stdout.lower()
    assert not (vault / "Daily_Work.md").exists()


@pytest.mark.parametrize("operation", ["sync", "rollover"])
def test_fixture_operations_use_only_fixture_state(fixture_vault, operation):
    vault, office_log, git_dir = fixture_vault
    result = run_native(vault, git_dir, operation)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FIXTURE MODE: Jellyfin watch history integration disabled." in result.stdout
    assert "FIXTURE MODE: biometrics integration disabled." in result.stdout or operation == "sync"
    assert "C:\\ProgramData\\Jellyfin" not in result.stdout + result.stderr
    assert "C:\\Projects\\Agents" not in result.stdout + result.stderr
    assert "S:\\My Drive" not in result.stdout + result.stderr
    assert (git_dir / "HEAD").is_file()
    assert "Fixture work item" not in office_log.read_text(encoding="utf-8-sig")
    assert "Fixture work item" in (vault / "Journal/2026/09/2026-09-28.md").read_text(encoding="utf-8-sig")
    assert (vault / "Journal" / "2026" / "09" / "2026-09-28.md").is_file()
    if operation == "rollover":
        today = date.today().isoformat()
        today_path = vault / "Journal" / today[:4] / today[5:7] / f"{today}.md"
        status = json.loads((vault / "Bridge" / "status.json").read_text(encoding="utf-8-sig"))
        assert today_path.is_file()
        assert status["last_updated"] == today


def test_fixture_rejects_outside_office_log_before_mutation(fixture_vault, fixture_root):
    vault, office_log, git_dir = fixture_vault
    settings_path = vault / "Bridge" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    settings["paths"]["office_work_log"] = str(fixture_root / "outside.md")
    settings_path.write_text(json.dumps(settings), encoding="utf-8-sig")
    old_log = office_log.read_bytes()
    result = run_native(vault, git_dir, "sync")
    assert result.returncode == 1
    assert "must be inside NAVIS_ROOT" in result.stdout
    assert office_log.read_bytes() == old_log
    assert not git_dir.exists()


def test_completed_history_and_recurring_cadence_survive_native_restart(fixture_vault):
    from datetime import timedelta
    vault, _, git_dir = fixture_vault
    today = date.today()
    yesterday = today - timedelta(days=1)
    day = yesterday.isoformat()
    (vault / 'Bridge/status.json').write_text(json.dumps({'last_updated': day, 'squad': []}), encoding='utf-8-sig')
    previous = vault / f'Journal/{day[:4]}/{day[5:7]}/{day}.md'
    previous.parent.mkdir(parents=True, exist_ok=True)
    history = b'\xef\xbb\xbf' + (
        '# Completed history\r\n## 🛡️ The High-Velocity Front\r\n'
        '- [x] Finished one-off\r\n- [x] Weekly inspection\r\nKeep 雪\r\n').encode()
    previous.write_bytes(history)
    state = {'tasks': [
        {'id': 'weekly', 'text': 'Weekly inspection', 'frequency': 'weekly', 'area': 'Front',
         'last_done': day, 'next_due': (yesterday + timedelta(days=7)).isoformat()},
        {'id': 'daily', 'text': 'Due daily inspection', 'frequency': 'daily', 'area': 'Front',
         'last_done': day, 'next_due': today.isoformat()}],
        'active_tasks': [{'id': 'done', 'text': 'Finished one-off', 'status': 'completed', 'area': 'Front'}]}
    (vault / 'Bridge/ops_state.json').write_text(json.dumps(state), encoding='utf-8-sig')
    result = run_native(vault, git_dir, 'rollover')
    assert result.returncode == 0, result.stdout + result.stderr
    current = vault / f'Journal/{today:%Y}/{today:%m}/{today.isoformat()}.md'
    saved = current.read_bytes()
    assert saved.count(b'Due daily inspection') == 1
    assert b'Weekly inspection' not in saved
    assert b'Finished one-off' not in saved
    # The backup only stages Bridge/Journal/Companions. Exclude disposable
    # fixture outputs so unrelated untracked files do not trigger an empty commit.
    (git_dir / 'info/exclude').write_text('Daily_Work.md\nKeeper/\n', encoding='utf-8')
    for operation in ['sync', 'rollover', 'rollover']:
        result = run_native(vault, git_dir, operation)
        assert result.returncode == 0, result.stdout + result.stderr
        assert current.read_bytes() == saved
        assert previous.read_bytes() == history


def test_failure_summary_is_redacted_and_bounded():
    sys.path.insert(0, str(BACKEND))
    try:
        from native_operations import _error_summary, _failed_result_lines
    finally:
        sys.path.remove(str(BACKEND))
    message = _error_summary("TOKEN=private " + "x" * 9000)
    assert "private" not in message
    assert len(message.encode("utf-8")) <= 4096
    assert _failed_result_lines("Error: status missing\nNo changes detected.") == ["Error: status missing"]


def test_journal_rollover_mid_sequence_crash_and_recovery(fixture_vault, monkeypatch):
    """Verify recovery behavior when rollover fails mid-sequence during incomplete task carry-forward."""
    vault, office_log, git_dir = fixture_vault
    status_path = vault / "Bridge/status.json"
    status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    status["last_updated"] = "2026-09-28"
    status_path.write_text(json.dumps(status), encoding="utf-8-sig")

    # Set up ops_state recurring incomplete task and Future.md incomplete task
    ops_path = vault / "Bridge/ops_state.json"
    ops_state = {
        "tasks": [
            {"text": "Calibrate warp drive", "area": "Front", "next_due": "2026-09-29", "frequency": "daily"}
        ]
    }
    ops_path.write_text(json.dumps(ops_state), encoding="utf-8-sig")

    future_path = vault / "Journal/Future.md"
    future_path.write_text(
        "## 2026-09-30\n- [ ] Deploy probe to asteroid belt\n",
        encoding="utf-8-sig"
    )

    monkeypatch.setenv("NAVIS_ROOT", str(vault))
    monkeypatch.setenv("NAVIS_FIXTURE_GIT_DIR", str(git_dir))
    monkeypatch.setenv("NAVIS_NATIVE_FIXTURE_MODE", "1")

    sys.path.insert(0, str(BACKEND))
    try:
        from services import sync_engine, rpg_engine, progression_db
        monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(vault))
        monkeypatch.setattr(sync_engine, "SETTINGS_FILE", str(vault / "Bridge/settings.json"))
        monkeypatch.setattr(rpg_engine, "NAVIS_ROOT", str(vault))
        monkeypatch.setattr(progression_db, "NAVIS_ROOT", str(vault))
        monkeypatch.setattr(progression_db, "DB_PATH", str(vault / "Keeper/navis_progression.db"))

        # Simulate crash mid-sequence on 2026-09-30 (after 2026-09-29 is written)
        day_29_path = vault / "Journal/2026/09/2026-09-29.md"
        day_30_path = vault / "Journal/2026/09/2026-09-30.md"
        assert not day_29_path.exists()
        assert not day_30_path.exists()

        original_open = open
        def failing_open(file, mode="r", *args, **kwargs):
            if str(day_30_path) in str(file) and "w" in mode:
                raise OSError("Simulated disk full or interrupt during 2026-09-30 carry-forward write")
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", failing_open)

        # Run rollover which encounters mid-sequence failure
        with pytest.raises(RuntimeError, match="journal write failed"):
            sync_engine.run_midnight_rollover()

        # Verify 2026-09-29 was written before crash, carrying its task
        assert day_29_path.exists()
        content_29 = day_29_path.read_text(encoding="utf-8-sig")
        assert "- [ ] Calibrate warp drive" in content_29
        # 2026-09-30 was not created due to crash
        assert not day_30_path.exists()

        # Remove the failing open to simulate recovery after restart
        monkeypatch.setattr("builtins.open", original_open)

        # Run rollover again (Recovery sequence)
        recovery_logs = []
        sync_engine.run_midnight_rollover(log_callback=recovery_logs.append)

        # Verify 2026-09-29 was preserved without duplicating tasks
        recovered_29 = day_29_path.read_text(encoding="utf-8-sig")
        assert recovered_29.count("- [ ] Calibrate warp drive") == 1

        # Verify 2026-09-30 was successfully created during recovery
        assert day_30_path.exists()
        content_30 = day_30_path.read_text(encoding="utf-8-sig")
        assert "- [ ] Deploy probe to asteroid belt" in content_30

        # Verify status advanced
        new_status = json.loads(status_path.read_text(encoding="utf-8-sig"))
        assert new_status["last_updated"] >= "2026-09-30"
    finally:
        if str(BACKEND) in sys.path:
            sys.path.remove(str(BACKEND))


def test_native_operations_watch(fixture_vault, monkeypatch):
    vault, _office_log, git_dir = fixture_vault
    env = os.environ.copy()
    env["NAVIS_ROOT"] = str(vault)
    env["NAVIS_FIXTURE_GIT_DIR"] = str(git_dir)
    env["NAVIS_NATIVE_FIXTURE_MODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(BACKEND)

    proc = subprocess.Popen(
        [sys.executable, str(ENTRYPOINT), "watch"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    try:
        import time
        # Read lines until WATCHER:READY
        ready = False
        start_t = time.time()
        while time.time() - start_t < 10:
            line = proc.stdout.readline()
            if "WATCHER:READY" in line:
                ready = True
                break
        assert ready, "Watcher did not emit WATCHER:READY"

        time.sleep(0.5)

        # Trigger a vault file change
        test_file = vault / "Journal" / "watch_test.md"
        test_file.write_text("# Test\n- [ ] reactive check\n", encoding="utf-8-sig")

        # Read for EVENT: line
        event_payload = None
        start_t = time.time()
        while time.time() - start_t < 10:
            line = proc.stdout.readline()
            if line.startswith("EVENT:"):
                raw = line[len("EVENT:"):].strip()
                event_payload = json.loads(raw)
                break

        assert event_payload is not None, "Watcher did not emit EVENT: line"
        assert event_payload["type"] == "journal"
        assert "Journal/watch_test.md" in event_payload["path"].replace("\\", "/")
        assert event_payload["action"] in {"created", "modified"}
        assert "timestamp" in event_payload
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


