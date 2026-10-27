import json
import math
import sqlite3

import pytest

from services import combat_service, progression_db as db, rpg_engine, talent_service
from services.holocron_engine import (
    build_weekly_holocron,
    export_standalone_html,
    query_progression_telemetry,
)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "Keeper" / "navis_progression.db"))
    monkeypatch.setattr(rpg_engine, "NAVIS_ROOT", str(tmp_path))
    (tmp_path / "Bridge").mkdir(parents=True)
    (tmp_path / "Keeper").mkdir(parents=True)
    (tmp_path / "Journal" / "2026" / "10").mkdir(parents=True)
    (tmp_path / "Bridge" / "CompanionStats.json").write_text(
        json.dumps({"companions": {"Keeper": {"xp": 0, "level": 1}}}), encoding="utf-8"
    )
    (tmp_path / "Bridge" / "status.json").write_text(
        json.dumps({
            "last_updated": "2026-10-03",
            "current_realm": "The Silicon Spires",
            "squad": [{"name": "Keeper"}],
        }),
        encoding="utf-8-sig",
    )
    db.init_db()
    return tmp_path


def manual_award(award_id="xp-award-1", amount=5000, **overrides):
    event = {
        "award_id": award_id,
        "entity_id": "keeper",
        "amount": amount,
        "source_type": "manual_adjustment",
        "source_ref": f"manual/{award_id}",
        "source_event_at": "2026-10-01T12:00:00-05:00",
        "local_date": "2026-10-01",
        "rule_version": "xp-v1",
        "provenance": {"actor": "Keeper", "interface": "test"},
        "reason": "Test level up",
        "details": "Test level up",
    }
    event.update(overrides)
    return event


# ---------------------------------------------------------------------------
# 1. Perk Multiplier Stacking & Boundary Capping
# ---------------------------------------------------------------------------


def test_perk_multiplier_stacking_and_boundary_capping():
    """Verify rank scaling, additive stacking, and boundary caps for XP multipliers."""
    # Rank scaling
    assert talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 1) == 0.10
    assert talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 2) == 0.20
    assert talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 3) == 0.30

    # Additive stacking with additional bonuses
    stacked = talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 2, additional_bonus=0.15)
    assert math.isclose(stacked, 0.35)

    # Boundary capping: cannot exceed max_multiplier (0.50 / 50%)
    capped = talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 10)
    assert capped == 0.50

    stacked_over_cap = talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 3, additional_bonus=0.40)
    assert stacked_over_cap == 0.50

    # Boundary capping: non-negative floor
    assert talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", 0) == 0.0
    assert talent_service.calculate_perk_multiplier("high_velocity_xp_bonus", -1) == 0.0
    assert talent_service.calculate_perk_multiplier("unknown_perk", 2) == 0.0


def test_combat_perk_modifiers_stacking_and_boundary_capping():
    """Verify combat shield boost stacking and debuff reduction caps."""
    # Empty perks -> zero modifiers
    mods_empty = talent_service.calculate_combat_perk_modifiers({})
    assert mods_empty["shield_percent_bonus"] == 0
    assert mods_empty["debuff_reduction"] == 0
    assert mods_empty["combat_xp_bonus"] == 0.0

    # Reduced rollover penalty (rank 2: +20% shield, -2 debuff)
    # Focus stamina boost (rank 2: +20% shield)
    # Stacking shields: 20% + 20% = 40% shield bonus
    active = {
        "reduced_rollover_penalty": 2,
        "focus_stamina_boost": 2,
        "high_velocity_xp_bonus": 3,
    }
    mods = talent_service.calculate_combat_perk_modifiers(active)
    assert mods["shield_percent_bonus"] == 40
    assert mods["debuff_reduction"] == 2
    assert math.isclose(mods["combat_xp_bonus"], 0.30)

    # Boundary capping on extreme ranks
    extreme = {
        "reduced_rollover_penalty": 10,
        "focus_stamina_boost": 10,
        "high_velocity_xp_bonus": 10,
    }
    mods_extreme = talent_service.calculate_combat_perk_modifiers(extreme)
    # Capped at 50% max shield boost from talents
    assert mods_extreme["shield_percent_bonus"] == 50
    # Capped at 5 max debuff reduction
    assert mods_extreme["debuff_reduction"] == 5
    # Capped at 0.50 max combat xp bonus
    assert mods_extreme["combat_xp_bonus"] == 0.50


# ---------------------------------------------------------------------------
# 2. Dynamic Active Perk Evaluation & Distinct Reason Attribution
# ---------------------------------------------------------------------------


def test_get_active_perks_retrieval(vault):
    """Verify active perk dictionary extraction from database."""
    # Initially no perks allocated
    assert talent_service.get_active_perks("keeper") == {}

    # Level up to gain points
    db.record_award(manual_award(amount=10000))
    state = talent_service.get_talent_state("keeper")
    assert state["available_points"] >= 4

    # Allocate martial_momentum (rank 2) and focus_deep_work (rank 1)
    talent_service.allocate_talent("keeper", "martial_momentum", rank=2)
    talent_service.allocate_talent("keeper", "focus_deep_work", rank=1)

    active = talent_service.get_active_perks("keeper")
    assert active == {
        "high_velocity_xp_bonus": 2,
        "focus_deep_work_multiplier": 1,
    }


