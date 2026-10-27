"""Read-only journal ranges and mission context over the shared Vault policy."""
from datetime import timedelta
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import time
from urllib.parse import unquote

from services.recurrence import validate_date
from services.vault_access import (
    MAX_DATA_BYTES, VaultAccessError, _is_link, _no_links, _note_lines,
    _parts, _path_input, _private, _under, read_note,
)
from services.vault_index import MAX_ENTRIES, _inventory


def _check(policy, deadline):
    policy.require_root()
    if time.monotonic() >= deadline:
        raise VaultAccessError("deadline_exceeded")


def _size(result):
    return len(json.dumps(result, ensure_ascii=False).encode("utf-8"))


def _result(policy, data, truncated=False, continuation=None):
    policy.require_root()
    return {"status": "ok", "data": data, "coverage": policy.coverage(),
            "truncated": truncated, "continuation": continuation}


def _directory(policy, relative):
    try:
        path = policy.root.joinpath(*relative.split("/"))
        _no_links(path)
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise OSError
        with os.scandir(path):
            pass
        return path
    except FileNotFoundError:
        raise VaultAccessError("source_unreadable") from None
    except OSError:
        policy.require_root()
        raise VaultAccessError("source_unreadable") from None


def _missing(policy, relative):
    """Only a missing ordinary path is absence; denied/linked paths stay errors."""
    parts = _parts(_path_input(relative))
    if not policy.allows(parts):
        raise VaultAccessError("not_found")
    path = policy.root
    try:
        for i, part in enumerate(parts):
            path = path / part
            info = path.lstat()
            if _is_link(info):
                raise VaultAccessError("not_found")
            if i < len(parts) - 1:
                if not stat.S_ISDIR(info.st_mode):
                    raise VaultAccessError("source_unreadable")
                with os.scandir(path):
                    pass
            elif not stat.S_ISREG(info.st_mode):
                raise VaultAccessError("source_unreadable")
    except FileNotFoundError:
        policy.require_root()
        return True
    except OSError:
        policy.require_root()
        raise VaultAccessError("source_unreadable") from None
    return False


def _trim(note, count):
    """Trim a shared read_note result without losing line/character continuation."""
    content = note["data"]["content"]
    if len(content) <= count:
        return note
    piece = content[:count]
    lines = _note_lines(content)
    line = note["data"]["start_line"]
    column = note["data"].get("start_column", 0)
    left = len(piece)
    for physical in lines:
        if left < len(physical):
            column += left
            break
        left -= len(physical)
        line += 1
        column = 0
    last = line if column else line - 1
    return {**note, "data": {**note["data"], "content": piece,
            "start_line": note["data"]["start_line"] if piece else None,
            "end_line": last if piece else None}, "truncated": True,
            "continuation": {"start_line": line, "start_column": column}}


def _note(policy, relative, count, deadline, section=None):
    return _trim(read_note(policy, {"path": _path_input(relative), "section": section,
                                    "max_lines": 200}, deadline=deadline), count)


def _source(note):
    return {**note["data"], "truncated": note["truncated"], "continuation": note["continuation"]}


def _fit(note, envelope):
    if _size(envelope(note)) <= MAX_DATA_BYTES:
        return note
    low, high = 0, len(note["data"]["content"])
    while low < high:
        mid = (low + high + 1) // 2
        if _size(envelope(_trim(note, mid))) <= MAX_DATA_BYTES:
            low = mid
        else:
            high = mid - 1
    if low == 0:
        raise VaultAccessError("response_too_large")
    return _trim(note, low)


