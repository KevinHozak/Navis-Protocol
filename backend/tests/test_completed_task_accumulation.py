"""Issue #222: synthetic writer reproduction, never the personal Vault."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from services import directive_completion, sync_engine, task_time


@pytest.fixture
def vault(tmp_path, monkeypatch):
    (tmp_path / 'Bridge').mkdir()
    journal = tmp_path / 'Journal/2026/10/2026-10-01.md'
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b'\xef\xbb\xbf' + (
        '## 🏰 The Sanctum\r\nKeep 雪\r\n- [ ] Inspect telescope\r\n'
        '## 🏠 The Domestic Breach\r\n- [ ] Inspect telescope\r\n').encode())
    (tmp_path / 'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}))
    state = tmp_path / 'Bridge/ops_state.json'
    state.write_text(json.dumps({'active_tasks': [
        {'id': 'one', 'text': 'Inspect telescope', 'area': 'Sanctum', 'status': 'pending'}],
        'tasks': [], 'keep': '雪'}))
    operations = tmp_path / 'Operations/Sanctum'
    operations.mkdir(parents=True)
    settings = tmp_path / 'Bridge/settings.json'
    settings.write_text(json.dumps({'paths': {'operations_dir': str(operations.parent),
                                            'journal_root': str(tmp_path / 'Journal')}}))
    monkeypatch.setattr(sync_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(sync_engine, 'SETTINGS_FILE', str(settings))
    return tmp_path, journal, state, operations / 'Tasks.md'


def test_completion_consumes_existing_occurrence_and_retry_is_byte_noop(vault):
    root, journal, state, _ = vault
    before = journal.read_bytes()
    directive_completion.complete_active(root, 'one', award=lambda **kw: None)
    saved = journal.read_bytes()
    sanctum, domestic = saved.decode('utf-8-sig').split('## 🏠')
    assert sanctum.count('Inspect telescope') == 1
    assert '- [x] Inspect telescope <!-- navis-directive:' in task_time.strip(sanctum)
    assert domestic == before.decode('utf-8-sig').split('## 🏠')[1]
    assert b'Keep \xe9\x9b\xaa\r\n' in saved
    directive_completion.complete_active(root, 'one', award=lambda **kw: pytest.fail('replay awarded XP'))
    assert journal.read_bytes() == saved
    assert json.loads(state.read_text(encoding='utf-8-sig'))['keep'] == '雪'


def test_sweep_does_not_append_already_recorded_completion(vault):
    _, journal, _, tasks = vault
    journal.write_bytes(journal.read_bytes().replace(b'- [ ] Inspect telescope', b'- [x] Inspect telescope', 1))
    tasks.write_text('- [x] Inspect telescope\n', encoding='utf-8-sig')
    before = journal.read_bytes()
    sync_engine.sync_active_tasks()
    assert journal.read_bytes() == before
    # A source restored after restart/retry must still be harmless.
    tasks.write_text('- [x] Inspect telescope\n', encoding='utf-8-sig')
    sync_engine.sync_active_tasks()
    assert journal.read_bytes() == before


def test_sweep_requires_exact_recurring_text(vault):
    _, journal, state, _ = vault
    journal.write_text('## 🏰 The Sanctum\n- [x] Inspect telescope lens\n', encoding='utf-8-sig')
    state.write_text(json.dumps({'tasks': [{'text': 'Inspect telescope', 'frequency': 'weekly',
                                          'last_done': None, 'next_due': '2026-10-01'}]}))
    before = state.read_bytes()
    sync_engine.sync_active_tasks()
    assert state.read_bytes() == before


@pytest.mark.parametrize('folder,header', [
    ('Domestic', '## 🏠 The Domestic Breach'),
    ('Bureaucratic', '## ⚖️ The Bureaucratic Gauntlet'),
])
def test_sweep_matches_full_heading_and_preserves_other_sections(vault, folder, header):
    root, journal, _, _ = vault
    source = root / 'Operations' / folder / 'Tasks.md'
    source.parent.mkdir()
    source.write_bytes(b'\xef\xbb\xbf- [x] Synthetic task\r\nKeep source\r\n')
    original = ('## 🏰 The Sanctum\r\nNote mentioning ' + folder + '\r\n'
                '- [ ] Synthetic task\r\n' + header + '\r\n'
                '- [ ] Synthetic task\r\nKeep 雪\r\n'
                '## ⚔️ The High-Velocity Front\r\n- [ ] Synthetic task\r\n')
    journal.write_bytes(b'\xef\xbb\xbf' + original.encode())
    sync_engine.sync_active_tasks()
    expected = original.replace(header + '\r\n- [ ]', header + '\r\n- [x]')
    saved = journal.read_bytes()
    assert saved == b'\xef\xbb\xbf' + expected.encode()
    assert source.read_bytes() == b'\xef\xbb\xbfKeep source\r\n'
    sync_engine.sync_active_tasks()
    assert journal.read_bytes() == saved


@pytest.mark.parametrize('transport', ['web', 'native'])
def test_routes_complete_existing_item_once_with_canonical_xp(vault, monkeypatch, transport):
    import asyncio
    from services import rpg_engine, progression_db
    root, journal, _, _ = vault
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(root / 'Keeper/navis_progression.db'))
    (root / 'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))
    before = journal.read_bytes()
    if transport == 'web':
        import main
        monkeypatch.setattr(main, 'NAVIS_ROOT', str(root))
        def invoke():
            return asyncio.run(main.complete_active_task('one'))
    else:
        def invoke():
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'native_directive.py')],
                input=json.dumps({'body': {'task_id': 'one'}}), capture_output=True, text=True,
                env={**os.environ, 'NAVIS_ROOT': str(root), 'PYTHONUTF8': '1'}, timeout=20)
            response = json.loads(result.stdout)
            assert response['status'] == 200, response
            return response['body']
    assert not invoke()['idempotent_replay']
    saved = journal.read_bytes()
    assert invoke()['idempotent_replay']
    assert journal.read_bytes() == saved
    assert saved.decode('utf-8-sig').split('## 🏠')[0].count('Inspect telescope') == 1
    assert progression_db.get_entity_total('keeper') == 12
    assert next(journal.parent.glob('*.backup_directive_*')).read_bytes() == before


def test_ambiguous_occurrences_fail_without_rewriting_history(vault):
    root, journal, _, _ = vault
    journal.write_bytes(journal.read_bytes().replace(b'Keep ', b'- [x] Inspect telescope\r\nKeep '))
    before = journal.read_bytes()
    with pytest.raises(ValueError, match='ambiguous'):
        directive_completion.complete_active(root, 'one', award=lambda **kw: None)
    assert journal.read_bytes() == before


def test_sweep_recovers_after_source_cleanup_failure(vault, monkeypatch):
    _, journal, _, tasks = vault
    tasks.write_bytes(b'\xef\xbb\xbf' + b'- [x] Inspect telescope\r\nKeep source\r\n')
    before = journal.read_bytes()
    real_atomic = sync_engine.atomic_bytes
    def interrupted(path, content):
        if path == tasks:
            raise OSError('synthetic cleanup interruption')
        real_atomic(path, content)
    with monkeypatch.context() as context:
        context.setattr(sync_engine, 'atomic_bytes', interrupted)
        with pytest.raises(OSError):
            sync_engine.sync_active_tasks()
    saved = journal.read_bytes()
    assert saved != before
    assert tasks.read_bytes().count(b'Inspect telescope') == 1
    sync_engine.sync_active_tasks()
    assert journal.read_bytes() == saved
    assert tasks.read_bytes() == b'\xef\xbb\xbfKeep source\r\n'
    assert next(journal.parent.glob('*.backup_sweep_*')).read_bytes() == before
