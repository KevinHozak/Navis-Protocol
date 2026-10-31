"""
holocron_engine.py - Weekly Holocron Telemetry & Synthesis Engine

Aggregates 7-day operating cycles (Monday-Sunday, ISO-8601) from Navis-Vault daily journals
and the canonical Keeper progression ledger to generate immutable Weekly Holocrons.
"""

import os
import re
import json
import sqlite3
from html import escape
import hashlib
from pathlib import Path

from services.holocron_evidence import journal_source, source_path, share_safe
from datetime import date, datetime, timedelta, timezone
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Any, Tuple

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")

MANOR_MAPPING = {
    "sanctum": {"id": "SANCTUM", "name": "The Sanctum", "icon": "🏰", "color": "#a855f7"},
    "high-velocity": {"id": "HIGH_VELOCITY_FRONT", "name": "High-Velocity Front", "icon": "⚡", "color": "#00d4ff"},
    "front": {"id": "HIGH_VELOCITY_FRONT", "name": "High-Velocity Front", "icon": "⚡", "color": "#00d4ff"},
    "daily work": {"id": "HIGH_VELOCITY_FRONT", "name": "High-Velocity Front", "icon": "⚡", "color": "#00d4ff"},
    "work": {"id": "HIGH_VELOCITY_FRONT", "name": "High-Velocity Front", "icon": "⚡", "color": "#00d4ff"},
    "domestic": {"id": "DOMESTIC_BREACH", "name": "Domestic Breach", "icon": "🛡️", "color": "#10b981"},
    "home": {"id": "DOMESTIC_BREACH", "name": "Domestic Breach", "icon": "🛡️", "color": "#10b981"},
    "bureaucratic": {"id": "BUREAUCRATIC_GAUNTLET", "name": "Bureaucratic Gauntlet", "icon": "⚖️", "color": "#f59e0b"},
    "gauntlet": {"id": "BUREAUCRATIC_GAUNTLET", "name": "Bureaucratic Gauntlet", "icon": "⚖️", "color": "#f59e0b"},
    "finances": {"id": "BUREAUCRATIC_GAUNTLET", "name": "Bureaucratic Gauntlet", "icon": "⚖️", "color": "#f59e0b"},
    "kinetic": {"id": "KINETIC_OUTLAND", "name": "Kinetic Outland", "icon": "🧭", "color": "#ff4d4d"},
    "outland": {"id": "KINETIC_OUTLAND", "name": "Kinetic Outland", "icon": "🧭", "color": "#ff4d4d"},
}

DEFAULT_MANOR = {"id": "GENERAL", "name": "General Mandates", "icon": "📜", "color": "#94a3b8"}


def resolve_manor(header_text: str) -> Dict[str, str]:
    """Map section header text to a canonical Manor."""
    normalized = header_text.lower().replace("#", "").strip()
    for key, manor in MANOR_MAPPING.items():
        if key in normalized:
            return manor
    return DEFAULT_MANOR


def get_week_date_range(week_id: str) -> Tuple[str, str, List[str]]:
    """
    Given an ISO week identifier (e.g. '2026-W40'), returns (start_date, end_date, [7 dates]).
    Monday is day 1, Sunday is day 7.
    """
    m = re.match(r"^(\d{4})-W(\d{1,2})$", week_id.strip())
    if not m:
        raise ValueError(f"Invalid ISO week format '{week_id}'. Expected 'YYYY-Www' (e.g. '2026-W40').")
    year = int(m.group(1))
    week = int(m.group(2))
    
    start_date = date.fromisocalendar(year, week, 1)
    end_date = date.fromisocalendar(year, week, 7)
    
    date_list = [(start_date + timedelta(days=i)).isoformat() for i in range(7)]
    return start_date.isoformat(), end_date.isoformat(), date_list


def get_current_iso_week(ref_date: Optional[date] = None) -> str:
    """Return the current ISO week string (e.g. '2026-W40') anchored to the 03:00 local cutoff."""
    if ref_date is None:
        try:
            from services.recurrence import journal_day
            ref_date = date.fromisoformat(journal_day())
        except Exception:
            ref_date = date.today()
    iso_year, iso_week, _ = ref_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_previous_iso_week(ref_date: Optional[date] = None) -> str:
    """Return the previous concluded ISO week string (e.g. '2026-W39') anchored to the 03:00 cutoff."""
    if ref_date is None:
        try:
            from services.recurrence import journal_day
            ref_date = date.fromisoformat(journal_day())
        except Exception:
            ref_date = date.today()
    prev = ref_date - timedelta(days=7)
    iso_year, iso_week, _ = prev.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def find_journal_file(vault_root: str, date_str: str) -> Optional[str]:
    """Locate a daily journal file across supported directory conventions."""
    parts = date_str.split("-")
    if len(parts) == 3:
        year, month, _ = parts
        candidate = os.path.join(vault_root, "Journal", year, month, f"{date_str}.md")
        if source_path(vault_root, os.path.relpath(candidate, vault_root)) and os.path.isfile(candidate):
            return candidate
    
    # Flat journal fallback
    flat_candidate = os.path.join(vault_root, "Journal", f"{date_str}.md")
    if source_path(vault_root, os.path.relpath(flat_candidate, vault_root)) and os.path.isfile(flat_candidate):
        return flat_candidate
    
    return None


