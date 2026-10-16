"""Durable active-directive and recurring mandate completion using the journal daily XP policy."""
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from services.combat_completion import atomic_bytes, atomic_json, battle_lock, safe_source
from services.recurrence import calculate_next_due

HEADERS = {
    'sanctum': '## 🏰 The Sanctum',
    'domestic': '## 🏠 The Domestic Breach',
    'front': '## ⚔️ The High-Velocity Front',
    'bureaucratic': '## ⚖️ The Bureaucratic Gauntlet',
    'world': '## 🥾 The Kinetic Outland',
}


def complete_section_item(content, header, text, marker=None):
    """Reuse one exact occurrence in its section; never guess between duplicates."""
    lines = content.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == header]
    if len(starts) != 1:
        raise ValueError('Directive journal section missing or ambiguous')
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith('## ') or lines[i].strip() == '---'), len(lines))
    matches = []
    for i in range(start + 1, end):
        match = re.fullmatch(r'(\s*[-*+]\s+\[)[ xX](\]\s+)([^\r\n]*)(\r?\n)?', lines[i])
        if match:
            label = re.sub(r'\s*<!-- navis-directive:[^>]+ -->', '', match[3])
            if ' '.join(label.split()) == ' '.join(text.split()):
                matches.append((i, match))
    if len(matches) > 1:
        raise ValueError('Directive journal occurrence ambiguous; review before retry')
    newline = '\r\n' if '\r\n' in content else '\n'
    suffix = f' {marker}' if marker else ''
    if matches:
        i, match = matches[0]
        if marker and '<!-- navis-directive:' in match[3]:
            raise ValueError('Journal occurrence already belongs to another directive')
        # Keep existing provenance when the legacy sweep encounters a canonical item.
        label = re.sub(r'\s*<!-- navis-directive:[^>]+ -->', '', match[3]) if marker else match[3]
        lines[i] = match[1] + 'x' + match[2] + label + suffix + (match[4] or '')
    else:
        if not lines[start].endswith(('\n', '\r')):
            lines[start] += newline
        lines.insert(start + 1, f'- [x] {text}{suffix}{newline}')
    return ''.join(lines)

CANONICAL_AREAS = {
    'sanctum': 'sanctum', 'the sanctum': 'sanctum', 'command': 'sanctum',
    'domestic': 'domestic', 'the domestic breach': 'domestic', 'home': 'domestic',
    'front': 'front', 'the high-velocity front': 'front', 'work': 'front',
    'bureaucratic': 'bureaucratic', 'gauntlet': 'bureaucratic',
    'the bureaucratic gauntlet': 'bureaucratic', 'finances': 'bureaucratic',
    'world': 'world', 'outland': 'world', 'the kinetic outland': 'world',
    'kinetic outland': 'world',
}


