import os
import json
import sys

# --- Calibrate Output for High-Fidelity Unicode ---
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def get_engine_paths():
    """Resolves centralized engine and manifold paths."""
    # Resolve protocol root using environment variable or default
    protocol_root = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
    settings_path = os.path.join(protocol_root, "Bridge", "settings.json")

    paths = {
        "companions_dir": os.path.join(protocol_root, "Companions"),
        "residents_dir": os.path.join(protocol_root, "Residents"),
        "realms_dir": os.path.join(protocol_root, "Realms"),
        "obstacles_dir": os.path.join(protocol_root, "Obstacles"),
        "antagonists_dir": os.path.join(protocol_root, "Obstacles", "Antagonists"),
        "beasts_dir": os.path.join(protocol_root, "Obstacles", "Beasts"),
        "stats_path": os.path.join(protocol_root, "Bridge", "CompanionStats.json"),
        "settings_path": settings_path,
    }

    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8-sig") as f:
                settings = json.load(f)
                s_paths = settings.get("paths", {})
                if "companions_dir" in s_paths:
                    paths["companions_dir"] = s_paths["companions_dir"]
                if "residents_dir" in s_paths:
                    paths["residents_dir"] = s_paths["residents_dir"]
                if "realms_dir" in s_paths:
                    paths["realms_dir"] = s_paths["realms_dir"]
                if "obstacles_dir" in s_paths:
                    paths["obstacles_dir"] = s_paths["obstacles_dir"]
                    paths["antagonists_dir"] = os.path.join(
                        s_paths["obstacles_dir"], "Antagonists"
                    )
                    paths["beasts_dir"] = os.path.join(
                        s_paths["obstacles_dir"], "Beasts"
                    )
                if "companion_stats" in s_paths:
                    paths["stats_path"] = s_paths["companion_stats"]
        except Exception:
            pass

    return paths


def establish_sector(target_dir):
    """Creates the target directory if it doesn't exist."""
    if os.path.exists(target_dir):
        print(f"⚠️ TARGET SECTOR OCCUPIED: {target_dir}")
        return False
    os.makedirs(target_dir, exist_ok=True)
    print(f"📂 SECTOR ESTABLISHED: {target_dir}")
    return True


def forge_persona(target_dir, name, role, realm, voice_id, personality, system_prompt):
    """Generates a high-fidelity Persona.json manifest."""
    persona_json = {
        "name": name,
        "role": role,
        "voice": personality,
        "system_prompt": system_prompt,
        "context_injection": ["vitals", "journal_highlights", "realm"],
        "edge_tts_voice": voice_id,
    }

    path = os.path.join(target_dir, "Persona.json")
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(persona_json, f, indent=4, ensure_ascii=False)
    print("🧠 NEURAL MANIFEST FORGED: Persona.json")
    return persona_json


# --- Visual Standards (Mandatory Aspect Ratios) ---
PORTRAIT_ASPECT = "1:1"
LANDSCAPE_ASPECT = "16:9"


def invalidate_sector_cache():
    """Invalidates the Navis Protocol frontend sector cache."""
    protocol_root = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
    cache_path = os.path.join(
        protocol_root, "Bridge", ".navis_cache", "sector_cache.json"
    )
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print("🔄 SECTOR CACHE INVALIDATED: Will rebuild on next portal load.")
        except Exception as e:
            print(f"⚠️ FAILED TO INVALIDATE CACHE: {e}")


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
