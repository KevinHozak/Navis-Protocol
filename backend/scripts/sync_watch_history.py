import os
import sys
import sqlite3
import re
import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path

CURRENT_USER = 1

JELLYFIN_DB = r"C:\ProgramData\Jellyfin\Server\data\library.db"

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
JOURNAL_ROOT = os.path.join(NAVIS_ROOT, "Journal")


def get_jellyfin_db():
    if not os.path.exists(JELLYFIN_DB):
        raise FileNotFoundError(f"Jellyfin database not found: {JELLYFIN_DB}")
    conn = sqlite3.connect(JELLYFIN_DB)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_watch_history(start_dt, end_dt):
    conn = get_jellyfin_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date(u.lastPlayedDate) AS day,
               u.playCount,
               u.playbackPositionTicks,
               u.lastPlayedDate,
               i.Name,
               i.Type,
               i.ProductionYear,
               i.SeriesName,
               i.ParentIndexNumber,
               i.IndexNumber
        FROM UserDatas u
        JOIN TypedBaseItems i ON u.key = i.UserDataKey
        WHERE u.userId = ?
          AND u.lastPlayedDate >= ?
          AND u.lastPlayedDate < ?
          AND u.played = 1
        ORDER BY u.lastPlayedDate ASC
        """,
        (CURRENT_USER, start_dt.isoformat(), end_dt.isoformat()),
    )
    rows = cur.fetchall()
    conn.close()

    by_day = defaultdict(list)
    for r in rows:
        title = r["Name"]
        if "Episode" in (r["Type"] or "") and r["SeriesName"]:
            parts = []
            if r["ParentIndexNumber"]:
                parts.append(f"S{int(r['ParentIndexNumber']):02d}")
            if r["IndexNumber"]:
                parts.append(f"E{int(r['IndexNumber']):02d}")

            if parts:
                title = f"{r['SeriesName']} - {''.join(parts)}: {title}"
            else:
                title = f"{r['SeriesName']} - {title}"

            if r["ProductionYear"]:
                title += f" ({int(r['ProductionYear'])})"
        elif r["ProductionYear"]:
            title += f" ({int(r['ProductionYear'])})"
        by_day[r["day"]].append(title)
    return by_day


_SANCTUM_HEADER_PATTERN = re.compile(r"## 🏰 The Sanctum", re.MULTILINE)
_SANCTUM_SECTION_PATTERN = re.compile(
    r"(## 🏰 The Sanctum\n)(.*?)((?=\n## |\n---|\Z))", re.DOTALL
)
_WATCH_HISTORY_SECTION_PATTERN = re.compile(
    r"\n*## 🎥 \d{4}-\d{2}-\d{2} releases?\n.*?(?=\n## |\n---|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_OLD_WATCH_LINE_PATTERN = re.compile(r"^- \[[ xX]\] Watched .*$\n?", re.MULTILINE)


def remove_duplicate_watch_lines(content):
    content = _OLD_WATCH_LINE_PATTERN.sub("", content)
    content = _WATCH_HISTORY_SECTION_PATTERN.sub("\n", content)
    return content


def update_journal_watch_section(path, day_dt, watches):
    new_watch_lines = [f"- [x] Watched {t}" for t in watches]
    watch_block = "\n".join(new_watch_lines) + "\n" if new_watch_lines else ""

    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    if not _SANCTUM_HEADER_PATTERN.search(content):
        return False, "missing_sanctum"

    updated = False
    new_content = content

    m = _SANCTUM_SECTION_PATTERN.search(content)
    if m:
        header, current_body, tail = m.groups()
        cleaned = _OLD_WATCH_LINE_PATTERN.sub("", current_body).rstrip("\r\n")
        if cleaned:
            replacement = header + cleaned + "\n" + watch_block + "\n"
        else:
            replacement = header + watch_block
        new_content = content[: m.start()] + replacement + content[m.end() :]
        updated = True

    if updated:
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(new_content)
    return updated, "updated" if updated else "no_change"


def get_journal_path(day_dt):
    return os.path.join(
        JOURNAL_ROOT,
        day_dt.strftime("%Y"),
        day_dt.strftime("%m"),
        f"{day_dt.strftime('%Y-%m-%d')}.md",
    )


def _load_last_sync_date():
    path = os.path.join(NAVIS_ROOT, "Bridge", "watch_sync_state.json")
    if os.path.exists(path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
            return datetime.strptime(data.get("last_sync", ""), "%Y-%m-%d").date()
        except Exception:
            pass
    return None


def _save_last_sync_date(dt):
    path = os.path.join(NAVIS_ROOT, "Bridge", "watch_sync_state.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Path(path).write_text(
        json.dumps(
            {"last_sync": dt.strftime("%Y-%m-%d")}, indent=4, ensure_ascii=False
        ),
        encoding="utf-8-sig",
    )


def sync_watch_history():
    today = datetime.now().date()
    last_sync = _load_last_sync_date()

    if last_sync is None:
        start_dt = datetime(2026, 3, 11)
    else:
        start_dt = datetime(last_sync.year, last_sync.month, last_sync.day)

    end_dt = datetime(today.year, today.month, today.day + 1)

    by_day = fetch_watch_history(start_dt, end_dt)
    counts = {
        "days_processed": 0,
        "journals_updated": 0,
        "entries_written": 0,
        "skipped": 0,
    }
    logs = []

    for day_str, watches in sorted(by_day.items()):
        counts["days_processed"] += 1
        day_dt = datetime.strptime(day_str, "%Y-%m-%d").date()
        path = get_journal_path(day_dt)

        if not os.path.exists(path):
            counts["skipped"] += 1
            logs.append(f"SKIP missing journal: {path}")
            continue

        updated, state = update_journal_watch_section(path, day_dt, watches)
        if state == "missing_sanctum":
            counts["skipped"] += 1
            logs.append(f"SKIP no Sanctum header: {path}")
            continue

        counts["entries_written"] += len(watches)
        if updated:
            counts["journals_updated"] += 1
            full_path = path
            tmp_path = full_path + ".tmp"
            with open(full_path, "r", encoding="utf-8-sig") as f:
                raw = f.read()
            normalized = re.sub(r"\n{3,}", "\n\n", raw)
            with open(tmp_path, "w", encoding="utf-8-sig") as f:
                f.write(normalized)
            os.replace(tmp_path, full_path)
            logs.append(f"{'SYNC'} {day_str}: {len(watches)} entries")
        else:
            logs.append(f"{'HOLD'} {day_str}: {len(watches)} entries")

    _save_last_sync_date(today)

    summary = (
        f"Watch history sync complete.\n"
        f"Range: {start_dt.date()} → {today}\n"
        f"Processed days: {counts['days_processed']}\n"
        f"Journals updated: {counts['journals_updated']}\n"
        f"Watch entries written: {counts['entries_written']}\n"
        f"Skipped: {counts['skipped']}"
    )
    print(summary)
    print("\n".join(logs))


if __name__ == "__main__":
    try:
        sync_watch_history()
    except Exception as e:
        print(f"FATAL: {e}")
        sys.exit(1)
