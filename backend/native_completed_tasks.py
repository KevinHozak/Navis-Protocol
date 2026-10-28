"""Read-only native completed-today bridge; no daemon or XP initialization."""
import json
import os
import sys
from services.completed_today import build


def main():
    try:
        request = json.load(sys.stdin)
        if request.get('path') != '/api/tasks/completed-today':
            raise ValueError('Unsupported read')
        result = {'status': 200, 'body': build(os.environ['NAVIS_ROOT'])}
    except Exception:
        result = {'status': 503, 'body': {'detail': 'Completion evidence unavailable'}}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
