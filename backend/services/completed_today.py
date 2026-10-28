"""Bounded, read-only completion evidence. Never imports mutation/XP services."""
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services import task_time

TASK = re.compile(r'^\s*[-*+]\s+\[([ xX])\]\s+([^\r\n]*)$')
IDENTITY = re.compile(r'<!-- navis-task:([a-f0-9]{32}):(pending|in_progress|deferred|cancelled|done) -->')
DIRECTIVE = re.compile(r'<!-- navis-directive:([a-f0-9]{64}) -->')
AREAS = {'the sanctum': 'sanctum', 'sanctum': 'sanctum', 'the domestic breach': 'domestic',
         'domestic': 'domestic', 'the high velocity front': 'front', 'front': 'front',
         'the bureaucratic gauntlet': 'bureaucratic', 'gauntlet': 'bureaucratic',
         'the kinetic outland': 'world', 'kinetic outland': 'world'}
MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, MAX_ROWS = 8000, 2 * 1024 * 1024, 64 * 1024 * 1024, 1000


def area_for(header):
    label = re.sub(r'[^a-z]+', ' ', header.lower()).strip()
    return AREAS.get(' '.join(label.split()), 'unassigned')


def label_for(label):
    label = task_time.strip(label)
    label = re.sub(r'\s*<!-- navis-(?:task|directive):[^>]+ -->', '', label)
    label = re.sub(r'\[\[([^\]]+)\]\]', lambda m: m[1].rsplit('|', 1)[-1], label)
    label = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', label)
    return label.strip()


def normalized_instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()


def visible_lines(content):
    """Ignore frontmatter, fenced examples and comment blocks; keep source lines."""
    fence, frontmatter, comment = None, False, False
    for number, line in enumerate(content.splitlines(), 1):
        if number == 1 and line.strip() == '---':
            frontmatter = True
            continue
        if frontmatter:
            if line.strip() in ('---', '...'):
                frontmatter = False
            continue
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = (marker[1][0], len(marker[1]))
            continue
        if comment or line.lstrip().startswith('<!--'):
            comment = '-->' not in line
            continue
        yield number, line


