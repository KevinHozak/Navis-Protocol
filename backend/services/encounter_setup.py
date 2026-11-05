"""Reviewed, server-owned encounter setup shared by HTTP and desktop."""
import hashlib
import json
from pathlib import Path
import uuid

from services.combat_service import elemental_profile, enemy_intent, stat


def read_state(root):
    path = Path(root) / "Battle/battle_state.json"
    state = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if not isinstance(state, dict):
        raise ValueError("Invalid battle state")
    return state


def blocked(state, root=None):
    if root and not all((Path(root) / relative).is_file() for relative in ("Battle/Cards.json", "Battle/battle_state.json")):
        return "Combat cards and battle state must be available before setting up an encounter."
    if any(op.get("phase") != "complete" for op in state.get("resolutions", {}).values()):
        return "Finish pending combat recovery before setting up an encounter."
    encounter = state.get("encounter")
    if encounter and encounter.get("outcome") not in ("won", "defeated"):
        return "Finish the current encounter before setting up another."
    if state.get("active_links"):
        return "Resolve or cancel linked maneuvers before setting up an encounter."
    return None


def candidates(root):
    base = Path(root).resolve(strict=True)
    found = {}
    for relative in ("Codex/Beasts", "Obstacles/Beasts"):
        directory = base / relative
        if not directory.is_dir() or not directory.resolve().is_relative_to(base):
            continue
        for folder in sorted(directory.iterdir(), key=lambda p: p.name.casefold()):
            if not folder.is_dir() or folder.name.casefold() in found:
                continue
            row = {"enemy_id": folder.name, "name": folder.name}
            found[folder.name.casefold()] = row
            try:
                path = (folder / "Combat.json").resolve(strict=True)
                if not path.is_relative_to(base) or not folder.resolve().is_relative_to(base):
                    raise ValueError("Combat profile must stay inside the Vault")
                profile = json.loads(path.read_text(encoding="utf-8-sig"))
                hp = stat(profile.get("hp"), "Enemy HP")
                if hp == 0:
                    raise ValueError("Enemy HP must be positive")
                attack = stat(profile.get("attack"), "Enemy attack")
                pattern = profile.get("intent_pattern", ["Strike"])
                enemy = {"id": folder.name, "beast": folder.name, "hp": hp, "max_hp": hp,
                         "attack": attack, "intent_pattern": pattern, **elemental_profile(profile)}
                enemy_intent(enemy, 1)
                row["enemy"] = enemy
            except (OSError, ValueError, TypeError, AttributeError) as error:
                row["unavailable"] = str(error)
    return list(found.values())


def preview(root, state, enemy_id):
    reason = blocked(state, root)
    if reason:
        raise ValueError(reason)
    row = next((row for row in candidates(root) if row["enemy_id"] == enemy_id), None)
    if row is None or "enemy" not in row:
        raise ValueError("Select an existing enemy with a valid combat profile")
    encounter = {"turn": 1, "player_hp": 100, "ap_per_turn": 2,
                 "outcome": "active", "enemies": [row["enemy"]]}
    token = hashlib.sha256(json.dumps([state, encounter], sort_keys=True).encode()).hexdigest()
    return {"encounter": encounter, "preview_token": token}


def dispatch(root, path, body):
    from services.combat_completion import atomic_json, battle_lock
    if path == "/api/battle/encounters":
        return {"candidates": candidates(root), "blocked": blocked(read_state(root), root)}
    if path == "/api/battle/encounter/preview":
        return preview(root, read_state(root), body.get("enemy_id"))
    with battle_lock(root):
        state = read_state(root)
        token = body.get("preview_token")
        current = state.get("encounter", {})
        if token and current.get("setup_token") == token and current.get("enemies", [{}])[0].get("id") == body.get("enemy_id"):
            return {"encounter": current, "idempotent_replay": True}
        reviewed = preview(root, state, body.get("enemy_id"))
        if not isinstance(token, str) or token != reviewed["preview_token"]:
            raise ValueError("The preview changed. Review the encounter again before confirming.")
        encounter = {**reviewed["encounter"], "history_id": str(uuid.uuid4()), "setup_token": token}
        state["encounter"] = encounter
        state.pop("last_round", None)
        atomic_json(Path(root) / "Battle/battle_state.json", state)
        return {"encounter": encounter, "idempotent_replay": False}
