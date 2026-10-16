import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import conversation_service as conv
from services.ai_provider import ProviderError


class MockProvider:
    def __init__(self, response_text="Mocked neural response"):
        self.response_text = response_text
        self.calls = []

    async def generate(self, prompt, *, system=None, feature="general", **kwargs):
        self.calls.append({"prompt": prompt, "system": system, "feature": feature})
        return self.response_text

    async def check(self):
        return True


class FailingProvider:
    async def generate(self, prompt, *, system=None, feature="general", **kwargs):
        raise ProviderError("Local Ollama is unavailable or timed out. Start Ollama and verify the configured model.")

    async def check(self):
        return False


class ConversationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "vault"
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "Bridge").mkdir(parents=True, exist_ok=True)
        (self.root / "Reflection Chamber" / "Fridr Hall").mkdir(parents=True, exist_ok=True)
        (self.root / "Companions" / "Ahri").mkdir(parents=True, exist_ok=True)
        (self.root / "Journal" / "2026" / "10").mkdir(parents=True, exist_ok=True)

        # Create status.json
        status_file = self.root / "Bridge" / "status.json"
        status_file.write_text(
            json.dumps({
                "current_realm": "Aethelgard",
                "current_antagonist": "Malakor",
                "current_beast": "Void Drake",
                "squad": [{"name": "Ahri", "role": "Vanguard"}]
            }),
            encoding="utf-8"
        )

        # Create Companion Persona
        persona_file = self.root / "Companions" / "Ahri" / "Persona.json"
        persona_file.write_text(
            json.dumps({
                "role": "Fox Spirit Vanguard",
                "voice": "Playful and sharp",
                "system_prompt": "Speak playfully but maintain combat vigilance."
            }),
            encoding="utf-8"
        )

        # Create Companion Profile
        profile_file = self.root / "Companions" / "Ahri" / "Profile.md"
        profile_file.write_text(
            "# Ahri\n\nA cunning kitsune scout.",
            encoding="utf-8-sig"
        )

        # Set env var
        self.orig_navis_root = os.environ.get("NAVIS_ROOT")
        self.orig_vault_root = os.environ.get("NAVIS_VAULT_ROOT")
        os.environ["NAVIS_ROOT"] = str(self.root)
        os.environ["NAVIS_VAULT_ROOT"] = str(self.root)

    def tearDown(self):
        if self.orig_navis_root is not None:
            os.environ["NAVIS_ROOT"] = self.orig_navis_root
        else:
            os.environ.pop("NAVIS_ROOT", None)
        if self.orig_vault_root is not None:
            os.environ["NAVIS_VAULT_ROOT"] = self.orig_vault_root
        else:
            os.environ.pop("NAVIS_VAULT_ROOT", None)
        self.temp.cleanup()

    def test_reid_trigger_words_return_synchronously_without_llm(self):
        provider = MockProvider("Should not be called")
        res = asyncio.run(conv.handle_reid_chat(
            self.root,
            {"message": "I feel completely overwhelmed with tasks"},
            provider=provider
        ))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["response"], "UI_TRIGGER:THREE_DOORS")
        self.assertEqual(len(provider.calls), 0)

    def test_reid_chat_generates_and_persists_transcript(self):
        provider = MockProvider("Focus on your breath, Keeper.")
        res = asyncio.run(conv.handle_reid_chat(
            self.root,
            {"message": "How do I regain clarity?"},
            provider=provider
        ))
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["response"], "Focus on your breath, Keeper.")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["feature"], "reid")

        # Verify Friðr Hall transcript file was written
        fridr_dir = self.root / "Reflection Chamber" / "Fridr Hall"
        files = list(fridr_dir.glob("*.md"))
        self.assertTrue(len(files) > 0)
        content = files[0].read_text(encoding="utf-8-sig")
        self.assertIn("Keeper:** How do I regain clarity?", content)
        self.assertIn("Reid:** Focus on your breath, Keeper.", content)

    def test_reid_chat_propagates_provider_unavailable(self):
        provider = FailingProvider()
        with self.assertRaises(ProviderError) as ctx:
            asyncio.run(conv.handle_reid_chat(
                self.root,
                {"message": "Hello Reid"},
                provider=provider
            ))
        self.assertIn("Local Ollama is unavailable", str(ctx.exception))

    def test_neural_chat_with_persona_and_squad_context(self):
        provider = MockProvider("*Ahri*: I sense something ahead, Keeper.")
        res = asyncio.run(conv.handle_neural_chat(
            self.root,
            {
                "message": "Status report.",
                "persona": "Ahri",
                "history": [{"role": "user", "content": "Entering sector."}]
            },
            provider=provider
        ))
        self.assertEqual(res["status"], "success")
        self.assertIn("*Ahri*", res["response"])
        self.assertEqual(len(provider.calls), 1)
        system_prompt = provider.calls[0]["system"]
        self.assertIn("Act as Ahri", system_prompt)
        self.assertIn("Current realm is Aethelgard", system_prompt)

    def test_warroom_chat_lifecycle_and_history_persistence(self):
        # 1. Clear history
        clear_res = conv.clear_warroom_history(self.root)
        self.assertEqual(clear_res["status"], "success")
        self.assertEqual(conv.get_warroom_history(self.root), [])

        # 2. /init command
        provider = MockProvider("*Ahri*: Standing by for deployment, Keeper.")
        init_res = asyncio.run(conv.handle_warroom_chat(
            self.root,
            {"message": "/init"},
            provider=provider
        ))
        self.assertEqual(init_res["status"], "success")
        self.assertIn("Standing by", init_res["response"])

        history = conv.get_warroom_history(self.root)
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0]["isHidden"])
        self.assertEqual(history[1]["role"], "assistant")

        # 3. Follow up command
        provider2 = MockProvider("*Ahri*: Target locked.")
        chat_res = asyncio.run(conv.handle_warroom_chat(
            self.root,
            {"message": "Engage the perimeter."},
            provider=provider2
        ))
        self.assertEqual(chat_res["status"], "success")
        self.assertIn("Target locked", chat_res["response"])

        history2 = conv.get_warroom_history(self.root)
        self.assertEqual(len(history2), 4)
        self.assertEqual(history2[2]["content"], "Engage the perimeter.")
        self.assertEqual(history2[3]["content"], "*Ahri*: Target locked.")

    def test_warroom_failure_preserves_history_and_retry_does_not_duplicate(self):
        asyncio.run(conv.handle_warroom_chat(self.root, {"message": "/init"}, provider=MockProvider()))
        before = conv.get_warroom_history(self.root)
        with self.assertRaises(ProviderError):
            asyncio.run(conv.handle_warroom_chat(self.root, {"message": "Retry this"}, provider=FailingProvider()))
        self.assertEqual(conv.get_warroom_history(self.root), before)
        asyncio.run(conv.handle_warroom_chat(self.root, {"message": "Retry this"}, provider=MockProvider()))
        history = conv.get_warroom_history(self.root)
        self.assertEqual(sum(m['content'] == 'Retry this' for m in history), 1)

    def test_lost_response_retry_replays_persisted_result(self):
        provider = MockProvider("Saved reply")
        request = {"message": "Save once", "request_id": "lost-response-1"}
        first = asyncio.run(conv.handle_warroom_chat(self.root, request, provider=provider))
        # The client never receives first; a fresh service invocation retries.
        replay = asyncio.run(conv.handle_warroom_chat(self.root, request, provider=FailingProvider()))
        self.assertEqual(replay, first)
        self.assertEqual(len(conv.get_warroom_history(self.root)), 2)
        self.assertEqual(len(provider.calls), 1)
        with self.assertRaises(conv.ConversationError):
            asyncio.run(conv.handle_warroom_chat(self.root, {**request, "message": "Different"}, provider=provider))

    def test_concurrent_retry_generates_once(self):
        class SlowProvider(MockProvider):
            async def generate(self, *args, **kwargs):
                await asyncio.sleep(0.1)
                return await super().generate(*args, **kwargs)
        provider = SlowProvider()
        async def run():
            request = {"message": "/init", "request_id": "concurrent-init"}
            return await asyncio.gather(*(conv.handle_warroom_chat(self.root, request, provider=provider) for _ in range(2)))
        results = asyncio.run(run())
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(conv.get_warroom_history(self.root)), 2)

    def test_retry_after_provider_failure_uses_same_identifier(self):
        request = {"message": "Try again", "request_id": "failed-1"}
        with self.assertRaises(ProviderError):
            asyncio.run(conv.handle_warroom_chat(self.root, request, provider=FailingProvider()))
        self.assertEqual(conv.get_warroom_history(self.root), [])
        asyncio.run(conv.handle_warroom_chat(self.root, request, provider=MockProvider()))
        self.assertEqual(len(conv.get_warroom_history(self.root)), 2)

    def test_cli_subprocess_dispatch_reid_and_warroom(self):
        backend_dir = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-m", "services.conversation_service", "reid_chat"],
            input=json.dumps({"message": "I am feeling paralyzed"}),
            text=True,
            capture_output=True,
            cwd=str(backend_dir),
            env={**os.environ, "NAVIS_ROOT": str(self.root)}
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["http_status"], 200)
        self.assertEqual(data["body"]["response"], "UI_TRIGGER:THREE_DOORS")

    def test_cli_subprocess_dispatch_provider_unavailable_returns_503(self):
        backend_dir = Path(__file__).resolve().parents[1]
        # Point Ollama to an unreachable port to guarantee failure
        proc = subprocess.run(
            [sys.executable, "-m", "services.conversation_service", "reid_chat"],
            input=json.dumps({"message": "Hello"}),
            text=True,
            capture_output=True,
            cwd=str(backend_dir),
            env={
                **os.environ,
                "NAVIS_ROOT": str(self.root),
                "NAVIS_OLLAMA_URL": "http://127.0.0.1:54321",
                "NAVIS_OLLAMA_TIMEOUT": "1",
            }
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["http_status"], 503)
        self.assertEqual(data["body"]["status"], "unavailable")
        self.assertEqual(data["body"]["code"], "native_dependency_unavailable")
        self.assertIn("Local Ollama is unavailable", data["body"]["detail"])
        self.assertNotIn("API_KEY", proc.stdout)


