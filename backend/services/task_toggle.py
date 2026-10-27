"""One target-safe checkbox contract for HTTP and desktop mutations."""
from html import unescape
import re
import uuid
from pathlib import Path
from services.combat_completion import atomic_bytes, battle_lock

STATES = {'pending', 'in_progress', 'deferred', 'cancelled', 'done'}
STATUS_MARKER = re.compile(r'\s*<!-- navis-task:([a-f0-9]{32}):(pending|in_progress|deferred|cancelled|done) -->')


class ToggleConflict(ValueError):
    def __init__(self, message, content):
        super().__init__(message)
        self.content = content


def _rendered_task_text(source_text):
    """Match Markdown source to the plain text exposed by the checkbox UI."""
    source_text = STATUS_MARKER.sub('', source_text)
    source_text = re.sub(r'\s*<!-- navis-directive:[^>]+ -->', '', source_text)
    text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m[1].rsplit('|', 1)[-1], source_text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*?)?\s*/?>", "", text)
    for _ in range(3):
        text = re.sub(r"(\*\*|~~|\*|`)(.*?)\1", r"\2", text)
        text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", text)
        text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return unescape(text).strip()


def toggle(root, path, request, award=None, locked=False):
    from contextlib import nullcontext
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Task file must be inside the Vault')
    with nullcontext() if locked else battle_lock(root):
        raw = path.read_bytes()
        content = raw.decode('utf-8-sig')
        expected = request.get('expected_content')
        if expected is None or expected != content:
            raise ToggleConflict('File changed; reload before retrying', content)
        lines = content.splitlines(keepends=True)
        pattern = re.compile(r'^(\s*[-*+]\s+\[)([ xX])(\]\s+)([^\r\n]*)(\r?\n)?$')
        matches = [(i, pattern.fullmatch(line)) for i, line in enumerate(lines)]
        matches = [(i, m) for i, m in matches if m and _rendered_task_text(m[4]) == _rendered_task_text(request['target_text'])]
        number = request.get('line_number')
        if number is not None:
            matches = [(i, m) for i, m in matches if i == number - 1]
        if len(matches) != 1:
            raise ToggleConflict('Task target missing, stale or ambiguous; reload', content)
        index, match = matches[0]
        if request.get('task_status') is None and not isinstance(request.get('is_checked'), bool):
            raise ValueError('A task status or checkbox state is required')
        desired = request.get('task_status') if request.get('task_status') is not None else ('done' if request['is_checked'] else 'pending')
        if desired not in STATES:
            raise ValueError('Unknown task status')
        if request.get('task_status') is not None and request.get('is_checked') is not None and request['is_checked'] != (desired == 'done'):
            raise ValueError('Task status and checkbox state disagree')
        if '<!-- navis-directive:' in match[4]:
            import json
            from services.directive_completion import transition
            ops = json.loads((root / 'Bridge/ops_state.json').read_text(encoding='utf-8-sig'))
            owners = [(task, recurring) for bucket, recurring in [('active_tasks', False), ('tasks', True)]
                      for task in ops.get(bucket, []) if task.get('completion', {}).get('marker')
                      and task['completion']['marker'] in match[4]]
            if len(owners) != 1 or owners[0][0]['completion']['journal_path'] != path.relative_to(root).as_posix():
                raise ToggleConflict('Linked task identity missing or ambiguous', content)
            task, recurring = owners[0]
            transition(root, task['id'], desired, task, is_recurring=recurring, award=award, locked=True)
            return {'status': 'success', 'saved': True, 'content': path.read_bytes().decode('utf-8-sig'),
                    'task_status': desired, 'task_id': task['id'], 'xp_status': 'complete'}
        state = 'x' if desired == 'done' else ' '
        markers = STATUS_MARKER.findall(match[4])
        if len(markers) > 1 or ('<!-- navis-task:' in match[4] and len(markers) != 1):
            raise ToggleConflict('Task identity ambiguous; reload', content)
        label = match[4]
        task_id = markers[0][0] if markers else None
        if task_id and content.count(f'<!-- navis-task:{task_id}:') != 1:
            raise ToggleConflict('Task identity duplicated; reload', content)
        if request.get('task_status') is not None or markers:
            task_id = task_id or uuid.uuid4().hex
            label = STATUS_MARKER.sub('', label) + f' <!-- navis-task:{task_id}:{desired} -->'
        modified = match[2].lower() != state or label != match[4]
        if modified:
            lines[index] = match[1] + state + match[3] + label + (match[5] or '')
            updated = ''.join(lines)
            if path.read_bytes() != raw:
                raise ToggleConflict('File changed before save; reload', path.read_bytes().decode('utf-8-sig'))
            atomic_bytes(path, (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8'))
            content = updated
        if path.read_bytes().decode('utf-8-sig') != content:
            raise ToggleConflict('Task changed after save; reload', path.read_bytes().decode('utf-8-sig'))
        result = {'status': 'success', 'saved': True, 'modified': modified, 'content': content, 'task_status': desired, 'task_id': task_id, 'xp_status': 'not_applicable'}
        relative = path.relative_to(root).as_posix()
        journal = re.fullmatch(r'Journal/(\d{4})/(\d{2})/(\d{4}-\d{2}-\d{2})\.md', relative)
        if journal and journal[3].startswith(f'{journal[1]}-{journal[2]}-'):
            try:
                if request.get('task_status') is not None and desired != 'done' and match[2] not in 'xX':
                    # Noncompletion transitions cannot mint a daily award. Reconcile
                    # only an existing source (including a pending projection retry).
                    from services import progression_db
                    if Path(progression_db.NAVIS_ROOT).resolve() != root:
                        raise ValueError('XP runtime Vault does not match task Vault')
                    if not (root / 'Keeper/navis_progression.db').exists():
                        return result
                    from datetime import datetime
                    day = datetime.strptime(journal[3], '%Y-%m-%d')
                    if not progression_db.get_source_states('journal_daily', f"Journal/{day.strftime('%Y/%m/%d')}.md#daily-xp"):
                        return result
                if award is None:
                    from services import rpg_engine, progression_db
                    if Path(rpg_engine.NAVIS_ROOT).resolve() != root or Path(progression_db.NAVIS_ROOT).resolve() != root:
                        raise ValueError("XP runtime Vault does not match task Vault")
                    rpg_engine.calculate_and_apply_xp(date_override=journal[3], root=root, journal_content=content)
                else:
                    award(date_override=journal[3])
                result['xp_status'] = 'complete'
            except Exception:
                result.update(status='saved_xp_pending', xp_status='pending', message='Task saved. XP pending; retry this checkbox state to reconcile safely.')
        return result
