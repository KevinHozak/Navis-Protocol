from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

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
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
    assert kwargs["encoding"] == "utf-8"


@pytest.mark.parametrize("exit_code", [0, 1])
def test_child_unicode_output_is_captured_on_success_and_failure(monkeypatch, tmp_path, exit_code):
    helper = tmp_path / "unicode_helper.py"
    helper.write_text(
        "import sys\n"
        "print('\\u2705 \\u4f60\\u597d')\n"
        "print('\\u26a0 diagnostics', file=sys.stderr)\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    # Reproduce a legacy Windows parent environment; the helper must override it.
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setattr(sync_engine, "NAVIS_ROOT", str(tmp_path))
    if exit_code:
        with pytest.raises(subprocess.CalledProcessError) as raised:
            sync_engine._run_biometrics_sync(str(helper))
        result = raised.value
    else:
        result = sync_engine._run_biometrics_sync(str(helper))
    assert result.stdout.strip() == "\u2705 \u4f60\u597d"
    assert result.stderr.strip() == "\u26a0 diagnostics"
