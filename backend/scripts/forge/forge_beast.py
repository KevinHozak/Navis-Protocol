import os
import argparse
import json
from forge_character import get_engine_paths, establish_sector


def forge_beast(
    name,
    threat_level,
    beast_class,
    height="6'0\" (183 cm)",
    voice_id="en-US-RogerNeural",
    personality="A menacing abstract beast.",
):
    """Forges a new, high-fidelity beast folder and standardized dossiers."""

    # 1. Path & Sector Resolution
    paths = get_engine_paths()
    target_dir = os.path.join(paths["beasts_dir"], name)

    if not establish_sector(target_dir):
        return

    # Create SFX folder
    sfx_dir = os.path.join(target_dir, "SFX")
    os.makedirs(sfx_dir, exist_ok=True)
    print(f"📂 SFX SECTOR ESTABLISHED: {sfx_dir}")

    # 2. Forge Profile.md (Dossier)
    profile_md_content = f"""![[Portrait.png|portrait]]

# 👾 {name.title()}
**Type:** Abstract Obstacle / Beast
**Threat Level:** {threat_level}
**Class:** {beast_class}
**Height:** {height}

## 📜 Lore
[ ENTER HIGH-FIDELITY LORE HERE ]

## 🎨 Appearance & Visual Data
- **Height/Build:** {height}; [ DESCRIPTION ]
- **Form:** [ DESCRIPTION ]
- **Face:** [ DESCRIPTION ]
- **Visual Aura:** [ DESCRIPTION ]

## ⚔️ Combat Stats
- **STRENGTH:** [ LEVEL ]
- **AGILITY:** [ LEVEL ]
- **REGEN:** [ DESCRIPTION ]

## ⚡ Abilities
- **[ ABILITY NAME ]:** [ DESCRIPTION ]
- **[ ABILITY NAME ]:** [ DESCRIPTION ]

## 🛡️ Tactical Countermeasures
- **[ COUNTERMEASURE ]:** [ DESCRIPTION ]
- **[ COUNTERMEASURE ]:** [ DESCRIPTION ]

---
**STATUS:** `ACTIVE` ⚠️
"""

    with open(os.path.join(target_dir, "Profile.md"), "w", encoding="utf-8-sig") as f:
        f.write(profile_md_content)
    print("📜 DOSSIER FORGED: Profile.md")

    # 3. Forge Persona.json (Neural Manifest)
    persona_json = {
        "name": name,
        "role": beast_class,
        "voice": personality,
        "system_prompt": f"You are the {name}, an abstract {beast_class} that challenges the Keeper (Kevin). Your threat level is {threat_level}. Your personality is: {personality}. You manifest as a psychological or conceptual obstacle that must be overcome through tactical action and mental fortitude.",
        "context_injection": ["vitals", "journal_highlights", "realm"],
        "edge_tts_voice": voice_id,
        "sfx_triggers": {"on_appear": "SFX/Appear.mp3", "on_taunt": "SFX/Taunt.mp3"},
    }

    path = os.path.join(target_dir, "Persona.json")
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(persona_json, f, indent=4, ensure_ascii=False)
    print("🧠 NEURAL MANIFEST FORGED: Persona.json (with SFX triggers)")

    # 4. Forge Banter.json (Growls/Taunts)
    banter_json = {
        "name": name,
        "quotes": [
            "Your focus is flickering...",
            "The fog returns to claim you.",
            "You cannot outrun your own shadow.",
        ],
    }

    with open(os.path.join(target_dir, "Banter.json"), "w", encoding="utf-8-sig") as f:
        json.dump(banter_json, f, indent=4, ensure_ascii=False)
    print("💬 BANTER MANIFEST FORGED: Banter.json")

    print(f"✅ BEAST FORGE COMPLETE: {name.upper()} is active.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navis Protocol: Beast Forge")
    parser.add_argument("name", type=str, help="The name of the beast")
    parser.add_argument(
        "--threat", type=str, default="🟡 MEDIUM", help="The threat level of the beast"
    )
    parser.add_argument(
        "--class",
        dest="beast_class",
        type=str,
        default="Abstract Predator",
        help="The class of the beast",
    )
    parser.add_argument(
        "--height", type=str, default="6'0\" (183 cm)", help="The height of the beast"
    )
    parser.add_argument(
        "--voice", type=str, default="en-US-RogerNeural", help="The edge-tts voice ID"
    )
    parser.add_argument(
        "--personality",
        type=str,
        default="A menacing abstract beast.",
        help="A short personality description",
    )

    args = parser.parse_args()
    forge_beast(
        args.name,
        args.threat,
        args.beast_class,
        args.height,
        args.voice,
        args.personality,
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
