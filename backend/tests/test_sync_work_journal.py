"""Recovery checks against synthetic work logs, never the configured Vault."""
import builtins
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from services import sync_engine


@pytest.fixture
def work_vault(tmp_path, monkeypatch):
    bridge = tmp_path / "Bridge"
    bridge.mkdir()
    office = tmp_path / "Daily_Work.md"
    settings = bridge / "settings.json"
    settings.write_text(json.dumps({"paths": {"office_work_log": str(office)}}))
    (bridge / "status.json").write_text(json.dumps({"last_updated": "2026-09-30"}))
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(sync_engine, "SETTINGS_FILE", str(settings))
    monkeypatch.setenv("NAVIS_NATIVE_FIXTURE_MODE", "1")
    journal = tmp_path / "Journal/2026/09/2026-09-30.md"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        "# Synthetic journal\n## 🏰 The Sanctum\nKeep this ☃\n"
        "## ⚔️ The High-Velocity Front\n- [x] Existing work\n"
        "## 🏠 The Domestic Breach\n- [ ] Unrelated task\n", encoding="utf-8-sig"
    )
    return tmp_path, office, journal


def test_duplicate_date_blocks_merge_once_and_retry_is_noop(work_vault):
    root, office, journal = work_vault
    office.write_text("## 2026-09-30\n- [ ] Ship synthetic patch\n"
                      "## 2026-09-30\n- Ship synthetic patch\n- Review fixture\n")
    before = journal.read_bytes()
    assert "2 work items" in sync_engine.sync_work_journal()
    saved = journal.read_bytes()
    text = saved.decode("utf-8-sig").replace("\r\n", "\n")
    assert text.count("Ship synthetic patch") == 1
    assert "- [x] 🛡️ Review fixture 📋" in text
    assert "## 🏰 The Sanctum\nKeep this ☃\n" in text
    assert text.endswith("## 🏠 The Domestic Breach\n- [ ] Unrelated task\n")
    assert saved.startswith(b"\xef\xbb\xbf")
    assert next(journal.parent.glob("*.backup_*")).read_bytes() == before
    assert office.read_text(encoding="utf-8-sig") == "## 2026-09-30\n"
    assert "0 work items" in sync_engine.sync_work_journal()
    assert journal.read_bytes() == saved


@pytest.mark.parametrize("target", ["missing", "missing_section"])
def test_unmerged_work_remains_available_for_retry(work_vault, target):
    root, office, journal = work_vault
    pending = root / "Journal/2026/09/2026-09-29.md"
    if target == "missing_section":
        pending.write_text("# Pending day\n## 🏰 The Sanctum\nKeep me\n", encoding="utf-8-sig")
    office.write_text("## 2026-09-29\n- Pending work\n## 2026-09-30\n- Available work\n")
    sync_engine.sync_work_journal()
    remaining = office.read_text(encoding="utf-8-sig")
    assert "Pending work" in remaining
    assert "Available work" not in remaining
    pending.write_text("# Pending day\n## ⚔️ The High-Velocity Front\n", encoding="utf-8-sig")
    assert "1 work items" in sync_engine.sync_work_journal()
    assert pending.read_text(encoding="utf-8-sig").count("Pending work") == 1
    saved = pending.read_bytes()
    sync_engine.sync_work_journal()
    assert pending.read_bytes() == saved


def test_failed_journal_write_does_not_purge_office_log_and_can_retry(work_vault, monkeypatch):
    _, office, journal = work_vault
    office.write_text("## 2026-09-30\n- Retriable work\n")
    original_office, original_journal = office.read_bytes(), journal.read_bytes()
    real_open = builtins.open

    def failing_open(path, mode="r", *args, **kwargs):
        if Path(path) == journal and mode == "w":
            raise PermissionError("synthetic write denial")
        return real_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(builtins, "open", failing_open)
        with pytest.raises(PermissionError, match="synthetic write denial"):
            sync_engine.sync_work_journal()
    assert office.read_bytes() == original_office
    assert journal.read_bytes() == original_journal
    assert "1 work items" in sync_engine.sync_work_journal()
    assert journal.read_text(encoding="utf-8-sig").count("Retriable work") == 1


@pytest.mark.parametrize("contents,expected", [("", "empty"), ("- Undated work", "No valid dates")])
def test_unstructured_work_is_preserved(work_vault, contents, expected):
    _, office, journal = work_vault
    office.write_text(contents)
    before = journal.read_bytes()
    assert expected in sync_engine.sync_work_journal()
    assert office.read_text() == contents
    assert journal.read_bytes() == before


def test_invalid_settings_fail_before_mutation(work_vault):
    root, office, journal = work_vault
    office.write_text("## 2026-09-30\n- Pending work\n")
    (root / "Bridge/settings.json").write_text("{invalid")
    before = office.read_bytes(), journal.read_bytes()
    with pytest.raises(json.JSONDecodeError):
        sync_engine.sync_work_journal()
    assert (office.read_bytes(), journal.read_bytes()) == before


def test_git_identity_prefers_local_then_environment_then_fallback(monkeypatch, tmp_path):
    runner = Mock(side_effect=[Mock(stdout="Local Name\n"), Mock(stdout="")])
    monkeypatch.setattr(sync_engine.subprocess, "run", runner)
    monkeypatch.setenv("NAVIS_GIT_USER_NAME", "Environment Name")
    monkeypatch.setenv("NAVIS_GIT_USER_EMAIL", "fixture@example.invalid")
    assert sync_engine._git_identity_args(tmp_path) == [
        "-c", "user.name=Local Name", "-c", "user.email=fixture@example.invalid"
    ]
    assert all(call.args[0][2:4] == ["--local", "--get"] for call in runner.call_args_list)
    monkeypatch.delenv("NAVIS_GIT_USER_NAME")
    monkeypatch.delenv("NAVIS_GIT_USER_EMAIL")
    runner.side_effect = None
    runner.return_value = Mock(stdout="")
    assert sync_engine._git_identity_args(tmp_path) == [
        "-c", "user.name=Navis Protocol", "-c", "user.email=navis-protocol@localhost"
    ]
