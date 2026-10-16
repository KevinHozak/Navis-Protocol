import asyncio
import concurrent.futures
import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import ai_benchmark as benchmark, online_ai


@pytest.fixture
def guard(tmp_path, monkeypatch):
    paths = (tmp_path / "settings.json", tmp_path / "usage.sqlite3")
    monkeypatch.setattr(online_ai, "_paths", lambda: paths)
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    online_ai.configure({"enabled": True, "monthly_budget_usd": 1})
    return paths


def test_plan_is_bounded_and_never_reads_vault_or_key(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No configuration/ledger access during planning")
    monkeypatch.setattr(online_ai, "_paths", forbidden)
    plan = benchmark.plan()
    assert plan["requests_per_model"] == 6
    assert 0 < plan["maximum_online_cost_usd"] < 0.05
    assert plan["production_activation"] is False
    assert len(plan["prompt_set_sha256"]) == 64


@pytest.mark.parametrize("repeats,limit", [(1, .05), (4, .05), (2, float("nan")), (2, .11), (2, .00001)])
def test_bad_run_limits_rejected(repeats, limit):
    with pytest.raises(online_ai.OnlineAIError):
        benchmark.plan(repeats, limit)


def test_stale_candidate_rejected_before_dispatch(monkeypatch):
    monkeypatch.setattr(benchmark, "CANDIDATES", (replace(benchmark.CANDIDATES[0], reviewed="2020-01-01"),))
    with pytest.raises(online_ai.OnlineAIError, match="stale"):
        benchmark.plan()


def test_shared_monthly_cap_is_atomic_across_models_and_features(guard):
    online_ai.configure({"monthly_budget_usd": .01})
    def reserve(index):
        try:
            if index % 2:
                return online_ai._reserve("synthetic_benchmark", 100, pricing=benchmark.CANDIDATES[0], output_limit=512, cap_fraction=.95)
            return online_ai._reserve("neural_chat", 100)
        except online_ai.OnlineAIError:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(reserve, range(24)))
    assert any(results)
    assert online_ai.diagnostics()["month_to_date_reserved_usd"] <= .01
    conn = sqlite3.connect(guard[1])
    assert set(row[0] for row in conn.execute("SELECT model FROM usage")) <= {online_ai.MODEL, benchmark.CANDIDATES[0].model}
    conn.close()


def test_candidate_usage_settles_at_its_own_price(guard):
    price = benchmark.CANDIDATES[0]
    identifier, reserved = online_ai._reserve("synthetic_benchmark", 100, pricing=price, output_limit=512)
    online_ai._settle(identifier, reserved, SimpleNamespace(prompt_token_count=10, candidates_token_count=20, thoughts_token_count=5), pricing=price)
    conn = sqlite3.connect(guard[1])
    row = conn.execute("SELECT estimated_cost_usd,model,state FROM usage").fetchone()
    conn.close()
    assert row[0] == pytest.approx(.000040)
    assert row[1:] == (price.model, "settled")


def test_automated_rubric_rejects_wrong_types_facts_and_prose():
    task = benchmark.TASKS[0]
    assert sum(benchmark.rubric(task, task.expected_json).values()) == 3
    assert benchmark.rubric(task, '{"total":false,"unit":"bolts"}')["schema"] == 0
    assert benchmark.rubric(task, '{"total":20,"unit":"bolts"}')["correctness"] == 0
    assert sum(benchmark.rubric(task, 'Here is your answer: ' + task.expected_json).values()) == 0


def mock_baseline(monkeypatch):
    async def local(task, config):
        return task.expected_json, 15, 25
    monkeypatch.setattr(benchmark, "_local", local)


def test_local_mode_never_accesses_online_and_has_stability(monkeypatch):
    mock_baseline(monkeypatch)
    def forbidden():
        raise AssertionError("No ledger access in local mode")
    monkeypatch.setattr(online_ai, "diagnostics", forbidden)
    report = asyncio.run(benchmark.run())
    assert report["status"] == "complete"
    assert len(report["rows"]) == 6
    stats = next(iter(report["summary"].values()))
    assert stats["mean_quality_score_out_of_3"] == 3
    assert all(item["identical_output"] for item in stats["stability"].values())
    serialized = json.dumps(report)
    assert "Three boxes hold" not in serialized
    assert not any({"prompt", "response", "contents", "api_key", "output"} & set(row) for row in report["rows"])
    assert report["production_activation"] is False


def test_online_requires_both_opt_ins_and_full_run_headroom(guard, monkeypatch):
    mock_baseline(monkeypatch)
    online_ai.configure({"enabled": False})
    with pytest.raises(online_ai.OnlineAIError, match="Enable P2"):
        asyncio.run(benchmark.run(enable_online=True))
    online_ai.configure({"enabled": True, "monthly_budget_usd": .01})
    online_ai._reserve("neural_chat", 100)
    with pytest.raises(online_ai.OnlineAIError, match="safety margin"):
        asyncio.run(benchmark.run(enable_online=True))


def test_baseline_failure_stops_before_any_paid_request(guard, monkeypatch):
    async def failed(*args):
        raise RuntimeError("private provider body secret-test-key")
    monkeypatch.setattr(benchmark, "_local", failed)
    report = asyncio.run(benchmark.run(enable_online=True))
    assert report["status"] == "stopped_on_error"
    assert len(report["rows"]) == 1
    assert online_ai.diagnostics()["month_to_date_reserved_usd"] == 0
    assert "secret-test-key" not in json.dumps(report)


