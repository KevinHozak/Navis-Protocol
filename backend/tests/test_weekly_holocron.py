"""
test_weekly_holocron.py - Unit tests for Weekly Holocron telemetry aggregation and API endpoints.
"""

import os
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from services.holocron_engine import (
    get_week_date_range,
    get_current_iso_week,
    get_previous_iso_week,
    resolve_manor,
    parse_daily_journal,
    build_weekly_holocron,
    get_holocron_manifest
)
from main import app


def test_week_date_range():
    """Verify ISO week mapping accurately bounds Monday to Sunday."""
    start_date, end_date, dates = get_week_date_range("2026-W40")
    assert start_date == "2026-09-28"
    assert end_date == "2026-10-04"
    assert len(dates) == 7
    assert dates[0] == "2026-09-28"
    assert dates[-1] == "2026-10-04"


def test_invalid_week_id():
    """Verify invalid week IDs raise ValueError."""
    with pytest.raises(ValueError):
        get_week_date_range("invalid-week")


def test_resolve_manor():
    """Verify section headers resolve to expected Manors."""
    assert resolve_manor("## The High-Velocity Front")["id"] == "HIGH_VELOCITY_FRONT"
    assert resolve_manor("## Daily Work")["id"] == "HIGH_VELOCITY_FRONT"
    assert resolve_manor("## The Sanctum")["id"] == "SANCTUM"
    assert resolve_manor("## The Domestic Breach")["id"] == "DOMESTIC_BREACH"
    assert resolve_manor("## The Bureaucratic Gauntlet")["id"] == "BUREAUCRATIC_GAUNTLET"
    assert resolve_manor("## The Kinetic Outland")["id"] == "KINETIC_OUTLAND"


