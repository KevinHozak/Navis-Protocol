"""Standalone desktop entrypoint for operations that normally run in FastAPI."""

import os
import sys
import json
import re
from pathlib import Path


MAX_FAILURE_BYTES = 4096


# Native desktop runs inherit the Windows console code page, which may be
# cp1252. Progress messages intentionally contain emoji, so keep the pipe
# consumed by Tauri UTF-8 encoded regardless of the host console.
for stream in (sys.stdout, sys.stderr):
    if stream.encoding and stream.encoding.lower() != "utf-8":
        try:
            stream.reconfigure(encoding="utf-8", line_buffering=True)
        except (AttributeError, OSError):
            pass
    else:
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, OSError):
            pass


def emit(message):
    print(message, flush=True)


def resolve_vault_root():
    root = Path(os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault"))
    if not root.is_dir():
        raise FileNotFoundError("NAVIS_ROOT is unavailable; connect the Vault and retry.")
    if not (root / "Bridge").is_dir() or not (root / "Journal").is_dir():
        raise ValueError("NAVIS_ROOT must contain Bridge and Journal directories.")
    if os.environ.get("NAVIS_NATIVE_FIXTURE_MODE") == "1":
        settings_path = root / "Bridge" / "settings.json"
        if not settings_path.is_file():
            raise FileNotFoundError("Fixture Bridge/settings.json is required.")
        with settings_path.open("r", encoding="utf-8-sig") as stream:
            settings = json.load(stream)
        paths = settings.get("paths", {})
        office_log = paths.get("office_work_log") if isinstance(paths, dict) else None
        if not office_log:
            raise ValueError("Fixture settings must define paths.office_work_log.")
        vault_root = os.path.realpath(root)
        office_root = os.path.realpath(office_log)
        if os.path.commonpath([vault_root, office_root]) != vault_root:
            raise ValueError("Fixture office work log must be inside NAVIS_ROOT.")
        fixture_git = os.environ.get("NAVIS_FIXTURE_GIT_DIR")
        if not fixture_git:
            raise ValueError("Fixture mode requires an isolated NAVIS_FIXTURE_GIT_DIR path.")
    return root


def _error_summary(error):
    message = " ".join(str(error).split())
    for key in ("NAVIS_ROOT", "NAVIS_FIXTURE_GIT_DIR"):
        configured = os.environ.get(key)
        if configured:
            message = message.replace(configured, "[REDACTED]")
    message = re.sub(
        r"(?i)\b(?:NAVIS_ROOT|NAVIS_FIXTURE_GIT_DIR|[A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|SECRET))\b\s*[:=]\s*\S+",
        "[REDACTED]",
        message,
    )
    encoded = message.encode("utf-8", errors="replace")[:MAX_FAILURE_BYTES]
    while True:
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError:
            encoded = encoded[:-1]


def _failed_result_lines(result):
    failure_prefixes = ("error:", "missing ", "unable ", "failed ", "failure:")
    return [
        line
        for line in result.splitlines()
        if "❌" in line or "⚠" in line or line.strip().lower().startswith(failure_prefixes)
    ]


def main(operation):
    if operation not in {"sync", "rollover", "watch"}:
        raise ValueError(f"unsupported native operation: {operation}")

    vault_root = resolve_vault_root()
    os.environ["NAVIS_ROOT"] = str(vault_root)
    if os.environ.get("NAVIS_NATIVE_FIXTURE_MODE") == "1":
        os.makedirs(os.environ["NAVIS_FIXTURE_GIT_DIR"], exist_ok=True)
        from services import rpg_engine, sync_engine

        rpg_engine.NAVIS_ROOT = str(vault_root)
        sync_engine.NAVIS_ROOT = str(vault_root)
        sync_engine.SETTINGS_FILE = os.path.join(str(vault_root), "Bridge", "settings.json")
        sync_engine.ENGINE_ROOT = os.path.join(str(vault_root), "Engine")
        if "scripts.sync_watch_history" in sys.modules:
            watch_history = sys.modules["scripts.sync_watch_history"]
            watch_history.NAVIS_ROOT = str(vault_root)
            watch_history.JOURNAL_ROOT = os.path.join(str(vault_root), "Journal")
            watch_history.JELLYFIN_DB = os.path.join(str(vault_root), "Bridge", "fixture-jellyfin.sqlite")

    if operation == "watch":
        import asyncio
        from services.watcher_service import VaultWatcherService, VaultChangeEvent

        emit("Starting Native Vault Watcher...")

        async def _run_native_watcher():
            watcher = VaultWatcherService(root_path=vault_root)

            def _on_event(event: VaultChangeEvent):
                emit(f"EVENT:{json.dumps(event.model_dump())}")

            watcher.add_listener(_on_event)
            await watcher.start()
            emit("WATCHER:READY")
            try:
                while True:
                    await asyncio.sleep(1.0)
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                await watcher.stop()

        try:
            asyncio.run(_run_native_watcher())
        except (KeyboardInterrupt, SystemExit):
            pass
        emit("Native vault watcher stopped.")
        return 0

    from services.operation_outcomes import run_operation
    import uuid

    job_id = os.environ.get("NAVIS_OPERATION_ID") or "native-" + uuid.uuid4().hex
    result = run_operation(vault_root, operation, job_id, log=emit)
    emit("Operation completed." if result["status"] == "completed" else
         "Operation incomplete. Review saved changes before starting another operation.")
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    if len(sys.argv) in (3, 4) and sys.argv[1] == "review":
        from services.operation_outcomes import acknowledge, read_operation
        if len(sys.argv) == 4 and sys.argv[3] != "--acknowledge":
            raise SystemExit("usage: native_operations.py review JOB_ID [--acknowledge]")
        try:
            action = acknowledge if len(sys.argv) == 4 else read_operation
            print(json.dumps(action(resolve_vault_root(), sys.argv[2])))
        except Exception:
            raise SystemExit("Operation review unavailable; no steps were repeated") from None
        raise SystemExit(0)
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_operations.py [sync|rollover|watch]")
    try:
        raise SystemExit(main(sys.argv[1]))
    except Exception as error:
        emit(f"Native {sys.argv[1]} failed: {_error_summary(error)}")
        raise SystemExit(1)
