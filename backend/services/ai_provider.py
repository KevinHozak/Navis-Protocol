"""Local-first text generation provider boundary for Forge and Banter."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Protocol

import aiohttp


class ProviderError(RuntimeError):
    """A normalized provider failure safe to show in application diagnostics."""


class TextProvider(Protocol):
    async def generate(
        self, prompt: str, *, system: str | None = None, feature: str = "general", **kwargs: object
    ) -> str: ...

    async def check(self) -> bool: ...


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    model: str = "Kimiko-20B:latest"
    timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        try:
            timeout = float(os.environ.get("NAVIS_OLLAMA_TIMEOUT", "90"))
        except ValueError:
            timeout = 90.0
        return cls(
            base_url=os.environ.get("NAVIS_OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            model=os.environ.get("NAVIS_OLLAMA_MODEL", "Kimiko-20B:latest"),
            timeout_seconds=max(1.0, min(timeout, 600.0)),
        )


class OllamaProvider:
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig.from_env()

    async def check(self) -> bool:
        timeout = aiohttp.ClientTimeout(total=min(self.config.timeout_seconds, 5.0))
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.config.base_url}/api/tags") as response:
                    return response.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def generate(
        self, prompt: str, *, system: str | None = None, feature: str = "general", **kwargs: object
    ) -> str:
        payload: dict[str, object] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.config.base_url}/api/generate", json=payload
                ) as response:
                    if response.status == 404:
                        raise ProviderError("Configured local Ollama model is unavailable. Install the model selected by NAVIS_OLLAMA_MODEL and retry.")
                    if response.status != 200:
                        raise ProviderError(f"Local Ollama returned HTTP {response.status}.")
                    data = await response.json()
                    result = data.get("response")
                    if not isinstance(result, str) or not result.strip():
                        raise ProviderError("Local Ollama returned an empty response.")
                    return result.strip()
        except ProviderError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(
                "Local Ollama is unavailable or timed out. Start Ollama and verify the configured model."
            ) from exc


def get_provider() -> TextProvider:
    """Return local by default; online selection is enforced by the experiment guard."""
    provider = os.environ.get("NAVIS_AI_PROVIDER", "ollama").strip().lower()
    if provider == "gemini":
        return GuardedGeminiProvider()
    if provider not in ("", "ollama", "local"):
        raise ProviderError("Unsupported AI provider. Select local Ollama or explicitly enabled Gemini.")
    return OllamaProvider()


class GuardedGeminiProvider:
    async def check(self) -> bool:
        from services.online_ai import diagnostics

        try:
            state = diagnostics()
            return state["enabled"] and state["api_key_available"] and not state["price_review_stale"]
        except Exception:
            # Diagnostics require writable accounting storage; its failure is a deny.
            return False

    async def generate(
        self, prompt: str, *, system: str | None = None, feature: str = "forge", **kwargs: object
    ) -> str:
        from services.online_ai import OnlineAIError, generate

        try:
            result, _ = await generate(prompt, feature=feature, system=system)
            return result
        except OnlineAIError as exc:
            raise ProviderError(str(exc)) from exc
