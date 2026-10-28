"""S023 clocks are synthetic; no personal Vault or file-mtime inference."""
import json
import pytest
from services import task_time
from services.task_toggle import toggle
from services.directive_completion import transition, complete_section_item
from test_task_status import vault as status_vault, current, RELATIVE


@pytest.fixture
def vault(tmp_path, monkeypatch):
    return status_vault.__wrapped__(tmp_path, monkeypatch)

FIRST = '2026-11-01T06:30:00+00:00'  # First 01:30 in Chicago.
SECOND = '2026-11-01T07:30:00+00:00'  # Second 01:30, distinct instant.


def test_journal_time_history_replay_unknown_and_preserved_bytes(vault, monkeypatch):
    path = vault / RELATIVE
    before = path.read_bytes()
    monkeypatch.setattr(task_time, 'now', lambda: FIRST)
    def save(desired):
        return toggle(vault, path, {'target_text': 'Keep 雪', 'line_number': 3,
            'task_status': desired, 'expected_content': path.read_bytes().decode('utf-8-sig')})
    assert save('done')['completed_at'] == FIRST
    first = path.read_bytes()
    monkeypatch.setattr(task_time, 'now', lambda: SECOND)
    assert save('done')['completed_at'] == FIRST
    assert path.read_bytes() == first
    save('pending')
    assert task_time.read(path.read_text(encoding='utf-8-sig')) == {'completed_at': None, 'history': [FIRST]}
    assert save('done')['completed_at'] == SECOND
    assert task_time.read(path.read_text(encoding='utf-8-sig')) == {'completed_at': SECOND, 'history': [FIRST]}
    from services.task_toggle import STATUS_MARKER
    stripped = task_time.strip(STATUS_MARKER.sub('', path.read_bytes().decode('utf-8-sig')))
    assert stripped.encode('utf-8') == before[3:].replace(b'[ ]', b'[x]', 1)
    # An unrelated manually checked row has no exact time, regardless of clock.
    result = toggle(vault, path, {'target_text': 'Legacy checked', 'line_number': 5,
        'is_checked': True, 'expected_content': path.read_bytes().decode('utf-8-sig')})
    assert result['completed_at'] is None


@pytest.mark.parametrize('recurring', [False, True])
def test_directive_recomplete_and_occurrence_history(vault, monkeypatch, recurring):
    monkeypatch.setattr(task_time, 'now', lambda: FIRST)
    identity = 'r' if recurring else 'a'
    def save(desired):
        return transition(vault, identity, desired, current(vault, recurring), is_recurring=recurring)
    first = save('done')['task']
    assert first['completed_at'] == FIRST
    monkeypatch.setattr(task_time, 'now', lambda: SECOND)
    assert save('done')['task']['completed_at'] == FIRST
    save('pending')
    reopened = current(vault, recurring)
    assert 'completed_at' not in reopened
    assert reopened['completion_history'][0]['completed_at'] == FIRST
    assert save('done')['task']['completed_at'] == SECOND
    assert task_time.read((vault / RELATIVE).read_text(encoding='utf-8-sig'))['history'] == [FIRST]
    if recurring:
        status = vault / 'Bridge/status.json'
        status.write_text(json.dumps({'last_updated': '2026-10-27', 'squad': []}))
        next_journal = vault / 'Journal/2026/10/2026-10-27.md'
        next_journal.write_text('## 🥾 The Kinetic Outland\n- [ ] Recurring\n', encoding='utf-8')
        monkeypatch.setattr(task_time, 'now', lambda: '2026-11-02T08:00:00Z')
        assert save('done')['task']['completed_at'] == '2026-11-02T08:00:00Z'
        assert current(vault, True)['completion_history'][-1]['completed_at'] == SECOND


def test_xp_failure_keeps_first_journal_instant(vault, monkeypatch):
    monkeypatch.setattr(task_time, 'now', lambda: FIRST)
    def fail(**kwargs): raise OSError('synthetic XP failure')
    with pytest.raises(OSError):
        transition(vault, 'a', 'done', current(vault), award=fail)
    monkeypatch.setattr(task_time, 'now', lambda: SECOND)
    result = transition(vault, 'a', 'done', current(vault))
    assert result['task']['completed_at'] == FIRST


def test_import_or_legacy_checked_cannot_mint_time(vault, monkeypatch):
    monkeypatch.setattr(task_time, 'now', lambda: FIRST)
    path = vault / RELATIVE
    path.write_bytes(path.read_bytes().replace(b'[ ]', b'[x]', 1))
    assert transition(vault, 'a', 'done', current(vault))['task']['completed_at'] is None
    text = '## 🥾 The Kinetic Outland\n- [ ] Import\n'
    assert 'navis-completion:' not in complete_section_item(text, '## 🥾 The Kinetic Outland', 'Import')


@pytest.mark.parametrize('value', ['2026-11-01', '2026-11-01T01:30:00', 'invalid'])
def test_naive_or_malformed_metadata_is_rejected(value):
    label = 'Task <!-- navis-completion:' + json.dumps({'completed_at': value, 'history': []}) + ' -->'
    with pytest.raises(ValueError): task_time.transition(label, True, False)


def test_completion_reconciliation_does_not_overwrite_concurrent_edit(vault):
    path = vault / 'Bridge/ops_state.json'
    def edit(**kwargs):
        state = json.loads(path.read_text(encoding='utf-8-sig'))
        state['external'] = 'preserve'
        path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match='sources changed'):
        transition(vault, 'a', 'done', current(vault), award=edit)
    assert json.loads(path.read_text(encoding='utf-8-sig'))['external'] == 'preserve'


def test_recompletion_interrupted_after_journal_write_reuses_instant(vault, monkeypatch):
    from services import directive_completion
    monkeypatch.setattr(task_time, 'now', lambda: FIRST)
    transition(vault, 'a', 'done', current(vault))
    transition(vault, 'a', 'pending', current(vault))
    monkeypatch.setattr(task_time, 'now', lambda: SECOND)
    original = directive_completion.atomic_json
    def fail(path, state):
        if state['active_tasks'][0]['completion']['phase'] == 'xp_pending':
            raise OSError('synthetic state persistence interruption')
        return original(path, state)
    monkeypatch.setattr(directive_completion, 'atomic_json', fail)
    with pytest.raises(OSError): transition(vault, 'a', 'done', current(vault))
    written = (vault / RELATIVE).read_bytes()
    monkeypatch.setattr(directive_completion, 'atomic_json', original)
    monkeypatch.setattr(task_time, 'now', lambda: '2026-11-02T08:00:00Z')
    assert transition(vault, 'a', 'done', current(vault))['task']['completed_at'] == SECOND
    assert (vault / RELATIVE).read_bytes() == written
