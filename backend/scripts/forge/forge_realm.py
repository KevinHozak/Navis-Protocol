import os
import json
import argparse
import sys

# --- Calibrate Output for High-Fidelity Unicode ---
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from forge_character import get_engine_paths, establish_sector


def forge_realm(name, atmosphere, description="A detailed lore description."):
    """Forges a new, high-fidelity realm folder and standardized dossiers."""

    # 1. Path & Sector Resolution
    paths = get_engine_paths()
    target_dir = os.path.join(paths["realms_dir"], name)

    if not establish_sector(target_dir):
        return

    # 2. Forge Realm.md (Dossier)
    realm_md_content = f"""![[Landscape.png|header]]

# 🌌 {name}

**Atmosphere:** {atmosphere}
**Status:** Discovered

## 📜 Realm Overview
{description}

---
## 🏷️ Tags
`#realm`, `#atmosphere/{atmosphere.lower().replace(" ", "-")}`
"""

    with open(os.path.join(target_dir, "Realm.md"), "w", encoding="utf-8-sig") as f:
        f.write(realm_md_content)
    print("📜 DOSSIER FORGED: Realm.md")

    # 2.5 Forge realm_data.json
    realm_data_json = {
        "name": name,
        "description": description,
        "tags": ["#realm", f"#atmosphere/{atmosphere.lower().replace(' ', '-')}"],
        "natives": [],
    }
    with open(
        os.path.join(target_dir, "realm_data.json"), "w", encoding="utf-8-sig"
    ) as f:
        json.dump(realm_data_json, f, indent=4, ensure_ascii=False)
    print("💾 DATA MANIFEST FORGED: realm_data.json")

    # 3. Forge theme.json (UI Customization)
    theme_json = {
        "name": name,
        "accent": "#00d4ff",
        "bg": "#0a0a0a",
        "sidebar": "#111111",
    }

    with open(os.path.join(target_dir, "theme.json"), "w", encoding="utf-8-sig") as f:
        json.dump(theme_json, f, indent=4, ensure_ascii=False)
    print("🎨 UI MANIFEST FORGED: theme.json")

    # 4. Forge Encounters.json (Bestiary Template)
    encounters_json = {
        "metadata": {"realm": name, "version": "1.0", "atmosphere": atmosphere},
        "encounters": {
            "tier_1_grunts": [
                {
                    "id": f"{name[:2].upper()}-G1",
                    "name": "Placeholder Grunt",
                    "level": 1,
                    "type": "Grunt",
                    "description": "Standard territory unit.",
                    "stats": {"HP": 10, "ATK": 2, "DEF": 1},
                    "loot_table": ["Generic Component"],
                }
            ],
            "tier_2_elites": [
                {
                    "id": f"{name[:2].upper()}-E1",
                    "name": "Placeholder Elite",
                    "level": 3,
                    "type": "Elite",
                    "description": "Enhanced field operative.",
                    "stats": {"HP": 25, "ATK": 5, "DEF": 4},
                    "loot_table": ["Advanced Component", "Focus Shard"],
                }
            ],
            "tier_3_bosses": [
                {
                    "id": f"{name[:2].upper()}-B1",
                    "name": "Placeholder Boss",
                    "level": 5,
                    "type": "Boss",
                    "description": "Regional threat-leader.",
                    "stats": {"HP": 100, "ATK": 12, "DEF": 10},
                    "special_mechanic": "None",
                    "loot_table": ["Master Component", "Major XP Core"],
                }
            ],
        },
    }

    with open(
        os.path.join(target_dir, "Encounters.json"), "w", encoding="utf-8-sig"
    ) as f:
        json.dump(encounters_json, f, indent=4, ensure_ascii=False)
    print("⚔️ BESTIARY FORGED: Encounters.json")

    print(f"✅ REALM FORGE COMPLETE: {name.upper()} is active.")
    print(
        f'🎨 VISUAL COMMAND: python "G:\\My Drive\\Agents\\Scripts\\generate_image.py" "Cinematic landscape of {name}..." -f "{target_dir}\\Landscape.png" -a "16:9"'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navis Protocol: Realm Forge")
    parser.add_argument("name", type=str, help="The name of the realm")
    parser.add_argument(
        "--atmosphere",
        type=str,
        default="Unknown",
        help="The thematic atmosphere of the realm",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="A detailed lore description.",
        help="A rich lore description",
    )

    args = parser.parse_args()
    forge_realm(args.name, args.atmosphere, args.description)


# --- CACHE INVALIDATION PROTOCOL ---
def invalidate_cache():
    import os

    if os.environ.get("NAVIS_FORGE_STAGING") == "1":
        return
    cache_path = os.path.join(os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault"), "Bridge", ".navis_cache", "sector_cache.json")
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print("💥 SECTOR CACHE INVALIDATED: Force rebuild on next UI load.")
        except:
            pass


invalidate_cache()
