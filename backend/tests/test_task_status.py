"""S022 behavioral acceptance on synthetic Vaults; HTTP and native Python bridge."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
import main
from services import progression_db, rpg_engine
from services.directive_completion import transition
from services.task_toggle import toggle, ToggleConflict

DAY = '2026-10-26'
RELATIVE = f'Journal/2026/10/{DAY}.md'
RAW = '\ufeff# Fixture\r\n## 🥾 The Kinetic Outland\r\n- [ ] Keep **雪**\r\n  note stays here\r\n- [X] Legacy checked\r\n'.encode()


def test_release_packages_both_canonical_status_entrypoints():
    repo = Path(__file__).parents[2]
    resources = json.loads((repo / 'frontend/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['bundle']['resources']
    for source in ('native_task_toggle.py', 'native_directive.py', 'services/task_toggle.py', 'services/directive_completion.py'):
        assert resources[f'../../backend/{source}'] == f'backend/{source}'


@pytest.fixture
def vault(tmp_path, monkeypatch):
    (tmp_path / 'Bridge').mkdir()
    journal = tmp_path / RELATIVE
    journal.parent.mkdir(parents=True)
    journal.write_bytes(RAW)
    (tmp_path / 'Bridge/status.json').write_text(json.dumps({'last_updated': DAY, 'squad': []}))
    (tmp_path / 'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))
    state = {'active_tasks': [{'id': 'a', 'text': 'Keep **雪**', 'area': 'world', 'status': 'pending'}],
             'tasks': [{'id': 'r', 'text': 'Recurring', 'area': 'world', 'frequency': 'daily', 'next_due': DAY}]}
    (tmp_path / 'Bridge/ops_state.json').write_text(json.dumps(state))
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(tmp_path / 'Keeper/navis_progression.db'))
    return tmp_path


def bridge(root, script, path, body):
    env = {**os.environ, 'NAVIS_ROOT': str(root), 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
    output = subprocess.run([sys.executable, str(Path(__file__).parents[1] / script)],
                            input=json.dumps({'path': path, 'body': body}), text=True,
                            encoding='utf-8', capture_output=True, env=env, timeout=30, check=True)
    return json.loads(output.stdout)


@pytest.mark.parametrize('transport', ['http', 'native'])
@pytest.mark.parametrize('desired', ['pending', 'in_progress', 'deferred', 'cancelled', 'done'])
def test_journal_status_roundtrip_and_stale_rejection(vault, transport, desired):
    file = vault / RELATIVE
    body = {'file_path': RELATIVE, 'expected_content': RAW.decode('utf-8-sig'),
            'target_text': 'Keep 雪', 'line_number': 3, 'task_status': desired}
    def send():
        if transport == 'native':
            result = bridge(vault, 'native_task_toggle.py', '/api/tasks/toggle', body)
            return result['status'], result['body']
        response = TestClient(main.app).post('/api/tasks/toggle', json=body)
        return response.status_code, response.json()
    status, result = send()
    assert status == 200, result
    assert result['saved'] and result['task_status'] == desired
    raw = file.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf') and raw.count(b'\r\n') == RAW.count(b'\r\n')
    assert raw.endswith(b'  note stays here\r\n- [X] Legacy checked\r\n')
    assert (b'- [x] Keep' in raw) == (desired == 'done')
    # The exact old snapshot is stale, even when a response was lost.
    assert send()[0] == 409
    assert file.read_bytes() == raw
    body['expected_content'] = result['content']
    status, replay = send()
    assert status == 200 and replay['modified'] is False
    assert file.read_bytes() == raw


def current(root, recurring=False):
    state = json.loads((root / 'Bridge/ops_state.json').read_text(encoding='utf-8-sig'))
    return state['tasks' if recurring else 'active_tasks'][0]


@pytest.mark.parametrize('recurring', [False, True])
def test_directive_reopen_and_recomplete_keeps_provenance_and_schedule(vault, recurring):
    task = current(vault, recurring)
    identity = task['id']
    original_schedule = task.get('next_due')
    for status in ['in_progress', 'deferred', 'cancelled', 'pending']:
        result = transition(vault, identity, status, current(vault, recurring), is_recurring=recurring)
        assert result['saved']
        assert current(vault, recurring).get('next_due') == original_schedule
        assert not (vault / 'Keeper/navis_progression.db').exists()
    done = transition(vault, identity, 'done', current(vault, recurring), is_recurring=recurring)
    marker = done['task']['completion']['marker']
    assert (vault / RELATIVE).read_text(encoding='utf-8-sig').count(marker) == 1
    transition(vault, identity, 'pending', current(vault, recurring), is_recurring=recurring)
    reopened = current(vault, recurring)
    assert reopened['completion']['phase'] == 'reopened'
    assert reopened['completion_history'][0]['marker'] == marker
    assert reopened.get('next_due') == original_schedule
    transition(vault, identity, 'done', reopened, is_recurring=recurring)
    after = (vault / RELATIVE).read_bytes()
    transition(vault, identity, 'done', current(vault, recurring), is_recurring=recurring)
    assert (vault / RELATIVE).read_bytes() == after
    assert after.decode('utf-8-sig').count(marker) == 1


def test_ambiguous_and_stale_targets_are_read_only(vault):
    file = vault / RELATIVE
    file.write_bytes(RAW + b'- [ ] Keep **' + '雪'.encode() + b'**\r\n')
    before = file.read_bytes()
    with pytest.raises(ToggleConflict):
        toggle(vault, file, {'target_text': 'Keep 雪', 'expected_content': before.decode('utf-8-sig'), 'task_status': 'done'})
    assert file.read_bytes() == before
    old = current(vault)
    transition(vault, 'a', 'deferred', old)
    with pytest.raises(ValueError, match='changed'):
        transition(vault, 'a', 'done', old)


@pytest.mark.parametrize('recurring', [False, True])
def test_native_directive_status_uses_same_contract(vault, recurring):
    task = current(vault, recurring)
    path = '/api/recurring/complete' if recurring else '/api/active_tasks/complete'
    result = bridge(vault, 'native_directive.py', path,
                    {'task_id': task['id'], 'task_status': 'deferred', 'expected_task': task})
    assert result['status'] == 200 and result['body']['saved']
    saved = current(vault, recurring)
    assert (saved['occurrence_status']['status'] if recurring else saved['status']) == 'deferred'
    assert (vault / RELATIVE).read_bytes() == RAW


def test_journal_done_reopen_and_recomplete_reconciles_same_source(vault):
    file = vault / RELATIVE
    request = {'target_text': 'Keep 雪', 'line_number': 3}
    identity = None
    for desired, expected_xp in [('done', 14), ('cancelled', 12), ('done', 14), ('done', 14)]:
        result = toggle(vault, file, {**request, 'task_status': desired,
                                     'expected_content': file.read_bytes().decode('utf-8-sig')})
        assert result['xp_status'] == 'complete'
        if identity:
            assert result['task_id'] == identity
        identity = result['task_id']
        states = progression_db.get_source_states('journal_daily', 'Journal/2026/10/26.md#daily-xp')
        assert states['keeper']['amount'] == expected_xp


def test_reopen_projection_failure_is_recoverable_without_duplicate_history(vault):
    task = current(vault)
    transition(vault, 'a', 'done', task)
    def unavailable(**kwargs):
        raise RuntimeError('synthetic XP projection obstruction')
    with pytest.raises(RuntimeError):
        transition(vault, 'a', 'pending', current(vault), award=unavailable)
    interrupted = current(vault)
    assert interrupted['completion']['phase'] == 'reopening'
    transition(vault, 'a', 'pending', interrupted)
    assert len(current(vault)['completion_history']) == 1
    transition(vault, 'a', 'done', current(vault))
    assert len(current(vault)['completion_history']) == 1


def test_web_directive_status_snapshot_and_completed_readback(vault):
    client = TestClient(main.app)
    task = current(vault)
    response = client.post('/api/active_tasks/a/complete', json={'task_status': 'done', 'expected_task': task})
    assert response.status_code == 200
    assert client.get('/api/active_tasks').json() == []
    listing = client.get('/api/active_tasks?include_completed=true').json()
    assert listing[0]['status'] == 'completed'
    response = client.post('/api/active_tasks/a/complete', json={'task_status': 'pending', 'expected_task': listing[0]})
    assert response.status_code == 200 and response.json()['saved']


def test_managed_operations_entry_is_not_collected_or_reordered(vault, monkeypatch):
    from services import sync_engine
    folder = vault / 'Operations/The Kinetic Outland'
    folder.mkdir(parents=True)
    source = folder / 'Tasks.md'
    source.write_bytes(b'\xef\xbb\xbf- [ ] Keep task\r\n  attached note\r\n')
    toggle(vault, source, {'target_text': 'Keep task', 'expected_content': source.read_bytes().decode('utf-8-sig'), 'task_status': 'done'})
    before = source.read_bytes()
    settings = vault / 'Bridge/settings.json'
    settings.write_text(json.dumps({'paths': {'operations_dir': str(folder.parent), 'journal_root': str(vault / 'Journal')}}))
    monkeypatch.setattr(sync_engine, 'NAVIS_ROOT', str(vault))
    monkeypatch.setattr(sync_engine, 'SETTINGS_FILE', str(settings))
    sync_engine.sync_active_tasks()
    assert source.read_bytes() == before


def test_edit_during_reopen_is_preserved_and_recovery_reloads(vault):
    transition(vault, 'a', 'done', current(vault))
    path = vault / 'Bridge/ops_state.json'
    def concurrent_edit(**kwargs):
        changed = json.loads(path.read_text(encoding='utf-8-sig'))
        changed['unrelated_note'] = 'synthetic concurrent edit'
        path.write_text(json.dumps(changed), encoding='utf-8')
    with pytest.raises(ValueError, match='changed during reconciliation'):
        transition(vault, 'a', 'pending', current(vault), award=concurrent_edit)
    assert json.loads(path.read_text(encoding='utf-8-sig'))['unrelated_note'] == 'synthetic concurrent edit'
    transition(vault, 'a', 'pending', current(vault))
    assert json.loads(path.read_text(encoding='utf-8-sig'))['unrelated_note'] == 'synthetic concurrent edit'
