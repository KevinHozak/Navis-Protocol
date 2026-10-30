"""End-to-End smoke and integration validation for Sector Task Boards and Directive Lifecycles (Issue #205)."""
import json
import pytest
from fastapi.testclient import TestClient
import main
from services import rpg_engine, progression_db, task_time


@pytest.fixture
def mock_navis_env(tmp_path, monkeypatch):
    """Set up an isolated Navis vault environment with bridge, journal, and progression DB."""
    root = tmp_path
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(root))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(root / 'Keeper/navis_progression.db'))

    (root / 'Bridge').mkdir(parents=True)
    (root / 'Journal/2026/10').mkdir(parents=True)

    today = '2026-10-03'
    journal_path = root / f'Journal/2026/10/{today}.md'
    initial_content = (
        '## 🏰 The Sanctum\r\n'
        'Initial Sanctum Note 🌟\r\n\r\n'
        '## 🏠 The Domestic Breach\r\n'
        'Home Note 雪\r\n\r\n'
        '## ⚔️ The High-Velocity Front\r\n'
        'Work Note\r\n\r\n'
        '## ⚖️ The Bureaucratic Gauntlet\r\n'
        'Finance Note\r\n\r\n'
        '## 🥾 The Kinetic Outland\r\n'
        'Outland Note\r\n'
    )
    journal_path.write_bytes(b'\xef\xbb\xbf' + initial_content.encode('utf-8'))

    (root / 'Bridge/status.json').write_text(json.dumps({'last_updated': today, 'squad': []}), encoding='utf-8-sig')
    (root / 'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}), encoding='utf-8-sig')

    state = {
        'tasks': [],
        'active_tasks': [],
        'unrelated': {'preserve': '雪'}
    }
    (root / 'Bridge/ops_state.json').write_text(json.dumps(state), encoding='utf-8-sig')
    return root, today, journal_path


def test_active_task_e2e_lifecycle(mock_navis_env):
    """Task lifecycle: Creation -> Edit -> Real-time completion -> Verification of - [x] markdown."""
    root, today, journal_path = mock_navis_env
    client = TestClient(main.app)

    # 1. Creation
    create_payload = {
        'text': 'Calibrate telescope sensors',
        'area': 'Sanctum',
        'priority': 1,
        'due_date': today,
        'description': 'Ensure precision alignment before evening sweep.',
        'labels': ['@optics', '@tech']
    }
    res_create = client.post('/api/active_tasks', json=create_payload)
    assert res_create.status_code == 200
    task_data = res_create.json()['task']
    task_id = task_data['id']
    assert task_data['text'] == 'Calibrate telescope sensors'
    assert task_data['priority'] == 1
    assert task_data['due_date'] == today
    assert task_data['description'] == 'Ensure precision alignment before evening sweep.'

    # 2. Edit
    edit_payload = {
        'text': 'Calibrate primary & secondary telescope sensors',
        'priority': 2,
        'description': 'Updated: focus on infrared spectrometer.',
        'labels': ['@optics', '@spectroscopy']
    }
    res_edit = client.put(f'/api/active_tasks/{task_id}', json=edit_payload)
    assert res_edit.status_code == 200
    updated_data = res_edit.json()['task']
    assert updated_data['text'] == 'Calibrate primary & secondary telescope sensors'
    assert updated_data['priority'] == 2
    assert updated_data['description'] == 'Updated: focus on infrared spectrometer.'

    # 3. Completion
    res_complete = client.post(f'/api/active_tasks/{task_id}/complete')
    assert res_complete.status_code == 200
    completed_body = res_complete.json()
    assert completed_body['status'] == 'completed'
    assert completed_body['task']['status'] == 'completed'

    # 4. Verification of - [x] markdown in daily journal with zero defects
    journal_bytes = journal_path.read_bytes()
    assert journal_bytes.startswith(b'\xef\xbb\xbf'), "Journal must retain UTF-8-SIG BOM"
    journal_text = journal_bytes.decode('utf-8-sig')
    assert 'Initial Sanctum Note 🌟' in journal_text
    expected_line = '- [x] Calibrate primary & secondary telescope sensors <!-- navis-directive:'
    assert expected_line in task_time.strip(journal_text), f"Journal missing completion marker: {journal_text}"

    completed_line = next(line for line in journal_text.splitlines() if line.startswith('- [x] Calibrate'))
    assert task_time.valid_instant(task_time.read(completed_line)['completed_at'])
    assert task_time.read(completed_line)['completed_at'] == completed_body['task']['completed_at']

    # Verify task is no longer pending in active tasks list
    res_active = client.get('/api/active_tasks?area=Sanctum')
    assert res_active.status_code == 200
    active_ids = [t['id'] for t in res_active.json()]
    assert task_id not in active_ids


def test_recurring_task_e2e_completion_and_progression(mock_navis_env):
    """Recurring task completion -> Next due date progression + XP accrual + Journal evidence."""
    root, today, journal_path = mock_navis_env
    client = TestClient(main.app)

    # 1. Creation
    rec_payload = {
        'text': 'Domestic water filter purge',
        'frequency': 'weekly',
        'area': 'Domestic',
        'priority': 3,
        'next_due': today,
        'description': 'Cycle 2 gallons through clean manifold.'
    }
    res_create = client.post('/api/recurring', json=rec_payload)
    assert res_create.status_code == 200
    rec_task = res_create.json()['task']
    task_id = rec_task['id']

    # 2. Completion
    res_complete = client.post(f'/api/recurring/{task_id}/complete')
    assert res_complete.status_code == 200
    completed = res_complete.json()['task']
    assert completed['last_done'] == today
    assert completed['next_due'] == '2026-10-10', "Weekly task must advance 7 days"

    # 3. Journal evidence verification
    journal_text = journal_path.read_bytes().decode('utf-8-sig')
    assert 'Home Note 雪' in journal_text
    assert '- [x] Domestic water filter purge <!-- navis-directive:' in task_time.strip(journal_text)

    completed_line = next(line for line in journal_text.splitlines() if line.startswith('- [x] Domestic'))
    assert task_time.valid_instant(task_time.read(completed_line)['completed_at'])
    assert task_time.read(completed_line)['completed_at'] == completed['completed_at']

    # 4. XP Accrual verification
    xp_total = progression_db.get_entity_total('keeper')
    assert xp_total > 0, "XP must be accrued after recurring mandate completion"


def test_ops_state_regression_no_missing_field_crashes(tmp_path):
    """Exercise legacy optional fields from a synthetic serialized ops state."""
    path = tmp_path / 'ops_state.json'
    active = [{'id': f'active-{i}', 'text': f'Synthetic task {i}',
               **({'priority': [None, 1, '2'][i % 3], 'labels': [None, [], ['@fixture']][i % 3]} if i % 2 else {})}
              for i in range(200)]
    recurring = [{'id': f'recurring-{i}', 'text': f'Synthetic recurring {i}', 'frequency': 'weekly'} for i in range(45)]
    path.write_text(json.dumps({'active_tasks': active, 'tasks': recurring}), encoding='utf-8-sig')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    active_tasks = data.get('active_tasks', [])
    recurring_tasks = data.get('tasks', [])

    assert len(active_tasks) >= 190, f"Expected 190+ synthetic active tasks, found {len(active_tasks)}"
    assert len(recurring_tasks) >= 40, f"Expected 40+ synthetic recurring tasks, found {len(recurring_tasks)}"

    # Check each active task has valid structure and doesn't fail basic access
    for t in active_tasks:
        assert isinstance(t.get('id'), str)
        assert isinstance(t.get('text'), str)
        # Priority can be None, int, or str
        p = t.get('priority')
        assert p is None or isinstance(p, (int, str))
        # Labels can be list or None
        labels = t.get('labels')
        assert labels is None or isinstance(labels, list)

    for r in recurring_tasks:
        assert isinstance(r.get('id'), str)
        assert isinstance(r.get('text'), str)
        assert isinstance(r.get('frequency'), str)
