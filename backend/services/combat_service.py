"""Deterministic tactical rules and local profile reads; no Vault writes."""
from copy import deepcopy
import json
import math
from pathlib import Path

ELEMENTS = ("Physical", "Digital", "Kinetic", "Arcane", "Void")
PASSIVE_LIMITS = {"shield_percent": 100, "ap_bonus": 10, "kinetic_percent": 100}


def companion_profile(profile):
    """Optional companion Combat.json schema; unknown attributes fail closed."""
    if not isinstance(profile, dict):
        raise ValueError("Companion combat profile must be an object")
    passives = profile.get("passives", {})
    if not isinstance(passives, dict) or any(
            key not in PASSIVE_LIMITS or type(value) is not int  # noqa: E721 - Exact JSON types reject bool-as-int.
            or not 0 <= value <= PASSIVE_LIMITS[key] for key, value in passives.items()):
        raise ValueError("Invalid companion combat passives")
    return {"passives": dict(passives)}


def squad_synergies(root):
    """Read only deployed companions, once each; Vanguard is a squad role."""
    base = Path(root).resolve()
    status_path = base / "Bridge/status.json"
    status = json.loads(status_path.read_text(encoding="utf-8-sig")) if status_path.is_file() else {}
    if not isinstance(status, dict):
        raise ValueError("Squad status must be an object")
    squad = status.get("squad", [])
    if not isinstance(squad, list):
        raise ValueError("Active squad must be a list")
    defaults = json.loads((Path(__file__).resolve().parents[1] / "data/companion_combat.json").read_text())
    defaults = {name.casefold(): profile for name, profile in defaults.items()}
    seen, synergies = set(), []
    for member in squad:
        name = member.get("name") if isinstance(member, dict) else None
        if not isinstance(name, str) or not name or name in (".", "..") or any(c in name for c in "/\\:"):
            raise ValueError("Invalid active companion name")
        key = name.casefold()
        if key == "keeper" or key in seen:
            continue
        seen.add(key)
        path = (base / "Companions" / name / "Combat.json").resolve()
        if not path.is_relative_to(base):
            raise ValueError("Companion profile must remain inside the Vault")
        profile = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else defaults.get(key, {})
        passives = companion_profile(profile)["passives"]
        if any(passives.values()):
            synergies.append({"name": name, "passives": passives})
    return synergies


def passive_totals(synergies):
    totals = dict.fromkeys(PASSIVE_LIMITS, 0)
    for synergy in synergies:
        for key, value in companion_profile(synergy)["passives"].items():
            totals[key] += value
    return totals


def elemental_profile(profile):
    """Explicit weaknesses only; affinity alone does not imply a weakness."""
    affinity = profile.get("affinity", "Physical")
    if affinity not in ELEMENTS:
        raise ValueError("Invalid elemental affinity")
    weaknesses = profile.get("vulnerabilities", {})
    if isinstance(weaknesses, list):
        weaknesses = {element: 2 for element in weaknesses}
    if not isinstance(weaknesses, dict) or any(
            element not in ELEMENTS or type(value) not in (int, float)
            or not math.isfinite(value) or not 1 < value <= 10
            for element, value in weaknesses.items()):
        raise ValueError("Vulnerabilities require known elements and multipliers greater than 1 and at most 10")
    return {"affinity": affinity, "vulnerabilities": dict(weaknesses)}


def hydrate_encounter(root, encounter):
    """Resolve trusted local Combat.json definitions, never request-supplied paths."""
    out = deepcopy(encounter)
    if out is None:
        return None
    base = Path(root).resolve()
    # Replace the last round's snapshot with current trusted squad state.
    out["synergies"] = squad_synergies(root)
    out["ap_available"] = stat(out.get("ap_per_turn", 2), "ap_per_turn") + passive_totals(out["synergies"])["ap_bonus"]
    try:
        from services.talent_service import get_active_perks
        out["talent_perks"] = get_active_perks("keeper", root=str(base))
    except Exception:
        out.setdefault("talent_perks", {})
    for enemy in out.get("enemies", []):
        name = enemy.get("beast", enemy.get("id", ""))
        profile = enemy
        if isinstance(name, str) and name and name not in (".", "..") and not any(c in name for c in "/\\:"):
            for directory in ("Codex/Beasts", "Obstacles/Beasts"):
                path = (base / directory / name / "Combat.json").resolve()
                if path.is_relative_to(base) and path.is_file():
                    profile = json.loads(path.read_text(encoding="utf-8-sig"))
                    break
        enemy.update(elemental_profile(profile))
    return out


def stat(value, name):
    if type(value) is not int or value < 0:  # noqa: E721 - Exact JSON integer, excluding booleans.
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def card_stats(card):
    """Legacy cards remain playable with one AP and no tactical effect."""
    element = card.get("element", card.get("type") if card.get("type") in ELEMENTS else "Physical")
    if element not in ELEMENTS:
        raise ValueError("Invalid card element")
    return {**card, "element": element, **{key: stat(card.get(key, default), key)
            for key, default in (("ap_cost", 1), ("attack", 0), ("shield", 0))}}