if __name__ == "__main__":
    unittest.main()


def test_warroom_prompt_only_model_has_rules_and_companion_cue(tmp_path):
    root = tmp_path
    (root / "Bridge").mkdir()
    (root / "Bridge/status.json").write_text(json.dumps({"squad": [{"name": "Keeper"}, {"name": "Ahri", "role": "Vanguard"}]}))
    provider = MockProvider("Welcome back.")
    result = asyncio.run(conv.handle_warroom_chat(root, {"message": "/init"}, provider))
    assert result["response"] == "*Ahri*: Welcome back."
    assert "NEVER generate their dialogue" in provider.calls[0]["prompt"]
    assert provider.calls[0]["prompt"].endswith("*Ahri*:")
    assert "=== Ahri ===" in provider.calls[0]["prompt"]
    assert "=== Keeper ===" not in provider.calls[0]["prompt"]


def test_warroom_rejects_generated_keeper_without_saving(tmp_path):
    import pytest
    (tmp_path / "Bridge").mkdir()
    (tmp_path / "Bridge/status.json").write_text(json.dumps({"squad": [{"name": "Ahri"}]}))
    for reply in ("*Keeper*: I am pleased.", "Kevin: Hello", "<|im_end|>"):
        with pytest.raises(ProviderError):
            asyncio.run(conv.handle_warroom_chat(tmp_path, {"message": "/init"}, MockProvider(reply)))
    assert not (tmp_path / "Bridge/warroom_history.json").exists()