def get_journal_range(policy, arguments, *, deadline=None):
    deadline = time.monotonic() + 10 if deadline is None else deadline
    _check(policy, deadline)
    if not isinstance(arguments, dict) or set(arguments) - {"start_date", "end_date", "section", "max_chars_per_day"}:
        raise VaultAccessError("invalid_argument")
    try:
        start, end = (validate_date(arguments[key]) for key in ("start_date", "end_date"))
    except (ValueError, TypeError, KeyError):
        raise VaultAccessError("invalid_argument") from None
    limit, section = arguments.get("max_chars_per_day", 4000), arguments.get("section")
    if (end < start or (end - start).days >= 31 or type(limit) is not int or not 1 <= limit <= 8000
            or (section is not None and (not isinstance(section, str) or not 1 <= len(section) <= 1024))):
        raise VaultAccessError("invalid_argument")
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    paths = {day: f"Journal/{day.year:04d}/{day.month:02d}/{day.isoformat()}.md" for day in dates}
    if any(not policy.allows(tuple(path.split("/"))) for path in paths.values()):
        raise VaultAccessError("not_found")
    _directory(policy, "Journal")
    journals, missing = [], []
    any_truncated = False

    def envelope(items, absent, next_date, partial=False):
        return _result(policy, {"start_date": start.isoformat(), "end_date": end.isoformat(),
                        "timezone": policy.timezone, "journals": items, "missing_dates": absent},
                       any_truncated or partial or next_date is not None,
                       {"next_date": next_date} if next_date is not None else None)

    for index, day in enumerate(dates):
        _check(policy, deadline)
        following = dates[index + 1].isoformat() if index + 1 < len(dates) else None
        if _missing(policy, paths[day]):
            candidate = envelope(journals, missing + [day.isoformat()], following)
            if _size(candidate) > MAX_DATA_BYTES:
                if not journals and not missing:
                    raise VaultAccessError("response_too_large")
                return envelope(journals, missing, day.isoformat())
            missing.append(day.isoformat())
            continue
        try:
            note = _note(policy, paths[day], limit, deadline, section)
        except VaultAccessError as error:
            if error.code == "not_found":
                raise VaultAccessError("source_changed") from None
            raise

        def with_note(value):
            return envelope(journals + [{"date": day.isoformat(), **_source(value)}], missing,
                            following, value["truncated"])

        if _size(with_note(note)) > MAX_DATA_BYTES:
            if journals or missing:
                return envelope(journals, missing, day.isoformat())
            note = _fit(note, with_note)
        journals.append({"date": day.isoformat(), **_source(note)})
        any_truncated |= note["truncated"]
    _check(policy, deadline)
    return envelope(journals, missing, None)


def _component(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 255:
        raise VaultAccessError("invalid_argument")
    try:
        parts = _parts(value)
    except VaultAccessError:
        raise VaultAccessError("invalid_argument") from None
    if len(parts) != 1:
        raise VaultAccessError("invalid_argument")
    return parts[0]


def _can_descend(policy, parts):
    return (not _private(parts) and not any(_under(parts, p) for p in policy.denied)
            and any(_under(parts, p) or _under(p, parts) for p in policy.allowed))


def _mission_candidates(policy, name, region, mission_type, deadline):
    if not _can_descend(policy, ("Operations",)):
        raise VaultAccessError("not_found")
    root = _directory(policy, "Operations")
    visited = 0

    def directories(parent):
        nonlocal visited
        result = []
        try:
            _no_links(parent)
            with os.scandir(parent) as entries:
                for entry in entries:
                    _check(policy, deadline)
                    visited += 1
                    if visited > MAX_ENTRIES:
                        raise VaultAccessError("inventory_limit_exceeded")
                    relative = Path(entry.path).relative_to(policy.root).as_posix()
                    try:
                        parts = _parts(_path_input(relative))
                    except VaultAccessError:
                        continue
                    if not _can_descend(policy, parts):
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode) and not _is_link(info):
                        result.append(Path(entry.path))
            return sorted(result, key=lambda p: p.name)
        except OSError:
            policy.require_root()
            raise VaultAccessError("source_unreadable") from None

    candidates = []
    for area in directories(root):
        if region is not None and area.name != region:
            continue
        for kind in directories(area):
            if kind.name not in {"Main", "Side"} or (mission_type is not None and kind.name != mission_type):
                continue
            for mission in directories(kind):
                if mission.name != name:
                    continue
                relative = (mission / "Mission.md").relative_to(policy.root).as_posix()
                if policy.allows(tuple(relative.split("/"))) and not _missing(policy, relative):
                    candidates.append(relative)
                    if len(candidates) == 21:
                        return candidates
    return candidates


def _ambiguity(candidates):
    shown = []
    result = {"status": "error", "error": {"code": "ambiguous_mission", "retryable": False,
              "candidates": shown, "truncated": False}}
    for candidate in candidates[:20]:
        shown.append(candidate)
        if _size(result) > MAX_DATA_BYTES:
            shown.pop()
            break
    result["error"]["truncated"] = len(shown) < len(candidates)
    return result


def _links(text):
    targets = []
    fence = None
    for line in _note_lines(text):
        code = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence is not None:
            if code and code[1][0] == fence[0] and len(code[1]) >= len(fence) and not code[2].strip():
                fence = None
            continue
        if code:
            if code[1][0] != "`" or "`" not in code[2]:
                fence = code[1]
            continue
        line = re.sub(r"`+[^`]*`+", "", line)
        for match in re.finditer(r"\[\[([^]\n]+)\]\]|\[[^]\n]*\]\((?:<([^>\n]+)>|([^\s)]+))\)", line):
            target = (match[1] or match[2] or match[3]).split("|", 1)[0].split("#", 1)[0]
            if target and len(target) <= 1024:
                targets.append(target)
            if len(targets) >= 33:
                return targets
    return targets