def build(root, now=None):
    root = Path(root)
    issues, snapshots = [], {}
    result = {'status': 'unavailable', 'date': None, 'timezone': 'America/Chicago',
              'completed': [], 'journal_evidence': [], 'issues': issues,
              'coverage': {'scanned_files': 0, 'scope': 'Journal/**/*.md', 'bounded': True}}
    def issue(path, reason):
        item = {'path': str(path), 'reason': reason}
        if item not in issues:
            issues.append(item)
    def read(path):
        relative = path.relative_to(root).as_posix()
        try:
            if any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
                   for p in [path, *path.parents] if p == root or root in p.parents):
                raise ValueError('linked_source')
            before = path.stat()
            if before.st_size > MAX_FILE_BYTES:
                raise ValueError('source_size_limit')
            raw = path.read_bytes()
            after = path.stat()
            signature = (after.st_size, after.st_mtime_ns)
            if len(raw) > MAX_FILE_BYTES or signature != (before.st_size, before.st_mtime_ns):
                raise ValueError('source_changed')
            snapshots[relative] = (path, signature)
            return raw
        except (OSError, ValueError) as error:
            issue(relative, str(error) if isinstance(error, ValueError) else 'source_unreadable')
            return None
    try:
        settings_file = root / 'Bridge/settings.json'
        raw_settings = read(settings_file) if settings_file.is_file() else None
        settings = json.loads(raw_settings.decode('utf-8-sig')) if raw_settings else {}
        name = settings.get('timezone') or 'America/Chicago'
        zone = ZoneInfo(name)
    except (OSError, ValueError, TypeError, AttributeError, ZoneInfoNotFoundError):
        try:
            name, zone = 'America/Chicago', ZoneInfo('America/Chicago')
        except ZoneInfoNotFoundError:
            issue('Bridge/settings.json', 'timezone_unavailable')
            return result
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware now required')
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone)
    end = datetime.combine(day + timedelta(days=1), time.min, zone)
    result.update(date=day.isoformat(), timezone=name, day_start=start.isoformat(), day_end=end.isoformat())
    journal_root = root / 'Journal'
    if not journal_root.is_dir() or journal_root.is_symlink() or (hasattr(journal_root, 'is_junction') and journal_root.is_junction()):
        issue('Journal', 'journal_unavailable')
        return result
    records = {}
    raw_ops = read(root / 'Bridge/ops_state.json')
    if raw_ops is not None:
        try:
            ops = json.loads(raw_ops.decode('utf-8-sig'))
            for bucket in ('active_tasks', 'tasks'):
                if not isinstance(ops.get(bucket, []), list):
                    raise ValueError()
                for task in ops.get(bucket, []):
                    for op in [*task.get('completion_history', []), task.get('completion')]:
                        if isinstance(op, dict) and op.get('marker') and op.get('journal_path'):
                            key = (op['journal_path'], op['marker'])
                            records.setdefault(key, []).append((task, op, op is task.get('completion'), bucket))
        except (ValueError, TypeError, AttributeError):
            records.clear()
            issue('Bridge/ops_state.json', 'invalid_provenance')
    paths, total = [], 0
    def walk_error(error):
        issue('Journal', 'directory_unreadable')
    for parent, dirs, files in os.walk(journal_root, followlinks=False, onerror=walk_error):
        for directory in list(dirs):
            path = Path(parent) / directory
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                dirs.remove(directory)
                issue(path.relative_to(root).as_posix(), 'linked_source')
        dirs.sort()
        for filename in sorted(files):
            if filename.lower().endswith('.md'):
                paths.append(Path(parent) / filename)
                if len(paths) >= MAX_FILES:
                    issue('Journal', 'file_count_limit')
                    break
        if len(paths) >= MAX_FILES:
            break
    for path in paths:
        raw = read(path)
        if raw is None:
            continue
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            issue('Journal', 'total_size_limit')
            break
        relative = path.relative_to(root).as_posix()
        result['coverage']['scanned_files'] += 1
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeError:
            issue(relative, 'invalid_encoding')
            continue
        lines = list(visible_lines(content))
        identities = Counter(identity for _, line in lines for identity, _ in IDENTITY.findall(line))
        owners = Counter(owner for _, line in lines for owner in DIRECTIVE.findall(line))
        area = 'unassigned'
        date_match = re.fullmatch(r'Journal/\d{4}/\d{2}/(\d{4}-\d{2}-\d{2})\.md', relative)
        journal_day = date_match[1] if date_match else None
        for number, line in lines:
            if line.startswith('## '):
                area = area_for(line[3:])
            match = TASK.fullmatch(line)
            if not match or match[1] not in 'xX':
                continue
            identities_here, owners_here = IDENTITY.findall(line), DIRECTIVE.findall(line)
            if ('<!-- navis-task:' in line and not identities_here) or ('<!-- navis-directive:' in line and not owners_here):
                issue(relative, 'invalid_task_identity')
                continue
            if (len(identities_here) > 1 or len(owners_here) > 1
                    or any(identities[item[0]] > 1 for item in identities_here)
                    or any(owners[item] > 1 for item in owners_here)):
                issue(relative, 'ambiguous_identity')
                continue
            if identities_here and identities_here[0][1] != 'done':
                issue(relative, 'checkbox_status_conflict')
                continue
            try:
                meta = task_time.read(line)
            except (ValueError, TypeError):
                issue(relative, 'invalid_completion_metadata')
                meta = {'completed_at': None}
            instant = meta['completed_at']
            if owners_here:
                marker = f'<!-- navis-directive:{owners_here[0]} -->'
                provenance = records.get((relative, marker), [])
                if not provenance and any(owner == marker for _, owner in records):
                    issue(relative, 'directive_source_mismatch')
                    continue
                current = [record for record in provenance if record[2]]
                if len(current) > 1:
                    issue(relative, 'ambiguous_provenance')
                    continue
                if any(op.get('phase') != 'complete' or (bucket == 'active_tasks' and task.get('status') != 'completed')
                       for task, op, _, bucket in current):
                    continue
                candidates = {normalized_instant(op['completed_at']) for _, op, _, _ in (current or provenance)
                              if op.get('phase') == 'complete' and task_time.valid_instant(op.get('completed_at'))}
                if instant and current and candidates and normalized_instant(instant) not in candidates:
                    issue(relative, 'completion_time_conflict')
                    continue
                if not instant and len(candidates) == 1:
                    instant = candidates.pop()
                elif not instant and len(candidates) > 1:
                    issue(relative, 'ambiguous_completion_time')
            if instant:
                instant = normalized_instant(instant)
            identity = f'directive:{owners_here[0]}' if owners_here else f'{relative}:{identities_here[0][0] if identities_here else number}'
            item = {'id': hashlib.sha256(identity.encode()).hexdigest(),
                    'text': label_for(match[2]), 'area': area, 'completed_at': instant,
                    'source': {'path': relative, 'line_number': number, 'journal_date': journal_day}}
            if instant and datetime.fromisoformat(instant.replace('Z', '+00:00')).astimezone(zone).date() == day:
                result['completed'].append(item)
            elif not instant and journal_day == day.isoformat():
                item['evidence'] = 'Checked journal item; completion time unknown; may be an activity log'
                result['journal_evidence'].append(item)
            if len(result['completed']) + len(result['journal_evidence']) >= MAX_ROWS:
                issue('Journal', 'row_limit')
                break
        if len(result['completed']) + len(result['journal_evidence']) >= MAX_ROWS:
            break
    counts = Counter(item['id'] for key in ('completed', 'journal_evidence') for item in result[key])
    for key in ('completed', 'journal_evidence'):
        for item in result[key]:
            if counts[item['id']] > 1:
                issue(item['source']['path'], 'ambiguous_provenance')
        result[key] = [item for item in result[key] if counts[item['id']] == 1]
    changed = set()
    for relative, (path, signature) in snapshots.items():
        try:
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != signature:
                raise OSError()
        except OSError:
            changed.add(relative)
            issue(relative, 'source_changed')
    if {'Bridge/ops_state.json', 'Bridge/settings.json'} & changed:
        result['completed'].clear()
        result['journal_evidence'].clear()
    else:
        for key in ('completed', 'journal_evidence'):
            result[key] = [item for item in result[key] if item['source']['path'] not in changed]
            result[key].sort(key=lambda item: (item['area'], item['completed_at'] or '', item['source']['path'], item['source']['line_number']))
    result['status'] = 'partial' if issues else 'complete' if result['completed'] or result['journal_evidence'] else 'empty'
    return result
