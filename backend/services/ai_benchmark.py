"""Operator-only synthetic benchmark. No production provider selection or Vault inputs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from types import SimpleNamespace

import aiohttp

from services import online_ai
from services.ai_provider import OllamaConfig


PROMPT_SET_VERSION = "navis-synthetic-v1"
PRICING_DATE = "2026-09-30"
CANDIDATES = (
    online_ai.Pricing("gemini-3.1-flash-lite", 0.25, 1.50, PRICING_DATE),
    online_ai.Pricing("gemini-3.5-flash-lite", 0.30, 2.50, PRICING_DATE),
)
OUTPUT_LIMIT = 512
TEMPERATURE = 0.0
SEED = 95
MAX_EXPERIMENT_USD = 0.10
MONTHLY_CAP_FRACTION = 0.95
TIMEOUT_SECONDS = 90


@dataclass(frozen=True)
class Task:
    identifier: str
    prompt: str
    expected_json: str


# These fictional tasks are intentionally unrelated to the Keeper, companions or Vault.
TASKS = (
    Task("arithmetic", 'Return only a JSON object with keys total and unit. Three boxes hold 7 bolts each. Unit must be "bolts". No extra keys.', '{"total":21,"unit":"bolts"}'),
    Task("ordering", 'Return only a JSON object with key order. Sort these fictional tasks by ascending priority: amber=3, blue=1, green=2. The order must be a list of names. No extra keys.', '{"order":["blue","green","amber"]}'),
    Task("constraints", 'Return only a JSON object with keys name, kind, approved. Describe a fictional proposed tool: name "Copper Kite", kind "tool", approved false. No extra keys.', '{"name":"Copper Kite","kind":"tool","approved":false}'),
)


def rubric(task: Task, output: str) -> dict[str, int]:
    """Three binary criteria: JSON-only, exact schema/types, correct synthetic facts."""
    expected = json.loads(task.expected_json)
    try:
        parsed = json.loads(output)
    except (ValueError, TypeError):
        return {"json_only": 0, "schema": 0, "correctness": 0}
    schema = (isinstance(parsed, dict) and set(parsed) == set(expected)
              and all(type(parsed[key]) is type(expected[key]) for key in expected))  # noqa: E721 - bool is not an integer answer
    return {"json_only": 1, "schema": int(schema),
            "correctness": int(schema and parsed == expected)}


def _validate(repeats: int, experiment_limit: float) -> None:
    if not isinstance(repeats, int) or isinstance(repeats, bool) or not 2 <= repeats <= 3:
        raise online_ai.OnlineAIError("Benchmark repeats must be 2 or 3.")
    if not math.isfinite(experiment_limit) or not 0 < experiment_limit <= MAX_EXPERIMENT_USD:
        raise online_ai.OnlineAIError("Benchmark limit must be positive and at most $0.10.")


def plan(repeats: int = 2, experiment_limit: float = 0.05) -> dict[str, Any]:
    """No credentials, configuration, Vault or ledger access; no network calls."""
    _validate(repeats, experiment_limit)
    costs = {
        price.model: repeats * sum(online_ai.estimate(len(task.prompt), OUTPUT_LIMIT, pricing=price) for task in TASKS)
        for price in CANDIDATES
    }
    maximum = sum(costs.values())
    if maximum >= experiment_limit:
        raise online_ai.OnlineAIError("Entire benchmark reservation must be strictly below the experiment limit.")
    return {
        "prompt_set_version": PROMPT_SET_VERSION,
        "prompt_set_sha256": hashlib.sha256("\n".join(task.prompt for task in TASKS).encode()).hexdigest(),
        "prompt_ids": [task.identifier for task in TASKS],
        "candidates": [asdict(price) for price in CANDIDATES],
        "requests_per_model": repeats * len(TASKS),
        "maximum_online_cost_usd": maximum,
        "maximum_by_model_usd": costs,
        "experiment_limit_usd": experiment_limit,
        "settings": {"repeats": repeats, "output_limit_tokens": OUTPUT_LIMIT,
                     "temperature": TEMPERATURE, "seed": SEED, "timeout_seconds": TIMEOUT_SECONDS,
                     "monthly_cap_fraction": MONTHLY_CAP_FRACTION, "online_thinking_level": "minimal", "local_thinking": False},
        "rubric": {"json_only": "1: parses as JSON without surrounding prose",
                   "schema": "1: exact keys and value types",
                   "correctness": "1: exact fictional facts, arithmetic or ordering"},
        "production_activation": False,
    }


async def _local(task: Task, config: OllamaConfig) -> tuple[str, int | None, int | None]:
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{config.base_url}/api/generate", json={
            "model": config.model, "prompt": task.prompt, "stream": False, "think": False,
            "options": {"temperature": TEMPERATURE, "seed": SEED, "num_predict": OUTPUT_LIMIT},
        }) as response:
            response.raise_for_status()
            payload = await response.json()
    output = payload.get("response")
    if not isinstance(output, str):
        raise online_ai.OnlineAIError("Local baseline returned no text.")
    counts = [payload.get("prompt_eval_count"), payload.get("eval_count")]
    counts = [value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None for value in counts]
    return output.strip(), counts[0], counts[1]


async def _online(task: Task, price: online_ai.Pricing) -> tuple[str, dict[str, Any]]:
    # The fixed task object is the sole input; no system/context or caller prompts accepted.
    request_id, reserved = online_ai._reserve(
        "synthetic_benchmark", len(task.prompt), pricing=price,
        output_limit=OUTPUT_LIMIT, cap_fraction=MONTHLY_CAP_FRACTION,
    )
    error = None
    provider_status = None
    rejected_fields = []
    output = ""
    try:
        # Direct REST avoids implicit SDK retries and supports the repository's older SDK.
        # The key is a header, never URL/renderer/report data; redirects are disabled.
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{price.model}:generateContent",
                headers={"x-goog-api-key": os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")},
                json={"contents": [{"parts": [{"text": task.prompt}]}],
                      "generationConfig": {"maxOutputTokens": OUTPUT_LIMIT, "temperature": TEMPERATURE,
                                           "seed": SEED, "thinkingConfig": {"thinkingLevel": "minimal"}}},
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    error = f"http_{response.status}"
                    failure = await response.json()
                    details = failure.get("error", {})
                    if details.get("status") in {"RESOURCE_EXHAUSTED", "INVALID_ARGUMENT", "PERMISSION_DENIED", "UNAUTHENTICATED", "NOT_FOUND", "UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED"}:
                        provider_status = details["status"]
                    message = str(details.get("message", "")).lower()
                    rejected_fields = [field for field in ("seed", "thinking", "maxoutputtokens") if field in message]
                    raise online_ai.OnlineAIError("Benchmark provider request failed.")
                result = await response.json()
        metadata = result.get("usageMetadata", {})
        usage = SimpleNamespace(prompt_token_count=metadata.get("promptTokenCount"),
                                candidates_token_count=metadata.get("candidatesTokenCount"),
                                thoughts_token_count=metadata.get("thoughtsTokenCount", 0))
        online_ai._settle(request_id, reserved, usage, pricing=price)
        output = "".join(part.get("text", "") for candidate in result.get("candidates", [])
                         for part in candidate.get("content", {}).get("parts", []) if not part.get("thought"))
        if not isinstance(output, str) or not output.strip():
            output = ""
            error = "empty_output"
    except Exception:
        # Never persist exception text, provider output, request payloads or credentials.
        error = error or "provider_or_usage_error"
        conn = online_ai._db()
        try:
            conn.execute("UPDATE usage SET state='unknown_usage' WHERE request_id=? AND state='reserved'", (request_id,))
        finally:
            conn.close()
    conn = online_ai._db()
    try:
        row = conn.execute("SELECT input_tokens,output_tokens,estimated_cost_usd,state FROM usage WHERE request_id=?", (request_id,)).fetchone()
    finally:
        conn.close()
    return output.strip(), {"request_id": request_id, "input_tokens": row[0], "output_tokens": row[1],
                           "accounted_cost_usd": row[2], "accounting_state": row[3],
                           "reserved_cost_usd": reserved, "actual_billed_cost_usd": None, "error": error,
                           "provider_error_status": provider_status, "rejected_config_fields": rejected_fields}


def summarize(rows: list[dict[str, Any]], models: list[str]) -> dict[str, Any]:
    summaries = {}
    for model in models:
        samples = [row for row in rows if row["model"] == model]
        successful = [row for row in samples if row["error"] is None]
        stability = {}
        for task in TASKS:
            repeats = [row for row in successful if row["prompt_id"] == task.identifier]
            stability[task.identifier] = {
                "successful_repeats": len(repeats),
                "identical_output": len(repeats) >= 2 and len({row["output_sha256"] for row in repeats}) == 1,
                "identical_rubric": len(repeats) >= 2 and len({json.dumps(row["scores"], sort_keys=True) for row in repeats}) == 1,
            }
        summaries[model] = {
            "samples": len(samples), "errors": len(samples) - len(successful),
            "mean_quality_score_out_of_3": sum(sum(row["scores"].values()) for row in samples) / len(samples) if samples else None,
            "mean_latency_seconds": sum(row["latency_seconds"] for row in samples) / len(samples) if samples else None,
            "accounted_cost_usd": sum(row["accounted_cost_usd"] for row in samples),
            "reported_input_tokens": sum(row["input_tokens"] or 0 for row in samples),
            "reported_output_tokens": sum(row["output_tokens"] or 0 for row in samples),
            "samples_missing_usage": sum(row["input_tokens"] is None or row["output_tokens"] is None for row in samples),
            "stability": stability,
        }
    return summaries


async def run(*, enable_online: bool = False, repeats: int = 2,
              experiment_limit: float = 0.05, checkpoint=None) -> dict[str, Any]:
    report = plan(repeats, experiment_limit)
    config = OllamaConfig.from_env()
    report.update({
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "local_baseline": {"provider": "ollama", "model": config.model},
        "online_explicitly_enabled": enable_online, "rows": [], "status": "running",
        "limitations": ["Synthetic exact-answer rubric does not measure personality, creative prose or therapeutic quality.",
                        "Token-based paid-list estimates are not verified provider invoices; actual billed cost is unavailable.",
                        "Small sample; local hardware, quantization, differing reasoning settings, fixed temperature and provider revisions affect results.",
                        "No private input or raw output persisted. Native hosted adapter remains unavailable."],
        "proposal": "Insufficient evidence; no production change authorized.",
    })
    if enable_online:
        info = online_ai.diagnostics()
        if not info["enabled"] or not info["api_key_available"]:
            raise online_ai.OnlineAIError("Enable P2 online experiments and configure a backend key before benchmarking.")
        if info["month_to_date_reserved_usd"] + report["maximum_online_cost_usd"] >= info["monthly_budget_usd"] * MONTHLY_CAP_FRACTION:
            raise online_ai.OnlineAIError("Full benchmark would reach the monthly safety margin; no requests dispatched.")

    providers = [("ollama", config.model, None)]
    if enable_online:
        providers.extend(("gemini", price.model, price) for price in CANDIDATES)
    for provider, model, price in providers:
        for task in TASKS:
            for repeat in range(repeats):
                started = time.perf_counter()
                output = ""
                metadata = {"input_tokens": None, "output_tokens": None, "accounted_cost_usd": 0.0,
                            "actual_billed_cost_usd": None, "error": None}
                try:
                    if price is None:
                        output, metadata["input_tokens"], metadata["output_tokens"] = await _local(task, config)
                        if not output:
                            metadata["error"] = "empty_output"
                    else:
                        output, metadata = await _online(task, price)
                except online_ai.OnlineAIError:
                    metadata["error"] = "policy_or_baseline_error"
                except Exception:
                    metadata["error"] = "local_provider_error"
                report["rows"].append({
                    "provider": provider, "model": model, "prompt_id": task.identifier, "repeat": repeat + 1,
                    "latency_seconds": round(time.perf_counter() - started, 6),
                    "scores": rubric(task, output),
                    "output_sha256": hashlib.sha256(output.encode()).hexdigest() if output else None,
                    **metadata,
                })
                report["summary"] = summarize(report["rows"], [entry[1] for entry in providers])
                if metadata["error"]:
                    report["status"] = "stopped_on_error"
                if checkpoint:
                    checkpoint(report)
                if metadata["error"]:
                    return report  # No retry, no fallback, no spending without usable baseline.
    report["status"] = "complete"
    baseline = report["summary"][config.model]["mean_quality_score_out_of_3"]
    baseline_latency = report["summary"][config.model]["mean_latency_seconds"]
    for model, stats in report["summary"].items():
        stats["quality_delta_from_local"] = stats["mean_quality_score_out_of_3"] - baseline
        stats["latency_ratio_to_local"] = stats["mean_latency_seconds"] / baseline_latency if baseline_latency else None
    qualifying = [model for model in report["summary"] if model != config.model
                  and report["summary"][model]["mean_quality_score_out_of_3"] >= baseline
                  and report["summary"][model]["mean_quality_score_out_of_3"] == 3
                  and all(item["identical_rubric"] for item in report["summary"][model]["stability"].values())]
    if qualifying:
        report["proposal"] = "Synthetic evidence supports a separate human-reviewed proposal for: " + ", ".join(qualifying) + ". Production remains unchanged."
    if checkpoint:
        checkpoint(report)
    return report
