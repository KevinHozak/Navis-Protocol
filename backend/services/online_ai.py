"""Explicitly gated, budgeted Google Gemini generation for interactive features."""

from __future__ import annotations

import asyncio
import json
import math
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODEL = "gemini-2.5-flash"
MAX_INPUT_CHARS = 12_000
MAX_OUTPUT_TOKENS = 2_048
# Conservative paid-tier list rates in USD per million tokens, reviewed 2026-09-27.
INPUT_USD_PER_MILLION = 0.30
OUTPUT_USD_PER_MILLION = 2.50
PRICE_REVIEW_DATE = "2026-09-27"
MAX_PRICE_AGE_DAYS = 30


@dataclass(frozen=True)
class Pricing:
    model: str
    input_rate: float
    output_rate: float
    reviewed: str
    source: str = "https://ai.google.dev/gemini-api/docs/pricing"


def default_pricing() -> Pricing:
    return Pricing(MODEL, INPUT_USD_PER_MILLION, OUTPUT_USD_PER_MILLION, PRICE_REVIEW_DATE)


def estimate(input_chars: int, output_limit: int = MAX_OUTPUT_TOKENS, *, pricing: Pricing | None = None) -> float:
    price = pricing or default_pricing()
    if not 0 <= input_chars <= MAX_INPUT_CHARS or not 1 <= output_limit <= MAX_OUTPUT_TOKENS:
        raise OnlineAIError("Online request limit exceeded.")
    if any(not math.isfinite(rate) or rate <= 0 for rate in (price.input_rate, price.output_rate)):
        raise OnlineAIError("Invalid provider pricing.")
    reviewed = datetime.strptime(price.reviewed, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - reviewed).days
    if not 0 <= age <= MAX_PRICE_AGE_DAYS:
        raise OnlineAIError("Provider pricing is stale; online generation is disabled until pricing is reviewed.")
    return (input_chars * 4 * price.input_rate + output_limit * price.output_rate) / 1_000_000


class OnlineAIError(RuntimeError):
    """Safe diagnostic for an online request rejected by policy or provider."""


def _paths() -> tuple[Path, Path]:
    root = Path(os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault"))
    bridge = root / "Bridge"
    return bridge / "ai_experiments.json", bridge / "ai_usage.sqlite3"


def _read_config() -> dict[str, Any]:
    config_path, _ = _paths()
    try:
        with config_path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("invalid configuration")
        return value
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise OnlineAIError("Online experiment configuration is unreadable; online generation is disabled.") from exc


def configure(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"enabled", "allow_vault_content", "monthly_budget_usd"}
    if set(payload) - allowed:
        raise OnlineAIError("Only enabled, allow_vault_content, and monthly_budget_usd can be configured.")
    current = _read_config()
    updated = {**current, **payload}
    if not isinstance(updated.get("enabled", False), bool) or not isinstance(updated.get("allow_vault_content", False), bool):
        raise OnlineAIError("Online opt-in settings must be booleans.")
    try:
        budget = float(updated.get("monthly_budget_usd", 0))
    except (TypeError, ValueError) as exc:
        raise OnlineAIError("Monthly experiment budget must be a number from $0.01 to $100.") from exc
    if not 0.01 <= budget <= 100:
        raise OnlineAIError("Monthly experiment budget must be from $0.01 to $100.")
    updated["monthly_budget_usd"] = round(budget, 6)
    config_path, _ = _paths()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(updated, indent=2), encoding="utf-8-sig")
    os.replace(temp_path, config_path)
    return diagnostics()


