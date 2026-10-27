"""One recoverable append authority for HTTP, desktop and opt-in MCP clients.

Intent records contain private source digests and belong in the Vault, never logs.
Cooperating mutations share battle_lock; external editors require hash checks.
"""
from datetime import date
import hashlib
import json
import re
from pathlib import Path

from services.combat_completion import atomic_bytes, atomic_json, battle_lock
from services.vault_access import VaultPolicy, VaultAccessError, _snapshot, _no_links, _note_lines, _headings, _parts, _path_input, MAX_FILE_BYTES

HEADINGS = {
    "sanctum": "## 🏰 The Sanctum", "domestic": "## 🏠 The Domestic Breach",
    "front": "## ⚔️ The High-Velocity Front", "gauntlet": "## ⚖️ The Bureaucratic Gauntlet",
    "outland": "## 🥾 The Kinetic Outland",
}


class JournalError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def checked_journal_list_item(entry):
    entry = entry.strip()
    match = re.match(r"^(?:[-*+][ \t]*)?\[(?: |/|x|X)\][ \t]*(.*)$", entry, re.S)
    if not match:
        match = re.match(r"^[-*+][ \t]+(.*)$", entry, re.S)
    return "- [x] " + (match[1] if match else entry)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(request, guarded=False):
    keys = {"date", "section", "entry", "request_id", "expected_sha256"}
    if not isinstance(request, dict) or set(request) - keys:
        raise JournalError("invalid_argument", 422)
    day, section, entry = (request.get(k) for k in ("date", "section", "entry"))
    try:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError
        if section not in HEADINGS or not isinstance(entry, str) or not 1 <= len(entry.strip()) <= 10000:
            raise ValueError
        # One completed item; multiline section injection is outside this API.
        if any(ord(c) < 32 or ord(c) == 127 for c in entry):
            raise ValueError
    except (ValueError, TypeError):
        raise JournalError("invalid_argument", 422) from None
    expected, identifier = request.get("expected_sha256"), request.get("request_id")
    if (expected is not None and (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected))) or (guarded and expected is None):
        raise JournalError("invalid_argument", 422)
    if identifier is not None and (not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", identifier)):
        raise JournalError("invalid_argument", 422)
    if guarded and identifier is None:
        raise JournalError("invalid_argument", 422)
    payload = {"date": day, "section": section, "entry": checked_journal_list_item(entry)}
    identity = digest(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())
    return payload, identifier or identity, identity, expected


def _insert(raw, section, entry):
    bom = raw[:3] if raw.startswith(b"\xef\xbb\xbf") else b""
    original = raw[len(bom):].decode("utf-8")
    lines = _note_lines(original)
    headings = _headings(lines)
    matches = [i for i, depth, title in headings if depth == 2 and title == HEADINGS[section][3:]]
    if len(matches) != 1:
        raise JournalError("section_missing_or_ambiguous", 422)
    start = matches[0]
    end = next((i for i, depth, _ in headings if i > start and depth <= 2), len(lines))
    fence = None
    for i in range(start + 1, end):
        code = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", lines[i].rstrip("\r\n"))
        if fence:
            if code and code[1][0] == fence[0] and len(code[1]) >= len(fence) and not code[2].strip():
                fence = None
        elif code:
            if code[1][0] != "`" or "`" not in code[2]:
                fence = code[1]
        elif lines[i].strip() == "---":
            end = i
            break
    if fence:
        raise JournalError("section_unclosed_fence", 422)
    if any(line.strip() == entry for line in lines[start + 1:end]):
        raise JournalError("duplicate_entry")
    insertion = start + 1
    for i in range(start + 1, end):
        if lines[i].strip():
            insertion = i + 1
    before, after = "".join(lines[:insertion]), "".join(lines[insertion:])
    newline = "\r\n" if "\r\n" in lines[start] else "\r" if lines[start].endswith("\r") else "\n"
    prefix = "" if not before or before.endswith(newline * 2) else newline
    # Existing bytes are unchanged except at this insertion point.
    return bom + (before + prefix + entry + newline + after).encode("utf-8")


def _state_path(root, identifier):
    # Check before mkdir/open: state and lock must never traverse reparse points.
    for relative in ("Battle", "Battle/.completion.lock", "Battle/journal-appends", f"Battle/journal-appends/{identifier}.json"):
        path = root / relative
        if path.exists() or path.is_symlink():
            _no_links(path)
    return root / "Battle/journal-appends" / (identifier + ".json")


def _sync(root, day, content):
    from services import rpg_engine, progression_db
    if Path(rpg_engine.NAVIS_ROOT).resolve() != root or Path(progression_db.NAVIS_ROOT).resolve() != root:
        raise ValueError("XP runtime Vault mismatch")
    # The existing engine owns cohort, correction and projection semantics.
    # Reject linked managed state and unsafe companion identifiers before calling it.
    for relative in ("Bridge", "Keeper", "Companions", "Bridge/status.json", "Bridge/CompanionStats.json", "Keeper/navis_progression.db", "Keeper/navis_progression.db-wal", "Keeper/navis_progression.db-shm", "Keeper/navis_progression.db-journal", "Keeper/XP.md"):
        path = root / relative
        if path.exists() or path.is_symlink():
            _no_links(path)
    status = json.loads((root / "Bridge/status.json").read_text(encoding="utf-8-sig"))
    stats = json.loads((root / "Bridge/CompanionStats.json").read_text(encoding="utf-8-sig"))
    names = set(stats.get("companions", {})) | {m.get("name") for m in status.get("squad", []) if isinstance(m, dict)}
    for name in names:
        if not isinstance(name, str) or len(_parts(_path_input(name))) != 1:
            raise ValueError("Unsafe XP recipient")
        for path in (root / "Companions" / name, root / "Companions" / name / "XP.md", root / "Companions" / name / "Profile.md"):
            if path.exists() or path.is_symlink():
                _no_links(path)
    rpg_engine.calculate_and_apply_xp(date_override=day, root=root, journal_content=content, strict_talents=True)


def append(root, request, *, policy=None, guarded=False, award=None):
    payload, identifier, identity, expected = validate(request, guarded)
    root = Path(root).absolute()
    if policy is None:
        _no_links(root)
        info = root.stat()
        policy = VaultPolicy(root, (("Journal",),), (), "UTC", (info.st_dev, info.st_ino))
    day = payload["date"]
    relative = f"Journal/{day[:4]}/{day[5:7]}/{day}.md"
    path = policy.resolve(relative)
    record_path = _state_path(root, identifier)
    with battle_lock(root):
        _state_path(root, identifier)
        _, content, sha, _ = _snapshot(policy, relative)
        raw = path.read_bytes()
        if digest(raw) != sha:
            raise JournalError("source_changed")
        record = json.loads(record_path.read_text(encoding="utf-8-sig")) if record_path.exists() else None
        replay = record is not None
        if record:
            if record["identity"] != identity or record.get("expected") != expected:
                raise JournalError("request_id_conflict")
            if record["phase"] == "prepared" and sha not in (record["before"], record["after"]):
                raise JournalError("recovery_required")
        else:
            if expected is not None and sha != expected:
                raise JournalError("source_changed")
            updated = _insert(raw, payload["section"], payload["entry"])
            if len(updated) > MAX_FILE_BYTES:
                raise JournalError("source_too_large", 422)
            record = {"identity": identity, "expected": expected, "before": sha, "after": digest(updated), "phase": "prepared"}
            record_path.parent.mkdir(exist_ok=True)
            atomic_json(record_path, record)
        if record["phase"] == "prepared":
            if sha == record["before"]:
                updated = _insert(raw, payload["section"], payload["entry"])
                if digest(updated) != record["after"]:
                    raise JournalError("recovery_required")
                # Close the ordinary editor race before replace; external writers
                # must also cooperate with this lock for full serialization.
                _, _, fresh_sha, _ = _snapshot(policy, relative)
                if fresh_sha != sha:
                    raise JournalError("source_changed")
                atomic_bytes(path, updated)
            # A crash after replace resumes here without inserting a second item.
            _, content, sha, _ = _snapshot(policy, relative)
            if sha != record["after"]:
                raise JournalError("recovery_required")
            record["phase"] = "saved"
            atomic_json(record_path, record)
        result = {"status": "success", "saved": True, "replayed": replay, "request_id": identifier,
                  "date": day, "path": relative, "sha256": sha, "content": content, "xp_status": "complete"}
        if record["phase"] != "complete":
            try:
                (award or _sync)(root, day, content)
                record["phase"] = "complete"
                atomic_json(record_path, record)
            except Exception:
                result.update(status="saved_xp_pending", xp_status="pending")
        return result


def mcp_append(policy, request, *, deadline=None):
    try:
        result = append(policy.root, request, policy=policy, guarded=True)
        result.pop("content")
        return {"status": "ok", "data": result}
    except JournalError as error:
        raise VaultAccessError(error.code) from None
    except (OSError, ValueError, UnicodeError):
        # The replace may have persisted. Never promise that an interrupted call
        # saved nothing; repeat the exact same request ID and expected hash.
        raise VaultAccessError("append_outcome_unknown_retry_same_request") from None