def test_task_completion_perk_bonus_and_distinct_reason(vault):
    """Verify task completion evaluates active perks and writes distinct awards with talent_perk:<perk_key>."""
    # Level up and allocate perks:
    # martial_momentum rank 2 (+20% on HIGH_VELOCITY_FRONT)
    # kinetic_vitality rank 1 (+10% on KINETIC_OUTLAND)
    db.record_award(manual_award())
    talent_service.allocate_talent("keeper", "martial_momentum", rank=2)
    talent_service.allocate_talent("keeper", "kinetic_vitality", rank=1)

    # Write a daily journal with tasks in different manors
    # 5 tasks in High-Velocity Front (base XP = 10 -> +20% = +2 bonus XP)
    # 5 tasks in Kinetic Outland (base XP = 10 -> +10% = +1 bonus XP)
    # 2 tasks in The Sanctum (0 rank allocated -> 0 bonus XP)
    journal_path = vault / "Journal" / "2026" / "10" / "2026-10-03.md"
    journal_path.write_text(
        "# 2026-10-03\n"
        "## The High-Velocity Front\n"
        "- [x] Mandate A1\n"
        "- [x] Mandate A2\n"
        "- [x] Mandate A3\n"
        "- [x] Mandate A4\n"
        "- [x] Mandate A5\n\n"
        "## The Kinetic Outland\n"
        "- [x] Expedition B1\n"
        "- [x] Expedition B2\n"
        "- [x] Expedition B3\n"
        "- [x] Expedition B4\n"
        "- [x] Expedition B5\n\n"
        "## The Sanctum\n"
        "- [x] Sanctuary C1\n"
        "- [x] Sanctuary C2\n",
        encoding="utf-8-sig",
    )

    result = rpg_engine.calculate_and_apply_xp(date_override="2026-10-03", root=str(vault))
    assert result["status"] == "success"
    assert "high_velocity_xp_bonus" in result["talent_perks_awarded"]
    assert "kinetic_stamina_efficiency" in result["talent_perks_awarded"]

    # Verify distinct ledger entries and attributed reasons
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT award_id, entity_id, amount, source_type, reason, details FROM xp_ledger WHERE source_type='talent_perk' ORDER BY reason"
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    perk_reasons = {r["reason"]: r["amount"] for r in rows}

    # Distinct reason: talent_perk:<perk_key>
    assert "talent_perk:high_velocity_xp_bonus" in perk_reasons
    assert perk_reasons["talent_perk:high_velocity_xp_bonus"] == 2

    assert "talent_perk:kinetic_stamina_efficiency" in perk_reasons
    assert perk_reasons["talent_perk:kinetic_stamina_efficiency"] == 1

    # Idempotent re-run does not double-award
    keeper_total_before = db.get_entity_total("keeper")
    rpg_engine.calculate_and_apply_xp(date_override="2026-10-03", root=str(vault))
    assert db.get_entity_total("keeper") == keeper_total_before


# ---------------------------------------------------------------------------
# 3. Combat Modifiers: Shield Boost & Penalty Streak Mitigation
# ---------------------------------------------------------------------------


def test_combat_shield_boost_and_stacking():
    """Verify combat round applies stacked shield bonus from active talent perks."""
    encounter = {
        "turn": 1,
        "player_hp": 100,
        "debuff": 0,
        "enemies": [{"id": "Wyrm", "hp": 50, "attack": 20, "intent_pattern": ["Strike"]}],
        "synergies": [{"name": "Kaelen", "passives": {"shield_percent": 20}}],
        # Talent perks: 2 ranks in reduced_rollover_penalty (+20% shield)
        # Total shield percent = 20% (companion) + 20% (talent) = 40%
        "talent_perks": {"reduced_rollover_penalty": 2},
    }
    # Play card with base shield 10
    # Shield = 10 * (100 + 40) // 100 = 14
    # Enemy attacks with 20. Blocked: 14. Damage taken: 20 - 14 = 6. Player HP: 100 - 6 = 94.
    cards = [{"id": "defend", "element": "Physical", "ap_cost": 1, "attack": 0, "shield": 10}]
    res = combat_service.evaluate_round(encounter, cards)
    assert res["shield_absorbed"] == 14
    assert res["player_damage"] == 6
    assert res["encounter"]["player_hp"] == 94
    assert res["talent_modifiers"]["shield_percent_bonus"] == 20


