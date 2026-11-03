"""Native read-only Projects adapter. No caller-supplied query, URL or credentials."""
import json
import sys
from services.projects import overview, ProjectsUnavailable

try:
    request = json.load(sys.stdin)
    if request.get('path') != '/api/projects':
        raise ValueError()
    response = {'status': 200, 'body': overview()}
except ProjectsUnavailable as error:
    response = {'status': 503, 'body': {'detail': str(error)}}
except Exception:
    response = {'status': 503, 'body': {'detail': 'GitHub overview unavailable. Refresh later.'}}
json.dump(response, sys.stdout, ensure_ascii=True)
