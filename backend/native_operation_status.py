"""Read durable operation outcomes without starting a service or replaying writes."""
import json
import os
import sys

from services.operation_outcomes import acknowledge, read_latest, read_operation


def main():
    try:
        request = json.load(sys.stdin)
        prefix = "/api/ops/jobs/"
        if request.get("path") == "/api/ops/latest" and (request.get("body") or {}).get("method", "GET") == "GET":
            print(json.dumps({"status": 200, "body": read_latest(os.environ["NAVIS_ROOT"])}))
            return
        if not request.get("path", "").startswith(prefix):
            raise ValueError("Unsupported operation read")
        target = request["path"][len(prefix):]
        method = (request.get("body") or {}).get("method", "GET")
        if target.endswith("/review") and method == "POST":
            value = acknowledge(os.environ["NAVIS_ROOT"], target[:-len("/review")])
        elif "/" not in target and method == "GET":
            value = read_operation(os.environ["NAVIS_ROOT"], target)
        else:
            raise ValueError("Unsupported operation method")
        result = {"status": 200, "body": value}
    except FileNotFoundError:
        result = {"status": 404, "body": {"detail": "Operation record unavailable"}}
    except Exception:
        result = {"status": 503, "body": {"detail": "Operation state unavailable; review saved changes"}}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
