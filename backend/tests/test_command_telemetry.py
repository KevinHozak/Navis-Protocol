import json
import pytest
from fastapi.testclient import TestClient
import main


@pytest.fixture
def telemetry_vault(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    bridge = vault / "Bridge"
    bridge.mkdir()

    status_data = {
        "current_realm": "Emerald Sea",
        "last_updated": "2026-10-01",
        "system_integrity": 88,
        "active_missions": [
            "Midnight Restoration",
            "Cognitive Offload",
            "Texas Expedition",
        ],
        "squad": [
            {"name": "Tress", "role": "Kind Practicality"}
        ],
    }
    (bridge / "status.json").write_text(
        json.dumps(status_data),
        encoding="utf-8-sig",
    )
    (bridge / "readiness.json").write_text(
        json.dumps({
            "readiness": {
                "The Sanctum": {"label": "Sanctum Integrity", "value": 90, "color": "#00d4ff"},
                "The Domestic Breach": {"label": "Domestic Readiness", "value": 85, "color": "#00d4ff"},
                "The High-Velocity Front": {"label": "Frontline Status", "value": 60, "color": "#f1c40f"},
                "The Bureaucratic Gauntlet": {"label": "Gauntlet Flow", "value": 80, "color": "#00d4ff"},
                "The Kinetic Outland": {"label": "Outland Mastery", "value": 100, "color": "#00d4ff"},
            },
            "last_calculated": "2026-10-01T12:00:00",
        }),
        encoding="utf-8-sig",
    )
    (bridge / "CompanionStats.json").write_text(
        json.dumps({"companions": {"Tress": {"xp": 500, "level": 2}, "Keeper": {"xp": 1000, "level": 3}}}),
        encoding="utf-8-sig",
    )

    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))
    monkeypatch.setattr(main, "STATUS_PATH", str(bridge / "status.json"))
    monkeypatch.setenv("NAVIS_API_KEY", "")
    monkeypatch.setenv("NAVIS_REQUIRE_AUTH", "0")
    return vault, bridge / "status.json"


def test_status_endpoint_returns_authoritative_telemetry(telemetry_vault):
    client = TestClient(main.app)
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["current_realm"] == "Emerald Sea"
    assert data["last_updated"] == "2026-10-01"
    assert data["active_missions"] == [
        "Midnight Restoration",
        "Cognitive Offload",
        "Texas Expedition",
    ]
    assert data["squad"][0]["xp"] == 500
    assert data["keeper_level"] == 3


def test_readiness_endpoint_returns_manor_metrics(telemetry_vault):
    client = TestClient(main.app)
    res = client.get("/api/readiness")
    assert res.status_code == 200
    data = res.json()
    assert "readiness" in data
    assert data["readiness"]["The Sanctum"]["value"] == 90
    assert data["readiness"]["The Kinetic Outland"]["value"] == 100


def test_set_active_mission_persists_and_returns_updated_list(telemetry_vault):
    _, status_path = telemetry_vault
    client = TestClient(main.app)
    payload = {"slot_index": 1, "mission_name": "Sanctum Defense"}
    res = client.post("/api/status/mission", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["active_missions"] == [
        "Midnight Restoration",
        "Sanctum Defense",
        "Texas Expedition",
    ]

    # Verify on-disk file was updated
    saved = json.loads(status_path.read_text(encoding="utf-8-sig"))
    assert saved["active_missions"][1] == "Sanctum Defense"


def test_set_active_mission_out_of_range_returns_400(telemetry_vault):
    client = TestClient(main.app)
    # Slot 99 exceeds active_missions length
    payload = {"slot_index": 99, "mission_name": "Invalid Slot Mission"}
    res = client.post("/api/status/mission", json=payload)
    assert res.status_code == 400
    assert "out of range" in res.json()["detail"]

    # Negative slot index is rejected
    neg_payload = {"slot_index": -1, "mission_name": "Negative Slot Mission"}
    res_neg = client.post("/api/status/mission", json=neg_payload)
    assert res_neg.status_code == 400
    assert "out of range" in res_neg.json()["detail"]