def _db() -> sqlite3.Connection:
    _, db_path = _paths()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            request_id TEXT PRIMARY KEY,
            period TEXT NOT NULL,
            feature TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            estimated_cost_usd REAL NOT NULL,
            actual_cost_usd REAL,
            state TEXT NOT NULL
        )
    """)
    return conn


def _period(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def diagnostics() -> dict[str, Any]:
    config = _read_config()
    try:
        budget = float(config.get("monthly_budget_usd", 0))
    except (TypeError, ValueError):
        budget = 0
    conn = _db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd),0) FROM usage WHERE period=? AND state IN ('reserved','settled','unknown_usage')",
            (_period(),),
        ).fetchone()
    finally:
        conn.close()
    key_available = bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    reviewed = datetime.strptime(PRICE_REVIEW_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - reviewed).days
    return {
        "enabled": config.get("enabled") is True,
        "allow_vault_content": config.get("allow_vault_content") is True,
        "provider": "gemini",
        "model": MODEL,
        "api_key_available": key_available,
        "monthly_budget_usd": budget,
        "month_to_date_reserved_usd": round(float(row[0]), 8),
        "input_limit_chars": MAX_INPUT_CHARS,
        "output_limit_tokens": MAX_OUTPUT_TOKENS,
        "price_review_date": PRICE_REVIEW_DATE,
        "price_review_stale": age > MAX_PRICE_AGE_DAYS,
        "last_reset_period": _period(),
        "vault_content_policy": "excluded unless explicitly enabled",
    }


def _reserve(feature: str, input_chars: int, *, pricing: Pricing | None = None,
             output_limit: int = MAX_OUTPUT_TOKENS, cap_fraction: float = 1.0) -> tuple[str, float]:
    config = _read_config()
    if config.get("enabled") is not True:
        raise OnlineAIError("Online generation is disabled. Explicitly enable it in AI experiment settings.")
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        raise OnlineAIError("No online provider API key is configured.")
    if input_chars > MAX_INPUT_CHARS:
        raise OnlineAIError(f"Online input exceeds the {MAX_INPUT_CHARS}-character request limit.")
    price = pricing or default_pricing()
    budget = float(config.get("monthly_budget_usd", 0))
    # Four tokens per input character is the hard preflight upper bound. Reserve max output tokens too.
    reserve_usd = estimate(input_chars, output_limit, pricing=price)
    if not math.isfinite(budget) or not 0 < cap_fraction <= 1:
        raise OnlineAIError("Invalid experiment budget.")
    budget *= cap_fraction
    if reserve_usd <= 0 or reserve_usd > budget:
        raise OnlineAIError("Request worst-case cost exceeds the configured monthly experiment budget.")
    now = datetime.now(timezone.utc)
    period = _period(now)
    request_id = str(uuid.uuid4())
    conn = _db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        spent = conn.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd),0) FROM usage WHERE period=? AND state IN ('reserved','settled','unknown_usage')",
            (period,),
        ).fetchone()[0]
        if spent + reserve_usd > budget:
            conn.rollback()
            raise OnlineAIError("Monthly experiment budget is exhausted or reserved by concurrent requests.")
        conn.execute(
            "INSERT INTO usage VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (request_id, period, feature[:80], "gemini", price.model, now.isoformat(), None, None, reserve_usd, None, "reserved"),
        )
        conn.commit()
    finally:
        conn.close()
    return request_id, reserve_usd


def _settle(request_id: str, reserve_usd: float, usage: Any, *, pricing: Pricing | None = None) -> None:
    price = pricing or default_pricing()
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    thoughts_tokens = getattr(usage, "thoughts_token_count", 0) if usage else None
    conn = _db()
    try:
        if (
            not isinstance(input_tokens, int)
            or not isinstance(output_tokens, int)
            or not isinstance(thoughts_tokens, int)
            or input_tokens < 0
            or output_tokens < 0
            or thoughts_tokens < 0
        ):
            conn.execute("UPDATE usage SET state='unknown_usage' WHERE request_id=?", (request_id,))
            raise OnlineAIError("Provider omitted usage metadata; the full reservation remains charged against the budget.")
        output_tokens += thoughts_tokens
        actual = (input_tokens * price.input_rate + output_tokens * price.output_rate) / 1_000_000
        if actual > reserve_usd:
            conn.execute("UPDATE usage SET input_tokens=?,output_tokens=?,estimated_cost_usd=?,actual_cost_usd=?,state='unknown_usage' WHERE request_id=?", (input_tokens, output_tokens, actual, actual, request_id))
            raise OnlineAIError("Provider usage exceeded the reserved limit; online generation is locked pending review.")
        conn.execute("UPDATE usage SET input_tokens=?,output_tokens=?,estimated_cost_usd=?,actual_cost_usd=?,state='settled' WHERE request_id=?", (input_tokens, output_tokens, actual, actual, request_id))
    finally:
        conn.close()


async def generate(prompt: str, *, feature: str, system: str | None = None, contents: Any = None) -> tuple[str, Any]:
    config = _read_config()
    if config.get("allow_vault_content") is not True and feature in {"neural_chat", "warroom", "reid", "forge"}:
        raise OnlineAIError("Online Vault-derived context is disabled. Enable the separate Vault-content opt-in to continue.")
    input_chars = len(prompt) + len(system or "")
    if contents is not None:
        input_chars = max(input_chars, sum(len(str(getattr(part, "text", ""))) for item in contents for part in getattr(item, "parts", [])))
    request_id, reserve_usd = _reserve(feature, input_chars)
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        result = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL,
            contents=contents if contents is not None else prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        _settle(request_id, reserve_usd, getattr(result, "usage_metadata", None))
        text = getattr(result, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise OnlineAIError("Online provider returned no text.")
        return text.strip(), getattr(result, "usage_metadata", None)
    except OnlineAIError:
        raise
    except Exception as exc:
        # The request may have reached the provider; keep the worst-case reservation.
        conn = _db()
        try:
            conn.execute("UPDATE usage SET state='unknown_usage' WHERE request_id=?", (request_id,))
        finally:
            conn.close()
        raise OnlineAIError("Online generation failed; the request reservation remains in the monthly budget.") from exc
