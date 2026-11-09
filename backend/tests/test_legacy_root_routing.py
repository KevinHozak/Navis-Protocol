"""Legacy routing checks: temporary data only, no providers or child processes."""
import builtins
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from types import ModuleType

import pytest

BACKEND = Path(__file__).resolve().parents[1]
DEFAULT = r"G:\My Drive\Navis-Vault"
FORGE = ("character", "mission", "antagonist", "resident", "beast", "companion", "realm")


def forbidden(*args, **kwargs):
    raise AssertionError("Live integration/process access forbidden")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.delenv("NAVIS_FORGE_STAGING", raising=False)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    fake = ModuleType("yt_dlp")
    fake.YoutubeDL = forbidden
    monkeypatch.setitem(sys.modules, "yt_dlp", fake)
    # Every application data access must stay in this test's temporary root.
    original_open, exists = builtins.open, os.path.exists
    remove, makedirs = os.remove, os.makedirs

    def check(path):
        assert Path(path).resolve().is_relative_to(tmp_path.resolve()), path

    def guarded_open(path, *args, **kwargs):
        check(path)
        return original_open(path, *args, **kwargs)

    def guarded_exists(path):
        check(path)
        return exists(path)

    def guarded_remove(path):
        check(path)
        return remove(path)

    def guarded_makedirs(path, *args, **kwargs):
        check(path)
        return makedirs(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(os.path, "exists", guarded_exists)
    monkeypatch.setattr(os, "remove", guarded_remove)
    monkeypatch.setattr(os, "makedirs", guarded_makedirs)


def load_forge(monkeypatch, kind):
    helper = ModuleType("forge_character")
    helper.__dict__.update(runpy.run_path(str(BACKEND / "scripts/forge/forge_character.py")))
    monkeypatch.setitem(sys.modules, "forge_character", helper)
    return runpy.run_path(str(BACKEND / f"scripts/forge/forge_{kind}.py"))


@pytest.mark.parametrize("kind", FORGE)
def test_forge_import_and_explicit_invalidation_use_selected_root(tmp_path, monkeypatch, kind):
    root = tmp_path / "Selected Vault 雪"
    other = tmp_path / "Other Vault"
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    caches = [r / "Bridge/.navis_cache/sector_cache.json" for r in (root, other)]
    for cache in caches:
        cache.parent.mkdir(parents=True)
        cache.write_text("canary", encoding="utf-8")
    module = load_forge(monkeypatch, kind)
    assert not caches[0].exists()
    assert caches[1].read_text() == "canary"
    caches[0].write_text("again")
    module["invalidate_cache"]()
    assert not caches[0].exists()
    assert caches[1].read_text() == "canary"


@pytest.mark.parametrize("value", [None, ""])
@pytest.mark.parametrize("kind", FORGE)
def test_forge_fallback_only_probes_expected_cache(monkeypatch, value, kind):
    if value is None:
        monkeypatch.delenv("NAVIS_ROOT", raising=False)
    else:
        monkeypatch.setenv("NAVIS_ROOT", value)
    seen = []
    expected = os.path.join(DEFAULT, "Bridge", ".navis_cache", "sector_cache.json")

    def probe(path):
        assert path == expected
        seen.append(path)
        return False

    monkeypatch.setattr(os.path, "exists", probe)
    module = load_forge(monkeypatch, kind)
    module["invalidate_cache"]()
    assert len(seen) == 3


def test_mission_reads_selected_settings_and_writes_configured_synthetic_folder(tmp_path, monkeypatch):
    root = tmp_path / "Selected Vault 雪"
    operations = tmp_path / "Configured Operations"
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    (root / "Bridge").mkdir(parents=True)
    (root / "Bridge/settings.json").write_text(json.dumps({"paths": {"operations_dir": str(operations)}}))
    (root / "Bridge/status.json").write_text(json.dumps({"location": "Sanctum"}))
    module = load_forge(monkeypatch, "mission")
    module["forge_mission"]("Fixture", "#area/realm", "main", 42)
    target = operations / "The Sanctum/Main/Fixture"
    assert "#area/self" in (target / "Mission.md").read_text(encoding="utf-8-sig")
    assert json.loads((target / "Data.json").read_text(encoding="utf-8-sig"))["xp_reward"] == 42
    assert not (root / "Operations").exists()


@pytest.mark.parametrize("primary,alias", [("selected", "other"), ("selected", None), (None, "selected"), ("", "selected")])
def test_reid_intervention_stays_in_selected_root(tmp_path, monkeypatch, primary, alias):
    selected = tmp_path / "selected"
    other = tmp_path / "other"
    for key, value in (("NAVIS_ROOT", primary), ("NAVIS_VAULT_ROOT", alias)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(tmp_path / value) if value else "")
    for root in (selected, other):
        (root / "Bridge").mkdir(parents=True)
        (root / "Bridge/biometrics.json").write_text(json.dumps({"biometrics": {"suds": {"value": 8}}}))
        (root / "Bridge/status.json").write_text('{"location":"canary"}')
    module = runpy.run_path(str(BACKEND / "services/reid_daemon.py"))
    calls = []
    module["check_biometrics_and_intervene"].__globals__["trigger_voice_alert"] = calls.append
    module["check_biometrics_and_intervene"]()
    assert json.loads((selected / "Bridge/status.json").read_text(encoding="utf-8-sig"))["location"] == "Friðr Hall"
    logs = list((selected / "Reflection Chamber/Fridr Hall").glob("*.md"))
    assert len(logs) == 1 and "Autonomous Intervention" in logs[0].read_text(encoding="utf-8-sig")
    assert len(calls) == 1
    assert (other / "Bridge/status.json").read_text() == '{"location":"canary"}'
    assert not (other / "Reflection Chamber").exists()
    module["check_biometrics_and_intervene"]()
    assert len(calls) == 1  # Existing cooldown still applies.


@pytest.mark.parametrize("value", [None, ""])
def test_reid_and_youtube_default_is_path_only(monkeypatch, value):
    for key in ("NAVIS_ROOT", "NAVIS_VAULT_ROOT"):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    reid = runpy.run_path(str(BACKEND / "services/reid_daemon.py"))
    youtube = runpy.run_path(str(BACKEND / "scripts/sync_youtube.py"))
    assert reid["NAVIS_VAULT_ROOT"] == DEFAULT
    assert youtube["VAULT_PATH"] == os.path.join(DEFAULT, "Lounge", "youtube.json")


def test_youtube_writes_only_selected_root_with_fake_provider(tmp_path, monkeypatch):
    root = tmp_path / "Vault with spaces 雪"
    monkeypatch.setenv("NAVIS_ROOT", str(root))

    class FakeYoutube:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download):
            assert download is False
            return {"entries": [{"id": "fixture", "title": "Synthetic"}]}

    monkeypatch.setattr(sys.modules["yt_dlp"], "YoutubeDL", FakeYoutube)
    module = runpy.run_path(str(BACKEND / "scripts/sync_youtube.py"))
    module["sync_watch_later"]()
    data = json.loads((root / "Lounge/youtube.json").read_text())
    assert data["total_items"] == 1
    assert data["videos"][0]["id"] == "fixture"


