"""Bounded, side-effect-free Vault reads. No portal startup or mutation imports."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from urllib.parse import unquote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.vault_paths import VaultPathError, resolve_relative_path

MAX_FILE_BYTES = 1024 * 1024
MAX_DATA_BYTES = 16 * 1024  # Leaves room for duplicated/escaped MCP representations.
DEFAULT_ROOTS = ("Journal", "Operations", "Codex", "Documentation")
RESERVED = re.compile(r"^(con|conin\$|conout\$|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)", re.I)
SECRET = re.compile(r"^(secret|credential|token|oauth|client.secret|service.account|private.key|config|settings)(?:[._ -]|$)", re.I)


class VaultAccessError(Exception):
    """Only this machine code, never an underlying path or exception, is public."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _parts(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        raise VaultAccessError("not_found")
    normalized = unquote(value).replace("\\", "/")
    parts = normalized.split("/")
    if any(ord(c) < 32 or ord(c) == 127 for c in normalized) or ":" in normalized:
        raise VaultAccessError("not_found")
    if any(not p or p in (".", "..") or p.startswith(".") or p.endswith((" ", "."))
           or p != p.strip() or RESERVED.match(p) or any(c in p for c in '<>"|?*~') for p in parts):
        raise VaultAccessError("not_found")
    return tuple(parts)


def _private(parts):
    return any(SECRET.match(p) or ".backup" in p.casefold() or p.casefold().endswith((".bak", ".tmp", "~"))
               for p in parts)


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _no_links(path):
    """Check every ancestor, including the configured root, without resolving it."""
    for candidate in reversed((path, *path.parents)):
        if _is_link(candidate.lstat()):
            raise VaultAccessError("not_found")


def _under(parts, base):
    return len(parts) >= len(base) and tuple(p.casefold() for p in parts[:len(base)]) == tuple(p.casefold() for p in base)


def _configured_paths(env, name, default):
    try:
        values = json.loads(env[name]) if name in env else list(default)
        if not isinstance(values, list) or len(values) > 32:
            raise ValueError
        result = tuple(_parts(v) for v in values)
        if any(_private(p) for p in result):
            raise ValueError
        return result
    except (ValueError, TypeError, VaultAccessError):
        raise VaultAccessError("invalid_configuration") from None


@dataclass(frozen=True)
class VaultPolicy:
    root: Path
    allowed: tuple
    denied: tuple
    timezone: str
    identity: tuple

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        raw = env.get("NAVIS_ROOT", "").strip()
        tz = env.get("NAVIS_MCP_TIMEZONE", "").strip()
        if not raw or not Path(raw).is_absolute() or not tz:
            raise VaultAccessError("invalid_configuration")
        try:
            ZoneInfo(tz)
        except (ValueError, ZoneInfoNotFoundError):
            raise VaultAccessError("invalid_configuration") from None
        allowed = _configured_paths(env, "NAVIS_MCP_ALLOWED_ROOTS", DEFAULT_ROOTS)
        denied = _configured_paths(env, "NAVIS_MCP_DENIED_PATHS", ())
        if not allowed:
            raise VaultAccessError("invalid_configuration")
        root = Path(os.path.abspath(raw))
        try:
            _no_links(root)
            info = root.stat()
            if not stat.S_ISDIR(info.st_mode):
                raise OSError
            with os.scandir(root):
                pass
        except (OSError, VaultAccessError):
            raise VaultAccessError("vault_unavailable") from None
        return cls(root, allowed, denied, tz, (info.st_dev, info.st_ino))

    def require_root(self):
        try:
            _no_links(self.root)
            info = self.root.stat()
            if (info.st_dev, info.st_ino) != self.identity or not stat.S_ISDIR(info.st_mode):
                raise OSError
            with os.scandir(self.root):
                pass
        except (OSError, VaultAccessError):
            raise VaultAccessError("vault_unavailable") from None

    def resolve(self, raw):
        self.require_root()
        parts = _parts(raw)
        if (_private(parts) or not any(_under(parts, base) for base in self.allowed)
                or any(_under(parts, base) for base in self.denied) or Path(parts[-1]).suffix.casefold() != ".md"):
            raise VaultAccessError("not_found")
        try:
            path = Path(resolve_relative_path(self.root, raw))
            _no_links(path)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise VaultAccessError("not_found")
        except (FileNotFoundError, NotADirectoryError, VaultPathError):
            raise VaultAccessError("not_found") from None
        except OSError:
            raise VaultAccessError("source_unreadable") from None
        return path

    def coverage(self):
        missing = []
        for parts in self.allowed:
            path = self.root.joinpath(*parts)
            try:
                _no_links(path)
                with os.scandir(path):
                    pass
            except FileNotFoundError:
                missing.append("/".join(parts))
            except (OSError, VaultAccessError):
                raise VaultAccessError("source_unreadable") from None
        return {"allowed_roots": ["/".join(p) for p in self.allowed], "missing_roots": missing,
                "index_state": "not_used"}


