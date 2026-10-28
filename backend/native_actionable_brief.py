"""Native brief adapter: no HTTP server or journal mutations."""
import json
import os
import sys
from services.actionable_brief import generate, save

try:
    request = json.load(sys.stdin)
    path, body = request.get("path"), request.get("body", {})
    if path == "/api/journal/brief/generate":
        result = generate(body)
    elif path == "/api/journal/brief/save":
        result = save(os.environ["NAVIS_ROOT"], body)
    else:
        raise ValueError("Unsupported brief operation.")
    response = {"status": 200, "body": result}
except ValueError as error:
    response = {"status": 422, "body": {"detail": str(error)}}
except Exception:
    response = {"status": 503, "body": {"detail": "Brief service unavailable. Original unchanged; retry the same save if needed."}}
json.dump(response, sys.stdout, ensure_ascii=True)
