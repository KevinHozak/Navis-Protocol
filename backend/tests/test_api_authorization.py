import json
import pytest
from fastapi.testclient import TestClient
import main


@pytest.fixture
def auth_vault(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    bridge = vault / "Bridge"
    bridge.mkdir()
    (bridge / "status.json").write_text(
        json.dumps({"current_realm": "Earth", "squad": []}),
        encoding="utf-8-sig",
    )
    (bridge / "settings.json").write_text(
        json.dumps({"lexicon": {"pillars": {}}}),
        encoding="utf-8-sig",
    )
    (bridge / "CompanionStats.json").write_text(
        json.dumps({"companions": {}}),
        encoding="utf-8-sig",
    )

    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))
    monkeypatch.setattr(main, "STATUS_PATH", str(bridge / "status.json"))
    return vault


def test_api_requires_authorization_when_key_configured(auth_vault, monkeypatch):
    monkeypatch.setenv("NAVIS_API_KEY", "super-secret-vanguard-key")
    client = TestClient(main.app)

    # 1. Unauthenticated request to protected endpoint fails
    res_unauth = client.get("/api/status")
    assert res_unauth.status_code == 401
    assert "WWW-Authenticate" in res_unauth.headers
    assert res_unauth.json()["detail"] == "Unauthorized: valid authentication token required"

    # 2. Invalid Bearer token fails
    res_bad_bearer = client.get(
        "/api/status", headers={"Authorization": "Bearer wrong-key"}
    )
    assert res_bad_bearer.status_code == 401

    # 3. Invalid X-Vanguard-Key header fails
    res_bad_header = client.get(
        "/api/status", headers={"X-Vanguard-Key": "wrong-key"}
    )
    assert res_bad_header.status_code == 401

    # 4. Valid Bearer token succeeds
    res_valid_bearer = client.get(
        "/api/status",
        headers={"Authorization": "Bearer super-secret-vanguard-key"},
    )
    assert res_valid_bearer.status_code == 200
    assert res_valid_bearer.json()["current_realm"] == "Earth"

    # 5. Valid X-Vanguard-Key succeeds
    res_valid_header = client.get(
        "/api/status", headers={"X-Vanguard-Key": "super-secret-vanguard-key"}
    )
    assert res_valid_header.status_code == 200


def test_auth_status_and_verify_endpoints(monkeypatch):
    monkeypatch.setenv("NAVIS_API_KEY", "vanguard-token-42")
    client = TestClient(main.app)

    # Status endpoint is public/exempt
    res_status = client.get("/api/auth/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["auth_required"] is True
    assert status_data["mode"] == "api_key"
    assert status_data["authenticated"] is False

    # Status with auth header reports authenticated: True
    res_status_auth = client.get(
        "/api/auth/status", headers={"Authorization": "Bearer vanguard-token-42"}
    )
    assert res_status_auth.status_code == 200
    assert res_status_auth.json()["authenticated"] is True

    # Verify with invalid key
    res_verify_bad = client.post("/api/auth/verify", json={"key": "wrong"})
    assert res_verify_bad.status_code == 401

    # Verify with valid key in JSON body
    res_verify_good = client.post(
        "/api/auth/verify", json={"key": "vanguard-token-42"}
    )
    assert res_verify_good.status_code == 200
    assert res_verify_good.json()["authenticated"] is True

    # Verify with valid header
    res_verify_header = client.post(
        "/api/auth/verify", headers={"X-Vanguard-Key": "vanguard-token-42"}
    )
    assert res_verify_header.status_code == 200


def test_cors_origin_constraints(auth_vault, monkeypatch):
    monkeypatch.setenv("NAVIS_API_KEY", "cors-test-key")
    client = TestClient(main.app)

    # 1. Allowed origin receives Access-Control-Allow-Origin
    res_allowed = client.get(
        "/api/status",
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer cors-test-key",
        },
    )
    assert res_allowed.status_code == 200
    assert (
        res_allowed.headers.get("access-control-allow-origin")
        == "http://localhost:3000"
    )
    assert res_allowed.headers.get("access-control-allow-credentials") == "true"

    # 2. Unauthorized request from allowed origin still receives CORS headers on 401
    res_401_cors = client.get(
        "/api/status", headers={"Origin": "http://localhost:3000"}
    )
    assert res_401_cors.status_code == 401
    assert (
        res_401_cors.headers.get("access-control-allow-origin")
        == "http://localhost:3000"
    )

    # 3. Disallowed external origin does NOT receive Access-Control-Allow-Origin
    res_disallowed = client.get(
        "/api/status",
        headers={
            "Origin": "https://malicious-website.com",
            "Authorization": "Bearer cors-test-key",
        },
    )
    assert res_disallowed.headers.get("access-control-allow-origin") is None

    # 4. Preflight OPTIONS from allowed origin
    res_options_good = client.options(
        "/api/tasks/toggle",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Vanguard-Key",
        },
    )
    assert res_options_good.status_code == 200
    assert (
        res_options_good.headers.get("access-control-allow-origin")
        == "http://127.0.0.1:3000"
    )

    # 5. Preflight OPTIONS from untrusted origin is rejected
    res_options_bad = client.options(
        "/api/tasks/toggle",
        headers={
            "Origin": "https://attacker.evil",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_options_bad.status_code == 400


def test_loopback_development_mode_when_key_unset(auth_vault, monkeypatch):
    monkeypatch.delenv("NAVIS_API_KEY", raising=False)
    monkeypatch.delenv("NAVIS_REQUIRE_AUTH", raising=False)
    client = TestClient(main.app)

    # Auth status reports loopback_dev mode and not required
    res_status = client.get("/api/auth/status")
    assert res_status.status_code == 200
    assert res_status.json()["auth_required"] is False
    assert res_status.json()["mode"] == "loopback_dev"

    # Loopback dev request to protected route passes without credentials
    res_protected = client.get("/api/status")
    assert res_protected.status_code == 200

    # But request carrying untrusted external Origin is rejected
    res_bad_origin = client.get(
        "/api/status", headers={"Origin": "https://external-site.com"}
    )
    assert res_bad_origin.status_code == 401

    # When NAVIS_REQUIRE_AUTH=true is set without key, requests fail closed
    monkeypatch.setenv("NAVIS_REQUIRE_AUTH", "true")
    res_enforced = client.get("/api/status")
    assert res_enforced.status_code == 401
