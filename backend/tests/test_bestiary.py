import json
import sqlite3

import pytest
from services.bestiary import build_bestiary, record_round
from services.combat_service import evaluate_round
from test_combat_completion import link, state, subprocess_call

pytest_plugins = ["test_combat_completion"]


def profile(root, name="Wyrm"):
    folder = root / "Codex/Beasts" / name
    folder.mkdir(parents=True)
    (folder / "Combat.json").write_text(json.dumps({"affinity": "Void", "vulnerabilities": {"Digital": 2}}))


def battle(identity="one", hp=10, attack=0, player_hp=100):
    return {"history_id": identity, "player_hp": player_hp,
            "enemies": [{"id": "Wyrm", "hp": hp, "attack": attack}]}


def test_read_only_empty_catalog(vault):
    profile(vault)
    before = sorted(str(p) for p in vault.rglob('*'))
    entry = build_bestiary(vault)["beasts"][0]
    assert entry["encounters"] == 0 and entry["win_rate"] is None
    assert entry["affinity"] == "Void" and entry["vulnerabilities"] == {"Digital": 2}
    assert before == sorted(str(p) for p in vault.rglob('*'))


def test_rounds_replay_outcomes_and_actual_damage(vault):
    profile(vault)
    start = battle()
    first = evaluate_round(start, [{"attack": 3}])
    record_round(vault, "a", start, first)
    record_round(vault, "a", start, first)
    second = evaluate_round(first["encounter"], [{"attack": 999}])
    record_round(vault, "b", first["encounter"], second)
    loss = battle("two", attack=20, player_hp=1)
    record_round(vault, "c", loss, evaluate_round(loss, [{"attack": 1}]))
    ongoing = battle("three")
    record_round(vault, "d", ongoing, evaluate_round(ongoing, [{"attack": 1}]))
    entry = build_bestiary(vault)["beasts"][0]
    assert (entry["encounters"], entry["wins"], entry["defeats"], entry["active"]) == (3, 1, 1, 1)
    assert entry["win_rate"] == entry["defeat_rate"] == 50
    assert entry["slayings"] == 1 and entry["highest_turn_damage"] == 7
    assert entry["trophies"] == ["First Slaying"]
    with pytest.raises(ValueError):
        record_round(vault, "a", loss, evaluate_round(loss, [{"attack": 1}]))


def test_native_read_and_completion_replay(vault, call):
    profile(vault)
    current = state(vault)
    current["encounter"] = battle()
    current["encounter"].pop("history_id")
    (vault / "Battle/battle_state.json").write_text(json.dumps(current))
    (vault / "Battle/Cards.json").write_text(json.dumps({"cards": [{"id": "a", "attack": 10}, {"id": "b"}]}))
    body = link(call)
    assert call("/api/battle/resolve", body)["status"] == "completed"
    call("/api/battle/resolve", body)
    entry = subprocess_call(vault, "/api/battle/bestiary", {})["beasts"][0]
    assert entry["wins"] == entry["encounters"] == entry["slayings"] == 1


def test_legacy_database_and_invalid_profile(vault):
    profile(vault)
    db = vault / "Keeper/navis_progression.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE xp_logs (details TEXT)")
        conn.execute("INSERT INTO xp_logs VALUES ('Wyrm')")
    (vault / "Codex/Beasts/Wyrm/Combat.json").write_text('{broken')
    entry = build_bestiary(vault)["beasts"][0]
    assert entry["profile_error"] and entry["encounters"] == 0


def test_http_native_read_parity_without_database_writes(vault, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    profile(vault)
    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))
    before = {str(path): path.read_bytes() for path in vault.rglob('*') if path.is_file()}
    response = TestClient(main.app).get('/api/battle/bestiary')
    assert response.status_code == 200
    assert response.json() == subprocess_call(vault, '/api/battle/bestiary', {})
    assert before == {str(path): path.read_bytes() for path in vault.rglob('*') if path.is_file()}


def test_history_failure_recovers_once(vault, monkeypatch):
    from services import bestiary, combat_completion
    profile(vault)
    current = state(vault)
    current["encounter"] = battle()
    (vault / "Battle/battle_state.json").write_text(json.dumps(current))
    (vault / "Battle/Cards.json").write_text(json.dumps({"cards": [{"id": "a", "attack": 10}, {"id": "b"}]}))
    body = link(combat_completion.dispatch)
    original = bestiary.record_round
    def fail_after_insert(*args):
        original(*args)
        raise OSError("Synthetic interruption after persisted history")
    monkeypatch.setattr(bestiary, "record_round", fail_after_insert)
    pending = combat_completion.dispatch('/api/battle/resolve', body)
    assert pending["status"] == 'pending_recovery' and pending["cards_resolved"]
    monkeypatch.setattr(bestiary, "record_round", original)
    assert combat_completion.dispatch('/api/battle/resolve', body)["status"] == 'completed'
    assert build_bestiary(vault)["beasts"][0]["slayings"] == 1
