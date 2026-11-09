"""Synthetic root-routing checks; no real tray, child process or integrations."""
import io
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace
import urllib.request

import pytest


BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = r"G:\My Drive\Navis-Vault"


def forbidden(*args, **kwargs):
    raise AssertionError("Live process/integration access forbidden in root-routing tests")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)


@pytest.mark.parametrize("configured", [False, True])
def test_lounge_connection_uses_only_synthetic_root(tmp_path, monkeypatch, configured):
    root = tmp_path / ("Vault with spaces 雪" if configured else "Second Vault")
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    module = runpy.run_path(str(BACKEND / "database/lounge_db.py"))
    expected = root / "Lounge/lounge.db"
    assert Path(module["DB_PATH"]) == expected
    assert not root.exists(), "Import must not create the database or folders"
    connect = sqlite3.connect
    seen = []

    def guarded_connect(path, *args, **kwargs):
        assert Path(path) == expected, "Refusing any database outside the synthetic target"
        seen.append(Path(path))
        return connect(path, *args, **kwargs)

    mkdir = os.makedirs

    def guarded_mkdir(path, *args, **kwargs):
        assert Path(path).is_relative_to(tmp_path), "Refusing real Vault directory access"
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
    monkeypatch.setattr(os, "makedirs", guarded_mkdir)
    with module["get_db_connection"]() as db:
        db.execute("CREATE TABLE fixture(value TEXT)")
        db.execute("INSERT INTO fixture VALUES ('synthetic')")
        assert db.execute("SELECT value FROM fixture").fetchone()["value"] == "synthetic"
    db.close()
    assert seen == [expected]
    assert expected.is_file()


@pytest.mark.parametrize("value", [None, ""])
def test_lounge_default_is_path_only_without_real_access(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("NAVIS_ROOT", raising=False)
    else:
        monkeypatch.setenv("NAVIS_ROOT", value)
    monkeypatch.setattr(os, "makedirs", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    module = runpy.run_path(str(BACKEND / "database/lounge_db.py"))
    assert module["DB_PATH"] == os.path.join(DEFAULT_ROOT, "Lounge", "lounge.db")


@pytest.mark.parametrize("configured", [None, "", "synthetic"])
def test_sync_lounge_inputs_share_database_root(tmp_path, monkeypatch, configured):
    root = tmp_path / "Synthetic Vault 雪"
    if configured is None:
        monkeypatch.delenv("NAVIS_ROOT", raising=False)
    else:
        monkeypatch.setenv("NAVIS_ROOT", str(root) if configured else "")
    expected = root if configured else Path(DEFAULT_ROOT)
    database = runpy.run_path(str(BACKEND / "database/lounge_db.py"))
    db_stub = ModuleType("database.lounge_db")
    db_stub.get_db_connection = forbidden
    parser_stub = ModuleType("services.jellyfin_parser")
    parser_stub.parse_jellyfin_movies = forbidden
    parser_stub.parse_jellyfin_series = forbidden
    monkeypatch.setitem(sys.modules, "database.lounge_db", db_stub)
    monkeypatch.setitem(sys.modules, "services.jellyfin_parser", parser_stub)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "path", list(sys.path))
    module = runpy.run_path(str(BACKEND / "scripts/sync_lounge.py"))
    assert Path(module["LOUNGE_DIR"]) == Path(database["DB_PATH"]).parent
    for key in ("GOODREADS_CSV", "YOUTUBE_JSON", "MANUAL_MEDIA_MD"):
        assert Path(module[key]).parent == expected / "Lounge"
    assert not root.exists(), "Inspecting sync paths must not run a sync"


@pytest.mark.parametrize("configured", [None, "", "synthetic"])
def test_tray_initial_and_restarted_backend_keep_selected_root(tmp_path, monkeypatch, configured):
    root = str(tmp_path / "Vault with spaces 雪")
    if configured is None:
        monkeypatch.delenv("NAVIS_ROOT", raising=False)
    else:
        monkeypatch.setenv("NAVIS_ROOT", root if configured else "")
    monkeypatch.setenv("ROOT_ROUTING_SENTINEL", "preserved")
    expected = root if configured else DEFAULT_ROOT
    parent_environment = dict(os.environ)
    calls = []
    fake_process = SimpleNamespace(terminate=lambda: None, wait=lambda **kwargs: None)

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(time, "sleep", lambda *args: None)
    tray = ModuleType("pystray")
    tray.Menu = lambda *args: args
    tray.MenuItem = lambda *args, **kwargs: None
    tray.Icon = lambda *args: SimpleNamespace(run=lambda: None)
    pil = ModuleType("PIL")
    pil.Image = SimpleNamespace(open=lambda *args: object(), new=lambda *args: object())
    pil.ImageDraw = SimpleNamespace(Draw=lambda *args: SimpleNamespace(rectangle=lambda *args, **kwargs: None))
    monkeypatch.setitem(sys.modules, "pystray", tray)
    monkeypatch.setitem(sys.modules, "PIL", pil)
    module = runpy.run_path(str(BACKEND / "tray_manager.py"))
    module["restart_backend"](None, None)
    backends = [kwargs for command, kwargs in calls if "uvicorn" in command]
    assert len(backends) == 2
    for kwargs in backends:
        assert kwargs["env"]["NAVIS_ROOT"] == expected
        assert kwargs["env"]["ROOT_ROUTING_SENTINEL"] == "preserved"
        assert kwargs["creationflags"] == module["CREATE_NO_WINDOW"]
    assert dict(os.environ) == parent_environment
    assert not Path(root).exists()
