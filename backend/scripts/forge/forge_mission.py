import os
import json
import argparse
import sys

# --- Calibrate Output for High-Fidelity Unicode ---
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def forge_mission(name, region, mission_type, xp_reward):
    """Forges a new, high-fidelity mission folder and standardized files."""

    # 1. Path Resolution
    project_root = r"G:\My Drive\Navis-Vault"
    settings_path = os.path.join(project_root, "Bridge", "settings.json")
    status_path = os.path.join(project_root, "Bridge", "status.json")

    operations_dir = None
    current_location = None

    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8-sig") as f:
            settings = json.load(f)
            operations_dir = settings.get("paths", {}).get("operations_dir")

    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8-sig") as f:
            status = json.load(f)
            current_location = status.get("location")

    if not operations_dir:
        operations_dir = os.path.join(project_root, "Operations")

    # If region is the default placeholder, use current_location
    if region == "#area/realm" and current_location:
        region = current_location

    # Mapping region to sub-folder (The Five Pillars) and tag
    pillar_map = {
        "Sanctum": ("The Sanctum", "#area/self"),
        "The Sanctum": ("The Sanctum", "#area/self"),
        "Domestic": ("The Domestic Breach", "#area/home"),
        "The Domestic Breach": ("The Domestic Breach", "#area/home"),
        "Front": ("The High-Velocity Front", "#area/office"),
        "The High-Velocity Front": ("The High-Velocity Front", "#area/office"),
        "Gauntlet": ("The Bureaucratic Gauntlet", "#area/finance"),
        "The Bureaucratic Gauntlet": ("The Bureaucratic Gauntlet", "#area/finance"),
        "Outland": ("The Kinetic Outland", "#area/world"),
        "The Kinetic Outland": ("The Kinetic Outland", "#area/world"),
    }

    pillar, tag = pillar_map.get(region, (region, region))

    # Determine Sub-folder (Main or Side)
    sub = "Main" if mission_type.lower() in ["epic", "main"] else "Side"

    target_dir = os.path.join(operations_dir, pillar, sub, name)

    if os.path.exists(target_dir):
        print(f"⚠️ TARGET SECTOR OCCUPIED: {target_dir}")
        return

    os.makedirs(target_dir, exist_ok=True)
    print(f"📂 SECTOR ESTABLISHED: {target_dir}")

    # 2. Forge Mission.md (Dossier)
    mission_md_content = f"""# 🏹 {name}

**Region:** {tag}
**Type:** {sub}

## 📜 Mission Parameters
[ ENTER STRATEGIC OVERVIEW HERE ]

## ⚔️ Tactical Objectives
- [ ] **Phase 1: Initial Reconnaissance**
    - [ ] [ TASK ]
- [ ] **Phase 2: Tactical Engagement**
    - [ ] [ TASK ]

---

## 🏆 Rewards
- **+{xp_reward} XP** to the Keeper.
- [ ADDITIONAL REWARDS ]

---

## 🏷️ Tags
`{tag}`, `#type/{sub.lower()}`, `#status/active`
"""

    with open(os.path.join(target_dir, "Mission.md"), "w", encoding="utf-8-sig") as f:
        f.write(mission_md_content)
    print("📜 DOSSIER FORGED: Mission.md")

    # 3. Forge Data.json (Manifest)
    data_json = {
        "name": name,
        "region": tag,
        "type": sub,
        "status": "Active",
        "xp_reward": xp_reward,
        "description": "Tactical objective initialized via Forge.",
    }

    with open(os.path.join(target_dir, "Data.json"), "w", encoding="utf-8-sig") as f:
        json.dump(data_json, f, indent=4, ensure_ascii=False)
    print("💎 MANIFEST FORGED: Data.json")

    print(f"✅ MISSION FORGE COMPLETE: {name.upper()} is active.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navis Protocol: Mission Forge")
    parser.add_argument("name", type=str, help="The name of the mission")
    parser.add_argument(
        "--region",
        type=str,
        default="#area/realm",
        help="The region tag (e.g., #area/self)",
    )
    parser.add_argument(
        "--type", type=str, default="Quest", help="The mission type (Quest, Epic, side)"
    )
    parser.add_argument("--xp", type=int, default=100, help="The XP reward")

    args = parser.parse_args()
    forge_mission(args.name, args.region, args.type, args.xp)


# --- CACHE INVALIDATION PROTOCOL ---
def invalidate_cache():
    import os

    cache_path = r"G:\My Drive\Navis-Vault\Bridge\.navis_cache\sector_cache.json"
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print("💥 SECTOR CACHE INVALIDATED: Force rebuild on next UI load.")
        except:
            pass


invalidate_cache()
