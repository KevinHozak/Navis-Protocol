"""Synthetic local FTS5, freshness and stdio acceptance for NAVIS-S018."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

from services.vault_access import VaultAccessError, VaultPolicy, read_note
import services.vault_index as index
from test_vault_mcp import Wire, _link, config


@pytest.fixture
def indexed(tmp_path):
    vault = tmp_path / "fixture-vault"
    (vault / "Documentation").mkdir(parents=True)
    (vault / "Journal").mkdir()
    (vault / "Documentation" / "one.md").write_bytes(b"\xef\xbb\xbf# One\r\n## Detail\r\nred blue orchard\r\nend\r\n")
    (vault / "Journal" / "two.md").write_text("# Two\nblue distant red\n", encoding="utf-8", newline="")
    policy = VaultPolicy.from_env(config(vault))
    state = str(tmp_path / "private-state")
    built = index.rebuild_index(policy, state)
    return policy, state, built


def search(indexed, query, **extra):
    policy, state, _ = indexed
    return index.search_vault(policy, state, {"query": query, **extra})


def code(call):
    with pytest.raises(VaultAccessError) as found:
        call()
    return found.value.code


def test_keyword_phrase_and_source_spans(indexed):
    policy, state, built = indexed
    result = search(indexed, "red blue")
    assert len(result["data"]["matches"]) == 2
    phrase = search(indexed, '"red blue"')
    hit = phrase["data"]["matches"][0]
    assert len(phrase["data"]["matches"]) == 1
    assert hit["path"] == "Documentation/one.md"
    assert hit["snippet"] == "red blue orchard\r\nend\r\n"
    assert (hit["start_line"], hit["end_line"], hit["start_column"], hit["heading"]) == (3, 4, 0, "Detail")
    note = read_note(policy, {"path": hit["path"], "section": "Detail"})
    assert note["data"]["sha256"] == hit["sha256"]
    assert phrase["coverage"]["index_state"] == "current"
    assert phrase["coverage"]["generation"] == built["generation"]
    assert phrase["coverage"]["indexed_at"] == built["indexed_at"]
    assert search(indexed, "red", root="Journal")["data"]["matches"][0]["path"] == "Journal/two.md"
    assert code(lambda: search(indexed, "red", root="Bridge")) == "not_found"
    assert (Path(state) / "vault-index.db").is_file()


def test_unicode_tokens_and_root_filtering_are_literal(indexed):
    policy, state, _ = indexed
    directory = policy.root / "Documentation" / "Café_100%keep"
    directory.mkdir()
    (directory / "unicode.md").write_text("# Café\n漢字 café literal\n", encoding="utf-8")
    index.rebuild_index(policy, state)
    result = search(indexed, '"漢字 cafe"', root="Documentation/CAFÉ_100%keep")
    assert len(result["data"]["matches"]) == 1
    assert result["data"]["matches"][0]["heading"] == "Café"
    assert result["data"]["matches"][0]["start_line"] == 2


def test_overlapping_roots_do_not_duplicate_notes(indexed):
    policy, state, _ = indexed
    configured = ["Documentation", "Documentation"]
    if os.name == "nt":
        configured.append("documentation")
    policy = VaultPolicy.from_env(config(policy.root, NAVIS_MCP_ALLOWED_ROOTS=json.dumps(configured)))
    assert index.rebuild_index(policy, state)["notes"] == 1
    assert len(index.search_vault(policy, state, {"query": "red"})["data"]["matches"]) == 1


def test_no_matches_and_missing_note_are_distinct(indexed):
    policy, _, _ = indexed
    result = search(indexed, "nonexistent")
    assert result["status"] == "ok" and result["data"]["matches"] == []
    assert not result["truncated"] and result["continuation"] is None
    assert code(lambda: read_note(policy, {"path": "Documentation/missing.md"})) == "not_found"


def test_heading_hashes_and_fences_keep_correct_section_provenance(indexed):
    policy, state, _ = indexed
    path = policy.root / "Documentation" / "one.md"
    path.write_text("# C#\nkeyword one\n~~~\n## Hidden\n~~~not-closing\n## Still hidden\n~~~\n# Tail ###\nkeyword two\n", encoding="utf-8", newline="")
    index.rebuild_index(policy, state)
    result = read_note(policy, {"path": "Documentation/one.md", "section": "C#"})
    assert "keyword one" in result["data"]["content"] and "keyword two" not in result["data"]["content"]
    assert code(lambda: read_note(policy, {"path": "Documentation/one.md", "section": "Still hidden"})) == "section_not_found"
    assert read_note(policy, {"path": "Documentation/one.md", "section": "Tail"})["data"]["content"].endswith("keyword two\n")
    assert search(indexed, '"keyword two"')["data"]["matches"][0]["heading"] == "Tail"


@pytest.mark.parametrize("query", ["", " ", '"unclosed', '""', '"red"blue', "*", "🐱", "x" * 513, "x\ny"])
def test_invalid_queries_do_not_reach_sql(indexed, query):
    assert code(lambda: search(indexed, query)) == "invalid_argument"


@pytest.mark.parametrize("extra", [{"limit": 0}, {"limit": 21}, {"limit": True}, {"limit": "1"},
                                    {"root": "../outside"}, {"root": ""}, {"unexpected": "synthetic"}])
def test_invalid_search_arguments(indexed, extra):
    assert code(lambda: search(indexed, "red", **extra)) == "invalid_argument"


def test_sql_and_fts_operators_are_literal(indexed):
    policy, state, _ = indexed
    (policy.root / "Documentation" / "operator.md").write_text("red OR blue AND content", encoding="utf-8")
    index.rebuild_index(policy, state)
    assert [m["path"] for m in search(indexed, "red OR blue")["data"]["matches"]] == ["Documentation/operator.md"]
    assert search(indexed, "red NOT blue")["data"]["matches"] == []
    assert search(indexed, "x;DROP_TABLE")["data"]["matches"] == []
    assert len(search(indexed, "red")["data"]["matches"]) == 3


@pytest.mark.parametrize("mutation", ["changed", "removed", "added", "renamed", "touched", "new_root"])
def test_stale_inventory_never_returns_results_and_rebuild_recovers(indexed, mutation):
    policy, state, _ = indexed
    path = policy.root / "Documentation" / "one.md"
    if mutation == "changed":
        path.write_text("replacement red", encoding="utf-8")
    elif mutation == "removed":
        path.unlink()
    elif mutation == "added":
        (policy.root / "Documentation" / "added.md").write_text("red", encoding="utf-8")
    elif mutation == "renamed":
        path.rename(path.with_name("renamed.md"))
    elif mutation == "touched":
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000000))
    else:
        (policy.root / "Operations").mkdir()
    assert code(lambda: search(indexed, "red")) == "index_stale"
    assert read_note(policy, {"path": "Journal/two.md"})["status"] == "ok"
    index.rebuild_index(policy, state)
    assert search(indexed, "red")["coverage"]["index_state"] == "current"


def test_missing_root_transition_and_policy_fingerprint(indexed):
    policy, state, _ = indexed
    (policy.root / "Journal" / "two.md").unlink()
    (policy.root / "Journal").rmdir()
    assert code(lambda: search(indexed, "no-match")) == "index_stale"
    index.rebuild_index(policy, state)
    assert "Journal" in search(indexed, "red")["coverage"]["missing_roots"]
    narrowed = VaultPolicy.from_env(config(policy.root, NAVIS_MCP_ALLOWED_ROOTS='["Journal"]'))
    assert code(lambda: index.search_vault(narrowed, state, {"query": "red"})) == "index_stale"


def test_unreadable_nonmatching_source_is_not_no_matches_and_failed_build_retains_generation(indexed, monkeypatch):
    policy, state, _ = indexed
    target = policy.root / "Journal" / "two.md"
    old = (Path(state) / "vault-index.db").read_bytes()
    original = Path.open

    def denied(path, *args, **kwargs):
        if path == target and args == ("rb",):
            raise PermissionError("SYNTHETIC_PRIVATE_ERROR")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    assert code(lambda: search(indexed, "absent")) == "source_unreadable"
    assert code(lambda: index.rebuild_index(policy, state)) == "source_unreadable"
    assert (Path(state) / "vault-index.db").read_bytes() == old
    assert not list(Path(state).glob("*.tmp"))


@pytest.mark.parametrize("contents,error", [(b"\xff", "unsupported_encoding"), (b"x" * (1024 * 1024 + 1), "file_too_large")], ids=["invalid-utf8", "oversized"])
def test_failed_rebuild_keeps_old_database_and_removes_temporary_files(indexed, contents, error):
    policy, state, _ = indexed
    old = (Path(state) / "vault-index.db").read_bytes()
    (policy.root / "Journal" / "invalid.md").write_bytes(contents)
    assert code(lambda: index.rebuild_index(policy, state)) == error
    assert (Path(state) / "vault-index.db").read_bytes() == old
    assert [p.name for p in Path(state).iterdir()] == ["vault-index.db"]


def test_missing_corrupt_and_incompatible_index(indexed):
    policy, state, _ = indexed
    target = Path(state) / "vault-index.db"
    assert code(lambda: index.search_vault(policy, None, {"query": "red"})) == "index_unavailable"
    target.unlink()
    assert code(lambda: search(indexed, "red")) == "index_unavailable"
    assert not target.exists()  # Read-only SQLite must not create an empty file.
    target.write_bytes(b"not sqlite")
    assert code(lambda: search(indexed, "red")) == "index_unavailable"
    index.rebuild_index(policy, state)
    with sqlite3.connect(target) as db:
        db.execute("UPDATE metadata SET value=?", (json.dumps({"schema": 999}),))
    assert code(lambda: search(indexed, "red")) == "index_unavailable"
    assert read_note(policy, {"path": "Journal/two.md"})["status"] == "ok"


def test_incomplete_index_is_not_a_successful_empty_search(indexed):
    _, state, _ = indexed
    with sqlite3.connect(Path(state) / "vault-index.db") as db:
        db.execute("DELETE FROM notes")
    assert code(lambda: search(indexed, "red")) == "index_unavailable"


def test_vault_unavailable_takes_precedence(indexed):
    policy, _, _ = indexed
    moved = policy.root.with_name("temporarily-unavailable")
    policy.root.rename(moved)
    try:
        assert code(lambda: search(indexed, "red")) == "vault_unavailable"
        assert code(lambda: index.search_vault(policy, None, {"query": "red"})) == "vault_unavailable"
    finally:
        moved.rename(policy.root)


def test_excluded_paths_and_real_junctions_never_enter_index(indexed, tmp_path):
    policy, state, _ = indexed
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.md").write_text("LEAKMARKER", encoding="utf-8")
    base = policy.root / "Documentation"
    for name in (".hidden", "excluded", "credentials"):
        (base / name).mkdir()
        (base / name / "leak.md").write_text("LEAKMARKER", encoding="utf-8")
    (base / "settings.md").write_text("LEAKMARKER", encoding="utf-8")
    (base / "tokens.md").write_text("LEAKMARKER", encoding="utf-8")
    link = base / "alias"
    _link(link, outside)
    try:
        policy = VaultPolicy.from_env(config(policy.root, NAVIS_MCP_DENIED_PATHS='["Documentation/excluded"]'))
        index.rebuild_index(policy, state)
        assert code(lambda: read_note(policy, {"path": "Documentation/credentials/leak.md"})) == "not_found"
        assert code(lambda: read_note(policy, {"path": "Documentation/tokens.md"})) == "not_found"
        assert index.search_vault(policy, state, {"query": "LEAKMARKER"})["data"]["matches"] == []
        with sqlite3.connect(Path(state) / "vault-index.db") as db:
            assert db.execute("SELECT count(*) FROM notes WHERE notes MATCH 'LEAKMARKER'").fetchone()[0] == 0
    finally:
        link.unlink() if link.is_symlink() else link.rmdir()


def test_same_metadata_modified_hit_is_rechecked_by_digest(indexed):
    policy, _, _ = indexed
    path = policy.root / "Documentation" / "one.md"
    info = path.stat()
    path.write_bytes(path.read_bytes().replace(b"orchard", b"changed"))
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert code(lambda: search(indexed, "red")) == "index_stale"


def test_output_budget_and_unicode_snippets_are_bounded(indexed):
    from navis_vault_mcp import _result
    policy, state, _ = indexed
    for n in range(24):
        (policy.root / "Documentation" / f"unicode{n}.md").write_text("needle " + "漢" * 800, encoding="utf-8")
    index.rebuild_index(policy, state)
    result = search(indexed, "needle", limit=20)
    assert result["truncated"] and 0 < len(result["data"]["matches"]) <= 20
    assert all(len(m["snippet"]) <= 500 for m in result["data"]["matches"])
    assert len(_result(result).model_dump_json(by_alias=True).encode("utf-8")) < 64 * 1024


def test_state_cannot_live_inside_vault_or_checkout_and_links_are_denied(indexed, tmp_path):
    policy, state, _ = indexed
    for invalid in (policy.root / "private-state", index.CHECKOUT / ".tools" / "mcp-state"):
        assert code(lambda: index.rebuild_index(policy, str(invalid))) == "invalid_configuration"
        assert not invalid.exists()
    alias = tmp_path / "alias-state"
    _link(alias, Path(state))
    try:
        assert code(lambda: index.search_vault(policy, str(alias), {"query": "red"})) == "index_unavailable"
    finally:
        alias.unlink() if alias.is_symlink() else alias.rmdir()


def test_inventory_and_deadline_limits_do_not_replace_generation(indexed, monkeypatch):
    policy, state, _ = indexed
    old = (Path(state) / "vault-index.db").read_bytes()
    monkeypatch.setattr(index, "MAX_NOTES", 1)
    assert code(lambda: index.rebuild_index(policy, state)) == "inventory_limit_exceeded"
    assert (Path(state) / "vault-index.db").read_bytes() == old
    assert code(lambda: index.rebuild_index(policy, state, deadline=time.monotonic() - 1)) == "deadline_exceeded"


def test_search_revalidates_after_query_even_without_matches(indexed, monkeypatch):
    original = index._inventory
    calls = 0

    def changing(policy, deadline):
        nonlocal calls
        calls += 1
        if calls == 2:
            (policy.root / "Journal" / "two.md").write_text("changed content", encoding="utf-8")
        return original(policy, deadline)

    monkeypatch.setattr(index, "_inventory", changing)
    assert code(lambda: search(indexed, "no-match")) == "index_stale"


def test_cli_and_real_stdio_search_do_not_mutate_vault_or_index(indexed):
    policy, state, _ = indexed
    env = {**os.environ, **config(policy.root), "NAVIS_MCP_STATE_DIR": state}
    before = {p.relative_to(policy.root): p.read_bytes() for p in policy.root.rglob("*") if p.is_file()}
    cli = subprocess.run([sys.executable, str(Path(__file__).parents[1] / "navis_vault_index.py"), "rebuild"],
                         capture_output=True, text=True, encoding="utf-8", env=env, timeout=15)
    assert cli.returncode == 0 and json.loads(cli.stdout)["notes"] == 2 and cli.stderr == ""
    db_before = (Path(state) / "vault-index.db").read_bytes()
    wire = Wire(env)
    try:
        wire.start()
        tool = next(t for t in wire.call("tools/list")["result"]["tools"] if t["name"] == "search_vault")
        assert tool["annotations"]["readOnlyHint"] and tool["inputSchema"]["additionalProperties"] is False
        found = wire.call("tools/call", {"name": "search_vault", "arguments": {"query": '"red blue"'}})["result"]
        assert not found["isError"] and len(found["structuredContent"]["data"]["matches"]) == 1
        unknown = wire.call("tools/call", {"name": "rebuild_index", "arguments": {}})["result"]
        assert unknown["isError"] and unknown["structuredContent"]["error"]["code"] == "unknown_tool"
        assert (Path(state) / "vault-index.db").read_bytes() == db_before
        assert {p.relative_to(policy.root): p.read_bytes() for p in policy.root.rglob("*") if p.is_file()} == before
        (policy.root / "Journal" / "two.md").write_text("changed", encoding="utf-8")
        stale = wire.call("tools/call", {"name": "search_vault", "arguments": {"query": "red"}})["result"]
        assert stale["isError"] and stale["structuredContent"]["error"]["code"] == "index_stale"
        assert "matches" not in json.dumps(stale)
    finally:
        logs = wire.close()
        assert wire.proc.returncode == 0 and logs == ""