class FakeResponse:
    status = 200
    def __init__(self, payload):
        self.payload = payload
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def json(self):
        return self.payload
    def raise_for_status(self):
        assert self.status == 200


def mock_rest(monkeypatch, *, missing_usage=False, fail=False, status=200):
    calls = []
    class Session:
        def __init__(self, **kwargs):
            assert kwargs["timeout"].total == 90
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        def post(self, url, **kwargs):
            if fail:
                raise RuntimeError("private upstream body secret-test-key")
            prompt = kwargs["json"]["contents"][0]["parts"][0]["text"]
            assert prompt in {task.prompt for task in benchmark.TASKS}
            assert kwargs["allow_redirects"] is False
            assert "secret-test-key" not in url
            assert kwargs["headers"]["x-goog-api-key"] == "secret-test-key"
            assert "systemInstruction" not in kwargs["json"]
            assert kwargs["json"]["generationConfig"]["maxOutputTokens"] == 512
            assert kwargs["json"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
            calls.append(prompt)
            task = next(task for task in benchmark.TASKS if task.prompt == prompt)
            payload = {"candidates": [{"content": {"parts": [{"text": task.expected_json}]}}]}
            if not missing_usage:
                payload["usageMetadata"] = {"promptTokenCount": 15, "candidatesTokenCount": 25}
            response = FakeResponse(payload if status == 200 else {"error": {"status": "NOT_FOUND", "message": "private upstream body secret-test-key"}})
            response.status = status
            return response
    monkeypatch.setattr(benchmark.aiohttp, "ClientSession", Session)
    return calls


def test_complete_synthetic_run_reports_metadata_and_no_private_content(guard, monkeypatch):
    mock_baseline(monkeypatch)
    calls = mock_rest(monkeypatch)
    checkpoints = []
    report = asyncio.run(benchmark.run(enable_online=True, checkpoint=lambda report: checkpoints.append(len(report["rows"]))))
    assert report["status"] == "complete"
    assert len(calls) == 12 and len(report["rows"]) == 18
    assert len(checkpoints) == 19
    assert online_ai.diagnostics()["allow_vault_content"] is False
    assert "separate human-reviewed proposal" in report["proposal"]
    assert report["production_activation"] is False
    assert "secret-test-key" not in json.dumps(report)
    assert all(row["actual_billed_cost_usd"] is None for row in report["rows"])
    assert online_ai.diagnostics()["month_to_date_reserved_usd"] < report["maximum_online_cost_usd"]


@pytest.mark.parametrize("missing_usage,fail", [(True, False), (False, True)])
def test_unknown_usage_or_failure_keeps_reservation_and_stops(guard, monkeypatch, missing_usage, fail):
    mock_baseline(monkeypatch)
    mock_rest(monkeypatch, missing_usage=missing_usage, fail=fail)
    report = asyncio.run(benchmark.run(enable_online=True))
    assert report["status"] == "stopped_on_error"
    assert len(report["rows"]) == 7
    last = report["rows"][-1]
    assert last["accounting_state"] == "unknown_usage"
    assert last["accounted_cost_usd"] == last["reserved_cost_usd"]
    assert "secret-test-key" not in json.dumps(report)


def test_http_failure_reports_only_safe_status_and_retains_reservation(guard, monkeypatch):
    mock_baseline(monkeypatch)
    mock_rest(monkeypatch, status=404)
    report = asyncio.run(benchmark.run(enable_online=True))
    assert report["status"] == "stopped_on_error"
    last = report["rows"][-1]
    assert last["error"] == "http_404"
    assert last["provider_error_status"] == "NOT_FOUND"
    assert last["rejected_config_fields"] == []
    assert last["accounting_state"] == "unknown_usage"
    assert last["accounted_cost_usd"] == last["reserved_cost_usd"]
    assert "private upstream" not in json.dumps(report)
    assert "secret-test-key" not in json.dumps(report)


def test_local_request_limits_and_empty_output_usage_preserved(monkeypatch):
    class Session:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        def post(self, url, **kwargs):
            payload = kwargs["json"]
            assert payload["think"] is False
            assert payload["options"]["num_predict"] == 512
            assert payload["prompt"] in {task.prompt for task in benchmark.TASKS}
            return FakeResponse({"response": "", "prompt_eval_count": 42, "eval_count": 1})
    monkeypatch.setattr(benchmark.aiohttp, "ClientSession", Session)
    report = asyncio.run(benchmark.run())
    assert report["status"] == "stopped_on_error"
    row = report["rows"][0]
    assert row["error"] == "empty_output"
    assert row["input_tokens"] == 42 and row["output_tokens"] == 1


def test_benchmark_cli_rejects_reports_inside_vault(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import benchmark_ai
    monkeypatch.setenv("NAVIS_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["benchmark_ai", "--run-local", "--output", str(tmp_path / "report.json")])
    assert benchmark_ai.main() == 1
    assert "outside the Vault" in capsys.readouterr().err
    assert not (tmp_path / "report.json").exists()
