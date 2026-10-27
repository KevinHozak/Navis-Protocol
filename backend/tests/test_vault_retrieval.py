"""Disposable date/mission fixtures, including stdio and no-mutation acceptance."""
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import time

import pytest

from services.vault_access import VaultAccessError, VaultPolicy, read_note
import services.vault_retrieval as retrieval
from test_vault_mcp import Wire, _link, config


def journal(root, day, text="# Day\r\n## Work\r\nentry\r\n"):
    path = root / "Journal" / day[:4] / day[5:7] / (day + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    return path


def mission(root, name="Route", region="Sanctum", kind="Main", text="# Route\nMission details\n"):
    path = root / "Operations" / region / kind / name / "Mission.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "fixture-vault"
    root.mkdir()
    (root / "Documentation").mkdir()
    (root / "Keeper").mkdir()
    (root / "Keeper" / "xp.db").write_bytes(b"synthetic unchanged XP state")
    journal(root, "2026-12-31")
    journal(root, "2027-01-01")
    mission(root)
    return root


def policy(root, **env):
    return VaultPolicy.from_env(config(root, **env))


def code(call):
    with pytest.raises(VaultAccessError) as found:
        call()
    return found.value.code


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_journal_range_is_inclusive_literal_and_source_linked(vault):
    before = snapshot(vault)
    result = retrieval.get_journal_range(policy(vault), {"start_date": "2026-12-30", "end_date": "2027-01-02"})
    assert result["data"]["timezone"] == "America/Chicago"
    assert [n["date"] for n in result["data"]["journals"]] == ["2026-12-31", "2027-01-01"]
    assert result["data"]["missing_dates"] == ["2026-12-30", "2027-01-02"]
    assert result["continuation"] is None and not result["truncated"]
    first = result["data"]["journals"][0]
    assert first["path"] == "Journal/2026/12/2026-12-31.md"
    assert first["sha256"] == hashlib.sha256(before[first["path"]]).hexdigest()
    assert first["content"] == "# Day\r\n## Work\r\nentry\r\n"
    assert (first["start_line"], first["end_line"]) == (1, 3)
    assert snapshot(vault) == before


@pytest.mark.parametrize("start,end,existing", [
    ("2024-02-28", "2024-03-01", "2024-02-29"),
    ("2026-02-28", "2026-03-01", "2026-03-01"),
    ("9999-12-31", "9999-12-31", "9999-12-31"),
])
def test_month_leap_and_max_year_boundaries(vault, start, end, existing):
    journal(vault, existing)
    result = retrieval.get_journal_range(policy(vault), {"start_date": start, "end_date": end})
    assert [item["date"] for item in result["data"]["journals"]] == [existing]
    assert len(result["data"]["missing_dates"]) == (date.fromisoformat(end) - date.fromisoformat(start)).days


@pytest.mark.parametrize("args", [
    {}, {"start_date": "2026-02-29", "end_date": "2026-03-01"},
    {"start_date": "2026-01-01", "end_date": "2026-02-01"},
    {"start_date": "2026-02-01", "end_date": "2026-01-01"},
    {"start_date": "2026-1-1", "end_date": "2026-01-02"},
    {"start_date": True, "end_date": "2026-01-02"},
    {"start_date": "2026-01-01", "end_date": "2026-01-02", "max_chars_per_day": True},
    {"start_date": "2026-01-01", "end_date": "2026-01-02", "max_chars_per_day": 8001},
    {"start_date": "2026-01-01", "end_date": "2026-01-02", "create": True},
])
def test_invalid_journal_inputs(vault, args):
    assert code(lambda: retrieval.get_journal_range(policy(vault), args)) == "invalid_argument"


def test_sections_missing_sections_and_per_day_continuation(vault):
    p = policy(vault)
    args = {"start_date": "2026-12-31", "end_date": "2026-12-31", "section": "Work", "max_chars_per_day": 5}
    result = retrieval.get_journal_range(p, args)
    note = result["data"]["journals"][0]
    assert note["content"] == "## Wo" and note["truncated"] and result["truncated"]
    resumed = read_note(p, {"path": note["path"], **note["continuation"]})
    assert note["content"] + resumed["data"]["content"] == "## Work\r\nentry\r\n"
    args["section"] = "Absent"
    assert code(lambda: retrieval.get_journal_range(p, args)) == "section_not_found"


def test_journal_global_byte_budget_pages_dates_without_false_missing(vault):
    from navis_vault_mcp import _result
    p = policy(vault)
    start = date(2026, 10, 1)
    for i in range(31):
        journal(vault, (start + timedelta(days=i)).isoformat(), "# Day\n" + "漢" * 9000 + "\n")
    next_day, seen = start.isoformat(), []
    for _ in range(32):
        got = retrieval.get_journal_range(p, {"start_date": next_day, "end_date": "2026-10-31", "max_chars_per_day": 8000})
        assert len(_result(got).model_dump_json(by_alias=True).encode("utf-8")) < 64 * 1024
        assert got["data"]["missing_dates"] == []
        seen.extend(n["date"] for n in got["data"]["journals"])
        if got["continuation"] is None:
            break
        assert got["continuation"]["next_date"] > next_day
        next_day = got["continuation"]["next_date"]
    else:
        pytest.fail("date pagination did not progress")
    assert seen == [(start + timedelta(days=i)).isoformat() for i in range(31)]


def test_journal_denial_and_unreadable_area_are_not_missing_dates(vault, monkeypatch):
    args = {"start_date": "2026-12-31", "end_date": "2026-12-31"}
    denied = policy(vault, NAVIS_MCP_DENIED_PATHS='["Journal/2026"]')
    assert code(lambda: retrieval.get_journal_range(denied, args)) == "not_found"
    p = policy(vault)
    original = Path.open

    def blocked(path, *a, **kw):
        if path.name == "2026-12-31.md" and a == ("rb",):
            raise PermissionError("synthetic private error")
        return original(path, *a, **kw)

    monkeypatch.setattr(Path, "open", blocked)
    assert code(lambda: retrieval.get_journal_range(p, args)) == "source_unreadable"


def test_missing_year_is_reported_without_initializing_directories(vault):
    before = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*"))
    got = retrieval.get_journal_range(policy(vault), {"start_date": "2028-01-01", "end_date": "2028-01-02"})
    assert got["data"]["journals"] == []
    assert got["data"]["missing_dates"] == ["2028-01-01", "2028-01-02"]
    assert sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*")) == before


def test_missions_main_side_paths_and_ambiguity(vault):
    p = policy(vault)
    second = mission(vault, "Route", "Outland", "Side")
    before = snapshot(vault)
    ambiguous = retrieval.get_mission(p, {"name": "Route"})
    assert ambiguous["status"] == "error" and ambiguous["error"]["code"] == "ambiguous_mission"
    assert ambiguous["error"]["candidates"] == ["Operations/Outland/Side/Route/Mission.md", "Operations/Sanctum/Main/Route/Mission.md"]
    found = retrieval.get_mission(p, {"name": "Route", "region": "Outland", "mission_type": "Side"})
    assert found["data"]["mission_type"] == "Side"
    direct = retrieval.get_mission(p, {"path": second.relative_to(vault).as_posix()})
    assert direct["data"]["mission"]["sha256"] == found["data"]["mission"]["sha256"]
    assert snapshot(vault) == before


@pytest.mark.parametrize("args", [
    {}, {"name": "Route", "path": "Operations/Sanctum/Main/Route/Mission.md"},
    {"name": "../escape"}, {"name": "Route", "mission_type": []}, {"name": "Route", "mission_type": None},
    {"path": 1}, {"path": "Operations/Sanctum/Main/Route/Mission.md", "region": "Sanctum"},
    {"name": "Route", "related_limit": 6}, {"name": "Route", "related_limit": True},
    {"name": "Route", "overwrite": True},
])
def test_invalid_mission_arguments(vault, args):
    assert code(lambda: retrieval.get_mission(policy(vault), args)) == "invalid_argument"


def test_missing_or_noncanonical_mission_is_not_found(vault):
    p = policy(vault)
    for args in ({"name": "Missing"}, {"path": "Documentation/not-a-mission.md"}, {"path": "../Mission.md"}):
        assert code(lambda: retrieval.get_mission(p, args)) == "not_found"


def test_ambiguous_candidate_list_is_bounded_and_excludes_denied_regions(vault):
    from navis_vault_mcp import _result
    for i in range(23):
        mission(vault, region=f"Region{i:02d}")
    p = policy(vault, NAVIS_MCP_DENIED_PATHS='["Operations/Region00"]')
    got = retrieval.get_mission(p, {"name": "Route"})
    assert got["error"]["truncated"] and len(got["error"]["candidates"]) == 20
    assert "Region00" not in json.dumps(got)
    assert len(_result(got).model_dump_json(by_alias=True).encode("utf-8")) < 64 * 1024


def test_related_notes_are_explicit_bounded_and_do_not_expand_recursively(vault):
    doc = vault / "Documentation"
    (doc / "Guide.md").write_text("# Guide\n" + "g" * 3000, encoding="utf-8")
    (doc / "Overview.md").write_text("# Overview\n[[Documentation/Never]]\n", encoding="utf-8")
    (doc / "Only.md").write_text("Only context", encoding="utf-8")
    (doc / "Never.md").write_text("NEVER_EXPANDED", encoding="utf-8")
    (doc / "Context.md").write_text("First duplicate", encoding="utf-8")
    (doc / "nested").mkdir()
    (doc / "nested" / "Context.md").write_text("Second duplicate", encoding="utf-8")
    (doc / "excluded").mkdir()
    (doc / "excluded" / "hidden.md").write_text("EXCLUDED_CONTENT", encoding="utf-8")
    mission(vault, text="# Route\n[guide](../../../../Documentation/Guide.md)\n[[Documentation/Overview|overview]]\n[[Context]]\n[[Documentation/excluded/hidden]]\n[remote](https://example.invalid/private)\n[[Only]]\n")
    p = policy(vault, NAVIS_MCP_DENIED_PATHS='["Documentation/excluded"]')
    before = snapshot(vault)
    got = retrieval.get_mission(p, {"name": "Route", "related_limit": 5})
    assert [n["path"] for n in got["data"]["related"]] == ["Documentation/Guide.md", "Documentation/Overview.md", "Documentation/Only.md"]
    assert len(got["data"]["related"][0]["content"]) == 2000
    assert got["data"]["related"][0]["truncated"]
    assert "NEVER_EXPANDED" not in json.dumps(got) and "EXCLUDED_CONTENT" not in json.dumps(got)
    assert any(u["code"] == "ambiguous_link" for u in got["data"]["unresolved_links"])
    assert all(set(u) == {"link_index", "code"} for u in got["data"]["unresolved_links"])
    assert snapshot(vault) == before


def test_unicode_related_paths_use_character_bounds_without_url_expansion(vault):
    directory = vault / "Documentation" / ("漢" * 50)
    directory.mkdir()
    path = directory / (("字" * 65) + ".md")
    path.write_text("Unicode linked context", encoding="utf-8")
    relative = path.relative_to(vault).as_posix()
    mission(vault, text="# Route\n[[" + relative + "]]\n")
    got = retrieval.get_mission(policy(vault), {"name": "Route"})
    assert got["data"]["related"][0]["content"] == "Unicode linked context"


def test_many_unresolved_links_do_not_overflow_a_large_mission(vault):
    from navis_vault_mcp import _result
    links = "\n".join(f"[[Documentation/missing{n}]]" for n in range(32))
    mission(vault, text="# Route\n" + links + "\n" + "漢" * 20000)
    got = retrieval.get_mission(policy(vault), {"name": "Route"})
    assert got["status"] == "ok" and got["truncated"]
    assert len(_result(got).model_dump_json(by_alias=True).encode("utf-8")) < 64 * 1024


def test_zero_related_limit_and_code_links_do_not_read_context(vault, monkeypatch):
    mission(vault, text="# Route\n[[Only]]\n")

    def forbidden(*args, **kwargs):
        raise AssertionError("context inventory must not run")

    monkeypatch.setattr(retrieval, "_inventory", forbidden)
    got = retrieval.get_mission(policy(vault), {"name": "Route", "related_limit": 0})
    assert got["data"]["related"] == [] and got["data"]["related_truncated"]
    mission(vault, text="# Route\n~~~\n[[Only]]\n~~~\n`[[Only]]`\n")
    got = retrieval.get_mission(policy(vault), {"name": "Route"})
    assert got["data"]["related"] == [] and not got["data"]["unresolved_links"]


def test_related_traversal_and_external_paths_do_not_disclose_outside_content(vault, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("OUTSIDE_PRIVATE_SENTINEL", encoding="utf-8")
    mission(vault, text="# Route\n[outside](../../../../../outside.md)\n[absolute](C:/outside.md)\n[remote](https://example.invalid/)\n")
    got = retrieval.get_mission(policy(vault), {"name": "Route"})
    assert got["data"]["related"] == [] and len(got["data"]["unresolved_links"]) == 3
    assert "OUTSIDE_PRIVATE_SENTINEL" not in json.dumps(got)
    assert all(set(u) == {"link_index", "code"} for u in got["data"]["unresolved_links"])


def test_large_mission_and_related_context_stay_under_wire_budget(vault):
    from navis_vault_mcp import _result
    mission(vault, text="# Route\n" + "漢" * 20000)
    got = retrieval.get_mission(policy(vault), {"name": "Route"})
    assert got["truncated"] and len(got["data"]["mission"]["content"]) <= 8000
    assert len(_result(got).model_dump_json(by_alias=True).encode("utf-8")) < 64 * 1024
    continuation = got["data"]["mission"]["continuation"]
    assert continuation is not None


def test_unavailable_root_and_deadlines(vault):
    p = policy(vault)
    assert code(lambda: retrieval.get_mission(p, {"name": "Route"}, deadline=time.monotonic() - 1)) == "deadline_exceeded"
    moved = vault.with_name("unavailable")
    vault.rename(moved)
    try:
        assert code(lambda: retrieval.get_mission(p, {"name": "Route"})) == "vault_unavailable"
        assert code(lambda: retrieval.get_journal_range(p, {"start_date": "2026-12-31", "end_date": "2027-01-01"})) == "vault_unavailable"
    finally:
        moved.rename(vault)


def test_journal_and_mission_junctions_are_not_followed(vault, tmp_path):
    outside = tmp_path / "outside"
    (outside / "01").mkdir(parents=True)
    (outside / "01" / "2030-01-01.md").write_text("OUTSIDE", encoding="utf-8")
    (outside / "Mission.md").write_text("OUTSIDE", encoding="utf-8")
    year = vault / "Journal" / "2030"
    alias = vault / "Operations" / "Sanctum" / "Main" / "Alias"
    _link(year, outside)
    _link(alias, outside)
    try:
        p = policy(vault)
        assert code(lambda: retrieval.get_journal_range(p, {"start_date": "2030-01-01", "end_date": "2030-01-01"})) == "not_found"
        assert code(lambda: retrieval.get_mission(p, {"name": "Alias"})) == "not_found"
        assert code(lambda: retrieval.get_mission(p, {"path": "Operations/Sanctum/Main/Alias/Mission.md"})) == "not_found"
    finally:
        year.unlink() if year.is_symlink() else year.rmdir()
        alias.unlink() if alias.is_symlink() else alias.rmdir()


def test_real_stdio_retrieval_is_read_only_without_an_index(vault):
    before = snapshot(vault)
    wire = Wire(config(vault, NAVIS_MCP_STATE_DIR=""))
    try:
        wire.start()
        tools = wire.call("tools/list")["result"]["tools"]
        assert len(tools) == 4 and all(t["annotations"]["readOnlyHint"] for t in tools)
        days = wire.call("tools/call", {"name": "get_journal_range", "arguments": {"start_date": "2026-12-31", "end_date": "2027-01-02"}})["result"]
        assert not days["isError"] and days["structuredContent"]["data"]["missing_dates"] == ["2027-01-02"]
        got = wire.call("tools/call", {"name": "get_mission", "arguments": {"name": "Route"}})["result"]
        assert not got["isError"] and got["structuredContent"]["data"]["name"] == "Route"
        mission(vault, "Route", "Outland", "Side")
        ambiguous = wire.call("tools/call", {"name": "get_mission", "arguments": {"name": "Route"}})["result"]
        assert ambiguous["isError"] and len(ambiguous["structuredContent"]["error"]["candidates"]) == 2
        assert {k: v for k, v in snapshot(vault).items() if k in before} == before
    finally:
        logs = wire.close()
        assert wire.proc.returncode == 0 and logs == ""
