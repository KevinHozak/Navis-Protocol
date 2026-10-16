import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import progression_db as db
from services import rpg_engine


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "Keeper" / "navis_progression.db"))
    monkeypatch.setattr(rpg_engine, "NAVIS_ROOT", str(tmp_path))
    (tmp_path / "Bridge").mkdir()
    (tmp_path / "Keeper").mkdir()
    (tmp_path / "Companions" / "Ava").mkdir(parents=True)
    (tmp_path / "Companions" / "Bryn").mkdir(parents=True)
    (tmp_path / "Companions" / "Ava" / "Profile.md").write_text("Status: [home] Arcadia\n", encoding="utf-8")
    (tmp_path / "Bridge" / "CompanionStats.json").write_text(json.dumps({"companions": {
        "Keeper": {"xp": 0, "level": 1}, "Ava": {"xp": 0, "level": 1}, "Bryn": {"xp": 0, "level": 1}
    }}), encoding="utf-8")
    status = {"last_updated": "2026-09-28", "current_realm": "Arcadia", "squad": [{"name": "Ava"}]}
    (tmp_path / "Bridge" / "status.json").write_text(json.dumps(status), encoding="utf-8")
    journal_dir = tmp_path / "Journal" / "2026" / "09"
    journal_dir.mkdir(parents=True)
    journal = journal_dir / "2026-09-28.md"
    journal.write_text("# Today\n- [x] One\n- [X] Two\n", encoding="utf-8")
    return tmp_path, journal


def manual_event(award_id="manual-1", **overrides):
    event = {
        "award_id": award_id, "entity_id": "keeper", "amount": 15,
        "source_type": "manual_adjustment", "source_ref": f"manual/{award_id}",
        "source_event_at": "2026-09-28T17:00:00-05:00", "local_date": "2026-09-28",
        "rule_version": "xp-v1", "provenance": {"actor": "Keeper", "interface": "test"},
        "reason": "Approved manual correction", "details": "Approved manual correction",
    }
    event.update(overrides)
    return event


def test_awards_are_entity_scoped_idempotent_and_keep_legacy_rows_unresolved(vault):
    conn = db.get_connection()
    conn.execute("INSERT INTO xp_logs(date,amount,details) VALUES('2026-09-28',999,'legacy unknown owner')")
    conn.close()
    assert db.record_award(manual_event(), project=False)["created"] is True
    assert db.record_award(manual_event(), project=False)["created"] is False
    assert db.get_total_xp("keeper") == 15
    assert db.get_total_xp("companion:Ava") == 0
    assert len(db.get_xp_history(entity_id="keeper")) == 1
    with pytest.raises(db.ProgressionValidationError, match="conflicting content"):
        db.record_award(manual_event(amount=16), project=False)


def test_manual_reason_and_correction_link_are_validated(vault):
    with pytest.raises(db.ProgressionValidationError, match="require an attributed reason"):
        db.record_award(manual_event(reason=""), project=False)
    db.record_award(manual_event(), project=False)
    correction = manual_event("correction-1", amount=-3, source_type="correction",
        source_ref="manual/manual-1/correction", correction_of="manual-1", reason="Corrected duplicate entry")
    db.record_award(correction, project=False)
    db.record_award(correction, project=False)
    assert db.get_total_xp("keeper") == 12
    reversal = manual_event("correction-3", amount=3, source_type="correction",
        source_ref="manual/manual-1/correction-reversal", correction_of="correction-1", reason="Reversed the earlier correction")
    db.record_award(reversal, project=False)
    assert db.get_total_xp("keeper") == 15
    wrong_entity = dict(correction, award_id="correction-2", entity_id="companion:Ava")
    with pytest.raises(db.ProgressionValidationError, match="same entity"):
        db.record_award(wrong_entity, project=False)


def test_journal_replay_keeps_original_cohort_and_corrects_unchecked_tasks(vault):
    root, journal = vault
    result = rpg_engine.calculate_and_apply_xp()
    assert set(result["entities_updated"]) == {"keeper", "companion:Ava"}
    assert db.get_total_xp("keeper") == 14
    assert db.get_total_xp("companion:Ava") == 19

    status_path = root / "Bridge" / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["squad"] = [{"name": "Bryn"}]
    status["current_realm"] = "Changed Realm"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    rpg_engine.calculate_and_apply_xp()
    assert db.get_total_xp("keeper") == 14
    assert db.get_total_xp("companion:Ava") == 19
    assert db.get_total_xp("companion:Bryn") == 0

    history_before_edit = len(db.get_xp_history(entity_id="keeper"))
    journal.write_text("# Today\n- [x] One edited\n- [X] Two\n", encoding="utf-8")
    rpg_engine.calculate_and_apply_xp()
    assert db.get_total_xp("keeper") == 14
    assert len(db.get_xp_history(entity_id="keeper")) == history_before_edit

    journal.write_text("# Today\n- [x] One\n- [ ] Two\n", encoding="utf-8")
    rpg_engine.calculate_and_apply_xp()
    assert db.get_total_xp("keeper") == 12
    assert db.get_total_xp("companion:Ava") == 17
    assert any(row["correction_of"] for row in db.get_xp_history(entity_id="keeper"))
    projection = json.loads((root / "Bridge" / "CompanionStats.json").read_text(encoding="utf-8-sig"))
    assert projection["companions"]["Keeper"]["ledger_xp"] == 12
    assert projection["companions"]["Keeper"]["xp"] == 0
    assert "Canonical total: 12 XP" in (root / "Keeper" / "XP.md").read_text(encoding="utf-8-sig")


