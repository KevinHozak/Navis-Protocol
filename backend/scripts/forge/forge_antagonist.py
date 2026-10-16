import os
import argparse
import json
from forge_character import get_engine_paths, establish_sector, forge_persona


def forge_antagonist(
    name,
    classification,
    origin,
    gender="Female",
    height="5'5\" (165 cm)",
    voice_id="en-US-ChristopherNeural",
    personality="A formidable professional antagonist.",
):
    """Forges a new, high-fidelity antagonist folder and standardized dossiers."""

    # 1. Path & Sector Resolution
    paths = get_engine_paths()
    target_dir = os.path.join(paths["antagonists_dir"], name)

    if not establish_sector(target_dir):
        return

    # 2. Forge Profile.md (Dossier)
    profile_md_content = f"""![[Portrait.png|portrait]]

# 🌫️ {name}
**Classification:** {classification}
**Gender:** {gender}
**Height:** {height}
**Origin:** {origin}
**Mandate Obstacle:** [ e.g., 🧭 The Commander's Triage ]

---

## 📜 Profile
[ ENTER HIGH-FIDELITY DESCRIPTION HERE ]

## 🎨 Appearance & Visual Data
- **Height/Build:** {height} {gender}; [ DESCRIPTION ]
- **Hair:** [ DESCRIPTION ]
- **Eyes:** [ DESCRIPTION ]
- **Signature Attire:** [ DESCRIPTION ]
- **Visual Aura:** [ DESCRIPTION ]

---

## ⚔️ Tactical Patterns
- **[ PATTERN NAME ]:** [ DESCRIPTION OF BEHAVIOR ]
- **[ PATTERN NAME ]:** [ DESCRIPTION OF BEHAVIOR ]

---

## 🎭 Known Weaknesses (Masks)
- **[ WEAKNESS NAME ]:** "[ COUNTER-DIALOGUE OR STRATEGY ]"

---
*Success in navigating {name} prevents the [DEBUFF] condition.*
"""

    with open(os.path.join(target_dir, "Profile.md"), "w", encoding="utf-8-sig") as f:
        f.write(profile_md_content)
    print("📜 DOSSIER FORGED: Profile.md")

    # 3. Forge Persona.json (Neural Manifest)
    system_prompt = f"You are {name}, a {classification} from {origin}. Your persona is: {personality}. You act as an antagonist to the Keeper (Kevin) in a professional or personal context, presenting obstacles, friction, or technical challenges that require tactical triage."
    forge_persona(
        target_dir, name, classification, origin, voice_id, personality, system_prompt
    )

    # 4. Forge Banter.json (Taunts)
    banter_json = {
        "name": name,
        "quotes": [
            "This task is missing critical documentation.",
            "I'll need you to focus on this minor detail immediately.",
            "Is the release really stable enough for deployment?",
        ],
    }

    with open(os.path.join(target_dir, "Banter.json"), "w", encoding="utf-8-sig") as f:
        json.dump(banter_json, f, indent=4, ensure_ascii=False)
    print("💬 BANTER MANIFEST FORGED: Banter.json")

    print(f"✅ ANTAGONIST FORGE COMPLETE: {name.upper()} is active.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navis Protocol: Antagonist Forge")
    parser.add_argument("name", type=str, help="The name of the antagonist")
    parser.add_argument(
        "--class",
        dest="classification",
        type=str,
        default="Professional Antagonist",
        help="The classification of the antagonist",
    )
    parser.add_argument(
        "--origin", type=str, default="Unknown", help="The origin realm or organization"
    )
    parser.add_argument(
        "--gender", type=str, default="Female", help="The gender of the antagonist"
    )
    parser.add_argument(
        "--height",
        type=str,
        default="5'5\" (165 cm)",
        help="The height of the antagonist",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="en-US-ChristopherNeural",
        help="The edge-tts voice ID",
    )
    parser.add_argument(
        "--personality",
        type=str,
        default="A formidable professional antagonist.",
        help="A short personality description",
    )

    args = parser.parse_args()
    forge_antagonist(
        args.name,
        args.classification,
        args.origin,
        args.gender,
        args.height,
        args.voice,
        args.personality,
    )


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
