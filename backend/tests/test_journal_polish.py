import asyncio
import sys
from pathlib import Path

import aiohttp
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeResponse:
    def __init__(self, suggestion, status=200, detail=""):
        self.status = status
        self.suggestion = suggestion
        self.detail = detail

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        return {"response": self.suggestion}

    async def text(self):
        return self.detail


class FakeSession:
    def __init__(self, *, timeout, suggestion, status=200, detail=""):
        self.timeout = timeout
        self.response = FakeResponse(suggestion, status, detail)
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def post(self, url, *, json):
        self.request = {"url": url, "payload": json}
        return self.response


def test_polish_uses_local_ollama_and_preserves_checklist_state(monkeypatch):
    sessions = []

    def make_session(**kwargs):
        session = FakeSession(**kwargs, suggestion="- [ ] I may finish this tomorrow.")
        sessions.append(session)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", make_session)
    result = asyncio.run(
        main.polish_journal_entry(
            main.JournalEntryPolishRequest(
                entry="- [ ] I might finish this tomorrow.", section="domestic"
            )
        )
    )

    assert result["suggestion"] == "- [ ] 🏠 I may finish this tomorrow"
    request = sessions[0].request
    assert request["url"] == "http://localhost:11434/api/generate"
    assert request["payload"]["model"] == "Kimiko-20B:latest"
    assert request["payload"]["stream"] is False
    assert "- [ ] I might finish this tomorrow." in request["payload"]["prompt"]
    assert "Correct obvious spelling mistakes" in request["payload"]["prompt"]
    assert "Section: The Domestic Breach" in request["payload"]["prompt"]
    assert "gemini" not in request["url"].lower()


def test_polish_rejects_suggestions_that_change_checklist_state(monkeypatch):
    monkeypatch.setattr(
        aiohttp,
        "ClientSession",
        lambda **kwargs: FakeSession(**kwargs, suggestion="- [x] Completed it."),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            main.polish_journal_entry(
                main.JournalEntryPolishRequest(entry="- [ ] It is still pending.")
            )
        )

    assert error.value.status_code == 503
    assert "checklist formatting" in error.value.detail


def test_polish_rejects_conversational_fallback_without_replacing_draft(monkeypatch):
    monkeypatch.setattr(
        aiohttp,
        "ClientSession",
        lambda **kwargs: FakeSession(
            **kwargs,
            suggestion="I'm sorry, but I don't understand your response. Please rephrase your message.",
        ),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            main.polish_journal_entry(
            main.JournalEntryPolishRequest(entry="I had a difficult day at work.")
            )
        )

    assert error.value.status_code == 503
    assert "conversational reply" in error.value.detail
    assert "not been changed" in error.value.detail


def test_polish_formats_capitalization_period_and_section_emoji():
    result = main.format_polished_journal_entry(
        " okay this is another test of the system. ",
        "okay this is another test of the system",
        "sanctum",
    )

    assert result == "🧪 Okay this is another test of the system"

    checklist_result = main.format_polished_journal_entry(
        "- [ ] i will test this.", "- [ ] i will test this.", "sanctum"
    )
    assert checklist_result == "- [ ] 🧪 I will test this"


def test_polish_rejects_empty_draft_without_calling_ollama():
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.polish_journal_entry(main.JournalEntryPolishRequest(entry="  ")))

    assert error.value.status_code == 422
