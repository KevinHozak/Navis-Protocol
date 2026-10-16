import json
from copy import deepcopy
import pytest
from services.combat_service import card_stats, evaluate_round
from test_combat_completion import link, state
pytest_plugins = ["test_combat_completion"]


def encounter(**values):
    return {"player_hp": 10, "ap_per_turn": 2, "turn": 1,
            "enemies": [{"id": "enemy", "hp": 10, "attack": 5}], **values}


@pytest.mark.parametrize("shield,expected", [(0, 5), (3, 2), (5, 0), (9, 0)])
def test_shields(shield, expected):
    original = encounter()
    before = deepcopy(original)
    result = evaluate_round(original, [{"attack": 2, "shield": shield}])
    assert result["player_damage"] == expected
    assert result["encounter"]["enemies"][0]["hp"] == 8
    assert original == before
    assert result == evaluate_round(original, [{"attack": 2, "shield": shield}])


def test_kill_prevents_retaliation_and_overkill_clamps():
    result = evaluate_round(encounter(), [{"attack": 100}])
    assert result["player_damage"] == 0
    assert result["encounter"]["outcome"] == "won"


def test_charge_and_debuff():
    initial = encounter(enemies=[{"hp": 20, "attack": 5, "intent_pattern": ["Charge", "Strike", "Debuff"]}])
    charged = evaluate_round(initial, [])
    hit = evaluate_round(charged["encounter"], [{"shield": 9}])
    assert hit["player_damage"] == 1
    debuffed = evaluate_round(hit["encounter"], [])
    assert debuffed["encounter"]["debuff"] == 1
    assert evaluate_round(debuffed["encounter"], [{"attack": 3}])["attack"] == 2


@pytest.mark.parametrize("value", [-1, True, 1.5, "3", None])
def test_invalid_stats(value):
    with pytest.raises(ValueError):
        card_stats({"attack": value})


def test_ap_and_defeat():
    with pytest.raises(ValueError, match="action points"):
        evaluate_round(encounter(), [{"ap_cost": 3}])
    assert evaluate_round(encounter(player_hp=1), [])["encounter"]["player_hp"] == 0
    with pytest.raises(ValueError, match="defeated"):
        evaluate_round(encounter(player_hp=0), [])


def test_shared_shield_multiple_enemies():
    result = evaluate_round(encounter(enemies=[{"hp": 5, "attack": 4}, {"hp": 5, "attack": 4}]), [{"shield": 6}])
    assert result["shield_absorbed"] == 6
    assert result["player_damage"] == 2


def test_round_persistence_and_replay(vault, call):
    battle = state(vault)
    battle["encounter"] = encounter()
    (vault / "Battle/battle_state.json").write_text(json.dumps(battle))
    command = link(call)
    result = call("/api/battle/resolve", command)
    assert result["tactical"]["player_damage"] == 5
    assert state(vault)["encounter"]["turn"] == 2
    assert call("/api/battle/resolve", command)["tactical"] == result["tactical"]
    assert state(vault)["encounter"]["turn"] == 2


def test_ap_failure_leaves_task_and_cards_untouched(vault, call):
    battle = state(vault)
    battle["encounter"] = encounter(ap_per_turn=0)
    (vault / "Battle/battle_state.json").write_text(json.dumps(battle))
    command = link(call)
    before = state(vault)
    journal = vault / command["source"]["path"]
    content = journal.read_bytes()
    with pytest.raises(ValueError, match="action points"):
        call("/api/battle/resolve", command)
    assert journal.read_bytes() == content
    assert state(vault) == before


@pytest.mark.parametrize("failing_save", [2, 3, 4, 5])
def test_tactical_recovery_applies_round_once(vault, monkeypatch, failing_save):
    from services import battle_engine, combat_completion
    from test_combat_completion import subprocess_call
    battle = state(vault)
    battle["encounter"] = encounter()
    (vault / "Battle/battle_state.json").write_text(json.dumps(battle))
    command = link(combat_completion.dispatch)
    original = battle_engine.BattleEngine.save_state
    saves = 0
    def interrupted(engine):
        nonlocal saves
        saves += 1
        if saves == failing_save:
            raise OSError("Interrupted tactical checkpoint")
        original(engine)
    monkeypatch.setattr(battle_engine.BattleEngine, "save_state", interrupted)
    assert combat_completion.dispatch("/api/battle/resolve", command)["status"] == "pending_recovery"
    result = subprocess_call(vault, "/api/battle/resolve", command)
    assert result["tactical"]["encounter"]["turn"] == 2
    assert state(vault)["encounter"]["player_hp"] == 5
    subprocess_call(vault, "/api/battle/resolve", command)
    assert state(vault)["encounter"]["turn"] == 2
