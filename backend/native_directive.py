import contextlib
import json
import os
import sys
from services.directive_completion import complete, complete_recurring, transition

try:
    request = json.load(sys.stdin)
    path = request.get('path', '/api/active_tasks/complete')
    if path == '/api/active_tasks/complete':
        is_rec = False
    elif path == '/api/recurring/complete':
        is_rec = True
    else:
        raise ValueError('Unsupported directive command')
    with contextlib.redirect_stdout(sys.stderr):
        body = request['body']
        result = transition(os.environ['NAVIS_ROOT'], body['task_id'], body['task_status'], body.get('expected_task'), is_recurring=is_rec) if 'task_status' in body else (complete_recurring(os.environ['NAVIS_ROOT'], body['task_id']) if is_rec else complete(os.environ['NAVIS_ROOT'], body['task_id']))
    json.dump({'status': 200, 'body': result}, sys.stdout)
except (ValueError, KeyError, FileNotFoundError) as error:
    json.dump({'status': 409, 'body': {'detail': str(error)}}, sys.stdout)

except Exception:
    json.dump({"status": 503, "body": {"detail": "Completion interrupted; retry Mark Done to recover"}}, sys.stdout)
