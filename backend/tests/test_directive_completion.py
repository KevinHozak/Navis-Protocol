import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.directive_completion import complete
from services import rpg_engine, progression_db, task_time

class CompletionTests(unittest.TestCase):
    def test_recovery_ledger_native_and_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'Bridge').mkdir()
            (root/'Journal/2026/10').mkdir(parents=True)
            journal = root/'Journal/2026/10/2026-10-01.md'
            original = b'\xef\xbb\xbf' + '## 🏰 The Sanctum\r\nKeep 雪\r\n'.encode()
            journal.write_bytes(original)
            state = {'active_tasks':[{'id':'imported/雪','text':'Repair telescope','area':'Sanctum','status':'pending'}], 'unrelated':{'keep':'雪'}}
            ops=root/'Bridge/ops_state.json'
            ops.write_text(json.dumps(state),encoding='utf-8-sig')
            (root/'Bridge/status.json').write_text(json.dumps({'last_updated':'2026-10-01','squad':[]}),encoding='utf-8')
            (root/'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))
            old=(rpg_engine.NAVIS_ROOT,progression_db.NAVIS_ROOT,progression_db.DB_PATH)
            rpg_engine.NAVIS_ROOT=progression_db.NAVIS_ROOT=str(root)
            progression_db.DB_PATH=str(root/'Keeper/navis_progression.db')
            try:
                def fail(**kwargs): raise OSError('fixture interruption')
                with self.assertRaises(OSError): complete(root,'imported/雪',award=fail)
                first=journal.read_bytes()
                self.assertTrue(first.startswith(b'\xef\xbb\xbf'))
                self.assertIn(b'Keep ',first)
                self.assertEqual(first.count(b'navis-directive:'),1)
                env={**os.environ,'NAVIS_ROOT':str(root),'PYTHONUTF8':'1'}
                request=json.dumps({'body':{'task_id':'imported/雪'}})
                process=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'native_directive.py')],input=request,text=True,capture_output=True,env=env)
                self.assertEqual(json.loads(process.stdout)['status'],200, process.stdout + process.stderr)
                self.assertEqual(journal.read_bytes(),first)
                saved=json.loads(ops.read_text(encoding='utf-8-sig'))
                self.assertEqual(saved['unrelated'],state['unrelated'])
                self.assertEqual(saved['active_tasks'][0]['status'],'completed')
                self.assertEqual(progression_db.get_entity_total('keeper'),12)
                complete(root,'imported/雪',award=fail)
                self.assertEqual(progression_db.get_entity_total('keeper'),12)
            finally:
                rpg_engine.NAVIS_ROOT,progression_db.NAVIS_ROOT,progression_db.DB_PATH=old

    def test_ambiguous_identity_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'Bridge').mkdir()
            path=root/'Bridge/ops_state.json';path.write_text(json.dumps({'active_tasks':[{'id':'x'},{'id':'x'}]}))
            before=path.read_bytes()
            with self.assertRaises(ValueError): complete(root,'x')
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__': unittest.main()


def test_web_completion_routes(tmp_path, monkeypatch):
    import asyncio
    import pytest
    import main
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(tmp_path/'Keeper/navis_progression.db'))
    (tmp_path/'Bridge').mkdir()
    (tmp_path/'Journal/2026/10').mkdir(parents=True)
    (tmp_path/'Journal/2026/10/2026-10-01.md').write_text('## 🏰 The Sanctum\nKeep 雪\n', encoding='utf-8')
    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated':'2026-10-01','squad':[]}))
    (tmp_path/'Bridge/CompanionStats.json').write_text(json.dumps({'companions':{'Keeper':{'xp':0,'level':1}}}))
    path=tmp_path/'Bridge/ops_state.json'
    path.write_text(json.dumps({'active_tasks':[{'id':'x','text':'Repair telescope','area':'Sanctum','status':'pending'}, {'id':'delete','text':'Discard draft','area':'Sanctum'}], 'keep':'雪'}), encoding='utf-8')
    result=asyncio.run(main.complete_active_task('x'))
    assert result['task']['id']=='x'
    assert asyncio.run(main.complete_active_task('x'))['idempotent_replay']
    assert [t['id'] for t in asyncio.run(main.get_active_tasks('Sanctum'))]==['delete']
    with pytest.raises(main.HTTPException): asyncio.run(main.delete_active_task('x'))
    with pytest.raises(main.HTTPException): asyncio.run(main.update_active_task('x',main.ActiveTaskUpdate(text='changed')))
    asyncio.run(main.delete_active_task('delete'))
    assert progression_db.get_entity_total('keeper')==12
    assert json.loads(path.read_text(encoding='utf-8-sig'))['keep']=='雪'


