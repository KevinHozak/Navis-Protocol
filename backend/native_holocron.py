"""Allowlisted desktop holocron adapter. JSON stdin/stdout; never starts HTTP."""
import asyncio
import contextlib
import json
import os
import sys

from services.holocron_engine import (
    build_weekly_holocron,
    get_holocron_manifest,
    get_current_iso_week,
    synthesize_ollama_debrief,
    export_standalone_html,
)

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")

for stream in (sys.stdout, sys.stderr):
    if stream.encoding and stream.encoding.lower() != "utf-8":
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def dispatch(path: str, method: str = "GET", body: dict = None) -> dict:
    body = body or {}
    clean_path = path.split("?")[0].rstrip("/")

    # 1. Manifest
    if clean_path == "/api/holocron/weekly/manifest":
        return get_holocron_manifest(NAVIS_ROOT)

    # 2. Latest concluded or available
    if clean_path == "/api/holocron/weekly/latest":
        return build_weekly_holocron(NAVIS_ROOT)

    # 3. Current in-flight WTD
    if clean_path == "/api/holocron/weekly/current":
        current_week = get_current_iso_week()
        return build_weekly_holocron(NAVIS_ROOT, week_id=current_week, force=True)

    # 4. Regenerate: /api/holocron/weekly/{week_id}/regenerate
    if clean_path.endswith("/regenerate"):
        parts = clean_path.split("/")
        week_id = parts[-2]
        return build_weekly_holocron(NAVIS_ROOT, week_id=week_id, force=True)

    # 5. AI Debrief: /api/holocron/weekly/{week_id}/debrief/ai
    if clean_path.endswith("/debrief/ai"):
        parts = clean_path.split("/")
        week_id = parts[-3]
        holocron_data = build_weekly_holocron(NAVIS_ROOT, week_id=week_id)
        debrief, source = asyncio.run(synthesize_ollama_debrief(holocron_data))
        holocron_data["tactical_debrief"] = debrief
        holocron_data["debrief_source"] = source

        # Persist updated debrief in json artifact if it exists on disk
        artifact_path = os.path.join(NAVIS_ROOT, "Bridge", "Holocron", "Weekly", f"{week_id}.json")
        if os.path.isfile(artifact_path):
            try:
                with open(artifact_path, "w", encoding="utf-8") as f:
                    json.dump(holocron_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        return {
            "week_id": week_id,
            "tactical_debrief": debrief,
            "debrief_source": source,
            "holocron": holocron_data,
        }

    # 6. HTML Export: /api/holocron/weekly/{week_id}/html
    if clean_path.endswith("/html"):
        parts = clean_path.split("/")
        week_id = parts[-2]
        html_file = os.path.join(NAVIS_ROOT, "Bridge", "Holocron", "Weekly", f"{week_id}.html")
        if os.path.isfile(html_file):
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            return {"html": content}
        data = build_weekly_holocron(NAVIS_ROOT, week_id=week_id)
        content = export_standalone_html(data, html_file)
        return {"html": content}

    # 7. Specific week: /api/holocron/weekly/{week_id}
    if clean_path.startswith("/api/holocron/weekly/"):
        week_id = clean_path.split("/")[-1]
        return build_weekly_holocron(NAVIS_ROOT, week_id=week_id)

    raise ValueError(f"Unsupported Holocron path: {path}")


def main():
    try:
        request = json.load(sys.stdin)
        path = request.get("path", "")
        method = request.get("method", "GET")
        body = request.get("body") or {}
        with contextlib.redirect_stdout(sys.stderr):
            result = dispatch(path, method, body)
        json.dump({"status": 200, "body": result}, sys.stdout, ensure_ascii=False)
    except (ValueError, KeyError, FileNotFoundError) as error:
        json.dump({"status": 400, "body": {"detail": str(error)}}, sys.stdout)
    except Exception as error:
        json.dump({"status": 500, "body": {"detail": str(error)}}, sys.stdout)


if __name__ == "__main__":
    main()