def _signature(info):
    # Python/Windows lstat ctime is creation time, while fstat may expose change
    # time. Compare ctime only within the same API, not across pathname/handle.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _snapshot(policy, raw):
    path = policy.resolve(raw)
    try:
        before = path.lstat()
        if before.st_size > MAX_FILE_BYTES:
            raise VaultAccessError("file_too_large")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _signature(before) != _signature(opened):
                raise VaultAccessError("source_changed")
            data = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
        policy.resolve(raw)  # Recheck root identity, links and policy after opening.
        final = path.lstat()
        if (_signature(before) != _signature(after) or _signature(after) != _signature(final)
                or opened.st_ctime_ns != after.st_ctime_ns or before.st_ctime_ns != final.st_ctime_ns):
            raise VaultAccessError("source_changed")
        if len(data) > MAX_FILE_BYTES:
            raise VaultAccessError("file_too_large")
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise VaultAccessError("unsupported_encoding") from None
    except OSError:
        raise VaultAccessError("source_unreadable") from None
    return path.relative_to(policy.root).as_posix(), text, hashlib.sha256(data).hexdigest(), before


def _headings(lines):
    result = []
    fence = None
    for i, line in enumerate(lines):
        code = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if code:
            marker = code[1]
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        match = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line.rstrip("\r\n"))
        if match and fence is None:
            result.append((i, len(match[1]), match[2]))
    return result


def read_note(policy, arguments, *, deadline=None):
    """Return a live bounded excerpt; never initialize, index, sync or mutate."""
    deadline = time.monotonic() + 10 if deadline is None else deadline

    def check_time():
        if time.monotonic() >= deadline:
            raise VaultAccessError("deadline_exceeded")

    check_time()
    policy.require_root()
    if not isinstance(arguments, dict) or set(arguments) - {"path", "section", "start_line", "start_column", "max_lines"}:
        raise VaultAccessError("invalid_argument")
    path, section = arguments.get("path"), arguments.get("section")
    first, column, limit = (arguments.get("start_line", 1), arguments.get("start_column", 0), arguments.get("max_lines", 100))
    if (not isinstance(path, str) or not 1 <= len(path) <= 1024
            or type(first) is not int or not 1 <= first <= MAX_FILE_BYTES + 1
            or type(column) is not int or not 0 <= column <= MAX_FILE_BYTES
            or type(limit) is not int or not 1 <= limit <= 200
            or (section is not None and (not isinstance(section, str) or not 1 <= len(section) <= 1024))):
        raise VaultAccessError("invalid_argument")
    relative, text, digest, info = _snapshot(policy, path)
    check_time()
    # Only CR/LF delimit physical Markdown lines, not Unicode separators.
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text)
    if lines and not lines[-1]:
        lines.pop()
    headings = _headings(lines)
    lo, hi = 0, len(lines)
    if section is not None:
        found = [h for h in headings if h[2] == section]
        if not found:
            raise VaultAccessError("section_not_found")
        if len(found) != 1:
            raise VaultAccessError("invalid_argument")
        lo, level, _ = found[0]
        hi = next((i for i, depth, _ in headings if i > lo and depth <= level), len(lines))
    begin = max(lo, first - 1)
    if column and (begin != first - 1 or begin >= hi or column >= len(lines[begin])):
        raise VaultAccessError("invalid_argument")
    end = min(begin + limit, hi)
    excerpt = "".join(lines[begin:end])[column:] if begin < hi else ""
    heading = next((h[2] for h in reversed(headings) if h[0] <= begin), None)
    coverage = policy.coverage()
    check_time()
    # Serialize the complete envelope while fitting; JSON escaping and UTF-8 count.
    def envelope(length):
        piece = excerpt[:length]
        line_index, offset, remaining = begin, column, len(piece)
        while line_index < end and remaining >= len(lines[line_index]) - offset:
            remaining -= len(lines[line_index]) - offset
            line_index += 1
            offset = 0
        offset += remaining
        more = line_index < hi
        last = line_index if offset == 0 else line_index + 1
        return {"status": "ok", "data": {"path": relative, "content": piece,
                "start_line": begin + 1 if piece else None, "end_line": last if piece else None,
                "start_column": column, "heading": heading,
                "modified_at": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                "sha256": digest}, "coverage": coverage, "truncated": more,
                "continuation": {"start_line": line_index + 1, "start_column": offset} if more else None}
    if not excerpt:
        result = envelope(0)
        result["truncated"], result["continuation"] = False, None
        return result
    low, high = 0, len(excerpt)
    while low < high:
        mid = (low + high + 1) // 2
        if len(json.dumps(envelope(mid), ensure_ascii=False).encode("utf-8")) <= MAX_DATA_BYTES:
            low = mid
        else:
            high = mid - 1
    result = envelope(low)
    if low == 0:
        raise VaultAccessError("response_too_large")
    check_time()
    return result
