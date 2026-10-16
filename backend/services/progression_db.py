"""Canonical, entity-scoped XP ledger and compatibility projections."""

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
DB_PATH = os.path.join(NAVIS_ROOT, "Keeper", "navis_progression.db")


class ProgressionValidationError(ValueError):
    pass


class ProjectionError(RuntimeError):
    """The ledger transaction committed, but one or more projections failed."""


class ReconciliationInProgressError(RuntimeError):
    """An XP writer attempted to run while a reconciliation owns the ledger."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _paths_for_root(root=None):
    root = os.fspath(root or NAVIS_ROOT)
    same_root = os.path.normcase(os.path.abspath(root)) == os.path.normcase(os.path.abspath(NAVIS_ROOT))
    db_path = DB_PATH if same_root else os.path.join(root, "Keeper", "navis_progression.db")
    return root, db_path


def get_connection(root=None):
    root, db_path = _paths_for_root(root)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Navis Vault is unavailable at {root}")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    init_db(conn)
    return conn


DEFAULT_TALENT_NODES = [
    (
        "focus_deep_work",
        "Focus",
        1,
        "[]",
        3,
        "focus_deep_work_multiplier",
        "Deep Work Flow",
        "Enhances focus depth and execution endurance during single-task sessions.",
    ),
    (
        "focus_clarity",
        "Focus",
        2,
        '["focus_deep_work"]',
        2,
        "focus_stamina_boost",
        "Mindful Clarity",
        "Reduces cognitive fatigue and extends focus stamina during extended deep work.",
    ),
    (
        "martial_momentum",
        "Martial",
        1,
        "[]",
        3,
        "high_velocity_xp_bonus",
        "High-Velocity Striker",
        "+10% XP yield on High-Velocity Front combat operations and rapid task completions.",
    ),
    (
        "martial_tenacity",
        "Martial",
        2,
        '["martial_momentum"]',
        2,
        "reduced_rollover_penalty",
        "Unyielding Tenacity",
        "Mitigates friction, morale loss, and rollover penalties from overdue objectives.",
    ),
    (
        "kinetic_vitality",
        "Kinetic",
        1,
        "[]",
        3,
        "kinetic_stamina_efficiency",
        "Kinetic Vitality",
        "Boosts physical endurance, energy reserves, and daily health habit tracking.",
    ),
    (
        "kinetic_surge",
        "Kinetic",
        2,
        '["kinetic_vitality"]',
        1,
        "daily_outland_surge",
        "Outland Surge",
        "Awards surge bonus rewards and stamina replenishment upon conquering physical expeditions.",
    ),
    (
        "lore_archivist",
        "Lore",
        1,
        "[]",
        3,
        "library_harvest_bonus",
        "Master Archivist",
        "Boosts wisdom and XP yields when harvesting or transmuting research scrolls.",
    ),
    (
        "lore_synthesis",
        "Lore",
        2,
        '["lore_archivist"]',
        2,
        "neural_arbiter_synergy",
        "Holocron Synthesis",
        "Amplifies cognitive telemetry synthesis, arbiter insights, and intelligence archives.",
    ),
]


def init_db(conn=None, root=None):
    owned = conn is None
    vault_root, db_path = _paths_for_root(root)
    if owned and not os.path.isdir(vault_root):
        raise FileNotFoundError(f"Navis Vault is unavailable at {vault_root}")
    conn = conn or sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS xp_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            amount INTEGER NOT NULL, details TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, description TEXT, date_achieved TEXT,
            category TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS xp_ledger (
            award_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, amount INTEGER NOT NULL,
            source_type TEXT NOT NULL, source_ref TEXT NOT NULL,
            source_event_at TEXT NOT NULL, local_date TEXT NOT NULL,
            rule_version TEXT NOT NULL, provenance TEXT NOT NULL,
            created_at TEXT NOT NULL, correction_of TEXT,
            reason TEXT, details TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(correction_of) REFERENCES xp_ledger(award_id))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_xp_ledger_entity_date ON xp_ledger(entity_id, local_date DESC, created_at DESC)")
        conn.execute("""CREATE TABLE IF NOT EXISTS xp_source_state (
            entity_id TEXT NOT NULL, source_type TEXT NOT NULL, source_ref TEXT NOT NULL,
            amount INTEGER NOT NULL, last_award_id TEXT NOT NULL,
            provenance TEXT NOT NULL, local_date TEXT NOT NULL,
            PRIMARY KEY(entity_id, source_type, source_ref))""")
        conn.execute("CREATE TABLE IF NOT EXISTS progression_schema (version INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS xp_reconciliation_lock (singleton INTEGER PRIMARY KEY CHECK(singleton=1), run_id TEXT NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS talent_nodes (
            id TEXT PRIMARY KEY, branch TEXT NOT NULL,
            tier INTEGER NOT NULL, prerequisites TEXT NOT NULL DEFAULT '[]',
            max_rank INTEGER NOT NULL DEFAULT 1, perk_key TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS talent_allocations (
            entity_id TEXT NOT NULL, node_id TEXT NOT NULL,
            rank INTEGER NOT NULL, allocated_at TEXT NOT NULL,
            PRIMARY KEY(entity_id, node_id),
            FOREIGN KEY(node_id) REFERENCES talent_nodes(id))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_talent_allocations_entity ON talent_allocations(entity_id)")
        for node in DEFAULT_TALENT_NODES:
            conn.execute("""INSERT OR IGNORE INTO talent_nodes
                (id, branch, tier, prerequisites, max_rank, perk_key, name, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", node)
        if conn.execute("SELECT COUNT(*) FROM progression_schema").fetchone()[0] == 0:
            conn.execute("INSERT INTO progression_schema(version) VALUES (2)")
        else:
            conn.execute("UPDATE progression_schema SET version = 2 WHERE version < 2")
    finally:
        if owned:
            conn.close()


def _validate_event(event):
    required = ("award_id", "entity_id", "source_type", "source_ref", "source_event_at", "local_date", "rule_version")
    missing = [key for key in required if not str(event.get(key, "")).strip()]
    if missing:
        raise ProgressionValidationError("Required progression fields missing: " + ", ".join(missing))
    if isinstance(event.get("amount"), bool) or not isinstance(event.get("amount"), int):
        raise ProgressionValidationError("amount must be a signed integer")
    if not -(2**63) <= event["amount"] < 2**63:
        raise ProgressionValidationError("amount must fit a signed 64-bit integer")
    entity_id = event["entity_id"]
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")
    try:
        datetime.strptime(event["local_date"], "%Y-%m-%d")
    except ValueError as exc:
        raise ProgressionValidationError("local_date must use YYYY-MM-DD") from exc
    try:
        event_time = datetime.fromisoformat(event["source_event_at"].replace("Z", "+00:00"))
        if event_time.tzinfo is None:
            raise ValueError("timezone offset required")
    except ValueError as exc:
        raise ProgressionValidationError("source_event_at must be an ISO-8601 timestamp with timezone") from exc
    if event["source_type"] == "manual_adjustment" and not str(event.get("reason", "")).strip():
        raise ProgressionValidationError("manual adjustments require an attributed reason")
    provenance = event.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ProgressionValidationError("provenance must be a JSON object")
    if event["source_type"] == "manual_adjustment" and not str(provenance.get("actor", "")).strip():
        raise ProgressionValidationError("manual adjustments require provenance.actor attribution")
    if event.get("correction_of") is not None and not str(event["correction_of"]).strip():
        raise ProgressionValidationError("correction_of cannot be empty")
    if bool(event.get("correction_of")) != (event["source_type"] == "correction"):
        raise ProgressionValidationError("corrections must use source_type=correction and correction_of")
    try:
        provenance_json = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ProgressionValidationError("provenance must be JSON serializable") from exc
    return provenance_json


def _insert_award(conn, event):
    provenance = _validate_event(event)
    normalized = dict(event)
    normalized["provenance"] = provenance
    existing = conn.execute("SELECT * FROM xp_ledger WHERE award_id=?", (event["award_id"],)).fetchone()
    comparable = ("entity_id", "amount", "source_type", "source_ref", "source_event_at", "local_date", "rule_version", "provenance", "correction_of", "reason", "details")
    if existing:
        if all(existing[k] == normalized.get(k) for k in comparable):
            return False
        raise ProgressionValidationError("award_id already exists with conflicting content")
    if event.get("correction_of"):
        original = conn.execute("SELECT entity_id FROM xp_ledger WHERE award_id=?", (event["correction_of"],)).fetchone()
        if not original or original["entity_id"] != event["entity_id"]:
            raise ProgressionValidationError("correction_of must identify an existing award for the same entity")
    conn.execute("""INSERT INTO xp_ledger
        (award_id, entity_id, amount, source_type, source_ref, source_event_at,
         local_date, rule_version, provenance, created_at, correction_of, reason, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event["award_id"], event["entity_id"], event["amount"], event["source_type"],
         event["source_ref"], event["source_event_at"], event["local_date"],
         event["rule_version"], provenance, _now(), event.get("correction_of"),
         event.get("reason"), str(event.get("details", ""))))
    return True


def _assert_reconciliation_unlocked(conn):
    lock = conn.execute("SELECT run_id FROM xp_reconciliation_lock WHERE singleton=1").fetchone()
    if lock:
        raise ReconciliationInProgressError("XP reconciliation is applying or recovering; retry after it completes")


def record_award(event, project=True):
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _assert_reconciliation_unlocked(conn)
        created = _insert_award(conn, event)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if project:
        project_entities([event["entity_id"]])
    return {"created": created, "award_id": event["award_id"], "entity_id": event["entity_id"]}


def level_for_total(total):
    import math
    discriminant = max(0, 0.25 + 2 * total / 1000)
    return max(1, math.floor(0.5 + math.sqrt(discriminant)))


def level_progress(total):
    level = level_for_total(total)
    base = 500 * level * (level - 1)
    next_base = 500 * (level + 1) * level
    return {"level": level, "current_level_xp": base, "next_level_xp": next_base,
            "xp_into_level": total - base, "xp_for_next_level": next_base - base,
            "progress_percent": min(100, max(0, (total - base) * 100 / (next_base - base)))}


def get_entity_total(entity_id, root=None):
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")
    conn = get_connection(root)
    try:
        return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE entity_id=?", (entity_id,)).fetchone()[0]
    finally:
        conn.close()


def get_xp_history(limit=100, entity_id="keeper"):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM xp_ledger WHERE entity_id=? ORDER BY local_date DESC, created_at DESC, award_id DESC LIMIT ?", (entity_id, max(1, min(int(limit), 1000)))).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["date"] = item["local_date"]
            item["provenance"] = json.loads(item["provenance"])
            item["details"] = item["details"] or item["reason"] or item["source_type"]
            result.append(item)
        return result
    finally:
        conn.close()


def get_total_xp(entity_id="keeper"):
    return get_entity_total(entity_id)


def get_unresolved_legacy_count():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM xp_logs").fetchone()[0]
    finally:
        conn.close()


def project_entities(entity_ids, root=None):
    """Refresh derived JSON and marked Markdown projections after ledger commit."""
    errors = []
    for entity_id in sorted(set(entity_ids)):
        try:
            _project_entity(entity_id, root=root)
        except Exception as exc:  # persist per-entity outcome for accurate recovery
            errors.append(f"{entity_id}: {exc}")
    if errors:
        raise ProjectionError("ledger committed; compatibility projection failed (rerun to repair): " + "; ".join(errors))


def _atomic_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".xp-projection-", dir=os.path.dirname(path), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _project_entity(entity_id, root=None):
    vault_root, _ = _paths_for_root(root)
    total = get_entity_total(entity_id, root=root)
    level = level_for_total(total)
    stats_path = os.path.join(vault_root, "Bridge", "CompanionStats.json")
    if not os.path.isfile(stats_path):
        raise FileNotFoundError(f"CompanionStats.json unavailable at {stats_path}")
    with open(stats_path, "r", encoding="utf-8-sig") as stream:
        stats_data = json.load(stream)
    name = "Keeper" if entity_id == "keeper" else entity_id.removeprefix("companion:")
    companions = stats_data.get("companions")
    if not isinstance(companions, dict) or name not in companions:
        raise KeyError(f"entity {name!r} is absent from CompanionStats.json")
    # P3 will reconcile unresolved legacy totals before replacing legacy fields.
    companions[name]["ledger_xp"] = total
    companions[name]["ledger_level"] = level
    _atomic_text(stats_path, json.dumps(stats_data, indent=4, ensure_ascii=False))

    xp_path = (os.path.join(vault_root, "Keeper", "XP.md") if entity_id == "keeper"
               else os.path.join(vault_root, "Companions", name, "XP.md"))
    block_start, block_end = "<!-- NAVIS XP LEDGER START -->", "<!-- NAVIS XP LEDGER END -->"
    conn = get_connection(root)
    try:
        rows = conn.execute("SELECT local_date, amount, details, source_type FROM xp_ledger WHERE entity_id=? ORDER BY local_date, created_at, award_id", (entity_id,)).fetchall()
    finally:
        conn.close()
    block = [block_start, f"**Canonical total: {total} XP (Level {level})**", ""]
    block.extend(f"- **{r['local_date']}:** {r['amount']:+d} XP ({r['details'] or r['source_type']})" for r in rows)
    block.append(block_end)
    content = ""
    if os.path.isfile(xp_path):
        with open(xp_path, "r", encoding="utf-8-sig") as stream:
            content = stream.read()
    import re
    pattern = re.compile(re.escape(block_start) + r".*?" + re.escape(block_end), re.S)
    if pattern.search(content):
        content = pattern.sub("\n".join(block), content)
    else:
        content = content.rstrip() + "\n\n" + "\n".join(block) + "\n"
    _atomic_text(xp_path, content)


def apply_source_batch(events):
    """Atomically capture the first recipient set and idempotently reconcile later source edits."""
    conn = get_connection()
    touched = set()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _assert_reconciliation_unlocked(conn)
        source_ref = events[0]["source_ref"] if events else ""
        source_type = events[0]["source_type"] if events else "journal_daily"
        existing = conn.execute("SELECT entity_id, amount, last_award_id FROM xp_source_state WHERE source_type=? AND source_ref=?", (source_type, source_ref)).fetchall()
        existing_by_entity = {row["entity_id"]: row for row in existing}
        if existing_by_entity:
            events = [e for e in events if e["entity_id"] in existing_by_entity]
        for event in events:
            event = dict(event)
            row = existing_by_entity.get(event["entity_id"])
            touched.add(event["entity_id"])
            desired = event["amount"]
            old_amount = row["amount"] if row else 0
            if desired == old_amount:
                continue
            delta = desired - old_amount
            if row:
                event["award_id"] = "correction:" + hashlib.sha256(f"{event['entity_id']}|{source_ref}|{row['last_award_id']}|{desired}|{json.dumps(event['provenance'], sort_keys=True)}".encode()).hexdigest()
                event["amount"] = delta
                event["source_type"] = "correction"
                event["correction_of"] = row["last_award_id"]
                event["reason"] = "Journal evidence changed; compensating entry preserves the original award."
            _insert_award(conn, event)
            conn.execute("""INSERT INTO xp_source_state(entity_id,source_type,source_ref,amount,last_award_id,provenance,local_date)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(entity_id,source_type,source_ref) DO UPDATE SET amount=excluded.amount,last_award_id=excluded.last_award_id,provenance=excluded.provenance,local_date=excluded.local_date""",
                (event["entity_id"], source_type, source_ref, desired, event["award_id"], json.dumps(event["provenance"], sort_keys=True), event["local_date"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if touched:
        project_entities(touched)
    return sorted(touched)


def get_source_states(source_type, source_ref):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT entity_id, amount, last_award_id, provenance FROM xp_source_state WHERE source_type=? AND source_ref=?", (source_type, source_ref)).fetchall()
        return {row["entity_id"]: {"amount": row["amount"], "last_award_id": row["last_award_id"], "provenance": json.loads(row["provenance"])} for row in rows}
    finally:
        conn.close()


def add_achievement(code, name, description, date_achieved=None, category="Uncategorized"):
    conn = get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO achievements(code,name,description,date_achieved,category) VALUES(?,?,?,?,?)", (code, name, description, date_achieved, category))
    finally:
        conn.close()


def get_achievements():
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM achievements ORDER BY category, date_achieved DESC")]
    finally:
        conn.close()


def get_available_talent_points(entity_id="keeper", root=None):
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")
    conn = get_connection(root)
    try:
        total_xp = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE entity_id=?", (entity_id,)).fetchone()[0]
        current_level = level_for_total(total_xp)
        allocated = conn.execute("SELECT COALESCE(SUM(rank), 0) FROM talent_allocations WHERE entity_id=?", (entity_id,)).fetchone()[0]
        return max(0, current_level - allocated)
    finally:
        conn.close()


def get_talent_allocations(entity_id="keeper", root=None):
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")
    conn = get_connection(root)
    try:
        rows = conn.execute(
            "SELECT entity_id, node_id, rank, allocated_at FROM talent_allocations WHERE entity_id=? ORDER BY allocated_at ASC",
            (entity_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_talent_nodes(root=None):
    conn = get_connection(root)
    try:
        rows = conn.execute(
            "SELECT id, branch, tier, prerequisites, max_rank, perk_key, name, description FROM talent_nodes ORDER BY branch ASC, tier ASC, id ASC"
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            raw_prereqs = item.get("prerequisites", "[]")
            try:
                item["prerequisites"] = json.loads(raw_prereqs) if raw_prereqs.startswith("[") else [p.strip() for p in raw_prereqs.split(",") if p.strip()]
            except Exception:
                item["prerequisites"] = []
            result.append(item)
        return result
    finally:
        conn.close()

