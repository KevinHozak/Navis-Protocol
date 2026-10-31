import asyncio
import json
import sys
from pathlib import Path

import aiohttp
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import ai_provider


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload or {"response": "generated locally"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self, *, timeout):
        self.timeout = timeout
        self.request = None
        self.status = 200
        self.payload = {"response": "generated locally"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def post(self, url, *, json):
        self.request = (url, json)
        return FakeResponse(self.status, self.payload)

    def get(self, url):
        self.request = (url, None)
        return FakeResponse(self.status)


def test_cloud_default_is_disabled_without_configuration(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("NAVIS_AI_PROVIDER", raising=False)
    monkeypatch.delenv("NAVIS_OLLAMA_MODEL", raising=False)

    provider = ai_provider.get_provider()

    assert isinstance(provider, ai_provider.GuardedOpenRouterProvider)
    monkeypatch.delenv("NAVIS_OPENROUTER_CONFIG", raising=False)
    with pytest.raises(ai_provider.ProviderError, match="disabled"):
        asyncio.run(provider.generate("Synthetic input", feature="forge"))


def test_generation_uses_configured_local_model_and_normalizes_errors(monkeypatch):
    sessions = []

    def session_factory(**kwargs):
        session = FakeSession(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", session_factory)
    config = ai_provider.OllamaConfig(base_url="http://ollama.local", model="test:latest", timeout_seconds=7)
    provider = ai_provider.OllamaProvider(config)

    result = asyncio.run(provider.generate("hello", system="be concise"))

    assert result == "generated locally"
    assert sessions[0].request == (
        "http://ollama.local/api/generate",
        {"model": "test:latest", "prompt": "hello", "stream": False, "system": "be concise"},
    )
    assert sessions[0].timeout.total == 7


def test_unavailable_local_provider_has_clear_diagnostic(monkeypatch):
    def fail_session(**kwargs):
        raise aiohttp.ClientConnectionError()

    monkeypatch.setattr(aiohttp, "ClientSession", fail_session)

    with pytest.raises(ai_provider.ProviderError, match="Start Ollama"):
        asyncio.run(ai_provider.OllamaProvider().generate("hello"))


def test_missing_local_model_is_actionable_and_recovers(monkeypatch):
    session = FakeSession(timeout=None)
    session.status = 404
    session.payload = {"error": "private provider diagnostics"}
    monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)
    provider = ai_provider.OllamaProvider()
    with pytest.raises(ai_provider.ProviderError, match="NAVIS_OLLAMA_MODEL") as error:
        asyncio.run(provider.generate("private prompt"))
    assert "private" not in str(error.value)
    session.status = 200
    session.payload = {"response": "Recovered locally"}
    assert asyncio.run(provider.generate("private prompt")) == "Recovered locally"


def test_legacy_gemini_is_rejected_for_migrated_text_features(monkeypatch):
    monkeypatch.setenv("NAVIS_AI_PROVIDER", "gemini")

    with pytest.raises(ai_provider.ProviderError, match="retired"):
        ai_provider.get_provider()


def test_connectivity_check_uses_local_tags_endpoint(monkeypatch):
    sessions = []

    def session_factory(**kwargs):
        session = FakeSession(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", session_factory)

    assert asyncio.run(ai_provider.OllamaProvider().check()) is True
    assert sessions[0].request[0] == "http://localhost:11434/api/tags"


def test_forge_submit_uses_local_provider_without_cloud_key(monkeypatch, tmp_path):
    from main import ForgeSubmitRequest, forge_submit
    monkeypatch.setattr("main.NAVIS_ROOT", str(tmp_path))

    class MockProvider:
        async def generate(self, prompt, *, system=None):
            assert "Aster" in prompt
            assert system
            from services.forge_service import FIELDS
            blueprint = {field: "A forest guide" for field in FIELDS}
            blueprint.update(name="Aster", role="Guide", voice_id="en-US-JennyNeural")
            return json.dumps(blueprint)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(ai_provider, "get_provider", lambda: MockProvider())

    result = asyncio.run(
        forge_submit(ForgeSubmitRequest(entity_type="Companion", name="Aster", prompt="A forest guide"))
    )

    assert result["blueprint"]["name"] == "Aster"
    assert result["blueprint"]["role"] == "Guide"
    assert result["proposal_id"]
    assert list(tmp_path.iterdir()) == []


def test_forge_submit_returns_local_unavailable_diagnostic(monkeypatch, tmp_path):
    from main import ForgeSubmitRequest, forge_submit
    monkeypatch.setattr("main.NAVIS_ROOT", str(tmp_path))

    class MockProvider:
        async def generate(self, prompt, *, system=None):
            raise ai_provider.ProviderError("Local Ollama is unavailable.")

    monkeypatch.setattr(ai_provider, "get_provider", lambda: MockProvider())

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            forge_submit(ForgeSubmitRequest(entity_type="Companion", name="Aster", prompt="test"))
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Local Ollama is unavailable."
