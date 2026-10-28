"""Read a shared Markdown source for the Tauri adapter without HTTP startup."""
import json
import os
import sys

from services.vault_access import (
    VaultAccessError,
    application_note_policy,
    is_shared_note_path,
    read_markdown_source,
)


def main():
    try:
        request = json.load(sys.stdin)
        route = request.get("path", "").split("?", 1)[0]
        prefix = "/api/vault/"
        if not isinstance(route, str) or not route.startswith(prefix):
            response = {"status": 400, "body": {"detail": "Invalid Vault note request"}}
        else:
            relative = route[len(prefix):]
            if not is_shared_note_path(relative):
                response = {"status": 204, "body": {}}
            else:
                source = read_markdown_source(
                    application_note_policy(os.environ["NAVIS_ROOT"]), relative
                )
                response = {
                    "status": 200,
                    "body": {"content": source["content"], "path": source["path"]},
                }
    except VaultAccessError as error:
        status = 404 if error.code == "not_found" else 500
        body = {"detail": "Resource not found" if status == 404 else "Resource unavailable"}
        response = {"status": status, "body": body}
    except Exception:
        response = {"status": 500, "body": {"detail": "Resource unavailable"}}
    json.dump(response, sys.stdout, ensure_ascii=True)


if __name__ == "__main__":
    main()
