"""Calendar-day evidence projection on disposable Vaults, with no mutation services."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
import main
from services import completed_today as view

NOW = datetime.fromisoformat('2026-10-28T01:00:00+00:00')
CURRENT = 'Journal/2026/10/2026-10-27.md'
OLDER = 'Journal/2026/10/2026-10-25.md'


def timed(text, instant='2026-10-28T00:30:00Z', identity=None, status='done', checked='x'):
    marker = f' <!-- navis-task:{identity}:{status} -->' if identity else ''
    return f'- [{checked}] {text}{marker} <!-- navis-completion:' + json.dumps({'completed_at': instant, 'history': []}, separators=(',', ':')) + ' -->\r\n'


@pytest.fixture
def vault(tmp_path):
    (tmp_path / 'Bridge').mkdir()
    (tmp_path / 'Bridge/settings.json').write_text('{}')
    (tmp_path / 'Bridge/ops_state.json').write_text(json.dumps({'active_tasks': [], 'tasks': []}))
    write(tmp_path, CURRENT, '## 🏰 The Sanctum\r\n- [X] Logged activity\r\n')
    return tmp_path


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\xef\xbb\xbf' + text.encode('utf-8'))
    return path


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_older_origins_grouping_distinct_same_text_and_read_only(vault):
    write(vault, OLDER, '## 🥾 The Kinetic Outland\r\n' + timed('Same task', identity='a' * 32)
          + '  note stays\r\n' + timed('Same task', identity='b' * 32)
          + timed('Pending', identity='c' * 32, status='pending', checked=' ')
          + timed('Cancelled', identity='d' * 32, status='cancelled', checked=' ')
          + '- [x] Older unknown activity\r\n')
    before = snapshot(vault)
    data = view.build(vault, NOW)
    assert data['date'] == '2026-10-27' and data['timezone'] == 'America/Chicago'
    assert data['status'] == 'complete'
    assert [item['text'] for item in data['completed']] == ['Same task', 'Same task']
    assert len({item['id'] for item in data['completed']}) == 2
    assert all(item['area'] == 'world' and item['source']['path'] == OLDER for item in data['completed'])
    assert [item['text'] for item in data['journal_evidence']] == ['Logged activity']
    assert snapshot(vault) == before


def test_directive_provenance_deduplicates_and_reuses_preexisting_time(vault):
    marker = '<!-- navis-directive:' + 'a' * 64 + ' -->'
    write(vault, OLDER, '## ⚔️ The High-Velocity Front\r\n- [x] Canonical task ' + marker + '\r\n')
    operation = {'phase': 'complete', 'completed_at': '2026-10-28T00:30:00Z', 'journal_path': OLDER, 'marker': marker}
    task = {'id': 'active', 'status': 'completed', 'completion': operation, 'completion_history': [operation]}
    ops = vault / 'Bridge/ops_state.json'
    ops.write_text(json.dumps({'active_tasks': [task], 'tasks': []}))
    data = view.build(vault, NOW)
    assert len(data['completed']) == 1
    assert data['completed'][0]['area'] == 'front'
    assert data['completed'][0]['completed_at'] == view.normalized_instant(operation['completed_at'])
    # Copying a representation cannot create another occurrence.
    write(vault, CURRENT, '## 🏰 The Sanctum\r\n- [x] Canonical task ' + marker + '\r\n')
    data = view.build(vault, NOW)
    assert len(data['completed']) == 1 and data['status'] == 'partial'
    task['completion']['phase'] = 'reopened'; task['status'] = 'pending'
    ops.write_text(json.dumps({'active_tasks': [task], 'tasks': []}))
    assert view.build(vault, NOW)['completed'] == []


@pytest.mark.parametrize('now,instant,expected', [
    ('2026-11-01T06:30:00Z', '2026-11-01T07:30:00Z', True),
    ('2026-03-08T08:00:00Z', '2026-03-08T07:59:59Z', True),
    ('2026-10-28T04:59:59Z', '2026-10-28T05:00:00Z', False),
    ('2026-10-28T05:00:00Z', '2026-10-28T04:59:59Z', False),
])
def test_dst_and_midnight_are_calendar_instants(vault, now, instant, expected):
    write(vault, OLDER, '## 🏠 The Domestic Breach\r\n' + timed('Boundary', instant))
    data = view.build(vault, datetime.fromisoformat(now.replace('Z', '+00:00')))
    assert bool(data['completed']) is expected


def test_configured_zone_and_invalid_fallback(vault):
    settings = vault / 'Bridge/settings.json'
    settings.write_text(json.dumps({'timezone': 'Asia/Tokyo'}))
    assert view.build(vault, NOW)['date'] == '2026-10-28'
    settings.write_text(json.dumps({'timezone': 'invalid'}))
    assert view.build(vault, NOW)['date'] == '2026-10-27'


def test_partial_unreadable_limit_encoding_and_unavailable(vault, monkeypatch):
    (vault / CURRENT).write_bytes(b'\xffinvalid')
    data = view.build(vault, NOW)
    assert data['status'] == 'partial' and data['issues'][0]['reason'] == 'invalid_encoding'
    (vault / CURRENT).unlink()
    assert view.build(vault, NOW)['status'] == 'empty'
    write(vault, CURRENT, timed('One'))
    monkeypatch.setattr(view, 'MAX_FILE_BYTES', 1)
    assert view.build(vault, NOW)['status'] == 'partial'
    assert view.build(vault / 'missing', NOW)['status'] == 'unavailable'


def test_duplicate_identity_is_not_merged_and_recompletion_uses_current_instant(vault):
    path = write(vault, OLDER, '## 🏰 The Sanctum\r\n' + timed('A', identity='a' * 32) + timed('B', identity='a' * 32))
    assert view.build(vault, NOW)['status'] == 'partial'
    assert view.build(vault, NOW)['completed'] == []
    line = timed('A', '2026-10-28T00:40:00Z', identity='a' * 32).replace('"history":[]', '"history":["2026-10-28T00:30:00Z"]')
    path.write_text('## 🏰 The Sanctum\n' + line, encoding='utf-8')
    assert len(view.build(vault, NOW)['completed']) == 1
    path.write_text('## 🏰 The Sanctum\n' + timed('A', None, identity='a' * 32, status='pending', checked=' '), encoding='utf-8')
    assert view.build(vault, NOW)['completed'] == []


def test_web_and_native_read_parity_no_vault_writes(vault, monkeypatch):
    # UTC keeps the two transports' runtime day unambiguous.
    (vault / 'Bridge/settings.json').write_text(json.dumps({'timezone': 'UTC'}))
    instant = datetime.now(timezone.utc).isoformat()
    write(vault, OLDER, '## 🏰 The Sanctum\r\n' + timed('Transport parity', instant))
    before = snapshot(vault)
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(vault))
    response = TestClient(main.app).get('/api/tasks/completed-today')
    assert response.status_code == 200
    env = {**os.environ, 'NAVIS_ROOT': str(vault), 'PYTHONUTF8': '1'}
    output = subprocess.run([sys.executable, '-B', str(Path(__file__).parents[1] / 'native_completed_tasks.py')],
                            input=json.dumps({'path': '/api/tasks/completed-today'}), capture_output=True,
                            encoding='utf-8', env=env, timeout=30, check=True)
    native = json.loads(output.stdout)
    assert native['status'] == 200 and native['body'] == response.json()
    assert snapshot(vault) == before
    assert TestClient(main.app).post('/api/tasks/completed-today').status_code == 405


def test_concurrent_source_edit_is_partial_and_not_overwritten(vault, monkeypatch):
    path = write(vault, OLDER, '## 🏰 The Sanctum\r\n' + timed('Concurrent'))
    read = Path.read_bytes
    def changed(file):
        raw = read(file)
        if file == path:
            file.write_bytes(raw + b'External edit\n')
        return raw
    monkeypatch.setattr(Path, 'read_bytes', changed)
    result = view.build(vault, NOW)
    assert result['status'] == 'partial' and result['completed'] == []
    assert read(path).endswith(b'External edit\n')


def test_examples_frontmatter_and_comments_are_not_completions(vault):
    content = '---\nexample: |\n' + timed('Frontmatter') + '---\n## 🏰 The Sanctum\n```md\n'
    content += timed('Fenced example', identity='a' * 32) + '```\n<!-- hidden\n' + timed('Commented example') + '-->\n'
    content += timed('Actual task', identity='a' * 32)
    write(vault, CURRENT, content)
    data = view.build(vault, NOW)
    assert data['status'] == 'complete'
    assert [item['text'] for item in data['completed']] == ['Actual task']


def test_recurring_occurrences_keep_separate_provenance_and_current_day(vault):
    first_marker = '<!-- navis-directive:' + '1' * 64 + ' -->'
    next_marker = '<!-- navis-directive:' + '2' * 64 + ' -->'
    first_op = {'phase':'complete','marker':first_marker,'journal_path':OLDER,'completed_at':'2026-10-28T00:20:00Z'}
    next_op = {'phase':'complete','marker':next_marker,'journal_path':CURRENT,'completed_at':'2026-10-28T00:40:00Z'}
    (vault / 'Bridge/ops_state.json').write_text(json.dumps({'active_tasks':[],'tasks':[{'id':'recurring','completion':next_op,'completion_history':[first_op]}]}))
    write(vault, OLDER, '## 🏠 The Domestic Breach\n- [x] Recurring ' + first_marker + '\n')
    write(vault, CURRENT, '## 🏠 The Domestic Breach\n- [x] Recurring ' + next_marker + '\n')
    before = snapshot(vault)
    data = view.build(vault, NOW)
    assert len(data['completed']) == 2 and len({item['id'] for item in data['completed']}) == 2
    assert snapshot(vault) == before


def test_file_and_row_limits_are_partial_not_empty(vault, monkeypatch):
    write(vault, OLDER, '## 🏰 The Sanctum\n' + timed('One') + timed('Two'))
    monkeypatch.setattr(view, 'MAX_ROWS', 1)
    data = view.build(vault, NOW)
    assert data['status'] == 'partial' and any(item['reason']=='row_limit' for item in data['issues'])
    monkeypatch.setattr(view, 'MAX_FILES', 1)
    assert any(item['reason']=='file_count_limit' for item in view.build(vault, NOW)['issues'])


def test_unreadable_source_is_reported_and_never_silently_omitted(vault, monkeypatch):
    path = write(vault, OLDER, timed('Unavailable'))
    original = Path.read_bytes
    def unreadable(file):
        if file == path:
            raise OSError('synthetic permission failure')
        return original(file)
    monkeypatch.setattr(Path, 'read_bytes', unreadable)
    data = view.build(vault, NOW)
    assert data['status'] == 'partial'
    assert {'path':OLDER,'reason':'source_unreadable'} in data['issues']