def test_build_weekly_holocron_isolated(tmp_path):
    """Verify full aggregation pipeline with an isolated mock vault."""
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    
    # 1. Create Daily Journals
    jdir = vault / "Journal" / "2026" / "09"
    jdir.mkdir(parents=True)
    
    jfile = jdir / "2026-09-28.md"
    jfile.write_text(
        "# 2026-09-28\n"
        "🌀 Realm: The Silicon Spires\n"
        "👾 Prime Beast: Syntax Wyrm\n"
        "🛡️ Active Squad:\n"
        "- Lyra\n"
        "- Kaelen\n\n"
        "## The High-Velocity Front\n"
        "- [x] Fix telemetry calculation\n"
        "- [x] Write regression tests\n"
        "- [ ] Update documentation\n\n"
        "## The Sanctum\n"
        "- [x] Morning protocol\n",
        encoding="utf-8-sig"
    )

    # 2. Create mock Progression DB
    kdir = vault / "Keeper"
    kdir.mkdir()
    db_path = kdir / "navis_progression.db"
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE xp_ledger (
            award_id TEXT PRIMARY KEY,
            local_date TEXT NOT NULL,
            source_type TEXT NOT NULL,
            amount INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE achievements (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            date_achieved TEXT NOT NULL
        )
    """)
    cur.execute("INSERT INTO xp_ledger VALUES ('AW-1', '2026-09-28', 'task', 300)")
    cur.execute("INSERT INTO xp_ledger VALUES ('AW-2', '2026-09-28', 'combat', 500)")
    cur.execute("INSERT INTO achievements VALUES ('TEST_ACH', 'Test Honor', 'Achieved in test', '2026-09-28')")
    conn.commit()
    conn.close()

    # 3. Execute aggregator
    payload = build_weekly_holocron(str(vault), "2026-W40", force=True)

    assert payload["week_id"] == "2026-W40"
    assert payload["start_date"] == "2026-09-28"
    assert payload["end_date"] == "2026-10-04"
    assert payload["summary"]["completed_tasks"] == 3
    assert payload["summary"]["pending_tasks"] == 1
    assert payload["summary"]["total_tasks"] == 4
    assert payload["summary"]["precision_rate"] == 75.0
    assert payload["summary"]["total_xp_gained"] == 800
    assert payload["progression"]["xp_breakdown"]["tasks"] == 300
    assert payload["progression"]["xp_breakdown"]["combat"] == 500
    assert len(payload["progression"]["achievements_unlocked"]) == 1
    assert payload["combat"]["beasts_neutralized"][0]["name"] == "Syntax Wyrm"
    assert payload["squad_mvp"]["name"] == "Lyra"
    assert "Syntax Wyrm" in payload["tactical_debrief"]

    # Verify persistence
    saved_file = vault / "Bridge" / "Holocron" / "Weekly" / "2026-W40.json"
    assert saved_file.exists()
    
    manifest_file = vault / "Bridge" / "Holocron" / "weekly_manifest.json"
    assert manifest_file.exists()
    
    manifest = get_holocron_manifest(str(vault))
    assert len(manifest) == 1
    assert manifest[0]["week_id"] == "2026-W40"


def test_api_holocron_endpoints(monkeypatch, tmp_path):
    """Verify FastAPI Holocron endpoints return proper schema."""
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    
    # Pre-populate a synthetic week
    holocron_dir = vault / "Bridge" / "Holocron" / "Weekly"
    holocron_dir.mkdir(parents=True)
    
    sample_payload = {
        "week_id": "2026-W40",
        "start_date": "2026-09-28",
        "end_date": "2026-10-04",
        "summary": {
            "total_tasks": 10,
            "completed_tasks": 8,
            "pending_tasks": 2,
            "precision_rate": 80.0,
            "total_xp_gained": 1200,
            "threats_neutralized": 1
        },
        "tactical_debrief": "High velocity test cycle."
    }
    
    with open(holocron_dir / "2026-W40.json", "w", encoding="utf-8") as f:
        json.dump(sample_payload, f)
        
    manifest_file = vault / "Bridge" / "Holocron" / "weekly_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump([{"week_id": "2026-W40", "precision_rate": 80.0}], f)

    import main
    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))

    client = TestClient(app)
    
    # Test GET by ID
    res = client.get("/api/holocron/weekly/2026-W40")
    assert res.status_code == 200
    data = res.json()
    assert data["week_id"] == "2026-W40"
    assert data["summary"]["precision_rate"] == 80.0

    # Test Manifest
    res = client.get("/api/holocron/weekly/manifest")
    assert res.status_code == 200
    manifest = res.json()
    assert len(manifest) == 1
    assert manifest[0]["week_id"] == "2026-W40"

    # Test HTML Endpoint
    res = client.get("/api/holocron/weekly/2026-W40/html")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in res.text
    assert "Weekly Holocron // 2026-W40" in res.text


def test_export_standalone_html(tmp_path):
    """Verify standalone HTML generation produces valid, styled self-contained document."""
    from services.holocron_engine import export_standalone_html
    payload = {
        "week_id": "2026-W40",
        "start_date": "2026-09-28",
        "end_date": "2026-10-04",
        "summary": {
            "total_tasks": 10,
            "completed_tasks": 9,
            "precision_rate": 90.0,
            "total_xp_gained": 3500,
            "threats_neutralized": 2,
            "current_level": 42
        },
        "tactical_debrief": "Superb operational tempo across all sectors.",
        "daily_telemetry": [
            {"date": "2026-09-28", "day_name": "Mon", "completed": 5, "total": 5, "precision": 100.0}
        ],
        "sector_distribution": [
            {"sector_id": "HIGH_VELOCITY_FRONT", "name": "High-Velocity Front", "icon": "⚡", "completed": 5, "percentage": 55.5, "color": "#00d4ff"}
        ],
        "combat": {
            "beasts_neutralized": [{"name": "Syntax Wyrm", "category": "Bug", "difficulty": "Elite", "xp_awarded": 350}]
        },
        "progression": {
            "achievements_unlocked": [{"code": "TEST", "name": "Iron Discipline", "description": "100% Day", "icon": "🛡️"}]
        },
        "squad_mvp": {"name": "Lyra", "role": "Navigator", "deployments": 5}
    }
    
    out_file = tmp_path / "holocron_export.html"
    html = export_standalone_html(payload, str(out_file))
    
    assert out_file.exists()
    assert "<!DOCTYPE html>" in html
    assert "Weekly Holocron // 2026-W40" in html
    assert "Syntax Wyrm" in html
    assert "Iron Discipline" in html
    assert "Lyra" in html
    assert "90.0%" in html


def test_startup_holocron_catchup(tmp_path):
    """Verify startup catchup synthesizes missing previous week Holocron."""
    from services.sync_engine import check_startup_holocron_catchup
    
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    
    # Run catchup when file does not exist
    msg = check_startup_holocron_catchup(str(vault))
    prev_week = get_previous_iso_week()
    assert "Synthesized missing Holocron" in msg or "up to date" in msg
    
    expected_file = vault / "Bridge" / "Holocron" / "Weekly" / f"{prev_week}.json"
    assert expected_file.exists()
    
    # Running again detects it's already up to date
    msg2 = check_startup_holocron_catchup(str(vault))
    assert "up to date" in msg2


def test_wtd_in_flight_telemetry(tmp_path):
    """Verify in-flight Week-to-Date telemetry assigns day statuses and elapsed metrics."""
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    current_week = get_current_iso_week()

    payload = build_weekly_holocron(str(vault), week_id=current_week, force=True)
    assert payload["week_id"] == current_week
    assert payload["is_in_flight"] is True
    assert payload["cycle_status"] == "in_flight"
    assert payload["summary"]["is_in_flight"] is True
    assert 1 <= payload["summary"]["days_elapsed"] <= 7
    assert 0 <= payload["summary"]["days_remaining"] <= 6

    # Verify daily telemetry day statuses
    statuses = [d["day_status"] for d in payload["daily_telemetry"]]
    assert len(statuses) == 7
    assert "active" in statuses or "concluded" in statuses


def test_synthesize_ollama_debrief_fallback(monkeypatch):
    """Verify Ollama debrief falls back gracefully to rule-based debrief when provider is offline."""
    from services.holocron_engine import synthesize_ollama_debrief
    from services import ai_provider
    import asyncio

    class OfflineOllama:
        async def check(self):
            return False

    monkeypatch.setattr(ai_provider, "OllamaProvider", OfflineOllama)

    payload = {
        "week_id": "2026-W40",
        "is_in_flight": True,
        "tactical_debrief": "Deterministic rule-based debrief fallback.",
        "summary": {
            "precision_rate": 88.0,
            "completed_tasks": 12,
            "total_tasks": 14,
            "total_xp_gained": 2400,
            "current_level": 42,
            "threats_neutralized": 1,
            "days_elapsed": 5
        },
        "sector_distribution": [
            {"name": "High-Velocity Front", "completed": 8}
        ],
        "combat": {"beasts_neutralized": [{"name": "Syntax Wyrm"}]},
        "squad_mvp": {"name": "Lyra", "deployments": 5}
    }

    debrief, source = asyncio.run(synthesize_ollama_debrief(payload))
    assert debrief == "Deterministic rule-based debrief fallback."
    assert source == "rule_based_fallback"


def test_synthesize_ollama_debrief_success(monkeypatch):
    """Verify Ollama debrief returns AI text when Ollama is available."""
    from services.holocron_engine import synthesize_ollama_debrief
    from services import ai_provider
    import asyncio

    class MockOllama:
        async def check(self):
            return True
        async def generate(self, prompt, system=None, feature="holocron"):
            return "Exceptional kinetic momentum maintained throughout Cycle 2026-W40. Defenses remain impenetrable."

    monkeypatch.setattr(ai_provider, "OllamaProvider", MockOllama)

    payload = {
        "week_id": "2026-W40",
        "is_in_flight": False,
        "tactical_debrief": "Rule-based text.",
        "summary": {
            "precision_rate": 95.0,
            "completed_tasks": 20,
            "total_tasks": 21,
            "total_xp_gained": 5000,
            "current_level": 43,
            "threats_neutralized": 2
        }
    }

    debrief, source = asyncio.run(synthesize_ollama_debrief(payload))
    assert "Exceptional kinetic momentum" in debrief
    assert source == "ollama"


def test_clean_debrief_output_edge_cases():
    """Verify clean_debrief_output sanitizes JSON code blocks, markdown headers, and quotation marks."""
    from services.holocron_engine import clean_debrief_output

    # 1. Markdown code block with JSON payload
    raw_json_block = "```json\n{\n  \"debrief\": \"Sovereign focus held unwavering across the High-Velocity Front.\"\n}\n```"
    assert clean_debrief_output(raw_json_block) == "Sovereign focus held unwavering across the High-Velocity Front."

    # 2. Markdown headers and quotation marks
    raw_headers = "### Tactical Debrief\n\n\"The Sovereign demonstrated exemplary precision throughout the campaign.\""
    cleaned_headers = clean_debrief_output(raw_headers)
    assert "###" not in cleaned_headers
    assert '"' not in cleaned_headers
    assert cleaned_headers == "The Sovereign demonstrated exemplary precision throughout the campaign."

    # 3. Unadorned code fence with bold tags
    raw_fenced = "```\n**Operational Focus:** Momentum remained resolute with zero breaches.\n```"
    cleaned_fenced = clean_debrief_output(raw_fenced)
    assert "```" not in cleaned_fenced
    assert "**" not in cleaned_fenced
    assert cleaned_fenced == "Operational Focus: Momentum remained resolute with zero breaches."

    # 4. Raw JSON object string
    raw_obj = '{"response": "Tactical discipline maintained at peak telemetry."}'
    assert clean_debrief_output(raw_obj) == "Tactical discipline maintained at peak telemetry."


def test_synthesize_ollama_debrief_malformed_output(monkeypatch):
    """Verify synthesize_ollama_debrief properly cleans malformed Ollama outputs."""
    from services.holocron_engine import synthesize_ollama_debrief
    from services import ai_provider
    import asyncio

    malformed_responses = [
        "```json\n{\"debrief\": \"The Sovereign executed all mandates with surgical precision.\"}\n```",
        "## Tactical Summary\n\n\"Martial momentum secured 100% operational clearance.\"",
        "```\n**Tactical Debrief:** All sectors held steady against external threats.\n```",
    ]

    for raw in malformed_responses:
        class MockOllama:
            async def check(self):
                return True
            async def generate(self, prompt, system=None, feature="holocron"):
                return raw

        monkeypatch.setattr(ai_provider, "OllamaProvider", MockOllama)

        payload = {
            "week_id": "2026-W40",
            "is_in_flight": False,
            "tactical_debrief": "Rule-based text.",
            "summary": {"precision_rate": 95.0, "completed_tasks": 20, "total_tasks": 20}
        }

        debrief, source = asyncio.run(synthesize_ollama_debrief(payload))
        assert source == "ollama"
        assert "```" not in debrief
        assert "#" not in debrief
        assert '"' not in debrief
        assert len(debrief) > 20



def test_api_current_and_ai_debrief(monkeypatch, tmp_path):
    """Verify GET /api/holocron/weekly/current and POST debrief/ai endpoints."""
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    monkeypatch.setattr("main.NAVIS_ROOT", str(vault))

    from services import ai_provider

    class OfflineOllama:
        async def check(self):
            return False

    monkeypatch.setattr(ai_provider, "OllamaProvider", OfflineOllama)

    client = TestClient(app)

    # 1. Test /api/holocron/weekly/current
    res = client.get("/api/holocron/weekly/current")
    assert res.status_code == 200
    data = res.json()
    assert data["is_in_flight"] is True
    assert data["summary"]["is_in_flight"] is True

    # 2. Test /api/holocron/weekly/{week_id}/debrief/ai
    week_id = data["week_id"]
    res_ai = client.post(f"/api/holocron/weekly/{week_id}/debrief/ai")
    assert res_ai.status_code == 200
    ai_data = res_ai.json()
    assert ai_data["week_id"] == week_id
    assert "tactical_debrief" in ai_data
    assert ai_data["debrief_source"] == "rule_based_fallback"


def test_native_holocron_adapter(monkeypatch, tmp_path):
    """Verify native_holocron adapter dispatches correctly for desktop app."""
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    monkeypatch.setenv("NAVIS_ROOT", str(vault))

    import native_holocron
    monkeypatch.setattr(native_holocron, "NAVIS_ROOT", str(vault))

    # Manifest
    manifest = native_holocron.dispatch("/api/holocron/weekly/manifest")
    assert isinstance(manifest, list)

    # Current
    current = native_holocron.dispatch("/api/holocron/weekly/current")
    assert current["is_in_flight"] is True
    week_id = current["week_id"]

    # Specific week
    specific = native_holocron.dispatch(f"/api/holocron/weekly/{week_id}")
    assert specific["week_id"] == week_id

    # HTML
    html_res = native_holocron.dispatch(f"/api/holocron/weekly/{week_id}/html")
    assert "html" in html_res
    assert "<!DOCTYPE html>" in html_res["html"]


def test_year_boundary_iso_week():
    """Verify ISO week calculation across calendar year transitions."""
    start_date, end_date, dates = get_week_date_range("2025-W52")
    assert start_date == "2025-12-22"
    assert end_date == "2025-12-28"
    assert len(dates) == 7

    start_date_w1, end_date_w1, dates_w1 = get_week_date_range("2026-W01")
    assert start_date_w1 == "2025-12-29"
    assert end_date_w1 == "2026-01-04"
    assert len(dates_w1) == 7


def test_corrupted_manifest_recovery(tmp_path):
    """Verify corrupted weekly_manifest.json degrades gracefully without unhandled exceptions."""
    vault = tmp_path / "Navis-Vault"
    manifest_dir = vault / "Bridge" / "Holocron"
    manifest_dir.mkdir(parents=True)
    corrupted_file = manifest_dir / "weekly_manifest.json"
    corrupted_file.write_text("{broken json syntax: [", encoding="utf-8")

    manifest = get_holocron_manifest(str(vault))
    assert isinstance(manifest, list)
    assert len(manifest) >= 1
    assert manifest[0]["is_in_flight"] is True


def test_empty_journal_and_missing_sections(tmp_path):
    """Verify daily journal parsing handles empty files, notes without tasks, and non-task bullets."""
    jfile = tmp_path / "2026-10-02.md"
    jfile.write_text(
        "# 2026-10-02\n\n"
        "Just arbitrary notes without checkboxes.\n"
        "- Bullet note 1\n"
        "- Bullet note 2\n",
        encoding="utf-8-sig"
    )

    result = parse_daily_journal(str(jfile), "2026-10-02")
    assert result["date"] == "2026-10-02"
    assert result["completed"] == 0
    assert result["total"] == 0
    assert result["precision"] == 0.0
    assert result["realm"] is None
    assert result["prime_beast"] is None


def test_native_holocron_cli_piping(tmp_path):
    """Verify native_holocron.py executes over stdio JSON protocol."""
    import subprocess
    import sys

    vault = tmp_path / "Navis-Vault"
    vault.mkdir()

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(backend_dir, "native_holocron.py")

    env = dict(os.environ)
    env["NAVIS_ROOT"] = str(vault)
    env["PYTHONIOENCODING"] = "utf-8"

    # Test valid dispatch
    req = json.dumps({"path": "/api/holocron/weekly/manifest", "method": "GET"}).encode("utf-8")
    proc = subprocess.run(
        [sys.executable, script_path],
        input=req,
        capture_output=True,
        cwd=backend_dir,
        env=env,
        check=True
    )
    res = json.loads(proc.stdout.decode("utf-8"))
    assert res["status"] == 200
    assert isinstance(res["body"], list)

    # Test unsupported path returns 400
    bad_req = json.dumps({"path": "/api/unknown/path", "method": "GET"}).encode("utf-8")
    proc_bad = subprocess.run(
        [sys.executable, script_path],
        input=bad_req,
        capture_output=True,
        cwd=backend_dir,
        env=env,
        check=True
    )
    res_bad = json.loads(proc_bad.stdout.decode("utf-8"))
    assert res_bad["status"] == 400
    assert "Unsupported Holocron path" in res_bad["body"]["detail"]

