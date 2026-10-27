"""Desktop bridge to the shared journal append authority; no HTTP startup."""
import json
import os
import sys
from services.journal_entry import append, JournalError
from services.vault_access import VaultAccessError


def main():
    try:
        request = json.load(sys.stdin)
        if request.get("path") != "/api/journal/entry":
            raise JournalError("unsupported_journal_command", 400)
        result = append(os.environ["NAVIS_ROOT"], request.get("body"))
        response = {"status": 200, "body": result}
    except JournalError as error:
        response = {"status": error.status, "body": {"detail": error.code}}
    except VaultAccessError as error:
        response = {"status": 404 if error.code == "not_found" else 503, "body": {"detail": error.code}}
    except Exception:
        response = {"status": 503, "body": {"detail": "append_outcome_unknown_retry_same_request"}}
    # ASCII JSON also works when a standalone Windows parent omitted UTF-8 env.
    json.dump(response, sys.stdout, ensure_ascii=True)


if __name__ == "__main__":
    main()
