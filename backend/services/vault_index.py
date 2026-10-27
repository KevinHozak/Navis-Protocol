"""Private FTS5 generations. Only the local operator rebuilds; MCP searches read."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import time
import uuid
from itertools import islice
from collections import deque
from dataclasses import replace
from services.vault_io import read_binary

from services.vault_access import (
    MAX_DATA_BYTES, MAX_FILE_BYTES, VaultAccessError, _headings, _is_link,
    _no_links, _note_lines, _parts, _path_input, _signature, _snapshot, _under,
)

SCHEMA = 1
MAX_NOTES = 20000
MAX_ENTRIES = 50000
MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_DB_BYTES = 256 * 1024 * 1024
CHECKOUT = Path(__file__).resolve().parents[2]
IO_WORKERS = 8


def _check(deadline):
    if time.monotonic() >= deadline:
        raise VaultAccessError("deadline_exceeded")


def _metadata(info):
    return (info.st_size, info.st_mtime_ns, str(info.st_dev), str(info.st_ino))


def _parallel(function, items, deadline):
    """Bound both pending work and retained results; never cache across calls."""
    iterator = iter(items)
    with ThreadPoolExecutor(max_workers=IO_WORKERS, thread_name_prefix="vault-io") as pool:
        pending = deque(pool.submit(function, item) for item in islice(iterator, IO_WORKERS * 2))
        while pending:
            _check(deadline)
            future = pending.popleft()
            try:
                yield future.result(timeout=max(0.001, deadline - time.monotonic()))
            except TimeoutError:
                raise VaultAccessError("deadline_exceeded") from None
            for item in islice(iterator, 1):
                pending.append(pool.submit(function, item))


def _open_probe(path):
    return read_binary(path)


def _directory_signature(info):
    return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns


def _probe_file(item):
    """Probe readability and pathname/handle identity, without reading content.

    Paths come only from the component-validated walk. Every directory in that
    walk is pinned and revalidated before this inventory may be returned.
    """
    relative, path = item
    try:
        before = path.lstat()  # DirEntry metadata lacks inode/device on Windows.
        if _is_link(before) or not stat.S_ISREG(before.st_mode):
            raise VaultAccessError("source_changed")
        if before.st_size > MAX_FILE_BYTES:
            raise VaultAccessError("file_too_large")
        with _open_probe(path) as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or _signature(before) != _signature(opened):
                raise VaultAccessError("source_changed")
            after = os.fstat(stream.fileno())
        final = path.lstat()
        if (_is_link(final) or not stat.S_ISREG(final.st_mode) or _signature(before) != _signature(after)
                or _signature(after) != _signature(final)
                or opened.st_ctime_ns != after.st_ctime_ns or before.st_ctime_ns != final.st_ctime_ns):
            raise VaultAccessError("source_changed")
        return relative, _metadata(final)
    except FileNotFoundError:
        raise VaultAccessError("source_changed") from None


def _fingerprint(policy):
    data = (os.path.normcase(str(policy.root)), policy.identity, policy.allowed, policy.denied, SCHEMA)
    return hashlib.sha256(json.dumps(data).encode("utf-8")).hexdigest()


def _scope_policy(policy, subtree, deadline):
    # Match the query's existing case-insensitive prefix semantics, but retain
    # actual on-disk spelling in provenance/manifest comparisons. Discover all
    # case aliases (possible on POSIX), including ones added since indexing.
    scope = (subtree[:-1] if Path(subtree[-1]).suffix.casefold() == ".md"
             and policy.allows(subtree[:-1]) else subtree)
    roots, examined = [()], 0
    for depth, part in enumerate(scope):
        following = []
        for prefix in roots:
            if len(prefix) == len(scope):
                following.append(prefix)
                continue
            _check(deadline)
            parent = policy.root.joinpath(*prefix)
            try:
                _no_links(parent)
                with os.scandir(parent) as children:
                    matches = []
                    for entry in children:
                        _check(deadline)
                        examined += 1
                        if examined > MAX_ENTRIES:
                            raise VaultAccessError("inventory_limit_exceeded")
                        if entry.name.casefold() == part.casefold():
                            matches.append(prefix + (entry.name,))
                following.extend(matches or [prefix + tuple(scope[depth:])])
            except FileNotFoundError:
                policy.require_root()
                following.append(prefix + tuple(scope[depth:]))
            except OSError:
                raise VaultAccessError("source_unreadable") from None
        if len(following) > 32:
            raise VaultAccessError("inventory_limit_exceeded")
        # Missing roots have their complete suffix already; do not append it
        # again while discovering other case aliases.
        roots = following
        if all(len(p) == len(scope) for p in roots):
            break
    return replace(policy, allowed=tuple(sorted(set(roots))))


def _inventory(policy, deadline):
    """Bound discovery before content reads; excluded subtrees are never entered."""
    policy.require_root()
    coverage = policy.coverage()
    files, visited, directories, candidates = {}, set(), {}, {}
    pending = [policy.root.joinpath(*p) for p in policy.allowed if "/".join(p) not in coverage["missing_roots"]]
    entries = total_bytes = 0
    try:
        while pending:
            _check(deadline)
            directory = pending.pop()
            relative = directory.relative_to(policy.root).as_posix()
            parts = _parts(_path_input(relative))
            key = os.path.normcase(relative)
            if not policy.allows(parts) or key in visited:
                continue
            visited.add(key)
            # Check ancestors once for configured roots. Descendants are formed
            # exclusively from validated components under already checked dirs.
            if directory in [policy.root.joinpath(*p) for p in policy.allowed]:
                _no_links(directory)
            info = directory.lstat()
            if _is_link(info) or not stat.S_ISDIR(info.st_mode):
                raise VaultAccessError("source_changed")
            directories[directory] = _directory_signature(info)
            with os.scandir(directory) as children:
                for entry in children:
                    _check(deadline)
                    entries += 1
                    if entries > MAX_ENTRIES:
                        raise VaultAccessError("inventory_limit_exceeded")
                    rel = Path(entry.path).relative_to(policy.root).as_posix()
                    raw = _path_input(rel)
                    try:
                        components = _parts(raw)
                    except VaultAccessError:
                        continue
                    if not policy.allows(components):
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if _is_link(info):
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(Path(entry.path))
                    elif stat.S_ISREG(info.st_mode) and Path(entry.name).suffix.casefold() == ".md":
                        if info.st_size > MAX_FILE_BYTES:
                            raise VaultAccessError("file_too_large")
                        if rel not in candidates:
                            total_bytes += info.st_size
                        candidates[rel] = Path(entry.path)
                        if len(candidates) > MAX_NOTES or total_bytes > MAX_INDEX_BYTES:
                            raise VaultAccessError("inventory_limit_exceeded")
        # Still open every permitted note, including nonmatches. Drive I/O is
        # parallelized; no TTL/readability cache can hide permission changes.
        for relative, metadata in _parallel(_probe_file, candidates.items(), deadline):
            files[relative] = metadata
        if sum(meta[0] for meta in files.values()) > MAX_INDEX_BYTES:
            raise VaultAccessError("inventory_limit_exceeded")
        for directory, expected in directories.items():
            _check(deadline)
            current = directory.lstat()
            if _is_link(current) or not stat.S_ISDIR(current.st_mode) or _directory_signature(current) != expected:
                raise VaultAccessError("source_changed")
        policy.require_root()
        if policy.coverage() != coverage:
            raise VaultAccessError("source_changed")
        _check(deadline)
    except OSError:
        policy.require_root()
        raise VaultAccessError("source_unreadable") from None
    return files, coverage


def _state_directory(policy, configured, *, create=False):
    if not configured or not isinstance(configured, str) or not Path(configured).is_absolute():
        raise VaultAccessError("index_unavailable")
    path = Path(os.path.abspath(configured))
    # State must neither contain nor be contained by the Vault or checkout.
    for boundary in (policy.root, CHECKOUT):
        try:
            common = os.path.normcase(os.path.commonpath([path, boundary]))
        except ValueError:  # Different Windows drives are disjoint.
            continue
        if common in (os.path.normcase(str(path)), os.path.normcase(str(boundary))):
            raise VaultAccessError("invalid_configuration")
    try:
        ancestor = path
        while not ancestor.exists():
            if ancestor.is_symlink():
                raise VaultAccessError("index_unavailable")
            ancestor = ancestor.parent
        _no_links(ancestor)
        if create:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        _no_links(path)
        if not path.is_dir():
            raise OSError
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise VaultAccessError("invalid_configuration")
    except (OSError, VaultAccessError) as error:
        if isinstance(error, VaultAccessError) and error.code == "invalid_configuration":
            raise
        raise VaultAccessError("index_unavailable") from None
    return path


def rebuild_index(policy, state_directory, *, deadline=None):
    """Publish a complete generation atomically; leave the previous one on failure."""
    deadline = time.monotonic() + 10 if deadline is None else deadline
    policy.require_root()
    files, coverage = _inventory(policy, deadline)
    state = _state_directory(policy, state_directory, create=True)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".vault-index-", suffix=".tmp", dir=state)
        os.close(fd)
        meta = {"schema": SCHEMA, "policy": _fingerprint(policy), "generation": uuid.uuid4().hex,
                "indexed_at": datetime.now(timezone.utc).isoformat(), "missing_roots": coverage["missing_roots"]}
        with closing(sqlite3.connect(temporary, timeout=1)) as db:
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE metadata (value TEXT NOT NULL)")
            db.execute("CREATE TABLE files (path TEXT PRIMARY KEY, size INTEGER, modified INTEGER, device TEXT, inode TEXT, digest TEXT)")
            db.execute("CREATE VIRTUAL TABLE notes USING fts5(path UNINDEXED, content, tokenize='unicode61')")
            def snapshot(item):
                _check(deadline)
                relative, expected = item
                _, text, digest, info = _snapshot(policy, _path_input(relative), opener=_open_probe)
                _check(deadline)
                if _metadata(info) != expected:
                    raise VaultAccessError("source_changed")
                return relative, expected, text, digest

            for relative, expected, text, digest in _parallel(snapshot, sorted(files.items()), deadline):
                _check(deadline)
                db.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?)", (relative, *expected, digest))
                db.execute("INSERT INTO notes(path, content) VALUES (?, ?)", (relative, text))
            db.execute("INSERT INTO metadata VALUES (?)", (json.dumps(meta),))
            db.commit()
        current, now_coverage = _inventory(policy, deadline)
        if current != files or now_coverage != coverage:
            raise VaultAccessError("source_changed")
        _state_directory(policy, state_directory)
        _no_links(Path(temporary))
        if Path(temporary).stat().st_size > MAX_DB_BYTES:
            raise VaultAccessError("inventory_limit_exceeded")
        target = state / "vault-index.db"
        if target.exists():
            _no_links(target)
        _check(deadline)
        os.replace(temporary, target)
        temporary = None
        return {"status": "ok", "generation": meta["generation"], "indexed_at": meta["indexed_at"],
                "notes": len(files), "missing_roots": coverage["missing_roots"]}
    except sqlite3.Error:
        _check(deadline)
        raise VaultAccessError("index_unavailable") from None
    except OSError:
        raise VaultAccessError("index_unavailable") from None
    finally:
        if temporary is not None:
            # Only files created by this build, always under the verified state dir.
            for suffix in ("", "-journal"):
                try:
                    Path(temporary + suffix).unlink(missing_ok=True)
                except OSError:
                    pass


def _query(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 512 or any(ord(c) < 32 for c in value):
        raise VaultAccessError("invalid_argument")
    terms = []
    position = 0
    while position < len(value):
        if not value[position:].strip():
            break
        match = re.match(r'\s*(?:"([^"\n]+)"|([^\s"]+))', value[position:])
        if not match:
            raise VaultAccessError("invalid_argument")
        term = match[1] if match[1] is not None else match[2]
        terms.append('"' + term.replace('"', '""') + '"')
        position += match.end()
        if position < len(value) and not value[position].isspace():
            raise VaultAccessError("invalid_argument")
    if value.count('"') % 2 or not terms or len(terms) > 64 or any(not re.search(r"\w", t) for t in terms):
        raise VaultAccessError("invalid_argument")
    return " AND ".join(terms)


def _excerpt(relative, text, digest, info, offset):
    lines = _note_lines(text)
    position = 0
    start = column = 0
    for i, line in enumerate(lines):
        if position + len(line) > offset:
            start, column = i, offset - position
            break
        position += len(line)
    snippet = text[offset:offset + 500]
    last = start
    remaining = len(snippet)
    for i in range(start, len(lines)):
        last = i
        remaining -= len(lines[i]) - (column if i == start else 0)
        if remaining <= 0:
            break
    heading = next((h[2] for h in reversed(_headings(lines)) if h[0] <= start), None)
    return {"path": relative, "snippet": snippet, "start_line": start + 1, "end_line": last + 1,
            "start_column": column, "heading": heading, "sha256": digest,
            "modified_at": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()}


def search_vault(policy, state_directory, arguments, *, deadline=None):
    deadline = time.monotonic() + 10 if deadline is None else deadline
    _check(deadline)
    policy.require_root()
    if not isinstance(arguments, dict) or set(arguments) - {"query", "root", "limit"}:
        raise VaultAccessError("invalid_argument")
    query = _query(arguments.get("query"))
    limit, subtree = arguments.get("limit", 10), arguments.get("root")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise VaultAccessError("invalid_argument")
    if subtree is not None:
        try:
            subtree = _parts(subtree)
        except VaultAccessError:
            raise VaultAccessError("invalid_argument") from None
        if not policy.allows(subtree):
            raise VaultAccessError("not_found")
    state = _state_directory(policy, state_directory)
    target = state / "vault-index.db"
    try:
        _no_links(target)
        if not stat.S_ISREG(target.stat().st_mode) or target.stat().st_size > MAX_DB_BYTES:
            raise OSError
        with closing(sqlite3.connect(target.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            meta_rows = db.execute("SELECT value FROM metadata LIMIT 2").fetchall()
            if len(meta_rows) != 1:
                raise VaultAccessError("index_unavailable")
            meta = json.loads(meta_rows[0][0])
            if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
                raise VaultAccessError("index_unavailable")
            if meta.get("policy") != _fingerprint(policy):
                raise VaultAccessError("index_stale")
            if (not re.fullmatch(r"[a-f0-9]{32}", str(meta.get("generation", "")))
                    or not isinstance(meta.get("indexed_at"), str) or len(meta["indexed_at"]) > 64):
                raise VaultAccessError("index_unavailable")
            rows = db.execute("SELECT path, size, modified, device, inode, digest FROM files LIMIT ?", (MAX_NOTES + 1,)).fetchall()
            if len(rows) > MAX_NOTES:
                raise VaultAccessError("index_unavailable")
            recorded = {r[0]: tuple(r[1:5]) for r in rows}
            digests = {r[0]: r[5] for r in rows}
            indexed_paths = [r[0] for r in db.execute("SELECT path FROM notes LIMIT ?", (MAX_NOTES + 1,))]
            if len(recorded) != len(rows) or len(indexed_paths) != len(rows) or set(indexed_paths) != set(recorded):
                raise VaultAccessError("index_unavailable")
            # An explicit root bounds both the query and its freshness work.
            # Keep the original policy for index identity and source access;
            # narrow only the walk, retaining denies and pinned root identity.
            validation_policy = policy
            expected = recorded
            if subtree is not None:
                # Preserve file-prefix filters by validating their parent dir.
                validation_policy = _scope_policy(policy, subtree, deadline)
                expected = {path: value for path, value in recorded.items()
                            if any(_under(path.split("/"), scope) for scope in validation_policy.allowed)}
            try:
                files, coverage = _inventory(validation_policy, deadline)
            except VaultAccessError as error:
                if error.code == "source_changed":
                    raise VaultAccessError("index_stale") from None
                raise
            if files != expected or (subtree is None and coverage["missing_roots"] != meta.get("missing_roots")):
                raise VaultAccessError("index_stale")
            index_coverage = {**coverage,
                              "allowed_roots": ["/".join(p) for p in policy.allowed],
                              "validated_roots": coverage["allowed_roots"],
                              "unvalidated_roots": ["/".join(p) for p in policy.allowed
                                                    if not any(_under(p, base) for base in validation_policy.allowed)],
                              "requested_root": "/".join(subtree) if subtree is not None else None,
                              "index_state": "current_for_scope" if subtree is not None else "current",
                              "generation": meta["generation"], "indexed_at": meta["indexed_at"]}
            # Literal path-prefix comparisons avoid SQL LIKE wildcard semantics.
            marker, close_marker = "\ue000" + uuid.uuid4().hex, "\ue001" + uuid.uuid4().hex
            db.create_function("within_root", 1, lambda relative: int(not subtree or _under(relative.split("/"), subtree)))
            matches = db.execute(
                "SELECT path, content, highlight(notes, 1, ?, ?) FROM notes WHERE notes MATCH ? "
                "AND within_root(path) "
                "ORDER BY rank, path LIMIT ?",
                (marker, close_marker, query, limit + 1),
            ).fetchall()
            data = []
            truncated = len(matches) > limit
            for relative, indexed_text, highlighted in matches[:limit]:
                _check(deadline)
                if relative not in files:
                    raise VaultAccessError("index_unavailable")
                try:
                    _, text, digest, info = _snapshot(policy, _path_input(relative))
                except VaultAccessError as error:
                    if error.code in {"source_changed", "not_found"}:
                        raise VaultAccessError("index_stale") from None
                    raise
                if digest != digests[relative] or _metadata(info) != files[relative]:
                    raise VaultAccessError("index_stale")
                if indexed_text != text:
                    raise VaultAccessError("index_unavailable")
                offset = highlighted.find(marker)
                if offset < 0 or marker in text or close_marker in text or not text.startswith(highlighted[:offset]):
                    raise VaultAccessError("index_unavailable")
                item = _excerpt(relative, text, digest, info, offset)
                candidate = {"status": "ok", "data": {"matches": data + [item]},
                             "coverage": index_coverage, "truncated": truncated, "continuation": None}
                if len(json.dumps(candidate, ensure_ascii=False).encode("utf-8")) > MAX_DATA_BYTES:
                    truncated = True
                    break
                data.append(item)
            final_policy = _scope_policy(policy, subtree, deadline) if subtree is not None else policy
            if final_policy.allowed != validation_policy.allowed:
                raise VaultAccessError("index_stale")
            final, final_coverage = _inventory(final_policy, deadline)
            if final != files or final_coverage != coverage:
                raise VaultAccessError("index_stale")
            if subtree is not None and _scope_policy(policy, subtree, deadline).allowed != validation_policy.allowed:
                raise VaultAccessError("index_stale")
            result = {"status": "ok", "data": {"matches": data},
                      "coverage": index_coverage, "truncated": truncated, "continuation": None}
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_DATA_BYTES or (matches and not data):
                raise VaultAccessError("response_too_large")
            _check(deadline)
            return result
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        _check(deadline)
        raise VaultAccessError("index_unavailable") from None
    except OSError:
        policy.require_root()
        raise VaultAccessError("index_unavailable") from None
