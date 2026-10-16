import os
import argparse
from forge_character import get_engine_paths, establish_sector, forge_persona


def forge_resident(
    name,
    realm,
    role,
    gender="Female",
    height="5'5\" (165 cm)",
    voice_id="en-IE-EmilyNeural",
    personality="A helpful local resident.",
    backstory="",
    website="",
    youtube_channel="",
    youtube_handle="",
):
    """Forges a new, high-fidelity resident folder and standardized dossiers."""

    # 1. Path & Sector Resolution
    paths = get_engine_paths()
    target_dir = os.path.join(paths["residents_dir"], name)

    if not establish_sector(target_dir):
        return

    # 2. Forge Profile.md (Dossier)
    profile_md_content = f"""![[Portrait.png|portrait]]

# 👥 {name}

**Realm:** {realm}
**Role:** {role}
**Gender:** {gender}
**Height:** {height}
**Status:** Friendly

## 📜 Dossier
{backstory if backstory else "[ ENTER HIGH-FIDELITY DESCRIPTION HERE ]"}

## 🎨 Appearance & Visual Data
- **Height/Build:** {height} {gender}; [ DESCRIPTION ]
- **Hair:** [ DESCRIPTION ]
- **Eyes:** [ DESCRIPTION ]
- **Signature Attire:** [ DESCRIPTION ]
- **Distinctive Features:** [ DESCRIPTION ]
- **Visual Aura:** Professional, high-fidelity, [ THEMATIC AURA ].

## 🏘️ Regional Influence
- **Location:** [ SPECIFIC AREA ]
- **Faction:** [ FACTION ]
- **Trade:** [ SERVICES/RESOURCES ]

## 🧠 Intelligence
{personality}
"""
    if website:
        profile_md_content += f"\n**Website:** {website}"
    if youtube_channel:
        profile_md_content += f"\n**YouTube Channel:** {youtube_channel}"
    if youtube_handle:
        profile_md_content += f"\n**YouTube Handle:** {youtube_handle}"

    profile_md_content += f"""

---
## 🏷️ Tags
`#resident`, `#realm/{realm.lower().replace(" ", "-")}`, `#role/{role.lower().replace(" ", "-")}`
"""

    with open(os.path.join(target_dir, "Profile.md"), "w", encoding="utf-8-sig") as f:
        f.write(profile_md_content)
    print("📜 DOSSIER FORGED: Profile.md")

    # 3. Forge Persona.json (Neural Manifest)
    system_prompt = f"You are {name}, a {role} residing in the {realm}. Your personality is: {personality}. You provide local intelligence, narrative flavor, and situational insights to the Keeper (Kevin)."
    forge_persona(target_dir, name, role, realm, voice_id, personality, system_prompt)

    print(f"✅ RESIDENT FORGE COMPLETE: {name.upper()} is active.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navis Protocol: Resident Forge")
    parser.add_argument("name", type=str, help="The name of the resident")
    parser.add_argument(
        "--realm",
        type=str,
        default="Earth",
        help="The realm the resident is anchored to",
    )
    parser.add_argument(
        "--role",
        type=str,
        default="Local Contact",
        help="The role/occupation of the resident",
    )
    parser.add_argument(
        "--gender", type=str, default="Female", help="The gender of the resident"
    )
    parser.add_argument(
        "--height",
        type=str,
        default="5'5\" (165 cm)",
        help="The height of the resident",
    )
    parser.add_argument(
        "--voice", type=str, default="en-IE-EmilyNeural", help="The edge-tts voice ID"
    )
    parser.add_argument(
        "--personality",
        type=str,
        default="A helpful local resident.",
        help="A short personality description",
    )
    parser.add_argument(
        "--backstory", type=str, default="", help="Detailed backstory or dossier info"
    )
    parser.add_argument("--website", type=str, default="", help="Official website URL")
    parser.add_argument(
        "--youtube-channel", type=str, default="", help="YouTube channel URL"
    )
    parser.add_argument(
        "--youtube-handle", type=str, default="", help="YouTube @handle"
    )

    args = parser.parse_args()
    forge_resident(
        args.name,
        args.realm,
        args.role,
        args.gender,
        args.height,
        args.voice,
        args.personality,
        args.backstory,
        args.website,
        args.youtube_channel,
        args.youtube_handle,
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