def test_mission_default_operations_and_character_paths(tmp_path, monkeypatch):
    root = tmp_path / "Vault 雪"
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    helper = load_forge(monkeypatch, "character")
    paths = helper["get_engine_paths"]()
    assert paths["companions_dir"] == str(root / "Companions")
    assert paths["settings_path"] == str(root / "Bridge/settings.json")
    module = load_forge(monkeypatch, "mission")
    module["forge_mission"]("Fixture", "Sanctum", "side", 5)
    assert (root / "Operations/The Sanctum/Side/Fixture/Mission.md").is_file()


@pytest.mark.parametrize("kind", ["realm", "companion", "beast"])
def test_staged_forge_preserves_sector_cache(tmp_path, monkeypatch, kind):
    root = tmp_path / "Staged Vault"
    monkeypatch.setenv("NAVIS_ROOT", str(root))
    monkeypatch.setenv("NAVIS_FORGE_STAGING", "1")
    # Character's existing import-time invalidation runs before the guarded CLI.
    helper = ModuleType("forge_character")
    helper.__dict__.update(runpy.run_path(str(BACKEND / "scripts/forge/forge_character.py")))
    monkeypatch.setitem(sys.modules, "forge_character", helper)
    cache = root / "Bridge/.navis_cache/sector_cache.json"
    cache.parent.mkdir(parents=True)
    cache.write_text("staging canary")
    module = runpy.run_path(str(BACKEND / f"scripts/forge/forge_{kind}.py"))
    module["invalidate_cache"]()
    assert cache.read_text() == "staging canary"
