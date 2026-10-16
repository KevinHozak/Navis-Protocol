import os
import re
import json
from datetime import datetime

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Protocol")
SETTINGS_FILE = os.path.join(NAVIS_ROOT, "Bridge", "settings.json")


def execute_realm_hop(new_realm_name, squad_names=None):
    """
    Natively executes the Moongate anchor protocol.
    Replaces Engine/rpg/anchor_realm.py and Engine/rpg/update_realm_stats.py
    """
    if not os.path.exists(SETTINGS_FILE):
        raise Exception(f"Error: settings.json not found in {SETTINGS_FILE}")

    with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
        settings.get("paths", {})

    status_path = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
    comp_dir = os.path.join(NAVIS_ROOT, "Companions")
    stats_path = os.path.join(NAVIS_ROOT, "Bridge", "CompanionStats.json")
    realm_stats_path = os.path.join(NAVIS_ROOT, "Bridge", "RealmStats.json")
    journal_root = os.path.join(NAVIS_ROOT, "Journal")
    realms_dir = os.path.join(NAVIS_ROOT, "Realms")

    print(f"🌀 ANCHORING: Calibrating moongate for {new_realm_name}...")

    # 1. Load Current Status and Stats
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8-sig") as f:
            status = json.load(f)
    else:
        status = {
            "current_realm": "Unknown",
            "squad": [],
            "current_antagonist": None,
            "current_beast": None,
        }

    companion_stats = {}
    if os.path.exists(stats_path):
        with open(stats_path, "r", encoding="utf-8-sig") as f:
            companion_stats = json.load(f).get("companions", {})

    status["current_realm"] = new_realm_name

    # Preserve threats
    antagonist_name = status.get("current_antagonist")
    beast_name = status.get("current_beast")

    new_squad = []

    # 2. Squad Selection Logic
    if squad_names and len(squad_names) == 3:
        for i, name in enumerate(squad_names):
            profile_path = os.path.join(comp_dir, name, "Profile.md")
            role = "Active Personnel"
            if os.path.exists(profile_path):
                with open(profile_path, "r", encoding="utf-8-sig") as pf:
                    content = pf.read()
                    role_match = re.search(r"- \*\*Role:\*\* (.*?)\n", content)
                    if role_match:
                        role = role_match.group(1).strip()

            entry_xp = companion_stats.get(name, {}).get("xp", 0)
            new_squad.append(
                {
                    "name": name,
                    "role": role,
                    "is_vanguard": (i == 0),
                    "entry_xp": entry_xp,
                }
            )
        print(f"   ⚔️ SQUAD ASSEMBLED: {', '.join(squad_names)}")
    else:
        # Fallback to legacy native detection
        native_companion = None
        if os.path.exists(comp_dir):
            for companion in os.listdir(comp_dir):
                if companion.startswith("."):
                    continue
                profile_path = os.path.join(comp_dir, companion, "Profile.md")
                if os.path.exists(profile_path):
                    with open(profile_path, "r", encoding="utf-8-sig") as pf:
                        content = pf.read()
                        home_match = re.search(
                            r"- \*\*Home Realm:\*\* (?:\[\[)?(.*?)(?:\]\])?\n", content
                        )
                        if (
                            home_match
                            and new_realm_name.upper()
                            in home_match.group(1).strip().upper()
                        ):
                            role_match = re.search(r"- \*\*Role:\*\* (.*?)\n", content)
                            native_companion = {
                                "name": companion,
                                "role": role_match.group(1).strip()
                                if role_match
                                else "Active",
                                "is_vanguard": True,
                            }
                            break

                        realm_match = re.search(
                            r"Status:.*?(?:🗼|\])\s*(.*)", content, re.IGNORECASE
                        )
                        if (
                            realm_match
                            and new_realm_name.upper()
                            in realm_match.group(1).strip().upper()
                        ):
                            role_match = re.search(r"- \*\*Role:\*\* (.*?)\n", content)
                            native_companion = {
                                "name": companion,
                                "role": role_match.group(1).strip()
                                if role_match
                                else "Active",
                                "is_vanguard": True,
                            }
                            break
        if native_companion:
            entry_xp = companion_stats.get(native_companion["name"], {}).get("xp", 0)
            native_companion["entry_xp"] = entry_xp
            new_squad.append(native_companion)
            for m in status.get("squad", []):
                if m["name"] != native_companion["name"]:
                    m["is_vanguard"] = False
                    if "entry_xp" not in m:
                        m["entry_xp"] = companion_stats.get(m["name"], {}).get("xp", 0)
                    new_squad.append(m)
                if len(new_squad) >= 3:
                    break
        else:
            new_squad = status.get("squad", [])
            for m in new_squad:
                if "entry_xp" not in m:
                    m["entry_xp"] = companion_stats.get(m["name"], {}).get("xp", 0)

    # Add Keeper entry XP
    status["keeper_entry_xp"] = companion_stats.get("Keeper", {}).get("xp", 0)

    status["squad"] = new_squad
    status["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    # 3. Update Status Manifold
    with open(status_path, "w", encoding="utf-8-sig") as f:
        json.dump(status, f, indent=4, ensure_ascii=False)

    try:
        from services.sync_engine import sync_status_to_today_journal

        sync_status_to_today_journal()
    except Exception as e:
        print(f"Failed to sync journal on realm hop: {e}")

    # 4. Update Current Journal Entry
    today_str = datetime.now().strftime("%Y-%m-%d")
    year, month = today_str.split("-")[0], today_str.split("-")[1]
    journal_path = os.path.join(journal_root, year, month, f"{today_str}.md")

    if os.path.exists(journal_path):
        try:
            with open(journal_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            realm_desc = "Exploration active."
            realm_md = os.path.join(realms_dir, status["current_realm"], "Realm.md")
            if os.path.exists(realm_md):
                with open(realm_md, "r", encoding="utf-8-sig") as wf:
                    w_content = wf.read()
                    role_match = re.search(
                        r"## 👤 REALM TITLE:.*?\n\*\*Role:\*\*\s*(.*?)(?=\n##|\Z)",
                        w_content,
                        re.DOTALL,
                    )
                    if role_match:
                        realm_desc = role_match.group(1).strip()

            # Robust replacement for bulleted metadata lines
            content = re.sub(
                r"[ \t]*-\s*(?:\*\*)?🌀 Realm:.*",
                f'- **🌀 Realm:** {status["current_realm"]}',
                content,
            )

            # Handle Active Squad - potentially replacing a block
            squad_block = "- **🛡️ Active Squad**\n"
            for m in new_squad:
                squad_block += f"    - {m['name']}\n"

            # Replace the old squad block.
            content = re.sub(
                r"- (?:\*\*)?🛡️ Active Squad(?:\*\*)?\n(?:    - .*\n?)*",
                squad_block,
                content,
            )

            # Update or Inject Threats
            threat_block = f"- **👹 Antagonist:** {antagonist_name or 'None'}\n"
            threat_block += f"- **👾 Prime Beast:** {beast_name or 'None'}\n"

            if "- **👹 Daily Antagonist:**" in content:
                content = re.sub(
                    r"- \*\*👹 Daily Antagonist:\*\*.*?\n- \*\*👾 Prime Beast:\*\*.*?\n",
                    threat_block,
                    content,
                )
            elif "- **👹 Antagonist:**" in content:
                content = re.sub(
                    r"- \*\*👹 Antagonist:\*\*.*?\n- \*\*👾 Prime Beast:\*\*.*?\n",
                    threat_block,
                    content,
                )
            else:
                # Inject after squad block
                content = content.replace(squad_block, squad_block + threat_block)

            # Update REALM INTELLIGENCE if it exists
            if "**📜 REALM INTELLIGENCE:**" in content:
                content = re.sub(
                    r"([ \t]*-\s*\*\*📜 REALM INTELLIGENCE:).*",
                    f"\\1** {realm_desc}",
                    content,
                )

            # Clean up any potential debris
            content = re.sub(
                r"\*\* (Exploration active\.|Ritual Architect\.).*?--- \*\*Role:\*\*",
                "** \\1",
                content,
                flags=re.DOTALL,
            )
            with open(journal_path, "w", encoding="utf-8-sig") as f:
                f.write(content)
            print("   ✅ Journal entry synchronized.")
        except Exception as e:
            print(f"   ⚠️ WARNING: Failed to update journal: {e}")

    # 5. Trigger update_realm_stats logic natively
    if os.path.exists(realm_stats_path):
        with open(realm_stats_path, "r", encoding="utf-8-sig") as f:
            stats = json.load(f)
    else:
        stats = {"visit_counts": {}, "history": [], "last_updated": ""}

    visit_counts = stats.get("visit_counts", {})
    history = stats.get("history", [])

    realm_id = new_realm_name.title()
    visit_counts[realm_id] = visit_counts.get(realm_id, 0) + 1
    history.append(realm_id)

    stats["visit_counts"] = visit_counts
    stats["history"] = history
    stats["last_updated"] = today_str

    with open(realm_stats_path, "w", encoding="utf-8-sig") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

    print(f"✅ ANCHOR STABLE: Welcome to {new_realm_name.upper()}.")

    # Generate fresh squad banter for the new realm!
    try:
        from services.banter_generator import generate_squad_banter

        generate_squad_banter(count=3)
    except Exception as e:
        print(f"⚠️ Error generating banter after realm hop: {e}")

    return {
        "status": "success",
        "message": f"Successfully anchored to {new_realm_name}.",
    }
