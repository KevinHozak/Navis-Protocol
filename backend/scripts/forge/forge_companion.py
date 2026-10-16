import os
import json
import argparse
from forge_character import (
    get_engine_paths,
    establish_sector,
    forge_persona,
    invalidate_sector_cache,
)


def forge_companion(
    name,
    role,
    home_realm,
    gender="Female",
    height="5'5\" (165 cm)",
    voice_id="en-IE-EmilyNeural",
    personality="A helpful tactical ally.",
    description="A detailed lore description.",
):
    """Forges a new, high-fidelity companion folder and standardized dossiers."""

    # 1. Path & Sector Resolution
    paths = get_engine_paths()
    target_dir = os.path.join(paths["companions_dir"], name)

    if not establish_sector(target_dir):
        return

    # 2. Forge Profile.md (Dossier)
    profile_md_content = f"""![[Portrait.png|portrait]]

# 🛡️ {name}

**Role:** {role}
**Gender:** {gender}
**Height:** {height}
**Home Realm:** {home_realm}
**Status:** Bonded

## 📜 Dossier
{description}

## 🧬 Resonance
{personality}

---
## 🏷️ Tags
`#companion`, `#realm/{home_realm.lower().replace(" ", "-")}`, `#role/{role.lower().replace(" ", "-")}`
"""

    with open(os.path.join(target_dir, "Profile.md"), "w", encoding="utf-8-sig") as f:
        f.write(profile_md_content)
    print("📜 DOSSIER FORGED: Profile.md")

    # 3. Forge Persona.json (Neural Manifest)
    system_prompt = f"You are {name}, a {role} native to {home_realm}. Your personality is: {personality}. You are a loyal companion to the Keeper (Kevin) and provide tactical insights and emotional support within the Navis Protocol framework."
    forge_persona(
        target_dir, name, role, home_realm, voice_id, personality, system_prompt
    )

    # 4. Forge XP.md (Progression)
    xp_md_content = f"""# 📈 XP Log: {name}

**Current Level:** 1
**Total XP:** 0

---

## 📜 Advancement History
- **INITIALIZATION:** +0 XP (Protocol Secured)
"""

    with open(os.path.join(target_dir, "XP.md"), "w", encoding="utf-8-sig") as f:
        f.write(xp_md_content)
    print("📈 PROGRESSION LOG FORGED: XP.md")

    # 5. Forge Banter.json
    banter_json = {
        "name": name,
        "quotes": [
            "Awaiting command, Keeper.",
            "The manifold is stable. For now.",
            "Synchronizing tactical data.",
        ],
    }

    with open(os.path.join(target_dir, "Banter.json"), "w", encoding="utf-8-sig") as f:
        json.dump(banter_json, f, indent=4, ensure_ascii=False)
    print("💬 BANTER MANIFEST FORGED: Banter.json")

    # 6. Initialize Central Stats
    stats_path = paths["stats_path"]
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8-sig") as f:
                stats_data = json.load(f)

            if "companions" not in stats_data:
                stats_data["companions"] = {}

            if name not in stats_data["companions"]:
                stats_data["companions"][name] = {"xp": 0, "level": 1}
                with open(stats_path, "w", encoding="utf-8-sig") as f:
                    json.dump(stats_data, f, indent=4, ensure_ascii=False)
                print("💎 CENTRAL LEDGER UPDATED: Companion Stats Initialized.")
        except Exception as e:
            print(f"⚠️ CENTRAL LEDGER ERROR: {e}")

    print(f"✅ COMPANION FORGE COMPLETE: {name.upper()} is active.")
    invalidate_sector_cache()
    print(
        f'🎨 VISUAL COMMAND: python "G:\\My Drive\\Agents\\Scripts\\generate_image.py" "Cinematic portrait of {name}..." -f "{target_dir}\\Portrait.png" -a "1:1"'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navis Protocol: Companion Forge")
    parser.add_argument("name", type=str, help="The name of the companion")
    parser.add_argument(
        "--role",
        type=str,
        default="Tactical Ally",
        help="The role/class of the companion",
    )
    parser.add_argument(
        "--gender", type=str, default="Female", help="The gender of the companion"
    )
    parser.add_argument(
        "--height",
        type=str,
        default="5'5\" (165 cm)",
        help="The height of the companion",
    )
    parser.add_argument(
        "--realm", type=str, default="Default", help="The home realm of the companion"
    )
    parser.add_argument(
        "--voice", type=str, default="en-IE-EmilyNeural", help="The edge-tts voice ID"
    )
    parser.add_argument(
        "--personality",
        type=str,
        default="A helpful tactical ally.",
        help="A short personality description",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="A detailed lore description.",
        help="A rich lore description",
    )

    args = parser.parse_args()
    forge_companion(
        args.name,
        args.role,
        args.realm,
        args.gender,
        args.height,
        args.voice,
        args.personality,
        args.description,
    )


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
