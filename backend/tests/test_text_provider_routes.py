import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from services.openrouter_provider import diagnostics


def test_diagnostics_are_read_only_and_do_not_expose_key(monkeypatch, tmp_path):
    config = tmp_path / 'disabled.json'
    config.write_text('{"enabled": false}')
    monkeypatch.setenv('NAVIS_OPENROUTER_CONFIG', str(config))
    monkeypatch.setenv('OPENROUTER_API_KEY', 'synthetic-placeholder')
    before = sorted(p.name for p in tmp_path.iterdir())
    value = diagnostics()
    assert value['enabled'] is False
    assert 'synthetic-placeholder' not in json.dumps(value)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize('packaged', [False, True])
def test_native_disabled_routes_make_no_vault_or_accounting_writes(tmp_path, packaged):
    repo = Path(__file__).resolve().parents[2]
    backend = repo / 'backend'
    if packaged:
        config = repo / 'frontend/src-tauri/tauri.conf.json'
        bundle = tmp_path / 'bundle'
        for source, target in json.loads(config.read_text())['bundle']['resources'].items():
            destination = bundle / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((config.parent / source).read_bytes())
        backend = bundle / 'backend'
    vault = tmp_path / 'vault'
    vault.mkdir()
    env = {**os.environ, 'NAVIS_AI_PROVIDER': 'openrouter', 'NAVIS_ROOT': str(vault), 'PYTHONDONTWRITEBYTECODE': '1'}
    env.pop('NAVIS_OPENROUTER_CONFIG', None)
    env.pop('OPENROUTER_API_KEY', None)
    for path, body, status in [
        ('/api/ai/text/status', {}, 200),
        ('/api/journal/brief/generate', {'original': 'Synthetic tangled note. Preserve originals.'}, 503),
        ('/api/journal/entry/polish', {'entry': '- [ ] Synthetic draft', 'section': 'sanctum'}, 503),
        ('/api/neural/banter/generate?count=1', {}, 503),
    ]:
        process = subprocess.run([sys.executable, str(backend / 'native_actionable_brief.py')],
                                 input=json.dumps({'path': path, 'body': body}), env=env,
                                 cwd=tmp_path, text=True, capture_output=True, timeout=15)
        assert process.returncode == 0, process.stderr
        result = json.loads(process.stdout)
        assert result['status'] == status, result
        if status == 200:
            assert result['body']['enabled'] is False
        else:
            assert ('not generated' if 'banter' in path else 'disabled') in result['body']['detail']
    assert not list(vault.rglob('*'))


def test_web_disabled_polish_keeps_original_and_returns_safe_diagnostic(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    monkeypatch.delenv('NAVIS_OPENROUTER_CONFIG', raising=False)
    monkeypatch.setenv('NAVIS_AI_PROVIDER', 'openrouter')
    with TestClient(app) as client:
        status = client.get('/api/ai/text/status')
        assert status.status_code == 200 and status.json()['enabled'] is False
        response = client.post('/api/journal/entry/polish', json={'entry': '- [ ] Original synthetic draft', 'section': 'sanctum'})
        assert response.status_code == 503
        assert 'disabled' in response.json()['detail']
