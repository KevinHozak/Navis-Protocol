import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import progression_db as db
from services import xp_reconciliation as reconcile


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "Keeper").mkdir(parents=True)
    (root / "Bridge").mkdir()
    (root / "Companions" / "Ava").mkdir(parents=True)
    monkeypatch.setattr(db, "NAVIS_ROOT", str(root))
    monkeypatch.setattr(db, "DB_PATH", str(root / "Keeper" / "navis_progression.db"))
    conn = db.get_connection()
    conn.execute("INSERT INTO xp_logs(date,amount,details) VALUES('2026-01-03',12,'Reviewed award')")
    conn.execute("INSERT INTO xp_logs(date,amount,details) VALUES('2026-01-03',12,'Reviewed award')")
    conn.close()
    (root / "Bridge" / "CompanionStats.json").write_text(json.dumps({"companions": {
        "Keeper": {"xp": 120, "level": 1}, "Ava": {"xp": 5, "level": 1}
    }}), encoding="utf-8")
    (root / "Keeper" / "XP.md").write_text(
        "# Keeper history\n- **2026-01-03:** +12 XP (Reviewed award)\n"
        "- **2026-01-03:** +12 XP (Reviewed award)\n"
        "- Historical adjustment, 4 XP\n"
        "<!-- NAVIS XP LEDGER START -->\n- **2026-01-03:** +12 XP (canonical)\n<!-- NAVIS XP LEDGER END -->\n",
        encoding="utf-8-sig")
    (root / "Companions" / "Ava" / "XP.md").write_text("# Ava history\n", encoding="utf-8")
    return root


def manifest_for(root):
    report = reconcile.dry_run(root)
    row = report["sources"]["legacy_sqlite"]
    del row
    conn = db.get_connection()
    legacy_id = conn.execute("SELECT MIN(id) FROM xp_logs").fetchone()[0]
    conn.close()
    return {"version": 1, "mappings": [{
        "source_id": f"xp_logs:{legacy_id}", "award_id": "import:keeper:legacy-1",
        "entity_id": "keeper", "amount": 12, "source_type": "manual_adjustment",
        "local_date": "2026-01-03", "source_event_at": "2026-01-03T12:00:00Z",
        "reason": "Reviewed legacy manual award", "provenance": {"actor": "reviewer", "review": "fixture"}
    }]}


def test_dry_run_is_read_only_and_surfaces_uncertainty(vault):
    db_file = vault / "Keeper" / "navis_progression.db"
    before = db_file.read_bytes(), (vault / "Bridge" / "CompanionStats.json").read_bytes(), (vault / "Keeper" / "XP.md").read_bytes()
    report = reconcile.dry_run(vault)
    after = db_file.read_bytes(), (vault / "Bridge" / "CompanionStats.json").read_bytes(), (vault / "Keeper" / "XP.md").read_bytes()
    assert before == after
    assert report["mutated"] is False
    assert report["sources"]["legacy_sqlite"] == {"rows": 2, "amount_total_unattributed": 24}
    assert report["sources"]["xp_markdown"]["legacy_totals_by_entity"] == {"keeper": 24}
    assert len(report["duplicates"]) == 1
    assert len(report["duplicates"][0]["source_ids"]) == 4
    assert report["ambiguous"]["count"] >= 5
    assert report["proposed_changes"] == []


def test_apply_requires_review_backup_updates_projection_and_replays_once(vault, tmp_path):
    manifest = manifest_for(vault)
    backup_dir = tmp_path / "verified-backup"
    result = reconcile.apply_migration(vault, manifest, backup_dir, allow_configured_root=True)
    assert result["state"] == "complete"
    assert result["imported_awards"] == 1
    assert db.get_entity_total("keeper") == 12
    stats = json.loads((vault / "Bridge" / "CompanionStats.json").read_text(encoding="utf-8-sig"))
    assert stats["companions"]["Keeper"]["xp"] == 120
    assert stats["companions"]["Keeper"]["ledger_xp"] == 12
    xp_text = (vault / "Keeper" / "XP.md").read_text(encoding="utf-8-sig")
    assert "# Keeper history\n- **2026-01-03:** +12 XP (Reviewed award)" in xp_text
    assert "Canonical total: 12 XP" in xp_text
    replay = reconcile.apply_migration(vault, manifest, backup_dir, allow_configured_root=True)
    assert replay["replayed"] is True
    assert len(db.get_xp_history(entity_id="keeper")) == 1
    conn = db.get_connection()
    assert not conn.execute("SELECT 1 FROM xp_reconciliation_lock").fetchone()
    conn.close()