def test_recurring_mandate_completion_and_advancement(tmp_path, monkeypatch):
    import main
    from services.directive_completion import complete_recurring
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(tmp_path/'Keeper/navis_progression.db'))

    (tmp_path/'Bridge').mkdir()
    (tmp_path/'Journal/2026/10').mkdir(parents=True)
    journal_path = tmp_path/'Journal/2026/10/2026-10-01.md'
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

    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}), encoding='utf-8-sig')
    (tmp_path/'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}), encoding='utf-8-sig')

    state = {
        'tasks': [
            {'id': 'rec/daily', 'text': 'Daily calibration', 'frequency': 'daily', 'area': 'The Sanctum', 'next_due': '2026-10-01', 'last_done': None, 'custom': 'keep_me'},
            {'id': 'rec/weekly', 'text': 'Weekly garden sweep', 'frequency': 'weekly', 'area': 'Domestic', 'next_due': '2026-10-01', 'last_done': None},
            {'id': 'rec/monthly', 'text': 'Monthly audit', 'frequency': 'monthly', 'area': 'Gauntlet', 'next_due': '2026-10-01', 'last_done': None},
        ],
        'active_tasks': [],
        'archive': {'meta': 'preserved'}
    }
    ops_path = tmp_path/'Bridge/ops_state.json'
    ops_path.write_text(json.dumps(state), encoding='utf-8-sig')

    # 1. Complete daily recurring mandate
    res_daily = complete_recurring(tmp_path, 'rec/daily')
    assert res_daily['status'] == 'completed'
    assert not res_daily['idempotent_replay']
    assert res_daily['task']['last_done'] == '2026-10-01'
    assert res_daily['task']['next_due'] == '2026-10-02'

    # Check ops_state.json retention and fields
    saved_state = json.loads(ops_path.read_text(encoding='utf-8-sig'))
    assert len(saved_state['tasks']) == 3
    assert saved_state['archive']['meta'] == 'preserved'
    daily_saved = next(t for t in saved_state['tasks'] if t['id'] == 'rec/daily')
    assert daily_saved['last_done'] == '2026-10-01'
    assert daily_saved['next_due'] == '2026-10-02'
    assert daily_saved['custom'] == 'keep_me'

    # Check journal markdown integrity and UTF-8-SIG preservation
    journal_bytes = journal_path.read_bytes()
    assert journal_bytes.startswith(b'\xef\xbb\xbf')
    journal_text = journal_bytes.decode('utf-8-sig')
    assert 'Initial Sanctum Note 🌟' in journal_text
    assert 'Home Note 雪' in journal_text
    assert '- [x] Daily calibration <!-- navis-directive:' in task_time.strip(journal_text)

    # Verify daily XP accrued: base daily (10) + 1 checkbox (2) = 12
    assert progression_db.get_entity_total('keeper') == 12

    # 2. Complete weekly recurring mandate
    res_weekly = complete_recurring(tmp_path, 'rec/weekly')
    assert res_weekly['status'] == 'completed'
    assert res_weekly['task']['next_due'] == '2026-10-08'
    assert progression_db.get_entity_total('keeper') == 14

    # 3. Complete monthly recurring mandate
    res_monthly = complete_recurring(tmp_path, 'rec/monthly')
    assert res_monthly['status'] == 'completed'
    assert res_monthly['task']['next_due'] == '2026-11-01'
    assert progression_db.get_entity_total('keeper') == 16

    # 4. Idempotency replay check on same day
    replay = complete_recurring(tmp_path, 'rec/daily')
    assert replay['idempotent_replay'] is True
    assert progression_db.get_entity_total('keeper') == 16
    assert journal_path.read_text(encoding='utf-8-sig').count('Daily calibration') == 1


def test_web_recurring_completion_endpoints_and_errors(tmp_path, monkeypatch):
    import asyncio
    import pytest
    import main
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(tmp_path/'Keeper/navis_progression.db'))

    (tmp_path/'Bridge').mkdir()
    (tmp_path/'Journal/2026/10').mkdir(parents=True)
    journal_path = tmp_path/'Journal/2026/10/2026-10-01.md'
    journal_path.write_text('## 🏰 The Sanctum\nKeep notes\n', encoding='utf-8-sig')
    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}))
    (tmp_path/'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))

    ops_path = tmp_path/'Bridge/ops_state.json'
    ops_path.write_text(json.dumps({
        'tasks': [{'id': 'task-r1', 'text': 'Clean sensors', 'frequency': 'daily', 'area': 'Sanctum', 'next_due': '2026-10-01', 'last_done': None}],
        'active_tasks': []
    }), encoding='utf-8-sig')

    # Web endpoint call
    res = asyncio.run(main.complete_recurring_task('task-r1'))
    assert res['status'] == 'completed'
    assert res['task']['id'] == 'task-r1'
    assert res['task']['next_due'] == '2026-10-02'
    assert res['task']['due_date'] == '2026-10-02'
    assert not res['idempotent_replay']

    # Calling again gives idempotent replay
    res_replay = asyncio.run(main.complete_recurring_task('task-r1'))
    assert res_replay['idempotent_replay'] is True

    # Check GET /api/recurring still returns task
    tasks = asyncio.run(main.get_recurring_tasks('Sanctum'))
    assert len(tasks) == 1
    assert tasks[0]['id'] == 'task-r1'
    assert tasks[0]['next_due'] == '2026-10-02'

    # Non-existent task returns 409
    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.complete_recurring_task('non-existent'))
    assert exc.value.status_code == 409

    # Calling complete_active_task on a recurring task ID returns 409
    with pytest.raises(main.HTTPException) as exc_active:
        asyncio.run(main.complete_active_task('task-r1'))
    assert exc_active.value.status_code == 409


