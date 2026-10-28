"""Native adapter for explicit-source reviewed knowledge notes."""
import json
import os
import sys
from services.knowledge_notes import selected_sources, save
from services.vault_access import VaultAccessError

try:
    request = json.load(sys.stdin)
    body = request.get("body", {})
    if request.get("path") == "/api/knowledge-notes/sources":
        result = selected_sources(os.environ["NAVIS_ROOT"], body.get("paths"))
    elif request.get("path") == "/api/knowledge-notes/save":
        result = save(os.environ["NAVIS_ROOT"], body)
    else:
        raise ValueError("Unsupported note operation.")
    response = {"status": 200, "body": result}
except (ValueError, VaultAccessError):
    response = {"status": 422, "body": {"detail": "Selected source or destination is unavailable or changed. Reload and review; existing records are unchanged."}}
except Exception:
    response = {"status": 503, "body": {"detail": "Note operation unavailable. Retry the same save to verify its outcome."}}
json.dump(response, sys.stdout, ensure_ascii=True)
