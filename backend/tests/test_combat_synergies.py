import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from services.combat_service import companion_profile, evaluate_round, hydrate_encounter
from services import combat_completion, battle_engine
from test_combat_completion import link, state, subprocess_call

pytest_plugins = ["test_combat_completion"]


def squad(vault, names):
    (vault / "Bridge/status.json").write_text(json.dumps({"squad": [{"name": name} for name in names]}))


def encounter():
    return {"ap_per_turn": 2, "player_hp": 20, "enemies": [{"id": "sentinel", "hp": 100, "attack": 10}]}


def test_combined_passives_and_no_compounding(vault):
    squad(vault, ["Groza", "Lyra", "Rita", "Groza", "Keeper"])
    hydrated = hydrate_encounter(vault, encounter())
    cards = [{"element": "Kinetic", "attack": 20, "shield": 5, "ap_cost": 3}]
    result = evaluate_round(hydrated, cards)
    assert result["ap_available"] == 3
    assert result["attack"] == 23
    assert result["shield_absorbed"] == 6
    assert result["player_damage"] == 4
    assert len(result["synergies"]) == 3
    second = evaluate_round(hydrate_encounter(vault, result["encounter"]), cards)
    assert (second["attack"], second["ap_available"], second["shield_absorbed"]) == (23, 3, 6)
    assert cards[0]["attack"] == 20


def test_recall_reserve_and_legacy(vault):
    squad(vault, ["Rita"])
    original = hydrate_encounter(vault, encounter())
    assert evaluate_round(original, [{"attack": 20}])["attack"] == 20
    assert evaluate_round(original, [{"element": "Kinetic", "attack": 1}])["attack"] == 1
    squad(vault, ["Unknown"])
    recalled = hydrate_encounter(vault, original)
    assert recalled["synergies"] == []
    assert evaluate_round(recalled, [{"element": "Kinetic", "attack": 20}])["attack"] == 20
    with pytest.raises(ValueError, match="action points"):
        evaluate_round(recalled, [{"ap_cost": 3}])


def test_custom_schema_override_and_stacking(vault):
    squad(vault, ["Groza", "Custom", "Second"])
    for name, passives in [("Groza", {}), ("Custom", {"shield_percent": 50, "ap_bonus": 2}),
                           ("Second", {"shield_percent": 10, "ap_bonus": 1})]:
        folder = vault / "Companions" / name
        folder.mkdir(parents=True)
        (folder / "Combat.json").write_text(json.dumps({"passives": passives}))
    hydrated = hydrate_encounter(vault, encounter())
    assert len(hydrated["synergies"]) == 2
    result = evaluate_round(hydrated, [{"shield": 5, "ap_cost": 5}])
    assert result["shield_absorbed"] == 8
    assert result["ap_available"] == 5


@pytest.mark.parametrize("passives", [{"ap_bonus": True}, {"ap_bonus": -1}, {"shield_percent": 101},
                                    {"kinetic_percent": 1.5}, {"unknown": 1}, []])
def test_invalid_profile(passives):
    with pytest.raises(ValueError, match="passives"):
        companion_profile({"passives": passives})


@pytest.mark.parametrize("name", ["../Rita", "..", "Rita/", "C:Rita"])
def test_invalid_squad_paths(vault, name):
    squad(vault, [name])
    with pytest.raises(ValueError, match="name"):
        hydrate_encounter(vault, encounter())


def prepare(vault):
    squad(vault, ["Groza", "Lyra", "Rita"])
    (vault / "Bridge/CompanionStats.json").write_text(json.dumps({"companions": {
        name: {"xp": 0, "level": 1} for name in ("Keeper", "Groza", "Lyra", "Rita")}}))
    battle = state(vault)
    battle["encounter"] = encounter()
    (vault / "Battle/battle_state.json").write_text(json.dumps(battle))
    (vault / "Battle/Cards.json").write_text(json.dumps({"cards": [
        {"id": "a", "attack": 20, "element": "Kinetic", "ap_cost": 2},
        {"id": "b", "shield": 5}]}))


def test_resolution_parity_and_replay(vault, call):
    prepare(vault)
    command = link(call)
    preview = battle_engine.BattleEngine().get_full_state()["encounter"]
    assert preview == subprocess_call(vault, "/api/battle/state", {})["encounter"]
    assert preview["ap_available"] == 3
    result = call("/api/battle/resolve", command)
    assert result["status"] == "completed", json.dumps(result)
    assert result["tactical"]["attack"] == 23
    assert result["tactical"]["shield_absorbed"] == 6
    squad(vault, [])
    assert call("/api/battle/resolve", command)["tactical"] == result["tactical"]
    assert state(vault)["encounter"]["turn"] == 2
    assert battle_engine.BattleEngine().get_full_state()["encounter"]["ap_available"] == 2


def test_recovery_keeps_prepared_squad_snapshot(vault, monkeypatch):
    prepare(vault)
    command = link(combat_completion.dispatch)
    original = combat_completion.complete_checkbox
    monkeypatch.setattr(combat_completion, "complete_checkbox", lambda *_: (_ for _ in ()).throw(OSError("Interrupted")))
    result = combat_completion.dispatch("/api/battle/resolve", command)
    assert result["status"] == "pending_recovery"
    squad(vault, [])
    monkeypatch.setattr(combat_completion, "complete_checkbox", original)
    recovered = subprocess_call(vault, "/api/battle/resolve", command)
    assert recovered["tactical"]["attack"] == 23
    assert recovered["tactical"]["ap_available"] == 3
    assert state(vault)["encounter"]["turn"] == 2


def test_bad_profile_fails_before_task_write(vault):
    prepare(vault)
    folder = vault / "Companions/Rita"
    folder.mkdir(parents=True)
    (folder / "Combat.json").write_text('{"passives":{"kinetic_percent":-1}}')
    command = link(combat_completion.dispatch)
    before = state(vault)
    journal = vault / command["source"]["path"]
    content = journal.read_bytes()
    with pytest.raises(ValueError, match="passives"):
        combat_completion.dispatch("/api/battle/resolve", command)
    assert journal.read_bytes() == content
    assert state(vault) == before


def test_packaged_native_resources(vault, tmp_path):
    prepare(vault)
    repo = Path(__file__).resolve().parents[2]
    tauri = repo / "frontend/src-tauri"
    resources = json.loads((tauri / "tauri.conf.json").read_text())["bundle"]["resources"]
    package = tmp_path / "package"
    for source, destination in resources.items():
        target = package / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tauri / source, target)
    expected = battle_engine.BattleEngine().get_full_state()["encounter"]
    result = subprocess.run([sys.executable, str(package / "backend/native_combat.py")],
        input=json.dumps({"path": "/api/battle/state"}), capture_output=True, text=True, timeout=30,
        cwd=package, env={**os.environ, "NAVIS_ROOT": str(vault), "PYTHONPATH": "", "PYTHONIOENCODING": "utf-8"}, check=True)
    envelope = json.loads(result.stdout)
    assert envelope["status"] == 200, envelope
    assert envelope["body"]["encounter"] == expected