def enemy_intent(enemy, turn):
    pattern = enemy.get("intent_pattern", ["Strike"])
    if not isinstance(pattern, list) or not pattern or any(
            intent not in ("Strike", "Debuff", "Charge") for intent in pattern):
        raise ValueError("Invalid enemy intent pattern")
    return pattern[(stat(turn, "turn") - 1) % len(pattern)]


def evaluate_round(encounter, cards):
    """Attack first; survivors act in order. Shields expire after the round.

    Charge doubles the next Strike. Debuff reduces next round's attack by one.
    AP refreshes each round. The encounter is owned by the server, never a request.
    """
    out = deepcopy(encounter)
    turn = stat(out.get("turn", 1), "turn")
    if turn < 1:
        raise ValueError("turn must be positive")
    hp = stat(out.get("player_hp", 100), "player_hp")
    if hp == 0:
        raise ValueError("Encounter is defeated")
    bonuses = passive_totals(out.get("synergies", []))
    talent_perks = out.get("talent_perks") or {}
    from services.talent_service import calculate_combat_perk_modifiers
    talent_mods = calculate_combat_perk_modifiers(talent_perks)

    budget = stat(out.get("ap_per_turn", 2), "ap_per_turn") + bonuses["ap_bonus"]
    out["ap_available"] = budget
    cards = [card_stats(card) for card in cards]
    cost = sum(card["ap_cost"] for card in cards)
    if cost > budget:
        raise ValueError("Insufficient action points")
    cards = [{**card, "attack": card["attack"] * (100 + bonuses["kinetic_percent"]) // 100
              if card["element"] == "Kinetic" else card["attack"]} for card in cards]
    raw_debuff = stat(out.get("debuff", 0), "debuff")
    effective_debuff = max(0, raw_debuff - talent_mods["debuff_reduction"])
    attack = max(0, sum(card["attack"] for card in cards) - effective_debuff)
    total_shield_percent = min(PASSIVE_LIMITS["shield_percent"], bonuses["shield_percent"] + talent_mods["shield_percent_bonus"])
    shield = sum(card["shield"] for card in cards) * (100 + total_shield_percent) // 100
    enemies = out.get("enemies", [])
    if not isinstance(enemies, list) or not enemies:
        raise ValueError("Encounter requires enemies")
    if not any(stat(enemy.get("hp", 0), "enemy hp") > 0 for enemy in enemies):
        raise ValueError("Encounter already won")
    remaining_attack = attack
    # Track only attacks that actually hit a living target. Shield-only cards,
    # dead targets and unused overkill cannot produce critical XP.
    remaining_cards = []
    penalty = effective_debuff
    for card in cards:
        reduced = min(penalty, card["attack"])
        penalty -= reduced
        remaining_cards.append([card, card["attack"] - reduced])
    critical_hits = []
    absorbed = damage = debuff = 0
    intents = []
    for enemy in enemies:
        health = stat(enemy.get("hp", 0), "enemy hp")
        dealt = min(health, remaining_attack)
        enemy["hp"] = health - dealt
        remaining_attack -= dealt
        profile = elemental_profile(enemy)
        enemy.update(profile)
        to_assign = dealt
        for entry in remaining_cards:
            card, available = entry
            hit = min(available, to_assign)
            entry[1] -= hit
            to_assign -= hit
            multiplier = profile["vulnerabilities"].get(card["element"], 1)
            if hit and multiplier > 1:
                critical_hits.append({"enemy_id": enemy.get("id"), "card_id": card.get("id"),
                                      "element": card["element"], "multiplier": multiplier, "damage": hit})
        intent = enemy_intent(enemy, turn)
        strength = stat(enemy.get("attack", 0), "enemy attack")
        charged = enemy.get("charged", False)
        if type(charged) is not bool:  # noqa: E721 - Require an exact JSON boolean.
            raise ValueError("charged must be boolean")
        intents.append({"id": enemy.get("id"), "intent": intent, "attack_dealt": dealt})
        if not enemy["hp"]:
            continue
        if intent == "Charge":
            enemy["charged"] = True
        elif intent == "Debuff":
            debuff += 1
        else:
            incoming = strength * (2 if charged else 1)
            blocked = min(shield, incoming)
            shield -= blocked
            absorbed += blocked
            damage += incoming - blocked
            enemy["charged"] = False
    reduced_debuff = max(0, debuff - talent_mods["debuff_reduction"])
    out.update(player_hp=max(0, hp - damage), turn=turn + 1, debuff=reduced_debuff)
    out["outcome"] = "won" if all(enemy["hp"] == 0 for enemy in enemies) else ("defeated" if out["player_hp"] == 0 else "active")
    base_multiplier = max((hit["multiplier"] for hit in critical_hits), default=1)
    effective_xp_multiplier = min(10.0, base_multiplier + talent_mods["combat_xp_bonus"]) if critical_hits and talent_mods["combat_xp_bonus"] > 0 else base_multiplier
    return {"encounter": out, "turn": turn, "ap_spent": cost, "ap_available": budget,
            "synergies": deepcopy(out.get("synergies", [])), "talent_perks": deepcopy(talent_perks),
            "talent_modifiers": talent_mods, "attack": attack,
            "shield_absorbed": absorbed, "player_damage": min(hp, damage), "intents": intents,
            "critical_hits": critical_hits,
            "xp_multiplier": effective_xp_multiplier}
