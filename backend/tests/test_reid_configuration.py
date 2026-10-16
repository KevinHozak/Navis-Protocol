"""Reid configuration uses only synthetic Vaults and an offline provider."""
import asyncio
import json
from pathlib import Path

import pytest

from services import reid_agent as reid


@pytest.fixture(autouse=True)
def isolated_reid(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVIS_ROOT", str(tmp_path))
    monkeypatch.delenv("NAVIS_VAULT_ROOT", raising=False)
    monkeypatch.delenv("NAVIS_REID_NOTE_FILES", raising=False)
    monkeypatch.setattr(reid, "VAULT_FILES_CACHE", {})


def test_root_requires_configuration_and_supports_alias(tmp_path, monkeypatch):
    monkeypatch.delenv("NAVIS_ROOT")
    with pytest.raises(ValueError, match="Configure NAVIS_ROOT"):
        reid.get_vault_root()
    monkeypatch.setenv("NAVIS_VAULT_ROOT", str(tmp_path / "alias"))
    assert reid.get_vault_root() == str((tmp_path / "alias").resolve())
    monkeypatch.setenv("NAVIS_ROOT", "  ")
    assert reid.get_vault_root() == str((tmp_path / "alias").resolve())
    monkeypatch.setenv("NAVIS_ROOT", str(tmp_path))
    assert reid.get_vault_root() == str(tmp_path.resolve())


@pytest.mark.parametrize("setting", [None, "", "  ", "[]"])
def test_unconfigured_notes_do_not_read_files(tmp_path, monkeypatch, setting):
    (tmp_path / "unlisted.md").write_text("Synthetic unlisted text")
    if setting is not None:
        monkeypatch.setenv("NAVIS_REID_NOTE_FILES", setting)
    assert reid.load_therapy_notes() == "No therapist sessions found."


def test_only_allowlisted_markdown_is_read_with_encoded_links(tmp_path, monkeypatch):
    directory = tmp_path / "notes"
    directory.mkdir()
    note = directory / "session #1.md"
    note.write_text("Synthetic allowed text", encoding="utf-8-sig")
    (directory / "other.md").write_text("Synthetic unlisted text")
    monkeypatch.setenv("NAVIS_REID_NOTE_FILES", json.dumps(["notes/session #1.md", "notes/missing.md"]))
    result = reid.load_therapy_notes()
    assert "Synthetic allowed text" in result
    assert "Synthetic unlisted text" not in result
    assert note.as_uri() in result
    assert "%23" in result and "%20" in result


@pytest.mark.parametrize("setting", ["not json", "{}", '"file.md"', "[1]", '[""]', '[" "]'])
def test_invalid_allowlist_fails_closed(monkeypatch, setting):
    monkeypatch.setenv("NAVIS_REID_NOTE_FILES", setting)
    with pytest.raises(ValueError, match="JSON array"):
        reid.load_therapy_notes()


@pytest.mark.parametrize("name", ["../outside.md", "notes/not-markdown.txt"])
def test_unsafe_paths_fail_before_reading_any_notes(tmp_path, monkeypatch, name):
    (tmp_path / "allowed.md").write_text("Synthetic text")
    monkeypatch.setenv("NAVIS_REID_NOTE_FILES", json.dumps(["allowed.md", name]))
    def unexpected_read(*args, **kwargs):
        raise AssertionError("Configuration must be validated before any read")
    monkeypatch.setattr(Path, "read_text", unexpected_read)
    with pytest.raises(ValueError, match="inside the Vault"):
        reid.load_therapy_notes()


def test_absolute_paths_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVIS_REID_NOTE_FILES", json.dumps([str(tmp_path / "note.md")]))
    with pytest.raises(ValueError, match="inside the Vault"):
        reid.load_therapy_notes()


def test_symlink_cannot_escape_vault(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Synthetic outside text")
    try:
        (vault / "linked.md").symlink_to(outside)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    monkeypatch.setenv("NAVIS_ROOT", str(vault))
    monkeypatch.setenv("NAVIS_REID_NOTE_FILES", '["linked.md"]')
    with pytest.raises(ValueError, match="inside the Vault"):
        reid.load_therapy_notes()


def test_configured_notes_reach_offline_provider_and_transcript(tmp_path, monkeypatch):
    note = tmp_path / "note.md"
    note.write_text("Synthetic configured context")
    monkeypatch.setenv("NAVIS_REID_NOTE_FILES", '["note.md"]')
    class Provider:
        async def generate(self, prompt, *, feature, system):
            assert feature == "reid"
            assert "Synthetic configured context" in system
            assert note.as_uri() in system
            return "Synthetic response"
    assert asyncio.run(reid.chat_with_reid("Hello", provider=Provider())) == "Synthetic response"
    transcripts = list((tmp_path / "Reflection Chamber" / "Fridr Hall").glob("*.md"))
    assert len(transcripts) == 1
    assert "Synthetic response" in transcripts[0].read_text(encoding="utf-8-sig")
