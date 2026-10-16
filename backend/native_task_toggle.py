"""Desktop bridge to the same task mutation used by HTTP."""
import contextlib
import json
import sys
import os
from pathlib import Path
from urllib.parse import unquote
from services.task_toggle import toggle, ToggleConflict

try:
    request = json.load(sys.stdin)
    if request['path'] != '/api/tasks/toggle':
        raise ValueError('Unsupported task command')
    with contextlib.redirect_stdout(sys.stderr):
        root = Path(os.environ['NAVIS_ROOT']).resolve()
        relative = unquote(request['body']['file_path']).replace('\\', '/')
        if not relative or relative.startswith('/') or ':' in relative or any(p in ('', '.', '..') for p in relative.split('/')):
            raise ValueError('Invalid Vault path')
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Path escapes Vault')
        if path.is_dir():
            path = next((path / name for name in ('Profile.md', 'profile.md', 'README.md', 'readme.md') if (path / name).is_file()), path)
        result = toggle(root, path, request['body'])
        result['source_content'] = result['content']
    json.dump({'status': 200, 'body': result}, sys.stdout)
except ToggleConflict as error:
    json.dump({'status': 409, 'body': {'detail': {'saved': False, 'content': error.content, 'message': str(error)}}}, sys.stdout)
except ValueError as error:
    json.dump({'status': 400, 'body': {'detail': str(error)}}, sys.stdout)
except Exception:
    json.dump({'status': 503, 'body': {'detail': 'Task request interrupted; reload and retry'}}, sys.stdout)
