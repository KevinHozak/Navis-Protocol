import concurrent.futures
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import online_ai


@pytest.fixture
def isolated_guard(tmp_path, monkeypatch):
    # Synthetic accounting tests need fresh fixture pricing, not an expired
    # production observation. This does not change runtime pricing evidence.
    monkeypatch.setattr(online_ai, "PRICE_REVIEW_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    paths = (tmp_path / "ai_experiments.json", tmp_path / "ai_usage.sqlite3")
    monkeypatch.setattr(online_ai, "_paths", lambda: paths)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    online_ai.configure({"monthly_budget_usd": 1.0})
    return paths


def test_online_unset_opt_in_is_disabled(isolated_guard):
    assert online_ai.diagnostics()["enabled"] is False
    with pytest.raises(online_ai.OnlineAIError, match="disabled"):
        online_ai._reserve("forge", 12)


def test_request_and_budget_boundaries_fail_closed(isolated_guard):
    online_ai.configure({"enabled": True})
    with pytest.raises(online_ai.OnlineAIError, match="request limit"):
        online_ai._reserve("forge", online_ai.MAX_INPUT_CHARS + 1)
    online_ai.configure({"monthly_budget_usd": 0.01})
    with pytest.raises(online_ai.OnlineAIError, match="worst-case cost"):
        online_ai._reserve("forge", 5_000)


def test_concurrent_reservations_cannot_exceed_hard_budget(isolated_guard):
    online_ai.configure({"enabled": True, "monthly_budget_usd": 0.01})

    def reserve(_):
        try:
            return online_ai._reserve("forge", 100)
        except online_ai.OnlineAIError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(reserve, range(12)))
    successes = [result for result in results if result]
    assert len(successes) == 1
    assert online_ai.diagnostics()["month_to_date_reserved_usd"] <= 0.01


def test_stale_price_and_missing_usage_fail_closed(isolated_guard, monkeypatch):
    online_ai.configure({"enabled": True, "monthly_budget_usd": 1})
    monkeypatch.setattr(online_ai, "PRICE_REVIEW_DATE", "2020-01-01")
    with pytest.raises(online_ai.OnlineAIError, match="pricing is stale"):
        online_ai._reserve("forge", 10)

    monkeypatch.setattr(online_ai, "PRICE_REVIEW_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    request_id, reserved = online_ai._reserve("forge", 10)
    with pytest.raises(online_ai.OnlineAIError, match="omitted usage"):
        online_ai._settle(request_id, reserved, None)
    conn = sqlite3.connect(isolated_guard[1])
    row = conn.execute("SELECT state,estimated_cost_usd FROM usage WHERE request_id=?", (request_id,)).fetchone()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(usage)")}
    conn.close()
    assert row[0] == "unknown_usage"
    assert row[1] == reserved
    assert not ({"prompt", "response", "contents", "api_key"} & columns)


def test_missing_api_key_refuses_online_generation(isolated_guard, monkeypatch):
    online_ai.configure({"enabled": True, "monthly_budget_usd": 1})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(online_ai.OnlineAIError, match="No online provider API key"):
        online_ai._reserve("forge", 10)


def test_monthly_reset_and_usage_records_are_content_free(isolated_guard):
    online_ai.configure({"enabled": True, "monthly_budget_usd": 1})
    request_id, reserved = online_ai._reserve("neural_chat", 25)
    usage = type("Usage", (), {"prompt_token_count": 10, "candidates_token_count": 20})()
    online_ai._settle(request_id, reserved, usage)
    conn = sqlite3.connect(isolated_guard[1])
    conn.execute("UPDATE usage SET period='2000-01' WHERE request_id=?", (request_id,))
    conn.commit()
    conn.close()
    assert online_ai.diagnostics()["month_to_date_reserved_usd"] == 0


def test_usage_settlement_includes_reasoning_tokens(isolated_guard):
    online_ai.configure({"enabled": True, "monthly_budget_usd": 1})
    request_id, reserved = online_ai._reserve("neural_chat", 25)
    usage = type("Usage", (), {"prompt_token_count": 10, "candidates_token_count": 20, "thoughts_token_count": 5})()
    online_ai._settle(request_id, reserved, usage)
    conn = sqlite3.connect(isolated_guard[1])
    output_tokens = conn.execute("SELECT output_tokens FROM usage WHERE request_id=?", (request_id,)).fetchone()[0]
    conn.close()
    assert output_tokens == 25


def test_vault_content_is_disabled_until_separate_opt_in(isolated_guard):
    online_ai.configure({"enabled": True, "monthly_budget_usd": 1})
    assert online_ai.diagnostics()["allow_vault_content"] is False


def test_background_generation_paths_have_no_paid_provider_fallback():
    backend = Path(__file__).resolve().parents[1]
    main_source = (backend / "main.py").read_text(encoding="utf-8")
    sync_source = (backend / "services" / "sync_engine.py").read_text(encoding="utf-8")
    realm_source = (backend / "services" / "moongate.py").read_text(encoding="utf-8")
    banter_source = (backend / "services" / "banter_generator.py").read_text(encoding="utf-8")
    image_source = (backend / "batch_generate_cards.py").read_text(encoding="utf-8")

    assert "# War Room includes recent journals and persona dossiers; it stays local-only." in main_source
    assert "generate_content(" not in sync_source
    assert "provider = OllamaProvider()" in banter_source
    assert "generate_squad_banter(count=3)" in realm_source
    assert "generate_images(" not in image_source
    assert "embed_content(" not in banter_source
