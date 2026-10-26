"""One target-safe checkbox contract for HTTP and desktop mutations."""
from html import unescape
import re
from pathlib import Path
from services.combat_completion import atomic_bytes, battle_lock


class ToggleConflict(ValueError):
    def __init__(self, message, content):
        super().__init__(message)
        self.content = content


def _rendered_task_text(source_text):
    """Match Markdown source to the plain text exposed by the checkbox UI."""
    text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: m[1].rsplit('|', 1)[-1], source_text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*?)?\s*/?>", "", text)
    for _ in range(3):
        text = re.sub(r"(\*\*|~~|\*|`)(.*?)\1", r"\2", text)
        text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", text)
        text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    return unescape(text).strip()


def toggle(root, path, request, award=None):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Task file must be inside the Vault')
    with battle_lock(root):
        raw = path.read_bytes()
        content = raw.decode('utf-8-sig')
        expected = request.get('expected_content')
        if expected is None or expected != content:
            raise ToggleConflict('File changed; reload before retrying', content)
        lines = content.splitlines(keepends=True)
        pattern = re.compile(r'^(\s*[-*+]\s+\[)([ xX])(\]\s+)([^\r\n]*)(\r?\n)?$')
        matches = [(i, pattern.fullmatch(line)) for i, line in enumerate(lines)]
        matches = [(i, m) for i, m in matches if m and _rendered_task_text(m[4]) == request['target_text'].strip()]
        number = request.get('line_number')
        if number is not None:
            matches = [(i, m) for i, m in matches if i == number - 1]
        if len(matches) != 1:
            raise ToggleConflict('Task target missing, stale or ambiguous; reload', content)
        index, match = matches[0]
        state = 'x' if request['is_checked'] else ' '
        modified = match[2].lower() != state
        if modified:
            lines[index] = match[1] + state + match[3] + match[4] + (match[5] or '')
            updated = ''.join(lines)
            if path.read_bytes() != raw:
                raise ToggleConflict('File changed before save; reload', path.read_bytes().decode('utf-8-sig'))
            atomic_bytes(path, (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8'))
            content = updated
        result = {'status': 'success', 'saved': True, 'modified': modified, 'content': content, 'xp_status': 'not_applicable'}
        relative = path.relative_to(root).as_posix()
        journal = re.fullmatch(r'Journal/(\d{4})/(\d{2})/(\d{4}-\d{2}-\d{2})\.md', relative)
        if journal and journal[3].startswith(f'{journal[1]}-{journal[2]}-'):
            try:
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