def _related_path(policy, source, target, inventory, deadline):
    target = unquote(target).replace("\\", "/")
    if target.startswith("/") or ":" in target or any(ord(c) < 32 for c in target):
        return None, "unresolved_link"
    if not target.casefold().endswith(".md"):
        if Path(target).suffix:
            return None, "unresolved_link"
        target += ".md"
    if "/" not in target:
        if inventory[0] is None:
            inventory[0] = _inventory(policy, deadline)[0]
        candidates = [p for p in inventory[0] if Path(p).name.casefold() == target.casefold()]
    else:
        choices = {posixpath.normpath(posixpath.join(posixpath.dirname(source), target)), posixpath.normpath(target)}
        candidates = []
        for candidate in sorted(choices):
            try:
                if not _missing(policy, candidate):
                    candidates.append(candidate)
            except VaultAccessError as error:
                if error.code != "not_found":
                    raise
    if len(candidates) != 1:
        return None, "ambiguous_link" if len(candidates) > 1 else "unresolved_link"
    return candidates[0], None


def get_mission(policy, arguments, *, deadline=None):
    deadline = time.monotonic() + 10 if deadline is None else deadline
    _check(policy, deadline)
    if not isinstance(arguments, dict) or set(arguments) - {"name", "path", "region", "mission_type", "related_limit"}:
        raise VaultAccessError("invalid_argument")
    by_name, by_path = "name" in arguments, "path" in arguments
    limit = arguments.get("related_limit", 3)
    if by_name == by_path or type(limit) is not int or not 0 <= limit <= 5:
        raise VaultAccessError("invalid_argument")
    if by_path:
        if "region" in arguments or "mission_type" in arguments:
            raise VaultAccessError("invalid_argument")
        if not isinstance(arguments["path"], str) or not 1 <= len(arguments["path"]) <= 1024:
            raise VaultAccessError("invalid_argument")
        parts = _parts(arguments["path"])
        if len(parts) != 5 or parts[0] != "Operations" or parts[2] not in {"Main", "Side"} or parts[4] != "Mission.md":
            raise VaultAccessError("not_found")
        relative = "/".join(parts)
    else:
        name = _component(arguments["name"])
        region = _component(arguments["region"]) if "region" in arguments else None
        kind = arguments.get("mission_type")
        if "mission_type" in arguments and (not isinstance(kind, str) or kind not in {"Main", "Side"}):
            raise VaultAccessError("invalid_argument")
        candidates = _mission_candidates(policy, name, region, kind, deadline)
        if not candidates:
            raise VaultAccessError("not_found")
        if len(candidates) > 1:
            return _ambiguity(candidates)
        relative = candidates[0]
        parts = tuple(relative.split("/"))
    primary = _note(policy, relative, 8000, deadline)
    related, unresolved = [], []
    more = False

    def envelope(mission=primary, context=None):
        return _result(policy, {"name": parts[3], "region": parts[1], "mission_type": parts[2],
                        "mission": _source(mission), "related": related if context is None else context,
                        "unresolved_links": unresolved, "related_truncated": more},
                       mission["truncated"] or more or any(p["truncated"] for p in related))

    primary = _fit(primary, lambda value: envelope(value))
    targets = _links(primary["data"]["content"])
    inventory, seen = [None], {relative.casefold()}

    def unresolved_link(link_index, reason):
        unresolved.append({"link_index": link_index, "code": reason})
        if _size(envelope(primary)) > MAX_DATA_BYTES:
            unresolved.pop()
            return False
        return True

    for i, target in enumerate(targets):
        _check(policy, deadline)
        if len(related) >= limit or i >= 32:
            more = True
            break
        try:
            path, reason = _related_path(policy, relative, target, inventory, deadline)
            if reason:
                if not unresolved_link(i, reason):
                    more = True
                    break
                continue
            if path.casefold() in seen:
                continue
            note = _note(policy, path, 2000, deadline)
            note = _fit(note, lambda value: envelope(primary, related + [_source(value)]))
            related.append(_source(note))
            seen.add(path.casefold())
        except VaultAccessError as error:
            if error.code in {"vault_unavailable", "deadline_exceeded"}:
                raise
            if error.code == "response_too_large":
                more = True
                break
            if not unresolved_link(i, "unresolved_link"):
                more = True
                break
    result = envelope(primary)
    if _size(result) > MAX_DATA_BYTES:
        raise VaultAccessError("response_too_large")
    _check(policy, deadline)
    return result
