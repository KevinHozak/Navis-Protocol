import pytest
from fastapi.testclient import TestClient

import main


@pytest.mark.parametrize("content", [None, "{", "[]", "{}", '{"squad":null}', '{"squad":[null]}'])
def test_status_unavailable_is_not_successful_default(tmp_path, monkeypatch, content):
    source = tmp_path / "status.json"
    if content is not None:
        source.write_text(content, encoding="utf-8")
    monkeypatch.setattr(main, "STATUS_PATH", str(source))
    response = TestClient(main.app).get("/api/status")
    assert response.status_code == 503
    assert "Earth" not in response.text
    assert str(tmp_path) not in response.text


@pytest.mark.parametrize("content", ['{"last_updated":"2026-10-26","squad":[]}', '{"last_updated":"2026-10-26"}'])
def test_valid_empty_squad_remains_available(tmp_path, monkeypatch, content):
    source = tmp_path / "status.json"
    source.write_text(content, encoding="utf-8-sig")
    monkeypatch.setattr(main, "STATUS_PATH", str(source))
    response = TestClient(main.app).get("/api/status")
    assert response.status_code == 200
    assert response.json().get("squad", []) == []
    assert response.json()["last_updated"] == "2026-10-26"


def test_unavailable_startup_root_neither_writes_nor_claims_completion(tmp_path, monkeypatch):
    from services.sync_engine import check_startup_holocron_catchup
    monkeypatch.delenv("NAVIS_NATIVE_FIXTURE_MODE", raising=False)
    root = tmp_path / "unavailable"
    result = check_startup_holocron_catchup(str(root))
    assert not root.exists()
    assert "no artifact persisted" in result
    assert "Synthesized" not in result
