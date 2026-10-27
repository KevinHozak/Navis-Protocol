import json
import sqlite3

import pytest

from services.holocron_engine import build_weekly_holocron, export_standalone_html
from services.holocron_evidence import inspect_source


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "Bridge").mkdir()
    (tmp_path / "Journal/2026/09").mkdir(parents=True)
    return tmp_path


def test_missing_root_does_not_create_cache_or_report_measurements(tmp_path):
    root = tmp_path / "missing"
    result = build_weekly_holocron(str(root), "2026-W40", force=True)
    assert not root.exists()
    for key in ("precision_rate", "total_xp_gained", "avg_readiness", "deep_work_hours", "threats_neutralized"):
        assert result["summary"][key] is None
    assert result["squad_mvp"] is None
    assert "zero critical" not in result["tactical_debrief"]


def test_real_sources_do_not_imply_combat_and_deleted_source_is_missing(vault):
    journal = vault / "Journal/2026/09/2026-09-28.md"
    journal.write_text("# Day\nPrime Beast: Hydra\n- [x] Synthetic task\n", encoding="utf-8")
    result = build_weekly_holocron(str(vault), "2026-W40", force=True)
    assert result["summary"]["precision_rate"] == 100
    assert result["evidence"]["metrics"]["precision_rate"]["status"] == "partial"
    assert result["combat"]["victories"] is None
    assert result["combat"]["total_damage_dealt"] is None
    assert result["combat"]["beasts_neutralized"] == []
    inspected = inspect_source(str(vault), "2026-W40", "journal-2026-09-28")
    assert inspected["counts"]["completed"] == 1
    assert inspected["fingerprint"] == result["evidence"]["sources"][0]["fingerprint"]
    journal.unlink()
    assert inspect_source(str(vault), "2026-W40", inspected["id"])["status"] == "missing"
    assert build_weekly_holocron(str(vault), "2026-W40")["summary"]["precision_rate"] is None
    with pytest.raises(ValueError):
        inspect_source(str(vault), "2026-W40", "../../private")
    with pytest.raises(ValueError):
        inspect_source(str(vault), "2026-W40", "journal-2026-10-20")


def test_keeper_ledger_scope_corrections_zero_and_missing(vault):
    (vault / "Keeper").mkdir()
    database = vault / "Keeper/navis_progression.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE xp_ledger(entity_id TEXT, local_date TEXT, source_type TEXT, amount INTEGER)")
        conn.executemany("INSERT INTO xp_ledger VALUES(?,?,?,?)", [
            ("keeper", "2026-09-28", "combat", 10), ("keeper", "2026-09-28", "combat", -10),
            ("companion:other", "2026-09-28", "combat", 900), ("keeper", "2026-10-20", "task", 50)])
    conn.close()
    result = build_weekly_holocron(str(vault), "2026-W40", force=True)
    assert result["summary"]["total_xp_gained"] == 0
    assert result["combat"]["victories"] is None
    assert result["evidence"]["metrics"]["total_xp_gained"]["status"] == "available"
    database.unlink()
    assert inspect_source(str(vault), "2026-W40", "keeper-ledger")["status"] == "missing"


def test_unreadable_text_and_empty_checklists_are_not_zero_measurements(vault):
    journal = vault / "Journal/2026/09/2026-09-28.md"
    journal.write_bytes(b"\xff\xfeinvalid UTF-8")
    assert inspect_source(str(vault), "2026-W40", "journal-2026-09-28")["status"] == "unavailable"
    result = build_weekly_holocron(str(vault), "2026-W40", force=True)
    assert result["summary"]["precision_rate"] is None
    journal.write_text("# Readable day without checklist items\n", encoding="utf-8")
    result = build_weekly_holocron(str(vault), "2026-W40", force=True)
    assert result["summary"]["precision_rate"] is None
    assert result["evidence"]["metrics"]["precision_rate"]["status"] == "unavailable"


def test_export_escapes_metadata_omits_private_paths_and_contains_evidence(vault):
    result = build_weekly_holocron(str(vault), "2026-W40", force=True)
    result["tactical_debrief"] = '<script>alert("test")</script>'
    result["squad_mvp"] = {"name": r"C:\Private\Person", "deployments": 1}
    html = export_standalone_html(result)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "C:\\Private" not in html
    assert "Evidence snapshot" in html and "Unavailable" in html
    assert "300 XP" not in html and "85.0%" not in html
    assert str(vault) not in json.dumps(result)


def test_native_and_web_source_routes_share_bounded_inspection(vault, monkeypatch):
    import main
    import native_holocron
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))
    monkeypatch.setattr(native_holocron, "NAVIS_ROOT", str(vault))
    path = "/api/holocron/weekly/2026-W40/evidence/journal-2026-09-28"
    assert TestClient(main.app).get(path).json() == native_holocron.dispatch(path)