def test_native_directive_supports_recurring_mandate(tmp_path, monkeypatch):
    root = tmp_path
    (root/'Bridge').mkdir()
    (root/'Journal/2026/10').mkdir(parents=True)
    journal = root/'Journal/2026/10/2026-10-01.md'
    journal.write_bytes(b'\xef\xbb\xbf' + '## 🏰 The Sanctum\r\nKeep 雪\r\n'.encode('utf-8'))
    ops = root/'Bridge/ops_state.json'
    ops.write_text(json.dumps({'tasks': [{'id': 'native-rec', 'text': 'Native inspection', 'frequency': 'daily', 'area': 'Sanctum'}], 'active_tasks': []}), encoding='utf-8-sig')
    (root/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}), encoding='utf-8')
    (root/'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))

    env = {**os.environ, 'NAVIS_ROOT': str(root), 'PYTHONUTF8': '1'}
    request = json.dumps({'path': '/api/recurring/complete', 'body': {'task_id': 'native-rec'}})
    process = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'native_directive.py')], input=request, text=True, capture_output=True, env=env)
    assert json.loads(process.stdout)['status'] == 200, process.stdout + process.stderr
    out_body = json.loads(process.stdout)['body']
    assert out_body['status'] == 'completed'
    assert out_body['task']['next_due'] == '2026-10-02'
    assert journal.read_bytes().startswith(b'\xef\xbb\xbf')


def test_invalid_date_or_section_raises_clear_error(tmp_path):
    from services.directive_completion import complete_recurring
    (tmp_path/'Bridge').mkdir()
    (tmp_path/'Bridge/ops_state.json').write_text(json.dumps({
        'tasks': [{'id': 't1', 'text': 'Task', 'frequency': 'daily', 'area': 'Sanctum'}],
        'active_tasks': []
    }))

    # Missing status.json
    with pytest.raises(ValueError, match="Journal date unavailable"):
        complete_recurring(tmp_path, 't1')

    # Invalid date in status.json
    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-02-30'}))
    with pytest.raises(ValueError, match="Journal date unavailable"):
        complete_recurring(tmp_path, 't1')

    # Valid date but missing journal file
    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01'}))
    with pytest.raises((ValueError, FileNotFoundError)):
        complete_recurring(tmp_path, 't1')

    # Journal file exists but missing Manor section
    (tmp_path/'Journal/2026/10').mkdir(parents=True)
    (tmp_path/'Journal/2026/10/2026-10-01.md').write_text('# Just Title\nNo sections here\n', encoding='utf-8-sig')
    with pytest.raises(ValueError, match="Directive journal section unavailable"):
        complete_recurring(tmp_path, 't1')