def test_combat_debuff_reduction_and_penalty_mitigation():
    """Verify talent perk mitigates friction, reduces attack debuff penalty, and counters debuff streaks."""
    encounter = {
        "turn": 1,
        "player_hp": 100,
        # Enemy previously inflicted debuff = 3
        "debuff": 3,
        "enemies": [{"id": "Phantom", "hp": 20, "attack": 0, "intent_pattern": ["Debuff"]}],
        "synergies": [],
        # 2 ranks in reduced_rollover_penalty -> debuff_reduction = 2
        "talent_perks": {"reduced_rollover_penalty": 2},
    }
    # Base attack = 10.
    # Effective debuff = max(0, 3 - 2) = 1.
    # Attack dealt = 10 - 1 = 9.
    cards = [{"id": "strike", "element": "Physical", "ap_cost": 1, "attack": 10, "shield": 0}]
    res = combat_service.evaluate_round(encounter, cards)
    assert res["attack"] == 9
    assert res["encounter"]["enemies"][0]["hp"] == 11
    # Next turn debuff: enemy casts Debuff (+1). Total raw debuff = 1.
    # Mitigated by talent perk debuff reduction: max(0, 1 - 2) = 0!
    assert res["encounter"]["debuff"] == 0


def test_combat_bonus_event_distinct_talent_award(vault):
    """Verify combat operation talent bonus event produces distinct award with reason talent_perk:<perk_key>."""
    tactical = {
        "xp_multiplier": 2.0,
        "critical_hits": [{"enemy_id": "Wyrm", "card_id": "c1", "element": "Digital", "multiplier": 2.0, "damage": 5}],
        "talent_perks": {"high_velocity_xp_bonus": 2},
    }
    source = {"path": "Journal/2026/10/2026-10-03.md"}
    resolution_id = "res-test-99"

    events = rpg_engine.combat_talent_bonus_events(resolution_id, source, tactical, root=str(vault))
    assert len(events) == 1
    event = events[0]
    assert event["source_type"] == "talent_perk"
    assert event["reason"] == "talent_perk:high_velocity_xp_bonus"
    assert event["amount"] >= 1
    assert event["provenance"]["perk_key"] == "high_velocity_xp_bonus"
    assert event["provenance"]["rank"] == 2

    # Recording the award succeeds
    res = db.record_award(event)
    assert res["created"] is True


# ---------------------------------------------------------------------------
# 4. Weekly Holocron Telemetry & Debrief Highlighting
# ---------------------------------------------------------------------------


def test_weekly_holocron_highlights_talent_contributions(tmp_path):
    """Verify Weekly Holocron telemetry queries, highlights, and synthesizes talent contributions."""
    vault = tmp_path / "Navis-Vault"
    vault.mkdir()
    kdir = vault / "Keeper"
    kdir.mkdir()
    db_path = kdir / "navis_progression.db"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE xp_ledger (
            entity_id TEXT NOT NULL, award_id TEXT PRIMARY KEY, local_date TEXT NOT NULL,
            source_type TEXT NOT NULL, amount INTEGER NOT NULL,
            reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE achievements (
            code TEXT PRIMARY KEY, name TEXT NOT NULL,
            description TEXT, date_achieved TEXT NOT NULL
        )
    """)
    # Add regular tasks, combat, and talent perk awards
    conn.execute("INSERT INTO xp_ledger VALUES ('keeper', 'AW-1', '2026-09-28', 'task', 100, 'daily_tasks')")
    conn.execute("INSERT INTO xp_ledger VALUES ('keeper', 'AW-2', '2026-09-29', 'combat_critical', 50, 'critical')")
    conn.execute("INSERT INTO xp_ledger VALUES ('keeper', 'AW-3', '2026-09-30', 'talent_perk', 25, 'talent_perk:high_velocity_xp_bonus')")
    conn.execute("INSERT INTO xp_ledger VALUES ('keeper', 'AW-4', '2026-10-01', 'talent_perk', 15, 'talent_perk:daily_outland_surge')")
    conn.commit()
    conn.close()

    # Query telemetry directly
    telemetry = query_progression_telemetry(str(vault), "2026-09-28", "2026-10-04")
    assert telemetry["total_xp"] == 190
    assert telemetry["xp_breakdown"]["tasks"] == 100
    assert telemetry["xp_breakdown"]["combat"] == 50
    assert telemetry["xp_breakdown"]["talents"] == 40
    assert telemetry["talent_telemetry"]["total_bonus_xp"] == 40
    assert len(telemetry["talent_telemetry"]["perks"]) == 2

    # Build weekly holocron payload
    payload = build_weekly_holocron(vault_root=str(vault), week_id="2026-W40", force=True)
    assert payload["summary"]["talent_bonus_xp"] == 40
    assert payload["progression"]["talent_telemetry"]["total_bonus_xp"] == 40
    assert payload["progression"]["xp_breakdown"]["talents"] == 40

    # Verify tactical debrief highlights talent contributions
    assert "Recorded talent-perk contribution: 40 XP" in payload["tactical_debrief"]

    # Verify standalone HTML dashboard contains constellation yields chip
    html = export_standalone_html(payload)
    assert "Constellation Yields (+40 XP)" in html
    assert "high_velocity_xp_bonus" in html
