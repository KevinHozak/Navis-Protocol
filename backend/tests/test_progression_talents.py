import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app
from services import progression_db as db
from services import talent_service


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "Keeper" / "navis_progression.db"))
    (tmp_path / "Bridge").mkdir(parents=True)
    (tmp_path / "Keeper").mkdir(parents=True)
    (tmp_path / "Bridge" / "CompanionStats.json").write_text(
        json.dumps({"companions": {"Keeper": {"xp": 0, "level": 1}}}), encoding="utf-8"
    )
    db.init_db()
    return tmp_path


def manual_award(award_id="xp-award-1", amount=1000, **overrides):
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


def test_schema_defines_talent_tables_and_seed_nodes(vault):
    conn = db.get_connection()
    # Check talent_nodes schema
    node_columns = {row["name"] for row in conn.execute("PRAGMA table_info(talent_nodes)").fetchall()}
    for col in ("id", "branch", "tier", "prerequisites", "max_rank", "perk_key", "name", "description"):
        assert col in node_columns

    # Check talent_allocations schema
    alloc_columns = {row["name"] for row in conn.execute("PRAGMA table_info(talent_allocations)").fetchall()}
    for col in ("entity_id", "node_id", "rank", "allocated_at"):
        assert col in alloc_columns

    # Check default starter constellation nodes
    nodes = conn.execute("SELECT * FROM talent_nodes ORDER BY branch, tier, id").fetchall()
    assert len(nodes) >= 8
    branches = {n["branch"] for n in nodes}
    assert {"Focus", "Martial", "Kinetic", "Lore"}.issubset(branches)

    # Check idempotent re-init
    db.init_db(conn)
    nodes_after = conn.execute("SELECT COUNT(*) FROM talent_nodes").fetchone()[0]
    assert nodes_after == len(nodes)
    conn.close()


def test_calculate_available_points_formula():
    # available talent points = current_level - total_allocated_ranks
    assert talent_service.calculate_available_points(1, 0) == 1
    assert talent_service.calculate_available_points(1, 1) == 0
    assert talent_service.calculate_available_points(5, 2) == 3
    assert talent_service.calculate_available_points(2, 3) == 0  # clamped to 0


def test_initial_talent_state_and_prerequisites(vault):
    state = talent_service.get_talent_state("keeper")
    assert state["entity_id"] == "keeper"
    assert state["current_level"] == 1
    assert state["level"] == 1
    assert state["total_xp"] == 0
    assert state["total_allocated_ranks"] == 0
    assert state["available_points"] == 1
    assert state["allocations"] == []

    nodes_by_id = {n["id"]: n for n in state["nodes"]}
    assert nodes_by_id["focus_deep_work"]["unlocked"] is True
    assert nodes_by_id["focus_deep_work"]["current_rank"] == 0
    assert nodes_by_id["focus_clarity"]["unlocked"] is False


def test_prerequisite_check_blocks_locked_nodes(vault):
    # focus_clarity requires focus_deep_work
    with pytest.raises(db.ProgressionValidationError, match="Prerequisite node 'focus_deep_work' is not unlocked"):
        talent_service.allocate_talent(entity_id="keeper", node_id="focus_clarity", rank=1)


def test_atomic_allocation_and_point_limits(vault):
    # Allocate tier 1 node
    res = talent_service.allocate_talent(entity_id="keeper", node_id="focus_deep_work", rank=1)
    assert res["status"] == "success"
    assert res["node_id"] == "focus_deep_work"
    assert res["allocated_rank"] == 1
    assert res["ranks_added"] == 1
    assert res["available_points"] == 0
    assert res["total_allocated_ranks"] == 1

    # Idempotent retry with same rank
    retry = talent_service.allocate_talent(entity_id="keeper", node_id="focus_deep_work", rank=1)
    assert retry["status"] == "success"
    assert retry["allocated_rank"] == 1
    assert retry["ranks_added"] == 0
    assert retry["available_points"] == 0

    # Point limit: 0 available points left, attempting another allocation fails
    with pytest.raises(db.ProgressionValidationError, match="Insufficient talent points"):
        talent_service.allocate_talent(entity_id="keeper", node_id="martial_momentum", rank=1)


