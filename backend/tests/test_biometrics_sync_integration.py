from pathlib import Path
from unittest.mock import Mock

from services import sync_engine


REPO = Path(__file__).resolve().parents[2]


def test_default_script_resolves_to_backend_source(monkeypatch):
    monkeypatch.delenv("NAVIS_BIOMETRICS_SCRIPT", raising=False)
    expected = REPO / "backend" / "scripts" / "sync_biometrics.py"
    assert Path(sync_engine._biometrics_script_path()).resolve() == expected.resolve()
    assert expected.is_file()


def test_explicit_script_override_is_preserved(monkeypatch, tmp_path):
    configured = tmp_path / "custom_sync_biometrics.py"
    monkeypatch.setenv("NAVIS_BIOMETRICS_SCRIPT", str(configured))
    assert sync_engine._biometrics_script_path() == str(configured)


def test_child_sync_receives_configured_vault_and_external_auth_paths(monkeypatch, tmp_path):
    vault_root = tmp_path / "vault"
    client_file = tmp_path / "oauth-client.json"
    token_file = tmp_path / "biometrics-token.json"
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(vault_root))
    monkeypatch.setenv("NAVIS_BIOMETRICS_CLIENT_SECRETS_FILE", str(client_file))
    monkeypatch.setenv("NAVIS_BIOMETRICS_TOKEN_FILE", str(token_file))
    runner = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(sync_engine.subprocess, "run", runner)

    sync_engine._run_biometrics_sync("bundled/backend/scripts/sync_biometrics.py")

    command, = runner.call_args.args
    kwargs = runner.call_args.kwargs
    assert command[-1] == "bundled/backend/scripts/sync_biometrics.py"
    assert kwargs["env"]["NAVIS_ROOT"] == str(vault_root)
    assert kwargs["env"]["NAVIS_BIOMETRICS_CLIENT_SECRETS_FILE"] == str(client_file)
    assert kwargs["env"]["NAVIS_BIOMETRICS_TOKEN_FILE"] == str(token_file)