def parse_daily_journal(file_path: str, date_str: str) -> Dict[str, Any]:
    """Parse a single daily journal file and return task counts and metadata."""
    res = {
        "date": date_str,
        "availability": "missing",
        "completed": 0,
        "pending": 0,
        "total": 0,
        "precision": 0.0,
        "realm": None,
        "prime_beast": None,
        "squad_members": [],
        "manor_counts": Counter()
    }
    
    if not file_path:
        return res
        
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return res
    except (OSError, UnicodeError):
        res["availability"] = "unavailable"
        return res

    res["availability"] = "available"

    current_manor = DEFAULT_MANOR
    in_squad_section = False

    for line in lines:
        sline = line.strip()
        
        # Section header
        if sline.startswith("## "):
            current_manor = resolve_manor(sline)
            in_squad_section = ("squad" in sline.lower() or "party" in sline.lower())
            continue
            
        # Metadata tokens
        if "Realm:" in sline:
            rname = sline.split("Realm:")[-1].strip().strip("*`")
            if rname:
                res["realm"] = rname
            in_squad_section = False
        elif "Prime Beast:" in sline:
            bname = sline.split("Prime Beast:")[-1].strip().strip("*`")
            if bname:
                res["prime_beast"] = bname
            in_squad_section = False
        elif "Active Squad" in sline or "Active Party" in sline:
            in_squad_section = True
        elif in_squad_section and sline.startswith("-") and not sline.startswith("- ["):
            member = sline.lstrip("- *`").strip()
            if member:
                res["squad_members"].append(member)
                
        # Task checkboxes
        if sline.startswith("- [x]"):
            in_squad_section = False
            res["completed"] += 1
            res["total"] += 1
            res["manor_counts"][current_manor["id"]] += 1
        elif sline.startswith("- [ ]"):
            in_squad_section = False
            res["pending"] += 1
            res["total"] += 1

    if res["total"] > 0:
        res["precision"] = round((res["completed"] / res["total"]) * 100, 1)

    return res


