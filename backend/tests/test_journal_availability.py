"""T02 availability checks use synthetic directories and an in-process API."""
import builtins
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

import main
from services.holocron_engine import build_weekly_holocron, parse_daily_journal, export_standalone_html
from services.holocron_evidence import inspect_source


@pytest.fixture
def calendar(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    return tmp_path, TestClient(main.app)


def test_calendar_missing_source_is_not_an_empty_month(calendar):
    root, client = calendar
    path = "/api/journal/month?year=2026&month=10"
    missing = client.get(path)
    assert missing.status_code == 503
    assert "dates" not in missing.json()
    assert str(root) not in missing.text
    (root / "Journal").mkdir()
    assert client.get(path).json() == {"availability": "available", "dates": [], "year": 2026, "month": 10}
    (root / "Journal/2026").write_text("Not a directory")
    assert client.get(path).status_code == 503


def test_calendar_filters_real_dates_and_reports_unreadable_sources(calendar, monkeypatch):
    root, client = calendar
    month = root / "Journal/2026/10"
    month.mkdir(parents=True)
    for name in ("2026-10-02.md", "2026-10-01.md", "2026-10-32.md", "2026-09-01.md", "20261001.md", "notes.md"):
        (month / name).write_text("synthetic")
    (month / "2026-10-03.md").mkdir()
    path = "/api/journal/month?year=2026&month=10"
    assert client.get(path).json()["dates"] == ["2026-10-01", "2026-10-02"]
    original = main.os.scandir
    def unreadable(value):
        if Path(value) == month:
            raise PermissionError("synthetic private path")
        return original(value)
    monkeypatch.setattr(main.os, "scandir", unreadable)
    response = client.get(path)
    assert response.status_code == 503 and "synthetic private path" not in response.text


@pytest.mark.parametrize("query", ["year=0&month=10", "year=2026&month=13", "year=2026&month=0", "year=10000&month=1"])
def test_calendar_rejects_invalid_months(calendar, query):
    assert calendar[1].get("/api/journal/month?" + query).status_code == 400


def test_holocron_parser_failure_is_unavailable_even_when_fingerprints_can_be_read(tmp_path, monkeypatch):
    (tmp_path / "Bridge").mkdir()
    journal = tmp_path / "Journal/2026/09/2026-09-28.md"
    journal.parent.mkdir(parents=True)
    journal.write_text("- [x] Synthetic task\n", encoding="utf-8")
    original = builtins.open
    def unreadable(path, *args, **kwargs):
        if Path(path) == journal:
            raise PermissionError("synthetic")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", unreadable)
    assert parse_daily_journal(str(journal), "2026-09-28")["availability"] == "unavailable"
    result = build_weekly_holocron(str(tmp_path), "2026-W40", force=True)
    assert result["summary"]["logged_days"] == 0
    assert result["summary"]["precision_rate"] is None
    assert result["daily_telemetry"][0]["completed"] is None
    assert all(sector["completed"] is None for sector in result["sector_distribution"])
    assert "Unavailable (Unavailable)" in export_standalone_html(result)
    assert inspect_source(str(tmp_path), "2026-W40", "journal-2026-09-28")["status"] == "unavailable"


def test_corrupt_ledger_missing_journal_and_real_zero_stay_distinct(tmp_path):
    (tmp_path / "Bridge").mkdir()
    journal = tmp_path / "Journal/2026/09/2026-09-28.md"
    journal.parent.mkdir(parents=True)
    journal.write_text("- [ ] Synthetic pending task\n", encoding="utf-8")
    keeper = tmp_path / "Keeper"
    keeper.mkdir()
    database = keeper / "navis_progression.db"
    database.write_bytes(b"not a SQLite database")
    result = build_weekly_holocron(str(tmp_path), "2026-W40", force=True)
    assert result["summary"]["precision_rate"] == 0
    assert result["summary"]["total_xp_gained"] is None
    assert result["evidence"]["sources"][-1]["status"] == "unavailable"
    assert result["daily_telemetry"][1]["total"] is None
    database.unlink()
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE xp_ledger(entity_id TEXT, local_date TEXT, source_type TEXT, amount INTEGER)")
    connection.commit()
    connection.close()
    zero = build_weekly_holocron(str(tmp_path), "2026-W40", force=True)
    assert zero["summary"]["total_xp_gained"] == 0
    assert zero["evidence"]["sources"][-1]["status"] == "available"
    assert "0 (0.0%)" in export_standalone_html(zero)
    assert parse_daily_journal(None, "2026-09-29")["availability"] == "missing"
