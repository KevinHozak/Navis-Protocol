"""Inline completion instants: written with the checkbox, never inferred by sync."""
import json
import re
from datetime import datetime, timezone

MARKER = re.compile(r' <!-- navis-completion:(\{[^\r\n]*?\}) -->')


def now():
    return datetime.now(timezone.utc).isoformat()


def valid_instant(value):
    if not isinstance(value, str) or 'T' not in value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


def strip(text):
    return MARKER.sub('', text)


def read(text):
    matches = MARKER.findall(text)
    if len(matches) > 1 or ('<!-- navis-completion:' in text and len(matches) != 1):
        raise ValueError('Completion metadata missing or ambiguous; review before saving')
    if not matches:
        return {'completed_at': None, 'history': []}
    value = json.loads(matches[0])
    if set(value) != {'completed_at', 'history'} or not isinstance(value['history'], list):
        raise ValueError('Invalid completion metadata')
    if any(not valid_instant(item) for item in value['history']) or (value['completed_at'] is not None and not valid_instant(value['completed_at'])):
        raise ValueError('Invalid completion instant')
    return value


def transition(label, was_done, done, instant=None):
    value = read(label)
    # Already checked manual/legacy rows remain time unknown, even on replay.
    if was_done == done:
        return label, value['completed_at'] if done else None
    previous = value['completed_at']
    if previous:
        value['history'].append(previous)
    value['completed_at'] = (instant or now()) if done else None
    if value['completed_at'] and not valid_instant(value['completed_at']):
        raise ValueError('Timezone-aware completion instant required')
    label = strip(label)
    marker = ' <!-- navis-completion:' + json.dumps(value, separators=(',', ':')) + ' -->'
    owner = re.search(r'[ \t]*<!-- navis-directive:', label)
    end = owner.start() if owner else len(label.rstrip(' \t'))
    label = label[:end] + marker + label[end:]
    return label, value['completed_at']
