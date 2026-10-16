import os
import json


def build_sector_cache(navis_root=None):
    if not navis_root:
        navis_root = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")

    cache_dir = os.path.join(navis_root, "Bridge", ".navis_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, "sector_cache.json")

    cache = {
        "sectors": {
            "MISSIONS": {"Main": [], "Side": []},
            "COMPANIONS": {"Companions": []},
            "RESIDENTS": {"Residents": []},
            "OBSTACLES": {"Antagonists": [], "Beasts": []},
            "REALMS": {"Discoveries": []},
            "SYNTHESIS_LAB": {"Archival": []},
            "REFLECTION_CHAMBER": {"Mental": []},
            "IRON_SANCTUM": {"Physical": []},
        }
    }

    # 1. Missions
    ops_dir = os.path.join(navis_root, "Operations")
    if os.path.exists(ops_dir):
        for region in os.listdir(ops_dir):
            region_dir = os.path.join(ops_dir, region)
            if os.path.isdir(region_dir):
                for m_type in ["Main", "Side"]:
                    type_dir = os.path.join(region_dir, m_type)
                    if os.path.exists(type_dir):
                        for mission in os.listdir(type_dir):
                            m_dir = os.path.join(type_dir, mission)
                            if os.path.isdir(m_dir):
                                p = os.path.join(m_dir, "Mission.md")
                                if os.path.exists(p):
                                    cache["sectors"]["MISSIONS"][m_type].append(
                                        {"name": mission, "path": p, "region": region}
                                    )

    # Helper for generic entities
    def scan_entities(base_path, category, subcategory, md_name="Profile.md"):
        full_path = os.path.join(navis_root, base_path)
        if os.path.exists(full_path):
            for item in os.listdir(full_path):
                item_dir = os.path.join(full_path, item)
                if os.path.isdir(item_dir):
                    p = os.path.join(item_dir, md_name)
                    if os.path.exists(p):
                        cache["sectors"][category][subcategory].append(
                            {"name": item, "path": p}
                        )

    # 2. Companions & Residents
    scan_entities("Companions", "COMPANIONS", "Companions")
    scan_entities("Residents", "RESIDENTS", "Residents")

    # 3. Obstacles
    scan_entities(os.path.join("Obstacles", "Antagonists"), "OBSTACLES", "Antagonists")
    scan_entities(os.path.join("Obstacles", "Beasts"), "OBSTACLES", "Beasts")

    # 4. Realms
    scan_entities("Realms", "REALMS", "Discoveries", "Realm.md")

    def scan_files(base_path, category, subcategory):
        full_path = os.path.join(navis_root, base_path)
        if os.path.exists(full_path):
            for item in os.listdir(full_path):
                if item in [
                    ".navis_cache",
                    "Profile.md",
                    "Realm.md",
                    "Tasks.md",
                    "SFX",
                    "Landscape.png",
                    "Portrait.png",
                ]:
                    continue
                item_path = os.path.join(full_path, item)
                if os.path.isdir(item_path):
                    cache["sectors"][category][subcategory].append(
                        {"name": item, "path": item_path, "type": "directory"}
                    )
                elif item.endswith(".md"):
                    name = item.replace(".md", "")
                    cache["sectors"][category][subcategory].append(
                        {"name": name, "path": item_path, "type": "file"}
                    )

    # 5. Facilities
    scan_files("Synthesis Lab", "SYNTHESIS_LAB", "Archival")
    scan_files("Reflection Chamber", "REFLECTION_CHAMBER", "Mental")
    scan_files("Iron Sanctum", "IRON_SANCTUM", "Physical")

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4)

    print(f"Built sector_cache.json at {cache_path}")
    return cache


if __name__ == "__main__":
    build_sector_cache()
