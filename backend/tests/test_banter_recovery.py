import json
import sqlite3
from pathlib import Path

from fastapi import HTTPException

import main


def configure_vault(root: Path, monkeypatch, status_bytes: bytes | None):
    (root / "Bridge").mkdir(parents=True, exist_ok=True)
    (root / "Journal").mkdir(parents=True, exist_ok=True)
    status_path = root / "Bridge" / "status.json"
    if status_bytes is not None:
        status_path.write_bytes(status_bytes)
    monkeypatch.setattr(main, "NAVIS_ROOT", str(root))
    monkeypatch.setattr(main, "STATUS_PATH", str(status_path))
    return status_path


def test_banter_generation_distinguishes_missing_malformed_and_empty_squad(tmp_path, monkeypatch):
    status_path = configure_vault(tmp_path, monkeypatch, None)
    try:
        main.trigger_banter_generation(count=1)
        assert False, "missing status must fail before generation"
    except HTTPException as error:
        assert error.status_code == 503
        assert "missing" in error.detail

    status_path.write_text("not-json", encoding="utf-8")
    try:
        main.trigger_banter_generation(count=1)
        assert False, "malformed status must fail before generation"
    except HTTPException as error:
        assert error.status_code == 503
        assert "malformed" in error.detail

    status_path.write_text(json.dumps({"squad": []}), encoding="utf-8")
    try:
        main.trigger_banter_generation(count=1)
        assert False, "empty squad must fail before generation"
    except HTTPException as error:
        assert error.status_code == 422
        assert "two uniquely named" in error.detail

    status_path.write_text(json.dumps({"squad": [{"name": "Aster"}, {"name": " aStEr "}]}), encoding="utf-8")
    try:
        main.trigger_banter_generation(count=1)
        assert False, "case-insensitive duplicate names must fail before generation"
    except HTTPException as error:
        assert error.status_code == 422
        assert "two uniquely named" in error.detail


def test_banter_accepts_bom_status_and_uses_local_generation_failure(tmp_path, monkeypatch):
    status = {"squad": [{"name": "Aster"}, {"name": "Rowan"}], "current_realm": "Mosswood"}
    status_path = configure_vault(tmp_path, monkeypatch, b"\xef\xbb\xbf" + json.dumps(status).encode())
    from services import banter_generator

    monkeypatch.setattr(banter_generator, "generate_squad_banter", lambda count=1: False)
    try:
        main.trigger_banter_generation(count=1)
        assert False, "local generator failure must remain visible"
    except HTTPException as error:
        assert error.status_code == 500
        assert "local provider" in error.detail
        assert "online fallback" in error.detail
    assert status_path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_recovered_generation_refreshes_history_without_duplicate_messages(tmp_path, monkeypatch):
    status = {"squad": [{"name": "Aster"}, {"name": "Rowan"}], "current_realm": "Mosswood"}
    configure_vault(tmp_path, monkeypatch, json.dumps(status).encode())
    database = tmp_path / "Journal" / "Chronicle.db"

    def local_generator(count=1):
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS banter_threads "
                "(id INTEGER PRIMARY KEY, realm TEXT, participants TEXT, chain TEXT, timestamp REAL, thread_hash TEXT UNIQUE)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO banter_threads "
                "(realm, participants, chain, timestamp, thread_hash) VALUES (?, ?, ?, ?, ?)",
                ("Mosswood", "Aster,Rowan", json.dumps([
                    {"speaker": "Aster", "text": "The grove is quiet."},
                    {"speaker": "Rowan", "text": "For now."},
                ]), 1.0, "stable-thread"),
            )
        return True

    from services import banter_generator
    monkeypatch.setattr(banter_generator, "generate_squad_banter", local_generator)

    assert main.trigger_banter_generation(count=1)["status"] == "success"
    first = main.get_banter_history()
    assert [message["sender"] for message in first] == ["Aster", "Rowan"]
    assert main.trigger_banter_generation(count=1)["status"] == "success"
    assert main.get_banter_history() == first


def test_history_reports_status_errors_and_empty_history_separately(tmp_path, monkeypatch):
    status_path = configure_vault(tmp_path, monkeypatch, None)
    try:
        main.get_banter_history()
        assert False, "missing status must not look like empty history"
    except HTTPException as error:
        assert error.status_code == 503
        assert "missing" in error.detail

    status_path.write_text(json.dumps({"squad": []}), encoding="utf-8")
    empty = main.get_banter_history()
    assert empty == []
    assert not (tmp_path / "Journal" / "Chronicle.db").exists()

    (tmp_path / "Journal" / "Chronicle.db").mkdir()
    try:
        main.get_banter_history()
        assert False, "unreadable history storage must not look empty"
    except HTTPException as error:
        assert error.status_code == 503
        assert "history could not be read" in error.detail


def test_existing_chronicle_without_banter_table_is_empty_history(tmp_path, monkeypatch):
    status = {"squad": [{"name": "Aster"}, {"name": "Rowan"}]}
    configure_vault(tmp_path, monkeypatch, json.dumps(status).encode())
    settings_path = tmp_path / "Bridge" / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "SETTINGS_PATH", str(settings_path))

    database = tmp_path / "Journal" / "Chronicle.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE journal_entries (id INTEGER PRIMARY KEY)")

    assert main.get_banter_history() == []

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE journal_entries")
        connection.execute("CREATE TABLE banter_threads (id INTEGER PRIMARY KEY)")

    try:
        main.get_banter_history()
        assert False, "a malformed banter table must remain a history error"
    except HTTPException as error:
        assert error.status_code == 503
        assert "history could not be read" in error.detail
