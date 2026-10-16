import contextlib
import json
import os
import sys
from services.directive_completion import complete, complete_recurring

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
        result = complete_recurring(os.environ['NAVIS_ROOT'], request['body']['task_id']) if is_rec else complete(os.environ['NAVIS_ROOT'], request['body']['task_id'])
    json.dump({'status': 200, 'body': result}, sys.stdout)
except (ValueError, KeyError, FileNotFoundError) as error:
    json.dump({'status': 409, 'body': {'detail': str(error)}}, sys.stdout)

except Exception:
    json.dump({"status": 503, "body": {"detail": "Completion interrupted; retry Mark Done to recover"}}, sys.stdout)
