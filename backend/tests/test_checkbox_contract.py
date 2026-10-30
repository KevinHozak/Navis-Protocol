import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch
import pytest
from services.task_toggle import toggle, ToggleConflict
from services import task_time

INSTANT = "2026-10-01T12:00:00+00:00"


@pytest.fixture(autouse=True)
def fixed_completion_clock(monkeypatch):
    monkeypatch.setattr(task_time, "now", lambda: INSTANT)


def native_command(backend):
    # Freeze only the disposable child process, with no production clock override.
    code = "import runpy; from services import task_time; task_time.now=lambda: " + repr(INSTANT) + "; runpy.run_path(" + repr(str(backend / "native_task_toggle.py")) + ", run_name='__main__')"
    return [sys.executable, "-c", code]


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'Journal/2026/10/2026-10-01.md'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'\xef\xbb\xbf' + '# Keep 雪\r\n- [ ] First\r\n- [ ] Second'.encode())
    return tmp_path, path


def request(path, **extra):
    return dict(target_text='First', is_checked=True, line_number=2,
                expected_content=path.read_bytes().decode('utf-8-sig'), **extra)


def test_stale_line_revision_and_duplicate(source):
    root, path = source
    payload = request(path)
    original = path.read_bytes()
    for change in ({'line_number': 3}, {'expected_content': 'old'}, {'expected_content': None}):
        with pytest.raises(ToggleConflict):
            toggle(root, path, payload | change)
        assert path.read_bytes() == original
    path.write_bytes(b'- [ ] First\n- [ ] First\n')
    with pytest.raises(ToggleConflict):
        toggle(root, path, request(path) | {'line_number': None})


@pytest.mark.parametrize(('source_line', 'target_text'), [
    ('- [ ] Review foo_bar_baz', 'Review foo_bar_baz'),
    ('- [ ] Check x < y > z', 'Check x < y > z'),
    ('- [ ] **Add funds for school lunch**', 'Add funds for school lunch'),
    ('- [ ] _school lunch_', 'school lunch'),
    ('- [ ] <em>School lunch</em>', 'School lunch'),
])
def test_toggle_matches_rendered_markdown_labels(tmp_path, source_line, target_text):
    path = tmp_path / 'Tasks.md'
    path.write_text(source_line + '\n', encoding='utf-8')
    expected = path.read_bytes().decode('utf-8-sig')
    result = toggle(tmp_path, path, {
        'target_text': target_text,
        'is_checked': True,
        'line_number': 1,
        'expected_content': expected,
    })
    assert task_time.strip(result['content']) == expected.replace('- [ ]', '- [x]', 1)
    assert task_time.read(result['content']) == {'completed_at': INSTANT, 'history': []}


def test_failure_retry_and_correction(source):
    root, path = source
    award = Mock(side_effect=RuntimeError('offline'))
    result = toggle(root, path, request(path), award)
    assert result['saved'] and result['xp_status'] == 'pending'
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')
    assert task_time.strip(path.read_bytes().decode('utf-8-sig')) == '# Keep 雪\r\n- [x] First\r\n- [ ] Second'
    assert task_time.read(result['content']) == {'completed_at': INSTANT, 'history': []}
    award.side_effect = None
    result = toggle(root, path, request(path), award)
    assert not result['modified'] and result['xp_status'] == 'complete'
    toggle(root, path, request(path) | {'is_checked': False}, award)
    award.assert_called_with(date_override='2026-10-01')


def test_write_failure_never_awards(source):
    root, path = source
    original = path.read_bytes()
    award = Mock()
    with patch('services.task_toggle.atomic_bytes', side_effect=OSError('read only')):
        with pytest.raises(OSError):
            toggle(root, path, request(path), award)
    assert path.read_bytes() == original
    award.assert_not_called()


def test_rapid_stale_request_rejected(source):
    root, path = source
    old = request(path)
    toggle(root, path, old, Mock())
    with pytest.raises(ToggleConflict):
        toggle(root, path, old | {'is_checked': False}, Mock())


def test_native_web_parity(source, monkeypatch):
    import main
    import asyncio
    root, path = source
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(root))
    from services import rpg_engine, progression_db
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(root))
    payload = request(path) | {'file_path': path.relative_to(root).as_posix()}
    # Missing synthetic status makes XP pending in both adapters after save.
    web = asyncio.run(main.toggle_task(main.TaskToggleRequest(**payload)))
    path.write_bytes(b'\xef\xbb\xbf' + payload['expected_content'].encode())
    backend = Path(__file__).resolve().parents[1]
    native = subprocess.run(native_command(backend),
        input=json.dumps({'path': '/api/tasks/toggle', 'body': payload}), text=True,
        capture_output=True, env=os.environ | {'NAVIS_ROOT': str(root), 'PYTHONUTF8': '1'}, check=True)
    assert json.loads(native.stdout)['body'] == web


def test_retry_after_committed_award_cannot_double_award(source, monkeypatch):
    from services import rpg_engine, progression_db as db
    root, path = source
    (root / 'Bridge').mkdir()
    (root / 'Keeper').mkdir()
    (root / 'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}))
    (root / 'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(db, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(db, 'DB_PATH', str(root / 'Keeper/navis_progression.db'))
    def interrupted(**kwargs):
        rpg_engine.calculate_and_apply_xp(**kwargs)
        raise RuntimeError('response lost after ledger commit')
    assert toggle(root, path, request(path), interrupted)['xp_status'] == 'pending'
    assert db.get_total_xp('keeper') == 12
    assert toggle(root, path, request(path))['xp_status'] == 'complete'
    assert db.get_total_xp('keeper') == 12
    toggle(root, path, request(path) | {'is_checked': False})
    assert db.get_total_xp('keeper') == 10


def test_saved_state_survives_reopen_and_native_restart(source):
    root, path = source
    payload = request(path)
    saved = toggle(root, path, payload, Mock())
    assert path.read_bytes().decode('utf-8-sig') == saved['content']
    backend = Path(__file__).resolve().parents[1]
    # Fresh native process retries the confirmed state with freshly reopened bytes.
    payload = request(path) | {'file_path': path.relative_to(root).as_posix()}
    native = subprocess.run(native_command(backend),
        input=json.dumps({'path': '/api/tasks/toggle', 'body': payload}), text=True,
        capture_output=True, env=os.environ | {'NAVIS_ROOT': str(root), 'PYTHONUTF8': '1'}, check=True)
    result = json.loads(native.stdout)['body']
    assert result['saved'] and not result['modified']
    assert result['content'] == saved['content']
    toggle(root, path, request(path) | {'is_checked': False}, Mock())
    reopened = path.read_bytes()
    assert reopened.startswith(b'\xef\xbb\xbf')
    assert task_time.strip(reopened.decode('utf-8-sig')) == task_time.strip(payload['expected_content']).replace('- [x] First', '- [ ] First')
    assert task_time.read(reopened.decode('utf-8-sig')) == {'completed_at': None, 'history': [INSTANT]}