def query_progression_telemetry(vault_root: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """Query Keeper/navis_progression.db for weekly XP breakdown and unlocked achievements."""
    db_path = os.path.join(vault_root, "Keeper", "navis_progression.db")
    result = {
        "availability": "missing",
        "fingerprint": None,
        "total_xp": 0,
        "xp_breakdown": {
            "tasks": 0,
            "combat": 0,
            "directives": 0,
            "missions": 0,
            "talents": 0
        },
        "daily_xp": defaultdict(int),
        "achievements_unlocked": [],
        "talent_telemetry": {
            "total_bonus_xp": 0,
            "perks": []
        }
    }
    
    if not source_path(vault_root, "Keeper/navis_progression.db") or not os.path.isfile(db_path):
        return result
        
    conn = None
    result["availability"] = "unavailable"
    try:
        conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        columns = [c[1] for c in cur.execute("PRAGMA table_info(xp_ledger)").fetchall()]
        if "entity_id" not in columns:
            raise sqlite3.DatabaseError("Unscoped legacy ledger")
        entity_filter = " AND lower(entity_id) = 'keeper'"
        # XP Ledger aggregation
        cur.execute("""
            SELECT local_date, source_type, SUM(amount) as xp_sum
            FROM xp_ledger
            WHERE local_date >= ? AND local_date <= ?
        """ + entity_filter + " GROUP BY local_date, source_type", (start_date, end_date))
        
        for row in cur.fetchall():
            ldate = row["local_date"]
            stype = (row["source_type"] or "").lower()
            amount = int(row["xp_sum"] or 0)
            
            result["total_xp"] += amount
            result["daily_xp"][ldate] += amount
            
            if "combat" in stype:
                result["xp_breakdown"]["combat"] += amount
            elif "directive" in stype:
                result["xp_breakdown"]["directives"] += amount
            elif "mission" in stype:
                result["xp_breakdown"]["missions"] += amount
            elif "talent" in stype or "perk" in stype:
                result["xp_breakdown"]["talents"] += amount
            else:
                result["xp_breakdown"]["tasks"] += amount

        result["availability"] = "available"
        # Query distinct talent perk contributions if table supports it
        try:
            columns = [c[1] for c in cur.execute("PRAGMA table_info(xp_ledger)").fetchall()]
            if "reason" in columns:
                cur.execute("""
                    SELECT reason, source_type, SUM(amount) as perk_sum, COUNT(*) as perk_count
                    FROM xp_ledger
                    WHERE local_date >= ? AND local_date <= ?
                      AND (reason LIKE 'talent_perk:%' OR source_type = 'talent_perk')
                """ + entity_filter + ' GROUP BY reason', (start_date, end_date))
                perks_list = []
                total_talent_sum = 0
                for row in cur.fetchall():
                    r_val = row["reason"] or f"talent_perk:{row['source_type']}"
                    perk_key = r_val.replace("talent_perk:", "").strip()
                    perk_sum = int(row["perk_sum"] or 0)
                    total_talent_sum += perk_sum
                    perks_list.append({
                        "perk_key": perk_key,
                        "bonus_xp": perk_sum,
                        "count": int(row["perk_count"] or 0)
                    })
                result["talent_telemetry"] = {
                    "total_bonus_xp": total_talent_sum,
                    "perks": perks_list
                }
                if result["xp_breakdown"]["talents"] < total_talent_sum:
                    result["xp_breakdown"]["talents"] = total_talent_sum
        except Exception:
            pass

        result["fingerprint"] = hashlib.sha256(json.dumps({"total": result["total_xp"], "daily": result["daily_xp"], "breakdown": result["xp_breakdown"]}, sort_keys=True).encode()).hexdigest()
        # Achievements unlocked
        cur.execute("""
            SELECT code, name, description, date_achieved
            FROM achievements
            WHERE date_achieved >= ? AND date_achieved <= ?
            ORDER BY date_achieved ASC
        """, (start_date, end_date))
        
        for row in cur.fetchall():
            result["achievements_unlocked"].append({
                "code": row["code"],
                "name": row["name"],
                "description": row["description"] or "",
                "icon": "🛡️",
                "unlocked_at": row["date_achieved"]
            })
            
        conn.close()
    except Exception:
        # Graceful degradation if database is temporarily locked or tables differ
        pass
        
    finally:
        if conn is not None:
            conn.close()
    return result


def synthesize_tactical_debrief(
    week_id: str,
    precision_rate: float,
    completed_tasks: int,
    total_xp: int,
    threats_count: int,
    top_sector_name: str,
    top_beast: Optional[str] = None,
    talent_bonus_xp: int = 0
) -> str:
    """Generate a crisp, narrative RPG tactical debrief for the Holocron."""
    precision = f"{precision_rate}% observed checklist completion" if precision_rate is not None else "Checklist completion unavailable"
    xp = f"{total_xp:,} signed Keeper XP" if total_xp is not None else "Keeper XP unavailable"
    talent = f" Recorded talent-perk contribution: {talent_bonus_xp:,} XP." if talent_bonus_xp else ""
    return f"{precision}; {xp}. Journal threat mentions do not establish combat outcomes.{talent}"


def build_weekly_holocron(
    vault_root: Optional[str] = None,
    week_id: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Main aggregator: compiles daily logs, XP ledger, and readiness into a complete Weekly Holocron.
    Supports concluded weeks (persisted immutably) and live Week-to-Date in-flight cycles.
    """
    root = vault_root or NAVIS_ROOT
    usable_root = all(source_path(root, part) and Path(root, part).is_dir() for part in ("Bridge", "Journal"))
    current_week = get_current_iso_week()
    target_week = week_id or get_previous_iso_week()

    # Determine 03:00-anchored operational day
    try:
        from services.recurrence import journal_day
        current_op_day = journal_day()
    except Exception:
        current_op_day = date.today().isoformat()

    is_in_flight = (target_week >= current_week)
    cycle_status = "in_flight" if is_in_flight else "concluded"
    
    holocron_dir = os.path.join(root, "Bridge", "Holocron", "Weekly")
    artifact_path = os.path.join(holocron_dir, f"{target_week}.json")
    
    # Re-read evidence on every request: deleted sources and legacy inferred caches
    # must not be presented as current facts. Historical files remain untouched
    # unless explicit regeneration is requested.
    start_date, end_date, date_list = get_week_date_range(target_week)
    
    # 1. Parse daily journal entries
    daily_records = []
    total_completed = 0
    total_pending = 0
    logged_days = 0
    beasts_encountered = []
    squad_deployments = Counter()
    manor_totals = Counter()
    days_elapsed = 0
    sources = []
    
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    for i, date_str in enumerate(date_list):
        source = journal_source(root, date_str)
        sources.append(source)
        jfile = find_journal_file(root, date_str) if source["status"] == "available" else None
        day_data = parse_daily_journal(jfile, date_str)
        if jfile and day_data["availability"] != "available":
            source["status"] = day_data["availability"]
            jfile = None
        if jfile and journal_source(root, date_str).get("fingerprint") != source.get("fingerprint"):
            source["status"] = "changed"
            jfile = None
            day_data = parse_daily_journal(None, date_str)
        day_name = day_names[i]
        
        if jfile:
            logged_days += 1
            
        total_completed += day_data["completed"]
        total_pending += day_data["pending"]
        
        for manor_id, count in day_data["manor_counts"].items():
            manor_totals[manor_id] += count
            
        if day_data["prime_beast"]:
            beasts_encountered.append(day_data["prime_beast"])
            
        for member in day_data["squad_members"]:
            squad_deployments[member] += 1

        # Classify day progression
        if date_str < current_op_day:
            day_status = "concluded"
            days_elapsed += 1
        elif date_str == current_op_day:
            day_status = "active"
            days_elapsed += 1
        else:
            day_status = "upcoming"
            
        daily_records.append({
            "date": date_str,
            "day_name": day_name,
            "day_status": day_status,
            "completed": day_data["completed"] if jfile else None,
            "pending": day_data["pending"] if jfile else None,
            "total": day_data["total"] if jfile else None,
            "precision": day_data["precision"] if jfile and day_data["total"] else None,
            "source_status": source["status"],
            "source_id": source["id"],
            "realm": day_data["realm"] or "Command Hub",
            "prime_beast": day_data["prime_beast"] or "None"
        })

    total_tasks = total_completed + total_pending
    overall_precision = round((total_completed / total_tasks * 100), 1) if total_tasks > 0 else 0.0
    
    # 2. Query Keeper progression ledger
    prog_data = query_progression_telemetry(root, start_date, end_date)
    
    # Attach daily XP to daily records
    for record in daily_records:
        record["xp"] = prog_data["daily_xp"].get(record["date"], 0) if prog_data["availability"] == "available" else None

    # 3. Compile Sector Manor distribution
    manor_order = ["HIGH_VELOCITY_FRONT", "SANCTUM", "DOMESTIC_BREACH", "BUREAUCRATIC_GAUNTLET", "KINETIC_OUTLAND"]
    sector_distribution = []
    top_sector_name = "Command Operations"
    top_sector_count = -1
    
    for manor_key in manor_order:
        # Find matching manor definition
        manor_def = next((m for m in MANOR_MAPPING.values() if m["id"] == manor_key), DEFAULT_MANOR)
        completed_in_manor = manor_totals[manor_key]
        pct = round((completed_in_manor / total_completed * 100), 1) if total_completed > 0 else 0.0
        
        if completed_in_manor > top_sector_count:
            top_sector_count = completed_in_manor
            top_sector_name = manor_def["name"]
            
        sector_distribution.append({
            "sector_id": manor_def["id"],
            "name": manor_def["name"],
            "icon": manor_def["icon"],
            "completed": completed_in_manor if logged_days else None,
            "total": completed_in_manor if logged_days else None, # Tracked against completions
            "percentage": pct if logged_days else None,
            "color": manor_def["color"]
        })

    # These measures have no supported historical source in this aggregator.
    current_level = None
    level_progress_percent = None
    unique_beasts = list(dict.fromkeys(beasts_encountered))
    top_beast = unique_beasts[0] if unique_beasts else None
    beasts_neutralized = []
    squad_mvp = None
    if squad_deployments:
        top_member, dep_count = squad_deployments.most_common(1)[0]
        squad_mvp = {"name": top_member, "role": "Most journal mentions",
                     "deployments": dep_count}

    talent_bonus_xp = prog_data.get("talent_telemetry", {}).get("total_bonus_xp", 0)

    # 7. Generate tactical debrief
    tactical_debrief = synthesize_tactical_debrief(
        week_id=target_week,
        precision_rate=overall_precision if logged_days and total_tasks else None,
        completed_tasks=total_completed,
        total_xp=prog_data["total_xp"] if prog_data["availability"] == "available" else None,
        threats_count=len(unique_beasts),
        top_sector_name=top_sector_name,
        top_beast=top_beast,
        talent_bonus_xp=talent_bonus_xp
    )

    holocron_payload = {
        "schema_version": "2.0.0",
        "week_id": target_week,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "America/Chicago",
        "boundary_cutoff": "03:00:00",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "is_synthetic": False,
        "summary": {
            "total_tasks": total_tasks,
            "completed_tasks": total_completed,
            "pending_tasks": total_pending,
            "precision_rate": overall_precision,
            "logged_days": logged_days,
            "total_xp_gained": prog_data["total_xp"],
            "talent_bonus_xp": talent_bonus_xp,
            "current_level": current_level,
            "level_progress_percent": level_progress_percent,
            "threats_neutralized": None,
            "battles_fought": None,
            "avg_readiness": None,
            "deep_work_hours": None,
            "is_in_flight": is_in_flight,
            "cycle_status": cycle_status,
            "days_elapsed": max(1, min(7, days_elapsed)) if is_in_flight else 7,
            "days_remaining": max(0, 7 - days_elapsed) if is_in_flight else 0,
            "current_journal_day": current_op_day
        },
        "is_in_flight": is_in_flight,
        "cycle_status": cycle_status,
        "debrief_source": "rule_based",
        "tactical_debrief": tactical_debrief,
        "daily_telemetry": daily_records,
        "sector_distribution": sector_distribution,
        "progression": {
            "total_xp": prog_data["total_xp"],
            "xp_breakdown": prog_data["xp_breakdown"],
            "current_level": current_level,
            "level_progress_percent": level_progress_percent,
            "achievements_unlocked": prog_data["achievements_unlocked"],
            "talent_telemetry": prog_data.get("talent_telemetry", {"total_bonus_xp": 0, "perks": []})
        },
        "combat": {
            "battles_fought": None,
            "victories": None,
            "fled": None,
            "total_damage_dealt": None,
            "mentioned_beasts": [{"name": b} for b in unique_beasts],
            "beasts_neutralized": beasts_neutralized
        },
        "squad_mvp": squad_mvp
    }

    summary = holocron_payload["summary"]
    if not logged_days:
        for key in ("total_tasks", "completed_tasks", "pending_tasks", "precision_rate"):
            summary[key] = None
    elif not total_tasks:
        summary["precision_rate"] = None
    if prog_data["availability"] != "available":
        summary["total_xp_gained"] = None
        summary["talent_bonus_xp"] = None
        holocron_payload["progression"]["total_xp"] = None
        holocron_payload["progression"]["xp_breakdown"] = None
    journal_ids = [s["id"] for s in sources if s["status"] == "available"]
    sources.append({"id": "keeper-ledger", "status": prog_data["availability"], "label": "Keeper XP ledger", "fingerprint": prog_data["fingerprint"]})
    task_status = "available" if logged_days == 7 else "partial" if logged_days else "unavailable"
    metrics = {
        "precision_rate": {"status": task_status if total_tasks else "unavailable", "rule": "Checked items / all checklist items in readable journals; no items means unavailable.", "source_ids": journal_ids},
        "total_xp_gained": {"status": prog_data["availability"], "rule": "Sum signed Keeper ledger amounts by local_date, inclusive; combat XP is not a victory count.", "source_ids": ["keeper-ledger"]},
        "threats_neutralized": {"status": "unavailable", "rule": "Journal Prime Beast mentions do not prove victories.", "source_ids": []},
        "avg_readiness": {"status": "unavailable", "rule": "No historical readiness measurements are aggregated.", "source_ids": []},
        "deep_work_hours": {"status": "unavailable", "rule": "Checklist counts are not measured focus duration.", "source_ids": []},
        "squad_mentions": {"status": task_status, "rule": "Count Active Squad journal mentions; not a performance ranking.", "source_ids": journal_ids},
    }
    holocron_payload["evidence"] = {"start_date": start_date, "end_date": end_date,
        "logged_days": logged_days, "sources": sources, "metrics": metrics,
        "interpretation": {"kind": "deterministic_summary", "source_ids": journal_ids + ["keeper-ledger"],
                           "support": "References support input metrics only, not generated conclusions."}}
    from services.holocron_decisions import decision_review
    holocron_payload["decision_review"] = share_safe(decision_review(root, sources))
    metrics["decision_review"] = {"status": task_status, "rule": "Compare matching checkbox labels on the first and last readable days; unchecked states do not prove blockers or urgency. Suggestions are rule-based review prompts.", "source_ids": holocron_payload["decision_review"]["source_ids"]}
    if not force and source_path(root, f"Bridge/Holocron/Weekly/{target_week}.json"):
        try:
            with open(artifact_path, encoding="utf-8-sig") as stream:
                previous = json.load(stream)
            if (previous.get("schema_version") == "2.0.0" and previous.get("summary") == summary
                    and previous.get("evidence", {}).get("sources") == sources
                    and previous.get("debrief_source") in {"ollama", "openrouter"}):
                holocron_payload["tactical_debrief"] = previous["tactical_debrief"]
                holocron_payload["debrief_source"] = previous["debrief_source"]
                holocron_payload["evidence"]["interpretation"]["kind"] = "ai_interpretation"
        except (OSError, ValueError, KeyError):
            pass
    holocron_payload = share_safe(holocron_payload)
    # Persist artifact (JSON and Standalone HTML)
    try:
        safe_outputs = all(source_path(root, relative) is not None for relative in (
            f"Bridge/Holocron/Weekly/{target_week}.json",
            f"Bridge/Holocron/Weekly/{target_week}.html",
            "Bridge/Holocron/weekly_manifest.json",
        ))
        if not usable_root or not safe_outputs or (not force and os.path.exists(artifact_path)):
            return holocron_payload
        os.makedirs(holocron_dir, exist_ok=True)
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(holocron_payload, f, indent=2, ensure_ascii=False)
        html_path = os.path.join(holocron_dir, f"{target_week}.html")
        export_standalone_html(holocron_payload, html_path)
        update_holocron_manifest(root, holocron_payload)
    except Exception:
        # If vault root is read-only or fixture mode, allow returning in-memory payload
        pass

    return holocron_payload


def export_standalone_html(payload: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """Generate a self-contained, zero-dependency HTML dashboard for the Holocron."""
    def escaped(value):
        if isinstance(value, dict):
            return {key: escaped(item) for key, item in value.items()}
        if isinstance(value, list):
            return [escaped(item) for item in value]
        return escape(value, quote=True) if isinstance(value, str) else value

    payload = escaped(share_safe(payload))
    def display(value, suffix=""):
        return "Unavailable" if value is None else f"{value}{suffix}"

    week_id = payload.get("week_id", "Unknown")
    summary = payload.get("summary", {})
    tactical_debrief = payload.get("tactical_debrief", "")
    decision = payload.get("decision_review", {})
    decision_refs = " ".join(f'<a href="#source-{source}">{source}</a>' for source in decision.get("source_ids", []))
    daily = payload.get("daily_telemetry", [])
    sectors = payload.get("sector_distribution", [])
    combat = payload.get("combat", {})
    progression = payload.get("progression", {})
    mvp = payload.get("squad_mvp")

    evidence = payload.get("evidence", {})
    source_rows = "".join(f'<li id="source-{item["id"]}">{item.get("date", item.get("label", item["id"]))}: {item["status"]}</li>' for item in evidence.get("sources", []))
    metric_rows = "".join(f'<details><summary>{key}: {item["status"]}</summary><p>{item["rule"]}</p>' +
        " ".join(f'<a href="#source-{source_id}">{source_id}</a>' for source_id in item["source_ids"]) + '</details>' for key, item in evidence.get("metrics", {}).items())
    evidence_html = f'<section class="panel"><h2>Evidence snapshot</h2><p>{payload.get("start_date")} to {payload.get("end_date")}; {evidence.get("logged_days", 0)} readable journal days. Source status at generation; local sources may change.</p>{metric_rows}<ul>{source_rows}</ul><p>References support metric inputs, not AI interpretations.</p></section>'

    # Build day chart HTML
    day_bars = []
    for day in daily:
        prec = round(day.get("precision") or 0)
        status = day.get("day_status", "concluded")
        if status == "upcoming":
            h_pct = 8
            color = "rgba(255, 255, 255, 0.08)"
            val_str = "—"
            border = "border: 1px dashed rgba(255, 255, 255, 0.2);"
            opacity = "opacity: 0.4;"
        elif status == "active":
            h_pct = max(10, min(100, prec))
            color = "#10b981" if prec >= 95 else ("#00d4ff" if prec >= 80 else ("#f59e0b" if prec >= 60 else "#ff4d4d"))
            val_str = display(day.get("precision"), "%")
            border = "border: 1px solid #00d4ff; box-shadow: 0 0 10px rgba(0, 212, 255, 0.4);"
            opacity = "opacity: 1;"
        else:
            h_pct = max(10, min(100, prec))
            color = "#10b981" if prec >= 95 else ("#00d4ff" if prec >= 80 else ("#f59e0b" if prec >= 60 else "#ff4d4d"))
            val_str = display(day.get("precision"), "%")
            border = ""
            opacity = "opacity: 1;"

        day_bars.append(f"""
          <div class="day-col" style="{opacity}">
            <span class="day-val">{val_str}</span>
            <div class="bar-track" style="{border}">
              <div class="bar-fill" style="height: {h_pct}%; background: {color};"></div>
            </div>
            <span class="day-label">{day.get('day_name', '')}{' ⚡' if status == 'active' else ''}</span>
          </div>""")
    day_chart_html = "\n".join(day_bars)

    # Build sector meters HTML
    sector_meters = []
    for s in sectors:
        pct = min(100, s.get("percentage") or 0)
        color = s.get("color", "#00d4ff")
        sector_meters.append(f"""
          <div class="sector-item">
            <div class="sector-info">
              <span class="sector-name">{s.get('icon', '🏰')} {s.get('name', '')}</span>
              <span class="sector-pct">{display(s.get('completed'))} ({display(s.get('percentage'), '%')})</span>
            </div>
            <div class="meter-track">
              <div class="meter-fill" style="width: {pct}%; background: {color};"></div>
            </div>
          </div>""")
    sector_meters_html = "\\n".join(sector_meters)

    # Build threat cards HTML
    threat_cards = []
    for beast in combat.get("beasts_neutralized", []):
        threat_cards.append(f"""
          <div class="threat-card">
            <div class="threat-meta">
              <span class="threat-name">{beast.get('name', 'Threat')}</span>
              <span class="threat-tag">{beast.get('category', 'Adversary')} // {beast.get('difficulty', 'Standard')}</span>
            </div>
            <span class="threat-xp">+{display(beast.get('xp_awarded'))} XP</span>
          </div>""")
    if not threat_cards:
        threat_cards.append('<div style="text-align: center; padding: 1.5rem; color: #64748b; font-family: monospace; font-size: 0.75rem;">NO CRITICAL THREATS LOGGED</div>')
    threat_cards_html = "\\n".join(threat_cards)

    # Build honors HTML
    honors = []
    talent_data = progression.get("talent_telemetry", {})
    if talent_data.get("total_bonus_xp", 0) > 0:
        perk_names = ", ".join(p["perk_key"] for p in talent_data.get("perks", []))
        honors.append(f"""
          <div class="achievement-chip" style="background: rgba(0, 212, 255, 0.1); border-color: rgba(0, 212, 255, 0.3);">
            <span class="achievement-icon">✨</span>
            <div>
              <strong style="font-size: 0.85rem; color: #fff;">Constellation Yields (+{talent_data['total_bonus_xp']:,} XP)</strong>
              <div class="achievement-desc">Active specialization perks: {perk_names}</div>
            </div>
          </div>""")
    for ach in progression.get("achievements_unlocked", []):
        honors.append(f"""
          <div class="achievement-chip">
            <span class="achievement-icon">{ach.get('icon', '🛡️')}</span>
            <div>
              <strong style="font-size: 0.85rem; color: #fff;">{ach.get('name', '')}</strong>
              <div class="achievement-desc">{ach.get('description', '')}</div>
            </div>
          </div>""")
    honors_html = "\n".join(honors) if honors else '<div style="color: #64748b; font-size: 0.8rem; font-family: monospace;">No new achievements unlocked</div>'

    mvp_html = ""
    if mvp:
        mvp_html = f"""
          <div style="margin-top: 0.75rem; background: rgba(0, 212, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.2); padding: 0.75rem; border-radius: 8px; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <span style="font-size: 0.7rem; font-family: monospace; color: #00d4ff; text-transform: uppercase;">Most journal mentions</span>
              <div style="font-size: 0.95rem; font-weight: 700; color: #fff;">{mvp.get('name')} // {mvp.get('role', 'Vanguard')}</div>
            </div>
            <span style="font-family: monospace; font-size: 0.85rem; color: #00d4ff; font-weight: 700;">{mvp.get('deployments', 0)} Journal mentions</span>
          </div>"""

    status_badge = '<span class="badge" style="background: rgba(16, 185, 129, 0.2); border-color: #10b981; color: #10b981;">⚡ LIVE WTD</span>' if payload.get("is_in_flight") else '<span class="badge" style="background: rgba(255, 255, 255, 0.05); border-color: rgba(255, 255, 255, 0.2); color: #94a3b8;">🔒 CONCLUDED</span>'
    debrief_tag = '<span style="font-size: 0.65rem; background: rgba(168, 85, 247, 0.2); border: 1px solid #a855f7; color: #d8b4fe; padding: 0.15rem 0.4rem; border-radius: 4px; margin-left: 0.5rem;">✨ AI INTERPRETATION</span>' if payload.get("debrief_source") in {"ollama", "openrouter"} else '<span style="font-size: 0.65rem; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.15); color: #94a3b8; padding: 0.15rem 0.4rem; border-radius: 4px; margin-left: 0.5rem;">RULE-BASED</span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Navis Protocol // Weekly Holocron - {week_id}</title>
  <style>
    :root {{
      --bg-dark: #07090e;
      --card-bg: rgba(15, 23, 42, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --cyan: #00d4ff;
      --purple: #a855f7;
      --crimson: #ff4d4d;
      --amber: #f59e0b;
      --emerald: #10b981;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg-dark);
      background-image: radial-gradient(circle at 50% 0%, rgba(0, 212, 255, 0.08) 0%, transparent 60%), linear-gradient(to bottom, #07090e, #0b0f19);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      padding: 2rem 1.5rem;
      display: flex;
      justify-content: center;
    }}
    .cockpit-container {{ width: 100%; max-width: 1100px; display: flex; flex-direction: column; gap: 1.5rem; }}
    .top-bar {{ display: flex; justify-content: space-between; align-items: center; background: var(--card-bg); border: 1px solid var(--card-border); backdrop-filter: blur(16px); padding: 1rem 1.5rem; border-radius: 12px; }}
    .badge {{ background: rgba(0, 212, 255, 0.15); border: 1px solid var(--cyan); color: var(--cyan); font-size: 0.75rem; font-family: var(--font-mono); font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; }}
    .briefing-card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-left: 4px solid var(--cyan); padding: 1.25rem 1.5rem; border-radius: 12px; }}
    .briefing-header {{ font-size: 0.8rem; font-family: var(--font-mono); color: var(--cyan); text-transform: uppercase; margin-bottom: 0.4rem; }}
    .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
    .metric-card {{ background: var(--card-bg); border: 1px solid var(--card-border); padding: 1.25rem; border-radius: 12px; display: flex; flex-direction: column; gap: 0.35rem; }}
    .metric-label {{ font-size: 0.75rem; font-family: var(--font-mono); text-transform: uppercase; color: var(--text-muted); }}
    .metric-value {{ font-size: 1.85rem; font-weight: 800; color: #fff; }}
    .analytics-grid {{ display: grid; grid-template-columns: 1.5fr 1fr; gap: 1.5rem; }}
    @media (max-width: 850px) {{ .analytics-grid {{ grid-template-columns: 1fr; }} }}
    .panel {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 1.5rem; display: flex; flex-direction: column; gap: 1.25rem; }}
    .panel-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border); padding-bottom: 0.75rem; font-size: 0.85rem; text-transform: uppercase; font-weight: 700; }}
    .day-chart {{ display: flex; justify-content: space-between; align-items: flex-end; height: 160px; padding-top: 1.5rem; gap: 0.75rem; }}
    .day-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; gap: 0.5rem; }}
    .bar-track {{ width: 100%; max-width: 32px; background: rgba(255, 255, 255, 0.04); border-radius: 6px; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; overflow: hidden; }}
    .bar-fill {{ width: 100%; border-radius: 4px; }}
    .day-label {{ font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); }}
    .day-val {{ font-family: var(--font-mono); font-size: 0.7rem; color: #fff; }}
    .sector-item {{ display: flex; flex-direction: column; gap: 0.35rem; }}
    .sector-info {{ display: flex; justify-content: space-between; font-size: 0.85rem; }}
    .meter-track {{ height: 8px; width: 100%; background: rgba(255, 255, 255, 0.05); border-radius: 4px; overflow: hidden; }}
    .meter-fill {{ height: 100%; border-radius: 4px; }}
    .threat-card {{ display: flex; justify-content: space-between; align-items: center; background: rgba(255, 255, 255, 0.02); border: 1px solid var(--card-border); border-left: 3px solid var(--crimson); padding: 0.65rem 0.85rem; border-radius: 6px; }}
    .threat-name {{ font-size: 0.85rem; font-weight: 600; color: #fff; }}
    .threat-tag {{ font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono); }}
    .threat-xp {{ font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; color: var(--amber); }}
    .achievement-chip {{ display: flex; align-items: center; gap: 0.6rem; background: rgba(168, 85, 247, 0.1); border: 1px solid rgba(168, 85, 247, 0.3); padding: 0.5rem 0.75rem; border-radius: 8px; }}
    .footer-meta {{ display: flex; justify-content: space-between; padding: 1rem 0; border-top: 1px solid var(--card-border); font-size: 0.75rem; font-family: var(--font-mono); color: var(--text-muted); }}
  </style>
</head>
<body>
  <div class="cockpit-container">
    <header class="top-bar">
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span class="badge">NAVIS // HOLOCRON</span>
        <h1 style="font-size: 1.25rem; font-weight: 800; text-transform: uppercase;">Weekly Holocron // {week_id}</h1>
        {status_badge}
      </div>
      <div style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">
        {payload.get('start_date')} → {payload.get('end_date')}
      </div>
    </header>

    <section class="briefing-card">
      <div class="briefing-header" style="display: flex; align-items: center; justify-content: space-between;">
        <span>💠 Command Tactical Debrief</span>
        {debrief_tag}
      </div>
      <p style="font-size: 0.95rem; line-height: 1.5; color: #e2e8f0;">{tactical_debrief}</p>
    </section>

    <section class="briefing-card" id="decision-review">
      <h2>Decision review · rule-based proposal</h2>
      <h3>What changed</h3><p>{decision.get('changed', 'Unknown')}</p>
      <h3>Unresolved</h3><p>{decision.get('unresolved', 'Unknown')}</p>
      <h3>Suggested adjustment</h3><p id="decision-adjustment">{decision.get('adjustment', 'Review missing evidence.')}</p>
      <p>{decision.get('limits', '')}</p><p>Evidence snapshot: {decision_refs}</p>
    </section>

    <section class="metrics-grid">
      <div class="metric-card">
        <span class="metric-label">Precision Clearance</span>
        <div class="metric-value" style="color: var(--cyan);">{display(summary.get('precision_rate'), '%')}</div>
        <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">{display(summary.get('completed_tasks'))} / {display(summary.get('total_tasks'))} Mandates Cleared</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Progression Yield</span>
        <div class="metric-value" style="color: var(--purple);">+{summary.get('total_xp_gained') if summary.get('total_xp_gained') is not None else 'Unavailable'} <span style="font-size: 1rem;">XP</span></div>
        <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">Sovereign Level {display(summary.get('current_level'))}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Threats Neutralized</span>
        <div class="metric-value" style="color: var(--crimson);">{display(summary.get('threats_neutralized'))}</div>
        <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">{display(summary.get('battles_fought'))} Battles Engaged</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">System Readiness</span>
        <div class="metric-value" style="color: var(--emerald);">{display(summary.get('avg_readiness'), '%')}</div>
        <span style="font-size: 0.8rem; color: var(--text-muted); font-family: var(--font-mono);">{display(summary.get('deep_work_hours'))} measured focus hours</span>
      </div>
    </section>

    <div class="analytics-grid">
      <div style="display: flex; flex-direction: column; gap: 1.5rem;">
        <section class="panel">
          <div class="panel-header">
            <span>📊 7-Day Precision & Task Rhythm</span>
            <span style="color: var(--cyan); font-family: var(--font-mono); font-size: 0.75rem;">Target: 80%+</span>
          </div>
          <div class="day-chart">{day_chart_html}</div>
        </section>
        <section class="panel">
          <div class="panel-header">
            <span>🏰 Manor & Sector Labor Distribution</span>
            <span style="color: var(--text-muted); font-family: var(--font-mono); font-size: 0.75rem;">{display(summary.get('completed_tasks'))} Cleared</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.9rem;">{sector_meters_html}</div>
        </section>
      </div>

      <div style="display: flex; flex-direction: column; gap: 1.5rem;">
        <section class="panel">
          <div class="panel-header">
            <span>👾 Threat Neutralization</span>
            <span style="color: var(--crimson); font-family: var(--font-mono); font-size: 0.75rem;">{display(combat.get('victories'))} verified victories</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.65rem;">{threat_cards_html}</div>
        </section>
        <section class="panel">
          <div class="panel-header">
            <span>🏅 Honors & Squad Mentions</span>
            <span style="color: var(--purple); font-family: var(--font-mono); font-size: 0.75rem;">Squad Status</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">{honors_html}</div>
          {mvp_html}
        </section>
      </div>
    </div>

    {evidence_html}
    <footer class="footer-meta">
      <span>BOUNDARY: 03:00 LOCAL // STANDALONE ARCHIVE</span>
      <span>CYCLE {week_id} // DEPLOYED</span>
    </footer>
  </div>
</body>
</html>
"""
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html


def update_holocron_manifest(vault_root: str, latest_payload: Dict[str, Any]):
    """Update Bridge/Holocron/weekly_manifest.json with summary entries."""
    if source_path(vault_root, "Bridge/Holocron/weekly_manifest.json") is None:
        return
    manifest_path = os.path.join(vault_root, "Bridge", "Holocron", "weekly_manifest.json")
    manifest = []
    
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = []

    week_id = latest_payload["week_id"]
    is_in_flight = latest_payload.get("is_in_flight", False)

    # Filter out existing entry for this week
    manifest = [item for item in manifest if item.get("week_id") != week_id]
    
    manifest.append({
        "week_id": week_id,
        "start_date": latest_payload["start_date"],
        "end_date": latest_payload["end_date"],
        "precision_rate": latest_payload["summary"]["precision_rate"],
        "total_xp": latest_payload["summary"]["total_xp_gained"],
        "completed_tasks": latest_payload["summary"]["completed_tasks"],
        "threats_neutralized": latest_payload["summary"]["threats_neutralized"],
        "is_in_flight": is_in_flight,
        "status": "in_flight" if is_in_flight else "concluded",
        "generated_at": latest_payload["generated_at"]
    })
    
    # Sort descending by week_id
    manifest.sort(key=lambda x: x["week_id"], reverse=True)
    
    try:
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_holocron_manifest(vault_root: Optional[str] = None, include_in_flight: bool = True) -> List[Dict[str, Any]]:
    """Retrieve the manifest list of generated weekly holocrons, including the active in-flight cycle."""
    root = vault_root or NAVIS_ROOT
    if not Path(root, "Journal").is_dir():
        return []
    manifest_path = os.path.join(root, "Bridge", "Holocron", "weekly_manifest.json")
    manifest = []
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = []
            
    # Fallback to inspecting directory
    if not manifest:
        holocron_dir = os.path.join(root, "Bridge", "Holocron", "Weekly")
        if os.path.isdir(holocron_dir):
            for fname in sorted(os.listdir(holocron_dir), reverse=True):
                if fname.endswith(".json"):
                    wid = fname[:-5]
                    manifest.append({
                        "week_id": wid,
                        "name": f"Cycle {wid}",
                        "is_in_flight": False,
                        "status": "concluded"
                    })

    current_week = get_current_iso_week()
    for item in manifest:
        if item.get("week_id") == current_week:
            item["is_in_flight"] = True
            item["status"] = "in_flight"
        elif "is_in_flight" not in item:
            item["is_in_flight"] = False
            item["status"] = "concluded"

    if include_in_flight:
        has_current = any(item.get("week_id") == current_week for item in manifest)
        if not has_current:
            start_date, end_date, _ = get_week_date_range(current_week)
            manifest.insert(0, {
                "week_id": current_week,
                "start_date": start_date,
                "end_date": end_date,
                "precision_rate": None,
                "total_xp": None,
                "completed_tasks": None,
                "threats_neutralized": None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_in_flight": True,
                "status": "in_flight"
            })
            
    return manifest


def clean_debrief_output(response: str) -> str:
    """Sanitize raw LLM response by stripping markdown code blocks, headers, and quotes."""
    if not response:
        return ""
    text = response.strip()

    # Handle markdown code fences (```json ... ``` or ``` ... ```)
    if "```" in text:
        code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_block_match:
            inner_block = code_block_match.group(1).strip()
            try:
                parsed = json.loads(inner_block)
                if isinstance(parsed, dict):
                    for key in ["debrief", "tactical_debrief", "response", "summary", "text", "message"]:
                        if key in parsed and isinstance(parsed[key], str):
                            inner_block = parsed[key].strip()
                            break
            except Exception:
                pass
            text = inner_block
        else:
            text = text.replace("```", "").strip()

    # If the text itself is a raw JSON object string
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for key in ["debrief", "tactical_debrief", "response", "summary", "text", "message"]:
                    if key in parsed and isinstance(parsed[key], str):
                        text = parsed[key].strip()
                        break
        except Exception:
            pass

    # Strip markdown headers (# Header, ## Title, ### Tactical Debrief)
    lines = []
    for line in text.splitlines():
        trimmed = line.strip()
        if re.match(r"^#{1,6}\s+", trimmed):
            continue
        lines.append(trimmed)
    text = " ".join([l for l in lines if l])

    # Strip quotation marks and markdown formatting
    text = text.replace('"', '').replace('“', '').replace('”', '').replace('**', '').strip()
    if (text.startswith("'") and text.endswith("'")) or (text.startswith("`") and text.endswith("`")):
        text = text[1:-1].strip()

    return text


async def synthesize_ollama_debrief(holocron_payload: Dict[str, Any]) -> Tuple[str, str]:
    """
    Synthesize an inspiring, military-sci-fi/RPG tactical debrief via local Ollama.
    Guarded by NAVIS_AI_PROVIDER (zero external cloud exposure, strict local privacy).
    Falls back gracefully to the rule-based debrief if Ollama is unavailable or times out.
    Returns (debrief_text, source) where source is 'ollama' or 'rule_based_fallback'.
    """
    rule_based = holocron_payload.get("tactical_debrief", "")
    summary = holocron_payload.get("summary", {})
    week_id = holocron_payload.get("week_id", "")
    is_in_flight = holocron_payload.get("is_in_flight", False)

    # Determine top sector and beasts
    sectors = [sector for sector in holocron_payload.get("sector_distribution", []) if sector.get("completed") is not None]
    top_sector = max(sectors, key=lambda s: s.get("completed", 0)) if sectors else {}
    top_sector_name = top_sector.get("name", "Unavailable")
    top_sector_tasks = top_sector.get("completed", "Unavailable")

    combat = holocron_payload.get("combat", {})
    beasts = [b.get("name") for b in combat.get("beasts_neutralized", []) if b.get("name")]
    beasts_str = ", ".join(beasts) if beasts else "No prime adversaries logged"

    mvp = holocron_payload.get("squad_mvp") or {}
    mvp_str = f"{mvp.get('name', 'Unavailable')} ({mvp.get('deployments', 0)} deployments)"

    cycle_desc = f"Cycle {week_id}"
    if is_in_flight:
        cycle_desc += f" (In-Flight WTD, Day {summary.get('days_elapsed', 1)} of 7)"

    prompt = (
        f"OPERATING TELEMETRY:\n"
        f"- Cycle: {cycle_desc}\n"
        f"- Precision Clearance Rate: {summary.get('precision_rate', 'Unavailable')} "
        f"({summary.get('completed_tasks', 'Unavailable')} / {summary.get('total_tasks', 'Unavailable')} mandates cleared)\n"
        f"- Progression Yield: +{summary.get('total_xp_gained') if summary.get('total_xp_gained') is not None else 'Unavailable'} XP\n"
        f"- Sovereign Level: {summary.get('current_level', 'Unavailable')}\n"
        f"- Primary Focus Sector: {top_sector_name} ({top_sector_tasks} tasks)\n"
        f"- Threat Neutralizations: {summary.get('threats_neutralized', 'Unavailable')} ({beasts_str})\n"
        f"- Vanguard MVP: {mvp_str}\n\n"
        f"Synthesize an inspiring, concise tactical commander debrief (2-3 sentences) evaluating the Sovereign's focus, "
        f"momentum, and martial discipline for this operating cycle."
    )

    system_prompt = (
        "You are the Chief Tactical Officer and Senior Sage aboard the Sovereign's flagship in the "
        "Navis Protocol productivity framework. You provide crisp, inspiring, highly immersive "
        "military-sci-fi/RPG tactical debriefs. Keep response strictly to 2 to 3 sentences. "
        "Never include markdown headings, bullet points, introductory filler, or quotation marks. "
        "Reference the actual telemetry metrics provided."
    )

    try:
        from services.ai_provider import get_provider
        provider = get_provider()
        is_online = await provider.check()
        if not is_online:
            return (rule_based, "rule_based_fallback")

        response = await provider.generate(prompt, system=system_prompt, feature="holocron")
        cleaned = clean_debrief_output(response)
        if cleaned and len(cleaned) > 20:
            return (cleaned, "openrouter" if type(provider).__name__ == "GuardedOpenRouterProvider" else "ollama")
        return (rule_based, "rule_based_fallback")
    except Exception:
        return (rule_based, "rule_based_fallback")