def _verify_journal_date(root):
    status_file = Path(root) / 'Bridge/status.json'
    if not status_file.is_file():
        raise ValueError("Journal date unavailable")
    try:
        status = json.loads(status_file.read_text(encoding='utf-8-sig'))
    except Exception as error:
        raise ValueError("Journal date unavailable") from error
    date = status.get('last_updated')
    if not isinstance(date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        raise ValueError("Journal date unavailable")
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError as error:
        raise ValueError("Journal date unavailable") from error
    return date


def _resolve_header(task, raw_bytes):
    raw_area = str(task.get('area', '')).strip().lower()
    area = CANONICAL_AREAS.get(raw_area, raw_area)
    header = HEADERS.get(area)
    if not header or header not in raw_bytes.decode('utf-8-sig').splitlines():
        raise ValueError('Directive journal section unavailable')
    return header


def complete(root, task_id, award=None, is_recurring=False):
    root = Path(root)
    with battle_lock(root):
        path = root / 'Bridge/ops_state.json'
        if not path.is_file():
            raise ValueError('Task identity missing or ambiguous')
        state = json.loads(path.read_text(encoding='utf-8-sig'))
        bucket = 'tasks' if is_recurring else 'active_tasks'
        matches = [t for t in state.get(bucket, []) if t.get('id') == task_id]
        if len(matches) != 1:
            raise ValueError('Task identity missing or ambiguous')
        task = matches[0]

        operation = task.get('completion')
        date = _verify_journal_date(root)

        if is_recurring:
            if operation and operation.get('local_date') == date and operation.get('phase') == 'complete':
                return {'status': 'completed', 'task': task, 'idempotent_replay': True}
            if task.get('last_done') == date and not operation:
                return {'status': 'completed', 'task': task, 'idempotent_replay': True}
        else:
            if operation and operation.get('phase') == 'complete':
                return {'status': 'completed', 'task': task, 'idempotent_replay': True}
            if not operation and task.get('status') == 'completed':
                raise ValueError('Legacy completion needs provenance review')

        needs_prepare = not operation or (is_recurring and operation.get('local_date') != date)

        if needs_prepare:
            relative = f'Journal/{date[:4]}/{date[5:7]}/{date}.md'
            journal = safe_source(root, relative)
            raw = journal.read_bytes()
            raw.decode('utf-8-sig')
            header = _resolve_header(task, raw)
            text = ' '.join(str(task.get('text', '')).split())
            if not text:
                raise ValueError('Directive text is empty')

            if is_recurring:
                freq = task.get('frequency', 'daily')
                next_due = calculate_next_due(freq, date)
                source_id = hashlib.sha256(f"{task_id}:{date}".encode()).hexdigest()
                operation = {
                    'phase': 'prepared',
                    'completed_at': datetime.now(timezone.utc).isoformat(),
                    'journal_path': relative,
                    'local_date': date,
                    'header': header,
                    'marker': f'<!-- navis-directive:{source_id} -->',
                    'text': text,
                    'source_ref': f'{relative}#daily-xp',
                    'rule_version': 'xp-v1',
                    'next_due': next_due,
                }
            else:
                source_id = hashlib.sha256(task_id.encode()).hexdigest()
                operation = {
                    'phase': 'prepared',
                    'completed_at': datetime.now(timezone.utc).isoformat(),
                    'journal_path': relative,
                    'local_date': date,
                    'header': header,
                    'marker': f'<!-- navis-directive:{source_id} -->',
                    'text': text,
                    'source_ref': f'{relative}#daily-xp',
                    'rule_version': 'xp-v1',
                }

            task['completion'] = operation
            atomic_json(path, state)

        journal = safe_source(root, operation['journal_path'])
        raw = journal.read_bytes()
        content = raw.decode('utf-8-sig')
        marker = operation['marker']

        if marker not in content:
            updated = complete_section_item(content, operation['header'], operation['text'], marker).encode('utf-8')
            if raw.startswith(b'\xef\xbb\xbf'):
                updated = b'\xef\xbb\xbf' + updated
            if journal.read_bytes() != raw:
                raise ValueError("Journal changed during completion; retry")
            shutil.copy2(journal, journal.with_name(journal.name + f'.backup_directive_{uuid.uuid4().hex}'))
            atomic_bytes(journal, updated)
        elif content.count(marker) != 1 or not any(re.match(r'^\s*[-*+]\s+\[[xX]\]\s+', line) and line.endswith(marker) for line in content.splitlines()):
            raise ValueError('Completion journal evidence changed; review before retry')

        operation['phase'] = 'xp_pending'
        if not is_recurring:
            task['status'] = 'completion_pending'
        atomic_json(path, state)

        if award is None:
            from services.rpg_engine import calculate_and_apply_xp
            award = calculate_and_apply_xp
        award(date_override=operation['local_date'])

        operation['phase'] = 'complete'
        task['completed_at'] = operation['completed_at']
        if is_recurring:
            task['last_done'] = operation['local_date']
            task['next_due'] = operation.get('next_due')
        else:
            task['status'] = 'completed'

        latest = json.loads(path.read_text(encoding='utf-8-sig'))
        targets = [t for t in latest.get(bucket, []) if t.get('id') == task_id]
        if len(targets) != 1 or targets[0].get('completion', {}).get('marker') != marker:
            raise ValueError('Completion state changed during XP sync; review before retry')

        if is_recurring:
            targets[0].update({
                'completion': operation,
                'last_done': task['last_done'],
                'next_due': task['next_due'],
                'completed_at': task['completed_at'],
            })
            if 'due_date' in targets[0]:
                targets[0]['due_date'] = task['next_due']
        else:
            targets[0].update({
                'completion': operation,
                'status': 'completed',
                'completed_at': task['completed_at'],
            })

        atomic_json(path, latest)
        return {'status': 'completed', 'task': targets[0], 'idempotent_replay': False}


def complete_recurring(root, task_id, award=None):
    return complete(root, task_id, award=award, is_recurring=True)


def complete_active(root, task_id, award=None):
    return complete(root, task_id, award=award, is_recurring=False)

