"""Allowlisted desktop combat adapter. JSON stdin/stdout; never starts HTTP."""
import contextlib
import json
import sys

from services.combat_completion import dispatch


def main():
    try:
        request = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = dispatch(request["path"], request.get("body") or {})
        json.dump({"status": 200, "body": result}, sys.stdout, ensure_ascii=False)
    except (ValueError, KeyError, FileNotFoundError) as error:
        json.dump({"status": 400, "body": {"detail": str(error)}}, sys.stdout)
    except Exception as error:
        json.dump({"status": 500, "body": {"detail": str(error)}}, sys.stdout)


if __name__ == "__main__":
    main()