def test_active_directive_preserves_surrounding_across_all_manors(tmp_path, monkeypatch):
    import main
    from services.directive_completion import complete
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(tmp_path/'Keeper/navis_progression.db'))

    (tmp_path/'Bridge').mkdir()
    (tmp_path/'Journal/2026/10').mkdir(parents=True)
    journal_path = tmp_path/'Journal/2026/10/2026-10-01.md'
    initial_content = (
        '## 🏰 The Sanctum\r\n'
        'Sanctum Lore 🌟\r\n\r\n'
        '## 🏠 The Domestic Breach\r\n'
        '- [ ] Existing Domestic Chore\r\n'
        'Domestic Notes 雪\r\n\r\n'
        '## ⚔️ The High-Velocity Front\r\n'
        'Front Objective Alpha\r\n\r\n'
        '## ⚖️ The Bureaucratic Gauntlet\r\n'
        'Gauntlet Log 42\r\n\r\n'
        '## 🥾 The Kinetic Outland\r\n'
        'Outland Trail Marker\r\n'
    )
    journal_path.write_bytes(b'\xef\xbb\xbf' + initial_content.encode('utf-8'))
    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}))
    (tmp_path/'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))

    areas = [
        ('t-sanctum', 'Command Meditation', 'sanctum'),
        ('t-domestic', 'Fix kitchen drawer', 'The Domestic Breach'),
        ('t-front', 'Deploy auth proxy', 'work'),
        ('t-gauntlet', 'Tax forms reconciliation', 'finances'),
        ('t-outland', '5k forest ruck', 'The Kinetic Outland'),
    ]
    state = {
        'active_tasks': [{'id': tid, 'text': text, 'area': area, 'status': 'pending'} for tid, text, area in areas],
        'preserve_root_prop': 'keep'
    }
    (tmp_path/'Bridge/ops_state.json').write_text(json.dumps(state), encoding='utf-8-sig')

    for tid, text, _ in areas:
        res = complete(tmp_path, tid)
        assert res['status'] == 'completed'
        assert not res['idempotent_replay']

    journal_text = journal_path.read_text(encoding='utf-8-sig')
    # Check that each task was added
    for _, text, _ in areas:
        assert f"- [x] {text} <!-- navis-directive:" in task_time.strip(journal_text)

    # Check that ALL surrounding text was preserved
    assert 'Sanctum Lore 🌟' in journal_text
    assert '- [ ] Existing Domestic Chore' in journal_text
    assert 'Domestic Notes 雪' in journal_text
    assert 'Front Objective Alpha' in journal_text
    assert 'Gauntlet Log 42' in journal_text
    assert 'Outland Trail Marker' in journal_text

    # Strict UTF-8-SIG preservation
    assert journal_path.read_bytes().startswith(b'\xef\xbb\xbf')


def test_battle_lock_concurrency(tmp_path, monkeypatch):
    import concurrent.futures
    import main
    from services.directive_completion import complete_recurring
    monkeypatch.setattr(main, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(rpg_engine, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'NAVIS_ROOT', str(tmp_path))
    monkeypatch.setattr(progression_db, 'DB_PATH', str(tmp_path/'Keeper/navis_progression.db'))

    (tmp_path/'Bridge').mkdir()
    (tmp_path/'Journal/2026/10').mkdir(parents=True)
    (tmp_path/'Journal/2026/10/2026-10-01.md').write_text('## 🏰 The Sanctum\nKeep notes\n', encoding='utf-8-sig')
    (tmp_path/'Bridge/status.json').write_text(json.dumps({'last_updated': '2026-10-01', 'squad': []}))
    (tmp_path/'Bridge/CompanionStats.json').write_text(json.dumps({'companions': {'Keeper': {'xp': 0, 'level': 1}}}))

    tasks = [{'id': f'concurrent-{i}', 'text': f'Concurrent task {i}', 'frequency': 'daily', 'area': 'Sanctum'} for i in range(5)]
    (tmp_path/'Bridge/ops_state.json').write_text(json.dumps({'tasks': tasks, 'active_tasks': []}), encoding='utf-8-sig')

    def run_complete(t):
        return complete_recurring(tmp_path, t['id'])

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(run_complete, tasks))

    assert len(results) == 5
    for res in results:
        assert res['status'] == 'completed'

    saved_state = json.loads((tmp_path/'Bridge/ops_state.json').read_text(encoding='utf-8-sig'))
    assert len(saved_state['tasks']) == 5
    for t in saved_state['tasks']:
        assert t['last_done'] == '2026-10-01'
        assert t['next_due'] == '2026-10-02'


