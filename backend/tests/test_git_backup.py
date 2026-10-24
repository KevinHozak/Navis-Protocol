"""Exercise backup staging in a temporary Git repository only."""
import subprocess
from unittest.mock import Mock

from services import sync_engine, rpg_engine
from scripts import sync_watch_history


def test_backup_includes_keeper_and_realms_and_retries_cleanly(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True,
            capture_output=True, text=True,
        ).stdout

    monkeypatch.delenv("NAVIS_NATIVE_FIXTURE_MODE", raising=False)
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(sync_engine, "sync_work_journal", Mock(return_value="Work synced"))
    monkeypatch.setattr(rpg_engine, "calculate_and_apply_xp", Mock())
    monkeypatch.setattr(sync_watch_history, "sync_watch_history", Mock())
    git("init")
    git("config", "user.name", "Backup Test")
    git("config", "user.email", "backup-test@localhost")
    keeper = tmp_path / "Keeper"
    keeper.mkdir()
    (keeper / "XP.md").write_text("Before")
    (keeper / "navis_progression.db").write_bytes(b"before")
    git("add", ".")
    git("commit", "-m", "baseline")
    (keeper / "XP.md").write_text("After")
    (keeper / "navis_progression.db").write_bytes(b"after")
    realm = tmp_path / "Realms" / "Emerald Sea"
    realm.mkdir(parents=True)
    (realm / "Overworld.json").write_text("{}")
    (realm / "Overworld.png").write_bytes(b"synthetic image")

    assert "SAVE COMPLETE" in sync_engine.execute_git_backup()
    assert git("status", "--porcelain") == ""
    assert git("show", "HEAD:Keeper/XP.md") == "After"
    assert "Realms/Emerald Sea/Overworld.png" in git("ls-files")
    saved_head = git("rev-parse", "HEAD")
    assert "NO CHANGES DETECTED" in sync_engine.execute_git_backup()
    assert git("rev-parse", "HEAD") == saved_head
