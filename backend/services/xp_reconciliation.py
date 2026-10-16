"""Conservative, restartable reconciliation for pre-ledger XP stores.

Legacy data is inventoried by default. Import requires an explicit mapping
manifest so ownership and identity are reviewed instead of guessed.
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from services import progression_db as ledger

MIGRATION_VERSION = 1
RULE_VERSION = "xp-reconciliation-v1"
CANONICAL_START = "<!-- NAVIS XP LEDGER START -->"
CANONICAL_END = "<!-- NAVIS XP LEDGER END -->"
XP_LINE = re.compile(r"^-\s*(?:\*\*)?(\d{4}-\d{2}-\d{2}):(?:\*\*)?\s*(?:\*\*)?([+-]?\d+)\s+XP\b(.*)$")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _store_digest(path):
    path = Path(path)
    if path.suffix.casefold() != ".db":
        return _sha256(path)
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        schema = conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('xp_reconciliation_lock','xp_reconciliation_runs') ORDER BY name").fetchall()
        content = []
        for name, _ in schema:
            escaped = name.replace('"', '""')
            rows = conn.execute(f'SELECT * FROM "{escaped}"').fetchall()
            content.append((name, rows))
        return hashlib.sha256(json.dumps([schema, content], ensure_ascii=False, sort_keys=True, default=list).encode()).hexdigest()
    finally:
        conn.close()


def _entity_id(name):
    return "keeper" if name == "Keeper" else f"companion:{name}"


def _duplicate_groups(legacy_rows, markdown):
    groups = {}
    for row in legacy_rows:
        key = (row["date"], row["amount"])
        groups.setdefault(key, []).append(f"xp_logs:{row['row_id']}")
    for row in markdown:
        key = (row["local_date"], row["amount"])
        groups.setdefault(key, []).append(row["source_id"])
    return [sorted(source_ids) for source_ids in groups.values() if len(source_ids) > 1]


def _read_legacy_sources(root):
    root = Path(root)
    db_path = root / "Keeper" / "navis_progression.db"
    legacy_rows = []
    if db_path.is_file():
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "xp_logs" in tables:
                legacy_rows = [dict(zip(("row_id", "date", "amount", "details"), row))
                               for row in conn.execute("SELECT id,date,amount,details FROM xp_logs ORDER BY id")]
        finally:
            conn.close()

    stats = {}
    stats_path = root / "Bridge" / "CompanionStats.json"
    if stats_path.is_file():
        raw = stats_path.read_text(encoding="utf-8-sig")
        parsed = json.loads(raw)
        companions = parsed.get("companions", {})
        if isinstance(companions, dict):
            for name, value in companions.items():
                if isinstance(value, dict) and isinstance(value.get("xp"), int) and not isinstance(value.get("xp"), bool):
                    stats[_entity_id(name)] = value["xp"]

    markdown = []
    unparsed_markdown = []
    for path in sorted([*root.glob("Keeper/XP.md"), *root.glob("Companions/*/XP.md")]):
        relative = path.relative_to(root).as_posix()
        entity = "keeper" if relative == "Keeper/XP.md" else _entity_id(path.parts[-2])
        text = path.read_text(encoding="utf-8-sig")
        in_projection = False
        for number, line in enumerate(text.splitlines(), 1):
            if CANONICAL_START in line:
                in_projection = True
                continue
            if CANONICAL_END in line:
                in_projection = False
                continue
            if in_projection or not line.strip():
                continue
            match = XP_LINE.match(line.strip())
            if match:
                markdown.append({"source_id": f"markdown:{relative}:{number}", "entity_id": entity,
                                 "local_date": match.group(1), "amount": int(match.group(2)),
                                 "details": match.group(3).strip(" *()"),
                                 "line_hash": hashlib.sha256(line.encode("utf-8")).hexdigest()})
            elif re.search(r"\bXP\b", line, re.IGNORECASE):
                unparsed_markdown.append({"source_id": f"markdown:{relative}:{number}", "entity_id": entity})
    return db_path, legacy_rows, stats, markdown, unparsed_markdown, stats_path


def dry_run(root=None, manifest=None):
    """Return an aggregate-only report; never writes to any source store."""
    root = Path(root or ledger.NAVIS_ROOT)
    db_path, legacy_rows, stats, markdown, unparsed_markdown, stats_path = _read_legacy_sources(root)
    legacy_total = sum(row["amount"] for row in legacy_rows if isinstance(row["amount"], int))
    xp_md_counts, xp_md_totals = {}, {}
    for row in markdown:
        xp_md_counts[row["entity_id"]] = xp_md_counts.get(row["entity_id"], 0) + 1
        xp_md_totals[row["entity_id"]] = xp_md_totals.get(row["entity_id"], 0) + row["amount"]

    existing_ledger = {}
    if db_path.is_file():
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "xp_ledger" in tables:
                existing_ledger = dict(conn.execute("SELECT entity_id,COALESCE(SUM(amount),0) FROM xp_ledger GROUP BY entity_id"))
        finally:
            conn.close()

    duplicate_groups = _duplicate_groups(legacy_rows, markdown)

    mapped = _load_manifest(manifest, legacy_rows, stats, markdown, root=root) if manifest else []
    proposed = [{"source_id": row["source_id"], "entity_id": row["entity_id"], "amount": row["amount"], "award_id": row["award_id"]} for row in mapped]
    unparsed_counts = {}
    for row in unparsed_markdown:
        unparsed_counts[row["entity_id"]] = unparsed_counts.get(row["entity_id"], 0) + 1
    total_sources = len(legacy_rows) + len(stats) + len(markdown) + len(unparsed_markdown)
    ambiguous = total_sources - len(mapped)
    known_entities = set(stats) | set(xp_md_counts) | set(existing_ledger)
    return {
        "migration_version": MIGRATION_VERSION,
        "vault_root": str(root),
        "mutated": False,
        "sources": {
            "legacy_sqlite": {"rows": len(legacy_rows), "amount_total_unattributed": legacy_total},
            "companion_stats": {"entities_with_legacy_totals": len(stats), "legacy_totals_by_entity": stats},
            "xp_markdown": {"legacy_rows": len(markdown) + len(unparsed_markdown), "parsed_rows": len(markdown),
                            "unparsed_xp_lines_by_entity": unparsed_counts,
                            "legacy_totals_by_entity": xp_md_totals, "legacy_lines_by_entity": xp_md_counts},
            "canonical_ledger_totals_by_entity": existing_ledger,
        },
        "duplicates": [{"source_ids": ids, "classification": "possible_duplicate_requires_review"} for ids in duplicate_groups],
        "missing": {
            "sqlite_database": not db_path.is_file(),
            "companion_stats": not stats_path.is_file(),
            "stats_entities_without_ledger_rows": sorted(known_entities - set(existing_ledger)),
            "stats_entities_without_xp_markdown": sorted(set(stats) - set(xp_md_counts)),
            "stats_entities_without_stats_record": sorted(set(existing_ledger) - set(stats)),
        },
        "ambiguous": {"count": max(0, ambiguous), "reason": "legacy stores lack sufficient stable source identity or cross-store attribution"},
        "proposed_changes": proposed,
        "unresolved_source_count_after_proposal": max(0, total_sources - len(mapped)),
    }


def _load_manifest(manifest, legacy_rows, stats, markdown, root=None):
    if isinstance(manifest, (str, os.PathLike)):
        manifest = json.loads(Path(manifest).read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get("version") != MIGRATION_VERSION:
        raise ValueError("manifest must be an object with version 1")
    legacy_by_id = {f"xp_logs:{r['row_id']}": r for r in legacy_rows}
    markdown_by_id = {r["source_id"]: r for r in markdown}
    mapped = []
    seen_sources = set()
    seen_awards = set()
    mapped_sources = set()
    existing_sources = set()
    db_path = Path(root or ledger.NAVIS_ROOT) / "Keeper" / "navis_progression.db"
    if db_path.is_file():
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "xp_ledger" in tables:
                for provenance, in conn.execute("SELECT provenance FROM xp_ledger"):
                    try:
                        payload = json.loads(provenance)
                    except (TypeError, ValueError):
                        continue
                    if payload.get("migration_version") == MIGRATION_VERSION and payload.get("source_id"):
                        existing_sources.add(payload["source_id"])
        finally:
            conn.close()
    for raw in manifest.get("mappings", []):
        row = dict(raw)
        source_id = row.get("source_id")
        if source_id in seen_sources:
            raise ValueError(f"manifest maps source more than once: {source_id}")
        seen_sources.add(source_id)
        mapped_sources.add(source_id)
        if source_id in legacy_by_id:
            source = legacy_by_id[source_id]
            if row.get("amount") != source["amount"] or row.get("local_date") != source["date"]:
                raise ValueError(f"manifest values do not match source: {source_id}")
            details = source["details"] or ""
        elif source_id in markdown_by_id:
            source = markdown_by_id[source_id]
            if row.get("entity_id") != source["entity_id"]:
                raise ValueError(f"manifest entity does not match source path: {source_id}")
            if row.get("source_line_hash") != source["line_hash"]:
                raise ValueError(f"manifest Markdown fingerprint is stale: {source_id}")
            if row.get("amount") != source["amount"] or row.get("local_date") != source["local_date"]:
                raise ValueError(f"manifest values do not match source: {source_id}")
            details = str(row.get("details", source["details"] or "Reviewed legacy XP Markdown record"))
        elif source_id and source_id.startswith("companion_stats:"):
            entity_id = source_id.removeprefix("companion_stats:")
            if row.get("amount") != stats.get(entity_id):
                raise ValueError(f"manifest balance does not match CompanionStats: {source_id}")
            if row.get("entity_id") != entity_id or not row.get("local_date"):
                raise ValueError("opening balances require matching entity_id and a reviewed local_date")
            details = str(row.get("details", "Reviewed opening balance"))
        else:
            raise ValueError(f"manifest source does not exist or is unsupported: {source_id}")
        if source_id.startswith("xp_logs:") and row.get("entity_id") not in ("keeper",) and not str(row.get("entity_id", "")).startswith("companion:"):
            raise ValueError(f"manifest entity is invalid: {source_id}")
        award_id = str(row.get("award_id", "")).strip()
        if not award_id or award_id in seen_awards:
            raise ValueError("manifest award_id values must be present and unique")
        seen_awards.add(award_id)
        event = {
            "award_id": award_id,
            "entity_id": row.get("entity_id"),
            "amount": row.get("amount"),
            "source_type": row.get("source_type", "legacy_import"),
            "source_ref": source_id,
            "source_event_at": row.get("source_event_at"),
            "local_date": row.get("local_date"),
            "rule_version": row.get("rule_version", RULE_VERSION),
            "provenance": {**row.get("provenance", {}), "migration_version": MIGRATION_VERSION, "source_id": source_id},
            "details": details,
            "reason": row.get("reason"),
        }
        ledger._validate_event(event)
        mapped.append({**event, "source_id": source_id})
    for group in _duplicate_groups(legacy_rows, markdown):
        mapped_group = mapped_sources.intersection(group) - existing_sources
        already_imported_group = existing_sources.intersection(group)
        if len(mapped_group) + len(already_imported_group) > 1:
            for event in mapped:
                if event["source_id"] in mapped_group and event["provenance"].get("identity_review") != "distinct_award":
                    raise ValueError("multiple possible duplicate sources require provenance.identity_review='distinct_award'")
    return mapped


def _verified_backup(root, backup_dir, db_path, stats_path, entities):
    root = Path(root)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=False)
    files = []
    candidates = [db_path, stats_path, *[root / ("Keeper/XP.md" if e == "keeper" else f"Companions/{e.removeprefix('companion:')}/XP.md") for e in entities]]
    seen_paths = set()
    for path in candidates:
        if path and Path(path) not in seen_paths:
            seen_paths.add(Path(path))
            if not Path(path).is_file():
                files.append({"path": str(path), "exists": False, "sha256": None})
                continue
            target = backup_dir / Path(path).relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            if Path(path) == Path(db_path):
                source = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
                destination = sqlite3.connect(target)
                try:
                    source.backup(destination)
                    destination.commit()
                finally:
                    destination.close(); source.close()
            else:
                shutil.copy2(path, target)
            expected, actual = _store_digest(path), _store_digest(target)
            if expected != actual:
                raise IOError(f"backup verification failed for {Path(path).relative_to(root)}")
            files.append({"path": str(path), "backup": str(target), "exists": True, "sha256": actual})
    if not any(Path(item["path"]) == Path(db_path) and item.get("exists") for item in files):
        raise FileNotFoundError("progression database is missing; migration requires an existing verified database")
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "files": files}
    (backup_dir / "backup-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _capture_post_migration_state(backup_dir):
    manifest_path = Path(backup_dir) / "backup-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = Path(item["path"])
        item["after_exists"] = path.is_file()
        item["after_sha256"] = _store_digest(path) if path.is_file() else None
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def apply_migration(root=None, manifest=None, backup_dir=None, allow_configured_root=False):
    """Apply a reviewed manifest once. A verified backup is mandatory."""
    root = Path(root or ledger.NAVIS_ROOT).resolve()
    configured = Path(ledger.NAVIS_ROOT).resolve()
    if root == configured and not allow_configured_root:
        raise PermissionError("applying to the configured Vault requires explicit allow_configured_root=True")
    if backup_dir is not None:
        backup_dir = Path(backup_dir).resolve()
    db_path, legacy_rows, stats, markdown, _unparsed_markdown, stats_path = _read_legacy_sources(root)
    mapped = _load_manifest(manifest, legacy_rows, stats, markdown, root=root)
    current = dry_run(root, manifest)
    manifest_hash = hashlib.sha256(json.dumps(mapped, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    run_id = f"xp-reconcile-v{MIGRATION_VERSION}-{manifest_hash[:16]}"
    prior = None
    if db_path.is_file():
        lookup = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            has_runs = lookup.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='xp_reconciliation_runs'").fetchone()
            if has_runs:
                prior = lookup.execute("SELECT state,backup_dir FROM xp_reconciliation_runs WHERE run_id=?", (run_id,)).fetchone()
        finally:
            lookup.close()
    if prior and prior[0] == "complete":
        return {"run_id": run_id, "state": "complete", "replayed": True, "backup": {"reused": prior[1]}}
    if prior:
        backup_dir = prior[1]
        backup = {"reused": str(backup_dir)}
    else:
        if not backup_dir:
            raise ValueError("backup_dir is required before migration can be applied")
        if Path(backup_dir).is_relative_to(root):
            raise ValueError("backup_dir must be outside the Vault root")
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("BEGIN IMMEDIATE")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "xp_ledger" not in tables:
            raise RuntimeError("canonical xp_ledger is missing; apply requires the completed P2 schema")
        if "xp_reconciliation_lock" in tables:
            lock = conn.execute("SELECT run_id FROM xp_reconciliation_lock WHERE singleton=1").fetchone()
            if lock and lock["run_id"] != run_id:
                raise ledger.ReconciliationInProgressError("another XP reconciliation is applying or requires recovery")
        latest_db, latest_rows, latest_stats, latest_markdown, _latest_unparsed, latest_stats_path = _read_legacy_sources(root)
        latest_mapping = _load_manifest(manifest, latest_rows, latest_stats, latest_markdown, root=root)
        if latest_mapping != mapped:
            raise RuntimeError("a reviewed source changed after the mapping was prepared; rerun the dry run")
        current = dry_run(root, manifest)
        if not prior:
            backup = _verified_backup(root, backup_dir, latest_db, latest_stats_path, [e["entity_id"] for e in mapped])
        ledger.init_db(conn)
        conn.execute("""CREATE TABLE IF NOT EXISTS xp_reconciliation_runs (
            run_id TEXT PRIMARY KEY, migration_version INTEGER NOT NULL, manifest_hash TEXT NOT NULL,
            state TEXT NOT NULL, backup_dir TEXT NOT NULL, dry_run_json TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT)""")
        lock = conn.execute("SELECT run_id FROM xp_reconciliation_lock WHERE singleton=1").fetchone()
        if lock and lock["run_id"] != run_id:
            raise ledger.ReconciliationInProgressError("another XP reconciliation is applying or requires recovery")
        conn.execute("INSERT OR IGNORE INTO xp_reconciliation_lock(singleton,run_id) VALUES(1,?)", (run_id,))
        conn.execute("INSERT OR REPLACE INTO xp_reconciliation_runs VALUES(?,?,?,?,?,?,?,NULL)",
            (run_id, MIGRATION_VERSION, manifest_hash, "applying", str(backup_dir), json.dumps(current, sort_keys=True), datetime.now(timezone.utc).isoformat()))
        for event in mapped:
            ledger._insert_award(conn, event)
        expected = {entity: conn.execute("SELECT COALESCE(SUM(amount),0) FROM xp_ledger WHERE entity_id=?", (entity,)).fetchone()[0]
                    for entity in sorted({event["entity_id"] for event in mapped})}
        conn.execute("UPDATE xp_reconciliation_runs SET state='ledger_committed',completed_at=? WHERE run_id=?",
                     (datetime.now(timezone.utc).isoformat(), run_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    try:
        ledger.project_entities(expected.keys(), root=root)
    except Exception as exc:
        _capture_post_migration_state(backup_dir)
        _set_run_state(db_path, run_id, "projection_pending")
        raise ledger.ProjectionError(f"ledger committed; reconciliation {run_id} awaits projection recovery: {exc}") from exc
    post = {entity: ledger.get_entity_total(entity, root=root) for entity in expected}
    if post != expected:
        _capture_post_migration_state(backup_dir)
        _set_run_state(db_path, run_id, "verification_failed")
        raise RuntimeError("post-migration totals differ from the committed ledger totals")
    _capture_post_migration_state(backup_dir)
    _set_run_state(db_path, run_id, "complete")
    return {"run_id": run_id, "state": "complete", "replayed": False, "imported_awards": len(mapped),
            "totals_by_entity": post, "backup": backup}


def _set_run_state(db_path, run_id, state):
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE xp_reconciliation_runs SET state=?,completed_at=? WHERE run_id=?",
                     (state, datetime.now(timezone.utc).isoformat(), run_id))
        if state == "complete":
            conn.execute("DELETE FROM xp_reconciliation_lock WHERE singleton=1 AND run_id=?", (run_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rollback_migration(root=None, run_id=None):
    """Restore a run's exact pre-migration stores; requires services to be stopped."""
    root = Path(root or ledger.NAVIS_ROOT).resolve()
    db_path = root / "Keeper" / "navis_progression.db"
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT backup_dir,state FROM xp_reconciliation_runs WHERE run_id=?", (run_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError("unknown reconciliation run_id")
    backup_dir = Path(row[0])
    backup_manifest = json.loads((backup_dir / "backup-manifest.json").read_text(encoding="utf-8"))
    for item in backup_manifest["files"]:
        target = Path(item["path"])
        if item.get("after_exists") is True and target.exists():
            if _store_digest(target) != item.get("after_sha256"):
                raise RuntimeError(f"refusing rollback because the migrated store changed afterward: {target}")
        if not item.get("exists"):
            if target.exists():
                if item.get("after_exists") is not True or _store_digest(target) != item.get("after_sha256"):
                    raise RuntimeError(f"refusing rollback because a formerly missing store changed afterward: {target}")
                target.unlink()
            continue
        source = Path(item["backup"])
        if _store_digest(source) != item["sha256"]:
            raise IOError(f"backup verification failed: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if _store_digest(target) != item["sha256"]:
            raise IOError(f"rollback verification failed: {target}")
    return {"run_id": run_id, "state": "rolled_back", "restored_files": len(backup_manifest["files"])}
