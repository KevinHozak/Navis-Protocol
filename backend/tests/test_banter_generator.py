import inspect
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import ai_provider, banter_generator


@pytest.fixture
def banter_vault(tmp_path, monkeypatch):
    bridge = tmp_path / "Bridge"
    bridge.mkdir()
    status_path = bridge / "status.json"
    status_path.write_text(
        json.dumps({"current_realm": "Mosswood", "squad": [{"name": "Aster"}, {"name": "Rowan"}]}),
        encoding="utf-8",
    )
    db_path = tmp_path / "Chronicle.db"
    settings_path = bridge / "settings.json"
    settings_path.write_text(json.dumps({"paths": {"chronicle_db": str(db_path)}}), encoding="utf-8")
    monkeypatch.setattr(banter_generator, "NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(banter_generator, "STATUS_PATH", str(status_path))
    monkeypatch.setattr(banter_generator, "SETTINGS_PATH", str(settings_path))
    monkeypatch.setattr(banter_generator.random, "choice", lambda values: values[0])
    monkeypatch.setattr(banter_generator.random, "shuffle", lambda values: None)
    return db_path


class FakeLocalProvider:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def generate(self, prompt):
        self.calls.append(prompt)
        if self.error:
            raise self.error
        speakers = ["Aster", "Rowan"]
        return self.response if self.response is not None else json.dumps(
            [{"speaker": name, "text": f"A line from {name}."} for name in speakers]
        )


def install_provider(monkeypatch, provider):
    monkeypatch.setattr(banter_generator, "OllamaProvider", lambda: provider, raising=False)

    # banter_generator imports the provider class inside the function.
    monkeypatch.setattr(ai_provider, "OllamaProvider", lambda: provider)


def test_local_generation_persists_complete_ordered_thread(banter_vault, monkeypatch):
    provider = FakeLocalProvider()
    install_provider(monkeypatch, provider)

    assert banter_generator.generate_squad_banter(count=1) is True
    assert len(provider.calls) == 1
    with sqlite3.connect(banter_vault) as conn:
        row = conn.execute("SELECT realm, participants, chain FROM banter_threads").fetchone()
    assert row[:2] == ("Mosswood", "Aster,Rowan")
    assert [turn["speaker"] for turn in json.loads(row[2])] == ["Aster", "Rowan"]


def test_unavailable_local_provider_fails_without_breaking_caller(banter_vault, monkeypatch):
    provider = FakeLocalProvider(error=ai_provider.ProviderError("Ollama unavailable"))
    install_provider(monkeypatch, provider)

    assert banter_generator.generate_squad_banter(count=1) is False
    assert not banter_vault.exists()


@pytest.mark.parametrize("response", ["not json", '[{"speaker":"Aster","text":"Only one turn"}]'])
def test_malformed_or_incomplete_output_is_not_persisted(banter_vault, monkeypatch, response):
    provider = FakeLocalProvider(response=response)
    install_provider(monkeypatch, provider)

    assert banter_generator.generate_squad_banter(count=1) is False
    if banter_vault.exists():
        with sqlite3.connect(banter_vault) as conn:
            assert conn.execute("SELECT COUNT(*) FROM banter_threads").fetchone()[0] == 0


def test_duplicate_thread_persistence_is_idempotent(tmp_path):
    db_path = tmp_path / "Chronicle.db"
    chain = [{"speaker": "Aster", "text": "The woods are quiet."}]

    banter_generator.add_banter_thread(str(db_path), chain, "Mosswood", ["Aster", "Rowan"])
    banter_generator.add_banter_thread(str(db_path), chain, "Mosswood", ["Aster", "Rowan"])

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM banter_threads").fetchone()[0] == 1


def test_persistence_error_is_contained(banter_vault, monkeypatch):
    provider = FakeLocalProvider()
    install_provider(monkeypatch, provider)

    def fail_persist(*args, **kwargs):
        raise sqlite3.OperationalError("read-only")

    monkeypatch.setattr(banter_generator, "add_banter_thread", fail_persist)

    assert banter_generator.generate_squad_banter(count=1) is False


def test_recent_usable_thread_skips_repeated_local_work(banter_vault, monkeypatch):
    provider = FakeLocalProvider()
    install_provider(monkeypatch, provider)

    assert banter_generator.generate_squad_banter(count=8) is True
    assert len(provider.calls) == banter_generator.MAX_BANTER_THREADS_PER_RUN
    assert banter_generator.generate_squad_banter(count=8) is True
    assert len(provider.calls) == banter_generator.MAX_BANTER_THREADS_PER_RUN


def test_banter_trigger_is_sync_route_for_threadpool_execution(monkeypatch):
    from main import trigger_banter_generation

    monkeypatch.setattr(banter_generator, "generate_squad_banter", lambda count: True)
    assert not inspect.iscoroutinefunction(trigger_banter_generation)
    assert trigger_banter_generation(count=1)["status"] == "success"


def test_explicit_banter_stays_local_when_online_provider_is_selected(banter_vault, monkeypatch):
    provider = FakeLocalProvider()
    install_provider(monkeypatch, provider)
    monkeypatch.setenv("NAVIS_AI_PROVIDER", "gemini")

    assert banter_generator.generate_squad_banter(count=1) is True
    assert len(provider.calls) == 1
