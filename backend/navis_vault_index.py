"""Explicit local operator command. Never exposed as an MCP mutation tool."""
import json
import os
import sys
import time

from services.vault_access import VaultAccessError, VaultPolicy
from services.vault_index import rebuild_index
from services.vault_limits import scan_timeout_seconds


def main():
    if sys.argv[1:] != ["rebuild"]:
        print("Usage: navis_vault_index.py rebuild", file=sys.stderr)
        return 2
    try:
        result = rebuild_index(VaultPolicy.from_env(), os.environ.get("NAVIS_MCP_STATE_DIR"),
                               deadline=time.monotonic() + scan_timeout_seconds())
        print(json.dumps(result))
        return 0
    except VaultAccessError as error:
        print(json.dumps({"status": "error", "error": {"code": error.code}}), file=sys.stderr)
        return 1
    except Exception:
        print('{"status":"error","error":{"code":"internal_error"}}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
