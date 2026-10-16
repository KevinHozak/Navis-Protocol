import os
import json
import random
import uuid
from datetime import datetime

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")


class BattleEngine:
    """
    The High-Fidelity Tactical Engine for Navis Protocol.
    Implements Gloomhaven-style Dual-Action mechanics.
    """

    def __init__(self):
        self.battle_dir = os.path.join(NAVIS_ROOT, "Battle")
        self.cards_path = os.path.join(self.battle_dir, "Cards.json")
        self.state_path = os.path.join(self.battle_dir, "battle_state.json")
        self.status_path = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
        self.companions_dir = os.path.join(NAVIS_ROOT, "Companions")

        self.cards_db = {}
        self.state = {
            "hand": [],
            "discard": [],
            "lost": [],
            "active_links": {},  # task_id -> {"top": card_id, "bottom": card_id}
        }

        self.load_cards()
        self.load_state()

    def load_cards(self):
        """Loads the master card database. Rebuilds from squad if missing."""
        if not os.path.exists(self.cards_path):
            if os.path.exists(self.state_path):
                raise FileNotFoundError("Card database missing; existing battle state retained")
            if os.path.exists(self.status_path):
                try:
                    with open(self.status_path, "r", encoding="utf-8-sig") as f:
                        status = json.load(f)
                    squad_names = [m["name"] for m in status.get("squad", [])]
                    if squad_names:
                        self.initialize_squad_hand(squad_names)
                except Exception as e:
                    print(f"⚠️ Reconstruction failed: {e}")

        if os.path.exists(self.cards_path):
            with open(self.cards_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                from services.combat_service import card_stats
                self.cards_db = {c["id"]: card_stats(c) for c in data.get("cards", [])}

    def load_state(self):
        """Loads the current battle state from the Bridge."""
        if os.path.exists(self.state_path):
            with open(self.state_path, "r", encoding="utf-8-sig") as f:
                self.state = json.load(f)

    def save_state(self):
        """Anchors the battle state to the Bridge."""
        from services.combat_completion import atomic_json
        atomic_json(self.state_path, self.state)

    def initialize_squad_hand(self, squad_names):
        """
        Initializes the 'Lean 24' hand based on the active squad.
        """
        all_cards = []
        for name in squad_names:
            comp_cards_path = os.path.join(self.companions_dir, name, "Cards.json")
            if os.path.exists(comp_cards_path):
                try:
                    with open(comp_cards_path, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                        all_cards.extend(data.get("cards", []))
                except Exception:
                    pass

        central_data = {
            "metadata": {
                "version": "party-dynamic",
                "timestamp": datetime.now().isoformat(),
                "squad": squad_names,
            },
            "cards": all_cards,
        }
        with open(self.cards_path, "w", encoding="utf-8-sig") as f:
            json.dump(central_data, f, indent=4, ensure_ascii=False)

        from services.combat_service import card_stats
        self.cards_db = {c["id"]: card_stats(c) for c in all_cards}

        new_hand = []
        for name in squad_names:
            comp_cards = [
                c_id
                for c_id, c in self.cards_db.items()
                if c["companion"].lower() in name.lower()
            ]
            new_hand.extend(comp_cards[:8])  # Max 8 per companion

        self.state["hand"] = new_hand
        self.state["discard"] = []
        self.state["lost"] = []
        self.state["active_links"] = {}
        self.save_state()

    def get_full_state(self):
        """Returns the fully hydrated state including card data."""
        from services.combat_service import enemy_intent, hydrate_encounter
        encounter = hydrate_encounter(NAVIS_ROOT, self.state.get("encounter"))
        if encounter:
            for enemy in encounter.get("enemies", []):
                enemy["intent"] = enemy_intent(enemy, encounter.get("turn", 1))
        hydrated_hand = [
            self.cards_db[cid]
            for cid in self.state.get("hand", [])
            if cid in self.cards_db
        ]
        hydrated_discard = [
            self.cards_db[cid]
            for cid in self.state.get("discard", [])
            if cid in self.cards_db
        ]
        hydrated_lost = [
            self.cards_db[cid]
            for cid in self.state.get("lost", [])
            if cid in self.cards_db
        ]

        hydrated_links = {}
        for task_id, link in self.state.get("active_links", {}).items():
            hydrated_links[task_id] = {
                "top": self.cards_db.get(link["top"]),
                "bottom": self.cards_db.get(link["bottom"]),
                "timestamp": link["timestamp"],
                "source": link.get("source"),
                "resolution_id": link.get("resolution_id"),
            }

        return {
            "encounter": encounter,
            "last_round": self.state.get("last_round"),
            "hand": hydrated_hand,
            "discard": hydrated_discard,
            "lost": hydrated_lost,
            "active_links": hydrated_links,
            "resolutions": self.state.get("resolutions", {}),
        }

    def link_task(self, task_id, top_card_id, bottom_card_id, source=None, resolution_id=None):
        from services.combat_completion import bind_source
        if task_id in self.state["active_links"]:
            return False, "Task already linked; resolve or cancel it before relinking."
        if any(op.get("task_id") == task_id and op.get("phase") != "complete" for op in self.state.get("resolutions", {}).values()):
            return False, "Task has a pending resolution; retry it first."
        bound = bind_source(NAVIS_ROOT, task_id, source)
        resolution_id = resolution_id or str(uuid.uuid4())
        if resolution_id in self.state.get("resolutions", {}) or any(link.get("resolution_id") == resolution_id for link in self.state["active_links"].values()):
            return False, "Resolution key already used."
        if (
            top_card_id not in self.state["hand"]
            or bottom_card_id not in self.state["hand"]
        ):
            return False, "Error: One or more cards not in hand."

        if top_card_id == bottom_card_id:
            return False, "Error: Cannot use the same card for both Top and Bottom."

        self.state["active_links"][task_id] = {
            "top": top_card_id,
            "bottom": bottom_card_id,
            "timestamp": datetime.now().isoformat(),
            "source": bound,
            "resolution_id": resolution_id,
        }

        self.state["hand"].remove(top_card_id)
        self.state["hand"].remove(bottom_card_id)

        self.save_state()
        return True, f"Task {task_id} linked."

    def resolve_task(self, task_id, is_completed=True, resolution_id=None, source=None):
        from services.combat_completion import resolve
        return resolve(self, task_id, resolution_id, is_completed, source)

    def transition_cards(self, task_id):
        link = self.state["active_links"].get(task_id)
        if not link:
            return False, "Task is not linked to any cards."

        self.cards_db.get(link["top"])
        self.cards_db.get(link["bottom"])

        # Move used cards to discard or lost (if Burn)
        for card_key in ["top", "bottom"]:
            card_id = link[card_key]
            card_data = self.cards_db.get(card_id)
            if card_data and card_data.get("is_burn"):
                self.state["lost"].append(card_id)
            else:
                self.state["discard"].append(card_id)

        del self.state["active_links"][task_id]
        return True, "Cards resolved."

    def short_rest(self):
        if any(op.get("phase") != "complete" for op in self.state.get("resolutions", {}).values()):
            return False, "Finish pending combat recovery before resting."
        if not self.state["discard"]:
            return False, "Discard pile empty."

        lost_card = random.choice(self.state["discard"])
        self.state["discard"].remove(lost_card)
        self.state["lost"].append(lost_card)

        # Reshuffle remaining discard cards into hand ensuring card IDs remain strictly unique
        existing_hand = set(self.state["hand"])
        for card_id in self.state["discard"]:
            if card_id not in existing_hand:
                self.state["hand"].append(card_id)
                existing_hand.add(card_id)
        self.state["discard"] = []

        self.save_state()
        return True, f"Rest Complete. Lost card: {lost_card}."


# Singleton-like instance access
_engine_instance = None


def get_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = BattleEngine()
    else:
        _engine_instance.load_state()  # Ensure fresh read from disk
    return _engine_instance
