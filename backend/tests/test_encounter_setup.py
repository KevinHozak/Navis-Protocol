import io
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import battle_engine, combat_completion, encounter_setup
import native_combat


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(battle_engine, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setenv("NAVIS_ROOT", str(tmp_path))
    for name, profile in (("Sentinel", {"hp": 20, "attack": 4, "intent_pattern": ["Charge", "Strike"],
                                       "vulnerabilities": {"Digital": 2}}), ("Unconfigured", {"affinity": "Void"})):
        folder = tmp_path / "Codex/Beasts" / name
        folder.mkdir(parents=True)
        (folder / "Combat.json").write_text(json.dumps(profile))
    (tmp_path / "Battle").mkdir()
    (tmp_path / "Battle/Cards.json").write_text('{"cards": [{"id": "a"}, {"id": "b"}]}')
    (tmp_path / "Battle/battle_state.json").write_text(json.dumps({
        "hand": ["a", "b"], "discard": ["c"], "lost": [], "active_links": {},
        "resolutions": {"old": {"phase": "complete"}}}))
    (tmp_path / "private.md").write_bytes(b"\xef\xbb\xbf- [ ] Original\r\n")
    return tmp_path


@pytest.fixture(params=["shared", "native", "http"])
def call(request, monkeypatch):
    if request.param == "shared":
        return combat_completion.dispatch
    if request.param == "http":
        from fastapi.testclient import TestClient
        import main
        client = TestClient(main.app)
        def http(path, body):
            response = client.get(path) if path.endswith("encounters") else client.post(path, json=body)
            if not response.is_success:
                raise ValueError(response.json()["detail"])
            return response.json()
        return http
    def native(path, body):
        output = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"path": path, "body": body})))
        monkeypatch.setattr(sys, "stdout", output)
        native_combat.main()
        result = json.loads(output.getvalue())
        if result["status"] != 200:
            raise ValueError(result["body"]["detail"])
        return result["body"]
    return native


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and p.name != ".completion.lock"}


def test_review_create_and_replay(vault, call):
    before = snapshot(vault)
    catalog = call("/api/battle/encounters", {})
    assert catalog["blocked"] is None
    assert "unavailable" in next(r for r in catalog["candidates"] if r["name"] == "Unconfigured")
    review = call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})
    assert snapshot(vault) == before  # No lock, DB, card initialization or writes on preview.
    body = {"enemy_id": "Sentinel", "preview_token": review["preview_token"], "hp": 99999}
    result = call("/api/battle/encounter", body)
    assert result["encounter"]["enemies"][0]["hp"] == 20
    assert result["encounter"]["player_hp"] == 100
    saved = snapshot(vault)
    assert call("/api/battle/encounter", body)["idempotent_replay"]
    assert snapshot(vault) == saved
    for path, content in before.items():
        if path != str(Path("Battle/battle_state.json")):
            assert saved[path] == content
    state = encounter_setup.read_state(vault)
    assert state["hand"] == ["a", "b"] and state["discard"] == ["c"]
    assert state["resolutions"] == {"old": {"phase": "complete"}}
    with pytest.raises(ValueError, match="current encounter"):
        call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})


@pytest.mark.parametrize("change", ["profile", "state"])
def test_stale_review_rejected(vault, call, change):
    review = call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})
    path = vault / ("Codex/Beasts/Sentinel/Combat.json" if change == "profile" else "Battle/battle_state.json")
    data = json.loads(path.read_text())
    data.update({"attack": 9} if change == "profile" else {"discard": ["changed"]})
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="preview changed"):
        call("/api/battle/encounter", {"enemy_id": "Sentinel", "preview_token": review["preview_token"]})
    assert path.read_bytes() == before
    assert "encounter" not in encounter_setup.read_state(vault)


@pytest.mark.parametrize("phase", ["prepared", "task_written", "battle_committed", "xp_sync_pending"])
def test_pending_recovery_blocked(vault, call, phase):
    state = encounter_setup.read_state(vault)
    state["resolutions"]["pending"] = {"phase": phase}
    path = vault / "Battle/battle_state.json"
    path.write_text(json.dumps(state))
    before = path.read_bytes()
    assert "pending combat recovery" in call("/api/battle/encounters", {})["blocked"]
    for route in ("/api/battle/encounter/preview", "/api/battle/encounter"):
        with pytest.raises(ValueError, match="pending combat recovery"):
            call(route, {"enemy_id": "Sentinel", "preview_token": "bad"})
    assert path.read_bytes() == before


@pytest.mark.parametrize("enemy", ["../private", "Unconfigured", "missing", None])
def test_untrusted_selection_rejected(vault, call, enemy):
    with pytest.raises(ValueError, match="valid combat profile"):
        call("/api/battle/encounter/preview", {"enemy_id": enemy})


def test_completed_encounter_replacement_preserves_history(vault, call):
    path = vault / "Battle/battle_state.json"
    state = encounter_setup.read_state(vault)
    state.update(encounter={"outcome": "won", "history_id": "old"}, last_round={"turn": 9})
    path.write_text(json.dumps(state))
    review = call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})
    result = call("/api/battle/encounter", {"enemy_id": "Sentinel", "preview_token": review["preview_token"]})
    assert result["encounter"]["history_id"] != "old"
    assert "last_round" not in encounter_setup.read_state(vault)
    assert encounter_setup.read_state(vault)["resolutions"] == state["resolutions"]


@pytest.mark.parametrize("profile", [{"hp": True, "attack": 1}, {"hp": 0, "attack": 1},
                                    {"hp": 20, "attack": -1}, {"hp": 20, "attack": 1, "intent_pattern": ["Invented"]}])
def test_invalid_combat_stats_unavailable(vault, call, profile):
    (vault / "Codex/Beasts/Sentinel/Combat.json").write_text(json.dumps(profile))
    row = next(row for row in call("/api/battle/encounters", {})["candidates"] if row["enemy_id"] == "Sentinel")
    assert "unavailable" in row
    with pytest.raises(ValueError):
        call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})


def test_missing_cards_and_linked_maneuver_fail_closed(vault, call):
    path = vault / "Battle/battle_state.json"
    state = encounter_setup.read_state(vault)
    state["active_links"] = {"task": {"top": "a", "bottom": "b"}}
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="linked maneuvers"):
        call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})
    (vault / "Battle/Cards.json").unlink()
    with pytest.raises(ValueError, match="cards and battle state"):
        call("/api/battle/encounter/preview", {"enemy_id": "Sentinel"})
    assert path.read_text() == json.dumps(state)
