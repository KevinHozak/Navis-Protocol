"""Bounded Holocron source inspection; no arbitrary paths or journal bodies."""
import hashlib
from pathlib import Path
import re


def source_path(root, relative):
    base = Path(root).resolve()
    path = base / relative
    if not path.resolve().is_relative_to(base):
        return None
    current = path
    while current != base:
        if current.is_symlink():
            return None
        current = current.parent
    return path


def journal_source(root, day):
    for relative in (f"Journal/{day[:4]}/{day[5:7]}/{day}.md", f"Journal/{day}.md"):
        path = source_path(root, relative)
        if path and path.is_file():
            try:
                if path.stat().st_size > 2 * 1024 * 1024:
                    return {"id": f"journal-{day}", "date": day, "status": "unavailable"}
                content = path.read_bytes()
                content.decode("utf-8-sig")
                return {"id": f"journal-{day}", "date": day, "status": "available",
                        "fingerprint": hashlib.sha256(content).hexdigest()}
            except (OSError, UnicodeError):
                return {"id": f"journal-{day}", "date": day, "status": "unavailable"}
    return {"id": f"journal-{day}", "date": day, "status": "missing"}


def inspect_source(root, week_id, source_id):
    from services.holocron_engine import get_week_date_range, find_journal_file, parse_daily_journal, query_progression_telemetry
    start, end, days = get_week_date_range(week_id)
    if source_id == "keeper-ledger":
        data = query_progression_telemetry(root, start, end)
        return {"id": source_id, "status": data["availability"], "start_date": start,
                "end_date": end, "fingerprint": data["fingerprint"], "total_xp": data["total_xp"] if data["availability"] == "available" else None,
                "rule": "Sum signed Keeper ledger amounts by local_date, inclusive."}
    day = source_id.removeprefix("journal-")
    if source_id != f"journal-{day}" or day not in days:
        raise ValueError("Unsupported Holocron source")
    source = journal_source(root, day)
    if source["status"] == "available":
        path = find_journal_file(root, day)
        parsed = parse_daily_journal(path, day)
        if parsed["availability"] != "available":
            return {"id": source_id, "date": day, "status": parsed["availability"]}
        if journal_source(root, day).get("fingerprint") != source["fingerprint"]:
            return {"id": source_id, "date": day, "status": "changed"}
        source["counts"] = {key: parsed[key] for key in ("completed", "pending", "total")}
        source["path"] = Path(path).relative_to(Path(root)).as_posix()
    return source


def share_safe(value):
    """Omit absolute paths even if they occur in user-authored metadata."""
    if isinstance(value, dict):
        return {key: share_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [share_safe(item) for item in value]
    if isinstance(value, str) and re.search(r"[A-Za-z]:[\\/]|\\\\|/(?:Users|home|mnt|Projects)/", value):
        return "[private path omitted]"
    return value