def test_projection_failure_blocks_writers_then_resume_repairs(vault, tmp_path, monkeypatch):
    manifest = manifest_for(vault)
    backup_dir = tmp_path / "resume-backup"
    original_projection = db.project_entities
    def fail_projection(_entities, root=None):
        raise OSError("fixture projection interruption")
    monkeypatch.setattr(db, "project_entities", fail_projection)
    with pytest.raises(db.ProjectionError):
        reconcile.apply_migration(vault, manifest, backup_dir, allow_configured_root=True)
    assert db.get_entity_total("keeper") == 12
    with pytest.raises(db.ReconciliationInProgressError):
        db.record_award({
            "award_id": "during-migration", "entity_id": "keeper", "amount": 1,
            "source_type": "manual_adjustment", "source_ref": "manual/test",
            "source_event_at": "2026-01-03T12:00:00Z", "local_date": "2026-01-03",
            "rule_version": "xp-v1", "provenance": {"actor": "tester"}, "reason": "fixture"
        }, project=False)
    monkeypatch.setattr(db, "project_entities", original_projection)
    resumed = reconcile.apply_migration(vault, manifest, None, allow_configured_root=True)
    assert resumed["state"] == "complete"
    assert resumed["replayed"] is False
    assert db.get_entity_total("keeper") == 12


def test_rollback_restores_verified_pre_migration_files(vault, tmp_path):
    manifest = manifest_for(vault)
    missing_projection = vault / "Companions" / "Ava" / "XP.md"
    missing_projection.unlink()
    manifest["mappings"][0]["entity_id"] = "companion:Ava"
    manifest["mappings"][0]["source_type"] = "legacy_import"
    originals = {path: (reconcile._store_digest(path) if path.suffix == ".db" else path.read_bytes())
        for path in [vault / "Keeper" / "navis_progression.db",
            vault / "Bridge" / "CompanionStats.json", vault / "Keeper" / "XP.md"]}
    result = reconcile.apply_migration(vault, manifest, tmp_path / "rollback-backup", allow_configured_root=True)
    restored = reconcile.rollback_migration(vault, result["run_id"])
    assert restored["restored_files"] == 3
    assert not missing_projection.exists()
    for path, contents in originals.items():
        actual = reconcile._store_digest(path) if path.suffix == ".db" else path.read_bytes()
        assert actual == contents


def test_apply_fails_closed_without_manifest_or_backup(vault):
    with pytest.raises(ValueError, match="backup_dir is required"):
        reconcile.apply_migration(vault, {"version": 1, "mappings": []}, allow_configured_root=True)
    with pytest.raises(ValueError, match="manifest must be an object"):
        reconcile.apply_migration(vault, None, "unused", allow_configured_root=True)


def test_explicit_root_is_used_for_every_read_and_projection(vault, tmp_path, monkeypatch):
    manifest = manifest_for(vault)
    configured_root = tmp_path / "personal-vault-must-not-be-touched"
    monkeypatch.setattr(db, "NAVIS_ROOT", str(configured_root))
    monkeypatch.setattr(db, "DB_PATH", str(configured_root / "Keeper" / "navis_progression.db"))
    result = reconcile.apply_migration(vault, manifest, tmp_path / "explicit-root-backup")
    assert result["state"] == "complete"
    assert db.get_entity_total("keeper", root=vault) == 12
    assert not configured_root.exists()


def test_overlapping_sqlite_and_markdown_awards_require_distinct_identity_review(vault):
    _, _, _, markdown, _, _ = reconcile._read_legacy_sources(vault)
    conn = db.get_connection()
    ids = [row[0] for row in conn.execute("SELECT id FROM xp_logs ORDER BY id")]
    conn.close()
    mapping = {"entity_id": "keeper", "amount": 12, "source_type": "legacy_import",
        "source_event_at": "2026-01-03T12:00:00Z", "local_date": "2026-01-03",
        "provenance": {"actor": "reviewer"}}
    manifest = {"version": 1, "mappings": [
        {**mapping, "source_id": f"xp_logs:{ids[0]}", "award_id": "overlap:sqlite"},
        {**mapping, "source_id": markdown[0]["source_id"], "source_line_hash": markdown[0]["line_hash"], "award_id": "overlap:markdown"},
    ]}
    with pytest.raises(ValueError, match="identity_review='distinct_award'"):
        reconcile._load_manifest(manifest, *reconcile._read_legacy_sources(vault)[1:4])

    conn = db.get_connection()
    conn.execute("""INSERT INTO xp_ledger
        (award_id,entity_id,amount,source_type,source_ref,source_event_at,local_date,rule_version,provenance,created_at,details)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        ("previously-imported", "keeper", 12, "legacy_import", f"xp_logs:{ids[0]}",
         "2026-01-03T12:00:00Z", "2026-01-03", "xp-reconciliation-v1",
         json.dumps({"migration_version": 1, "source_id": f"xp_logs:{ids[0]}"}), "2026-09-30T00:00:00Z", "Reviewed"))
    conn.close()
    followup = {"version": 1, "mappings": [{**mapping, "source_id": f"xp_logs:{ids[1]}", "award_id": "overlap:later"}]}
    with pytest.raises(ValueError, match="identity_review='distinct_award'"):
        reconcile._load_manifest(followup, *reconcile._read_legacy_sources(vault)[1:4])