def test_level_progression_unlocks_further_allocations(vault):
    # Allocate rank 1 in focus_deep_work
    talent_service.allocate_talent(entity_id="keeper", node_id="focus_deep_work", rank=1)

    # Award XP to reach level 2 (needs 1000 XP)
    db.record_award(manual_award("lvl-2", 1000), project=False)
    state = talent_service.get_talent_state("keeper")
    assert state["current_level"] == 2
    assert state["total_allocated_ranks"] == 1
    assert state["available_points"] == 1

    # Prerequisite focus_deep_work is met and 1 point is available -> focus_clarity succeeds!
    res = talent_service.allocate_talent(entity_id="keeper", node_id="focus_clarity", rank=1)
    assert res["status"] == "success"
    assert res["allocated_rank"] == 1
    assert res["available_points"] == 0
    assert res["total_allocated_ranks"] == 2


def test_max_rank_and_decrease_constraints(vault):
    # Give Keeper plenty of XP for Level 10
    db.record_award(manual_award("lvl-10", 50000), project=False)

    # focus_clarity max_rank is 2
    talent_service.allocate_talent(entity_id="keeper", node_id="focus_deep_work", rank=1)
    talent_service.allocate_talent(entity_id="keeper", node_id="focus_clarity", rank=2)

    with pytest.raises(db.ProgressionValidationError, match="exceeds max rank"):
        talent_service.allocate_talent(entity_id="keeper", node_id="focus_clarity", rank=3)

    with pytest.raises(db.ProgressionValidationError, match="Cannot decrease talent rank"):
        talent_service.allocate_talent(entity_id="keeper", node_id="focus_clarity", rank=1)


def test_entity_validation_and_companion_support(vault):
    with pytest.raises(db.ProgressionValidationError, match="entity_id must be keeper or companion:<stable-name>"):
        talent_service.get_talent_state("invalid_entity")

    with pytest.raises(db.ProgressionValidationError, match="entity_id must be keeper or companion:<stable-name>"):
        talent_service.allocate_talent(entity_id="stranger", node_id="focus_deep_work", rank=1)

    # Companion entity works and is isolated
    comp_state = talent_service.get_talent_state("companion:Ava")
    assert comp_state["entity_id"] == "companion:Ava"
    assert comp_state["total_allocated_ranks"] == 0
    assert comp_state["available_points"] == 1


def test_fastapi_talent_endpoints(vault):
    client = TestClient(app)

    # GET /api/v1/progression/talents/nodes
    nodes_res = client.get("/api/v1/progression/talents/nodes")
    assert nodes_res.status_code == 200
    nodes = nodes_res.json()
    assert len(nodes) >= 8

    # GET /api/v1/progression/talents
    state_res = client.get("/api/v1/progression/talents?entity_id=keeper")
    assert state_res.status_code == 200
    state = state_res.json()
    assert state["entity_id"] == "keeper"
    assert state["available_points"] == 1

    # POST /api/v1/progression/talents/allocate (prerequisite failure)
    prereq_res = client.post(
        "/api/v1/progression/talents/allocate",
        json={"entity_id": "keeper", "node_id": "focus_clarity", "rank": 1},
    )
    assert prereq_res.status_code == 422
    assert "Prerequisite" in prereq_res.json()["detail"]

    # POST /api/v1/progression/talents/allocate (success)
    alloc_res = client.post(
        "/api/v1/progression/talents/allocate",
        json={"entity_id": "keeper", "node_id": "focus_deep_work", "rank": 1},
    )
    assert alloc_res.status_code == 200
    alloc_data = alloc_res.json()
    assert alloc_data["status"] == "success"
    assert alloc_data["allocated_rank"] == 1
    assert alloc_data["available_points"] == 0
    assert alloc_data["total_allocated_ranks"] == 1

    # POST /api/v1/progression/talents/allocate (insufficient points)
    point_res = client.post(
        "/api/v1/progression/talents/allocate",
        json={"entity_id": "keeper", "node_id": "martial_momentum", "rank": 1},
    )
    assert point_res.status_code == 422
    assert "Insufficient talent points" in point_res.json()["detail"]
