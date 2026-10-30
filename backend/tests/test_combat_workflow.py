"""P3 workflow evidence: synthetic Vaults, HTTP routes and process restarts."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from services import task_time

from test_combat_completion import (
    link, state, assert_contract, subprocess_call,
    battle_engine, combat_completion, rpg_engine, progression_db,
)
# Explicit re-exports register these pytest fixtures without looking like unused imports.
from test_combat_completion import vault as _vault_fixture, call as _call_fixture

vault = _vault_fixture
call = _call_fixture


pytest_plugins = ["test_combat_completion"]


@pytest.mark.parametrize("failing_save", [2, 3, 4, 5])
def test_restart_finishes_each_durable_checkpoint(vault, call, monkeypatch, failing_save):
    command = link(call)
    original = battle_engine.BattleEngine.save_state
    saves = 0
    def fail_once(engine):
        nonlocal saves
        saves += 1
        if saves == failing_save:
            raise OSError("Synthetic interrupted battle commit")
        original(engine)
    monkeypatch.setattr(battle_engine.BattleEngine, "save_state", fail_once)
    pending = call("/api/battle/resolve", command)
    assert_contract(pending, "task_written_battle_pending" if failing_save < 4 else "battle_committed_xp_pending")
    before = (vault / command["source"]["path"]).read_bytes()
    # A new Python process reloads only disk state, independent of monkeypatches.
    assert_contract(subprocess_call(vault, "/api/battle/resolve", command), "completed")
    assert_contract(subprocess_call(vault, "/api/battle/resolve", command), "same_key_retry")
    assert (vault / command["source"]["path"]).read_bytes() == before
    assert state(vault)["active_links"] == {}
    assert state(vault)["discard"] == ["a"]
    assert state(vault)["lost"] == ["b"]
    assert progression_db.get_entity_total("keeper") == 12
    assert len(progression_db.get_xp_history(entity_id="keeper")) == 1


@pytest.mark.parametrize("after_award", [False, True])
def test_xp_failure_restart_keeps_original_cohort_and_single_award(vault, call, monkeypatch, after_award):
    status_path = vault / "Bridge/status.json"
    status = json.loads(status_path.read_text())
    status["squad"] = [{"name": "SyntheticScout"}]
    status_path.write_text(json.dumps(status))
    stats_path = vault / "Bridge/CompanionStats.json"
    stats = json.loads(stats_path.read_text())
    stats["companions"]["SyntheticScout"] = {"xp": 0, "level": 1}
    stats_path.write_text(json.dumps(stats))
    command = link(call)
    sync = rpg_engine.calculate_and_apply_xp
    def interrupted(**kwargs):
        if after_award:
            sync(**kwargs)
        raise OSError("Synthetic XP interruption")
    monkeypatch.setattr(rpg_engine, "calculate_and_apply_xp", interrupted)
    assert_contract(call("/api/battle/resolve", command), "battle_committed_xp_pending")
    assert progression_db.get_entity_total("keeper") == (12 if after_award else 0)
    if after_award:
        status["squad"] = [{"name": "LaterScout"}]
        status_path.write_text(json.dumps(status))
    assert_contract(subprocess_call(vault, "/api/battle/resolve", command), "completed")
    assert_contract(subprocess_call(vault, "/api/battle/resolve", command), "same_key_retry")
    assert progression_db.get_entity_total("keeper") == 12
    assert progression_db.get_entity_total("companion:SyntheticScout") == 12
    assert progression_db.get_entity_total("companion:LaterScout") == 0
    for entity in ("keeper", "companion:SyntheticScout"):
        assert len(progression_db.get_xp_history(entity_id=entity)) == 1


def test_duplicate_process_requests_are_serialized(vault):
    command = link(lambda path, body: subprocess_call(vault, path, body))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: subprocess_call(vault, "/api/battle/resolve", command), range(4)))
    assert all(result["status"] == "completed" for result in results)
    assert sum(bool(result.get("idempotent_replay")) for result in results) == 3
    assert state(vault)["discard"] == ["a"]
    assert state(vault)["lost"] == ["b"]
    assert progression_db.get_entity_total("keeper") == 12
    assert len(progression_db.get_xp_history(entity_id="keeper")) == 1


def test_journal_write_failure_can_recover_after_restart(vault, call, monkeypatch):
    command = link(call)
    journal = vault / command["source"]["path"]
    before = journal.read_bytes()
    atomic = combat_completion.atomic_bytes
    def fail_task(path, content):
        if path == journal:
            raise OSError("Synthetic task storage failure")
        atomic(path, content)
    monkeypatch.setattr(combat_completion, "atomic_bytes", fail_task)
    assert_contract(call("/api/battle/resolve", command), "task_written_battle_pending")
    assert journal.read_bytes() == before
    assert state(vault)["active_links"]
    assert not (vault / "Keeper/navis_progression.db").exists()
    assert_contract(subprocess_call(vault, "/api/battle/resolve", command), "completed")
    completed = journal.read_bytes()
    assert completed.startswith(b"\xef\xbb\xbf")
    assert task_time.strip(completed.decode("utf-8-sig")).encode("utf-8-sig") == before.replace(b"[ ]", b"[x]", 1)
    metadata = task_time.read(completed.decode("utf-8-sig"))
    assert task_time.valid_instant(metadata["completed_at"])
    assert metadata["history"] == []
    assert progression_db.get_entity_total("keeper") == 12


def test_second_task_uses_existing_daily_delta_rule(vault, call):
    first = link(call)
    assert_contract(call("/api/battle/resolve", first), "completed")
    journal = vault / first["source"]["path"]
    journal.write_bytes(journal.read_bytes() + b"- [ ] Calibrate antenna\r\n")
    (vault / "Battle/Cards.json").write_text(json.dumps({"cards": [{"id": "a"}, {"id": "b", "is_burn": True}, {"id": "c"}, {"id": "d"}]}))
    battle = state(vault)
    battle["hand"] = ["c", "d"]
    combat_completion.atomic_json(vault / "Battle/battle_state.json", battle)
    linked = call("/api/battle/link", {"task_id": "task-2", "top_card_id": "c", "bottom_card_id": "d",
        "source": {"path": first["source"]["path"], "target_text": "Calibrate antenna"}})
    second = {"task_id": "task-2", "resolution_id": linked["resolution_id"], "source": linked["source"]}
    assert_contract(call("/api/battle/resolve", second), "completed")
    assert_contract(call("/api/battle/resolve", second), "same_key_retry")
    assert progression_db.get_entity_total("keeper") == 14
    assert sorted(row["amount"] for row in progression_db.get_xp_history(entity_id="keeper")) == [2, 12]


def test_http_workflow_reads_journal_battle_and_ledger(vault, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))
    monkeypatch.setattr(battle_engine, "_engine_instance", None)
    client = TestClient(main.app)
    def http(path, body):
        response = client.post(path, json=body)
        assert response.status_code == 200, response.text
        return response.json()
    command = link(http)
    assert_contract(http("/api/battle/resolve", command), "completed")
    journal = client.get("/api/vault/" + command["source"]["path"])
    assert journal.status_code == 200
    assert "[x] Repair telescope" in journal.text
    battle = client.get("/api/battle/state")
    assert battle.status_code == 200
    assert battle.json()["active_links"] == {}
    xp = client.get("/api/v1/progression/xp?entity_id=keeper")
    assert xp.status_code == 200
    assert_contract(http("/api/battle/resolve", command), "same_key_retry")
    assert client.get("/api/v1/progression/xp?entity_id=keeper").json() == xp.json()
    assert progression_db.get_entity_total("keeper") == 12


def test_http_and_native_invalid_reference_status_parity(vault):
    from fastapi.testclient import TestClient
    import main
    import io
    import sys
    import native_combat
    from unittest.mock import patch
    client = TestClient(main.app)
    body = {"task_id": "missing", "resolution_id": "synthetic-missing"}
    http = client.post("/api/battle/resolve", json=body)
    output = io.StringIO()
    with patch.object(sys, "stdin", io.StringIO(json.dumps({"path": "/api/battle/resolve", "body": body}))), patch.object(sys, "stdout", output):
        native_combat.main()
    native = json.loads(output.getvalue())
    assert http.status_code == native["status"] == 400
    assert http.json() == native["body"]
    assert not state(vault).get("resolutions")
    assert not (vault / "Keeper/navis_progression.db").exists()


def test_combat_hand_reshuffle_card_draw_and_uniqueness(vault, call):
    """Verify card draw mechanics during short rest reshuffle, ensuring card IDs remain unique."""
    # Setup initial deck with cards in hand and discard
    card_ids = ["c1", "c2", "c3", "c4", "c5", "c6"]
    cards_data = {"cards": [{"id": cid, "name": f"Card {cid}"} for cid in card_ids]}
    (vault / "Battle/Cards.json").write_text(json.dumps(cards_data), encoding="utf-8-sig")

    battle_path = vault / "Battle/battle_state.json"
    initial_state = {
        "hand": ["c1", "c2"],
        "discard": ["c3", "c4", "c5", "c6"],
        "lost": [],
        "active_links": {},
        "resolutions": {},
    }
    combat_completion.atomic_json(battle_path, initial_state)

    # Trigger short rest via API
    rest_res = call("/api/battle/rest", {})
    assert rest_res["status"] == "success"
    assert "Rest Complete" in rest_res["message"]

    updated_state = state(vault)
    # Exactly one card must be lost
    assert len(updated_state["lost"]) == 1
    lost_card = updated_state["lost"][0]
    assert lost_card in ["c3", "c4", "c5", "c6"]

    # Discard pile must now be empty
    assert updated_state["discard"] == []

    # Hand must contain original hand cards plus remaining drawn cards
    assert len(updated_state["hand"]) == 5
    assert "c1" in updated_state["hand"]
    assert "c2" in updated_state["hand"]
    assert lost_card not in updated_state["hand"]

    # All card IDs in hand must be strictly unique
    assert len(updated_state["hand"]) == len(set(updated_state["hand"]))

    # Hand and lost must be completely disjoint
    assert set(updated_state["hand"]).isdisjoint(set(updated_state["lost"]))

    # Test short rest when discard is empty returns error
    with pytest.raises(ValueError, match="Discard pile empty"):
        call("/api/battle/rest", {})

    # Test reshuffle resilience when duplicate card IDs were in discard
    corrupted_state = {
        "hand": ["c1"],
        "discard": ["c2", "c2", "c3"],
        "lost": [],
        "active_links": {},
        "resolutions": {},
    }
    combat_completion.atomic_json(battle_path, corrupted_state)
    rest_res_2 = call("/api/battle/rest", {})
    assert rest_res_2["status"] == "success"
    res_state = state(vault)
    # Hand IDs must still remain unique despite duplicates in discard
    assert len(res_state["hand"]) == len(set(res_state["hand"]))

