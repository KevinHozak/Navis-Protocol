import json
import pytest
from services.combat_service import ELEMENTS, elemental_profile, evaluate_round, hydrate_encounter
from test_combat_completion import link, state
from services import combat_completion, progression_db, rpg_engine

pytest_plugins = ["test_combat_completion"]


def encounter():
    return {"enemies": [{"id": "Wyrm", "hp": 10, "attack": 0,
                         "affinity": "Void", "vulnerabilities": {"Digital": 2.5}}]}


def test_elemental_matching_and_legacy():
    result = evaluate_round(encounter(), [{"id": "a", "element": "Digital", "attack": 3}])
    assert result["xp_multiplier"] == 2.5
    assert result["critical_hits"][0]["damage"] == 3
    assert evaluate_round(encounter(), [{"attack": 3}])["xp_multiplier"] == 1
    assert evaluate_round(encounter(), [{"element": "Digital", "shield": 3}])["xp_multiplier"] == 1
    assert elemental_profile({"vulnerabilities": ["Kinetic"]})["vulnerabilities"] == {"Kinetic": 2}


@pytest.mark.parametrize("element", ELEMENTS)
def test_all_card_types(element):
    battle = encounter()
    battle["enemies"][0]["vulnerabilities"] = {element: 2}
    assert evaluate_round(battle, [{"type": element, "attack": 1}])["xp_multiplier"] == 2


def test_target_order_debuff_and_overkill():
    battle = encounter()
    battle["enemies"].insert(0, {"id": "neutral", "hp": 1, "attack": 0})
    assert evaluate_round(battle, [{"element": "Digital", "attack": 1}])["xp_multiplier"] == 1
    assert evaluate_round(battle, [{"element": "Digital", "attack": 2}])["xp_multiplier"] == 2.5
    battle["debuff"] = 2
    assert evaluate_round(battle, [{"element": "Digital", "attack": 2}])["xp_multiplier"] == 1
    battle = encounter()
    assert evaluate_round(battle, [{"attack": 10}, {"element": "Digital", "attack": 5}])["xp_multiplier"] == 1


@pytest.mark.parametrize("value", [True, 0, 1, -2, 11, float("nan"), float("inf"), "2"])
def test_invalid_multiplier(value):
    with pytest.raises(ValueError):
        elemental_profile({"vulnerabilities": {"Digital": value}})


@pytest.mark.parametrize("directory", ["Codex/Beasts", "Obstacles/Beasts"])
def test_profile_loading(vault, directory):
    folder = vault / directory / "Wyrm"
    folder.mkdir(parents=True)
    (folder / "Combat.json").write_text(json.dumps({"affinity": "Arcane", "vulnerabilities": ["Digital"]}))
    original = encounter()
    assert hydrate_encounter(vault, original)["enemies"][0]["affinity"] == "Arcane"
    assert original["enemies"][0]["affinity"] == "Void"


def prepare(vault, call):
    battle = state(vault)
    battle["encounter"] = encounter()
    (vault / "Battle/battle_state.json").write_text(json.dumps(battle))
    (vault / "Battle/Cards.json").write_text(json.dumps({"cards": [
        {"id": "a", "element": "Digital", "attack": 3}, {"id": "b"}]}))
    return link(call)


def test_bonus_ledger_and_replay(vault, call):
    command = prepare(vault, call)
    assert call("/api/battle/resolve", command)["status"] == "completed"
    critical = [row for row in progression_db.get_xp_history() if row["source_type"] == "combat_critical"]
    assert len(critical) == 1
    assert critical[0]["amount"] == 3
    assert critical[0]["provenance"]["multiplier"] == 2.5
    assert progression_db.get_entity_total("keeper") == 15
    call("/api/battle/resolve", command)
    assert progression_db.get_entity_total("keeper") == 15


def test_bonus_recovery_after_ledger_commit(vault, monkeypatch):
    command = prepare(vault, combat_completion.dispatch)
    original = rpg_engine.apply_combat_bonus
    def interrupted(event):
        original(event)
        raise OSError("Interrupted after award commit")
    monkeypatch.setattr(rpg_engine, "apply_combat_bonus", interrupted)
    assert combat_completion.dispatch("/api/battle/resolve", command)["status"] == "pending_recovery"
    monkeypatch.setattr(rpg_engine, "apply_combat_bonus", original)
    assert combat_completion.dispatch("/api/battle/resolve", command)["status"] == "completed"
    assert progression_db.get_entity_total("keeper") == 15
    assert state(vault)["encounter"]["turn"] == 2


def test_cancel_does_not_award_bonus(vault):
    command = prepare(vault, combat_completion.dispatch)
    result = combat_completion.dispatch("/api/battle/resolve", {**command, "is_completed": False})
    assert result["status"] == "cancelled"
    assert not (vault / "Keeper/navis_progression.db").exists()


def test_invalid_profile_leaves_task_untouched(vault):
    command = prepare(vault, combat_completion.dispatch)
    folder = vault / "Codex/Beasts/Wyrm"
    folder.mkdir(parents=True)
    (folder / "Combat.json").write_text('{"vulnerabilities": {"Digital": -2}}')
    before = state(vault)
    journal = vault / command["source"]["path"]
    content = journal.read_bytes()
    with pytest.raises(ValueError):
        combat_completion.dispatch("/api/battle/resolve", command)
    assert state(vault) == before
    assert journal.read_bytes() == content