def test_unavailable_journal_does_not_create_an_award(vault):
    root, journal = vault
    journal.unlink()
    with pytest.raises(FileNotFoundError, match="no XP was awarded"):
        rpg_engine.calculate_and_apply_xp()
    assert db.get_total_xp("keeper") == 0


def test_same_local_day_distinct_awards_and_utc_day_boundary(vault):
    first = manual_event("day-boundary-1", amount=4,
        source_event_at="2026-09-29T02:00:00Z", local_date="2026-09-28",
        source_ref="manual/day-boundary-1")
    second = manual_event("day-boundary-2", amount=6,
        source_event_at="2026-09-28T19:30:00-05:00", local_date="2026-09-28",
        source_ref="manual/day-boundary-2")
    db.record_award(first, project=False)
    db.record_award(second, project=False)
    assert db.get_total_xp("keeper") == 10
    assert {row["date"] for row in db.get_xp_history(entity_id="keeper")} == {"2026-09-28"}
    assert db.record_award(first, project=False)["created"] is False


def test_negative_corrections_are_not_clamped_and_level_stays_at_one(vault):
    db.record_award(manual_event("negative-total", amount=-300), project=False)
    assert db.get_total_xp("keeper") == -300
    assert db.level_for_total(-300) == 1


def test_projection_failure_is_reported_after_commit_and_retry_repairs(vault):
    root, _ = vault
    (root / "Bridge" / "CompanionStats.json").unlink()
    with pytest.raises(db.ProjectionError, match="ledger committed"):
        db.record_award(manual_event(), project=True)
    assert db.get_total_xp("keeper") == 15
    (root / "Bridge" / "CompanionStats.json").write_text(json.dumps({"companions": {"Keeper": {"xp": 0, "level": 1}}}), encoding="utf-8")
    assert db.record_award(manual_event(), project=True)["created"] is False
    projection = json.loads((root / "Bridge" / "CompanionStats.json").read_text(encoding="utf-8-sig"))
    assert projection["companions"]["Keeper"]["ledger_xp"] == 15


def test_fastapi_and_direct_ledger_share_the_same_idempotent_contract(vault, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main
    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault[0]))
    payload = manual_event("api-manual")
    first = asyncio.run(main.log_progression_xp(main.XPAwardRequest(**payload)))
    second = asyncio.run(main.log_progression_xp(main.XPAwardRequest(**payload)))
    assert first["created"] is True and second["created"] is False
    result = asyncio.run(main.get_progression_xp(entity_id="keeper"))
    assert result["total_xp"] == 15
    assert result["history"][0]["award_id"] == "api-manual"


def test_dashboard_thresholds_at_boundaries():
    for total, level, base, next_base in [(-10, 1, 0, 1000), (999, 1, 0, 1000),
                                          (1000, 2, 1000, 3000), (3000, 3, 3000, 6000)]:
        progress = db.level_progress(total)
        assert progress["level"] == level
        assert progress["current_level_xp"] == base
        assert progress["next_level_xp"] == next_base
        assert progress["xp_into_level"] == total - base
        assert 0 <= progress["progress_percent"] <= 100


def test_dashboard_history_and_totals_survive_reopen(vault):
    rpg_engine.calculate_and_apply_xp()
    rpg_engine.calculate_and_apply_xp()
    assert db.get_total_xp() == 14
    db.record_award(manual_event("dashboard-manual", amount=1000))
    correction = manual_event("dashboard-correction", amount=-4, source_type="correction",
        source_ref="manual/dashboard-manual/correction", correction_of="dashboard-manual")
    db.record_award(correction)
    db.record_award(correction)
    before = db.get_xp_history()
    # Each read reopens SQLite; reload the service as a fresh application process would.
    import importlib
    root, _ = vault
    original_root, original_path = db.NAVIS_ROOT, db.DB_PATH
    importlib.reload(db)
    try:
        db.NAVIS_ROOT, db.DB_PATH = str(root), str(root / "Keeper" / "navis_progression.db")
        assert db.get_total_xp() == 1010
        assert db.get_xp_history() == before
        assert db.level_progress(db.get_total_xp())["level"] == 2
        assert next(row for row in before if row["award_id"] == "dashboard-manual")["provenance"]["actor"] == "Keeper"
        assert before == sorted(before, key=lambda row: (row["local_date"], row["created_at"], row["award_id"]), reverse=True)
    finally:
        db.NAVIS_ROOT, db.DB_PATH = original_root, original_path
