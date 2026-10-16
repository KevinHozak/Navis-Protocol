"""Read-only historical Bestiary projections and idempotent round persistence."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from services.combat_service import elemental_profile


def record_round(root, resolution_id, before, tactical):
    from services.progression_db import get_connection
    payload = {"encounter_id": tactical["encounter"]["history_id"],
               "turn": tactical["turn"], "outcome": tactical["encounter"]["outcome"],
               "enemies": []}
    for old, new in zip(before["enemies"], tactical["encounter"]["enemies"]):
        payload["enemies"].append({"name": old.get("beast", old.get("id", "Unknown")),
            "damage": max(0, old.get("hp", 0) - new.get("hp", 0)),
            "slain": old.get("hp", 0) > 0 and new.get("hp", 0) == 0})
    encoded = json.dumps(payload, sort_keys=True)
    conn = get_connection(root)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS combat_rounds (
            resolution_id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, payload TEXT NOT NULL)""")
        existing = conn.execute("SELECT payload FROM combat_rounds WHERE resolution_id=?", (resolution_id,)).fetchone()
        if existing and existing[0] != encoded:
            raise ValueError("Combat history resolution conflicts")
        conn.execute("INSERT OR IGNORE INTO combat_rounds VALUES (?, ?, ?)",
                     (resolution_id, datetime.now(timezone.utc).isoformat(), encoded))
    finally:
        conn.close()


def build_bestiary(root):
    base = Path(root).resolve(strict=True)
    entries = {}
    for directory in ("Codex/Beasts", "Obstacles/Beasts"):
        folder = base / directory
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir()):
            if not child.is_dir() or not child.resolve().is_relative_to(base) or child.name in entries:
                continue
            profile = child / "Combat.json"
            try:
                if not profile.resolve().is_relative_to(base):
                    raise ValueError("Profile escapes Vault")
                elements = elemental_profile(json.loads(profile.read_text(encoding="utf-8-sig")) if profile.is_file() else {})
                error = None
            except (ValueError, OSError) as exc:
                elements, error = {"affinity": None, "vulnerabilities": {}}, str(exc)
            entries[child.name] = {"name": child.name, "profile_path": f"{directory}/{child.name}/Profile.md",
                                   **elements, "profile_error": error}
    rounds = []
    db = base / "Keeper/navis_progression.db"
    if db.is_file():
        if not db.resolve().is_relative_to(base):
            raise ValueError("Progression database escapes Vault")
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='combat_rounds'").fetchone():
                rounds = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM combat_rounds ORDER BY recorded_at, resolution_id")]
        finally:
            conn.close()
    encounters = {}
    for row in rounds:
        for enemy in row["enemies"]:
            name = enemy["name"]
            entries.setdefault(name, {"name": name, "profile_path": None, "affinity": None, "vulnerabilities": {}})
            key = (name, row["encounter_id"])
            item = encounters.setdefault(key, {"outcome": "active", "slayings": 0, "damage": {}})
            item["outcome"] = row["outcome"]
            item["slayings"] += int(enemy["slain"])
            item["damage"][row["turn"]] = item["damage"].get(row["turn"], 0) + enemy["damage"]
    for name, entry in entries.items():
        history = [value for (beast, _), value in encounters.items() if beast == name]
        wins = sum(h["outcome"] == "won" for h in history)
        defeats = sum(h["outcome"] == "defeated" for h in history)
        resolved = wins + defeats
        slayings = sum(h["slayings"] for h in history)
        entry.update(encounters=len(history), wins=wins, defeats=defeats,
                     active=len(history) - resolved, slayings=slayings,
                     win_rate=round(wins * 100 / resolved, 1) if resolved else None,
                     defeat_rate=round(defeats * 100 / resolved, 1) if resolved else None,
                     highest_turn_damage=max((d for h in history for d in h["damage"].values()), default=0),
                     trophies=[label for threshold, label in ((1, "First Slaying"), (10, "Beast Hunter"), (50, "Master Hunter")) if slayings >= threshold])
    return {"beasts": sorted(entries.values(), key=lambda e: e["name"].casefold()),
            "history_note": "Counts cover recorded tactical rounds. Earlier encounters without outcome evidence are excluded. Rates use resolved encounters."}
