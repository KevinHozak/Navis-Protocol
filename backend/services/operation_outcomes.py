"""Durable, conservative sync outcomes; never replay an uncertain write sequence."""
import contextlib
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading

from services.combat_completion import atomic_json

_current = ContextVar("navis_operation", default=None)
_locks = {}
_guard = threading.Lock()
LABELS = {
    "work": "Work journal", "xp": "XP reconciliation", "watch": "Watch history",
    "backup": "Vault backup", "sweep": "Task sweep", "journals": "Daily journals",
    "indexes": "Journal index and readiness", "banter": "Squad banter",
    "biometrics": "Biometrics", "holocron": "Weekly Holocron", "cache": "View cache",
}


class OperationBusy(ValueError):
    pass


def _directory(root, create=False):
    base = Path(root).resolve(strict=True)
    if not (base / "Bridge").is_dir() or not (base / "Journal").is_dir():
        raise ValueError("Vault is unavailable")
    directory = base / "Bridge" / ".navis_operations"
    for path in (base / "Bridge", directory):
        if path.is_symlink() or (path.exists() and path.resolve() != path):
            raise ValueError("Operation state path is unsafe")
    if create:
        directory.mkdir(exist_ok=True)
    return directory


def _identifier(value):
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value)
            or value.casefold() == "latest"):
        raise ValueError("Invalid operation identity")
    return value


@contextlib.contextmanager
def operation_lock(root):
    directory = _directory(root, True)
    if (directory / ".lock").is_symlink():
        raise ValueError("Operation lock path is unsafe")
    with _guard:
        lock = _locks.setdefault(str(directory), threading.Lock())
    if not lock.acquire(blocking=False):
        raise OperationBusy("An operation is already running")
    try:
        with open(directory / ".lock", "a+b") as stream:
            try:
                if os.fstat(stream.fileno()).st_size == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise OperationBusy("An operation is already running") from error
            try:
                yield directory
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)
    finally:
        lock.release()


def _read(path):
    if path.is_symlink():
        raise ValueError("Operation state path is unsafe")
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Operation state is invalid")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_operation(root, job_id):
    path = _directory(root) / f"{_identifier(job_id)}.json"
    if not path.is_file():
        raise FileNotFoundError("Operation record not found")
    result = _read(path)
    if result["status"] == "running":
        try:
            with operation_lock(root):
                result = _read(path)  # Recheck after acquiring the writer lock.
                if result["status"] == "running":
                    result["status"] = "interrupted"
                    result["recovery"] = "review_saved_changes"
                    for step in result["steps"]:
                        if step["status"] == "running":
                            step["status"] = "unknown"
        except OperationBusy:
            pass
    return result


def read_latest(root):
    latest = _read(_directory(root) / "latest.json")
    return read_operation(root, _identifier(latest["job_id"]))


def acknowledge(root, job_id):
    """Operator-only review acknowledgement. Does not resume or repeat any step."""
    with operation_lock(root):
        path = _directory(root) / f"{_identifier(job_id)}.json"
        value = _read(path)
        if value["status"] == "running":
            value["status"] = "interrupted"
            value["recovery"] = "review_saved_changes"
            for current in value["steps"]:
                if current["status"] == "running":
                    current["status"] = "unknown"
        value["reviewed"] = True
        atomic_json(path, value)
    return value


def step(name):
    current = _current.get()
    if current:
        current.start(name)


def failure():
    current = _current.get()
    if current and current.active is not None:
        current.value["steps"][current.active]["status"] = "failed"
        current.save()


def committed():
    current = _current.get()
    if current and current.active is not None:
        current.value["steps"][current.active]["persistence"] = "confirmed"
        current.save()


def note(message):
    """Conservative adapter for legacy helpers which return errors as strings."""
    current = _current.get()
    if not current:
        return
    text = str(message)
    if any("❌" in line or "⚠" in line or re.match(r"\s*(error:|missing |unable |failed |failure:|last_updated not set|daily log not found)", line, re.I)
           for line in text.splitlines()):
        failure()
    elif "FIXTURE MODE:" in text and current.active is not None:
        current.value["steps"][current.active]["status"] = "skipped"
        current.value["steps"][current.active]["persistence"] = "not_attempted"
        current.save()


class _Report:
    def __init__(self, directory, operation, job_id, publish):
        self.path = directory / f"{job_id}.json"
        self.publish = publish
        self.active = None
        names = ["work", "xp", "watch", "backup"]
        if operation == "rollover":
            names += ["sweep", "work", "xp", "watch", "journals", "indexes", "banter", "biometrics", "holocron"]
        names += ["cache"]
        self.value = {"job_id": job_id, "operation": operation, "status": "running",
                      "steps": [{"id": name, "label": LABELS[name], "status": "not_run",
                                 "persistence": "not_attempted"} for name in names],
                      "changes_may_have_committed": False,
                      "recovery": "wait", "reviewed": False}

    def save(self):
        self.value["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(self.path, self.value)
        if self.publish:
            self.publish(json.loads(json.dumps(self.value)))

    def finish_step(self):
        if self.active is not None and self.value["steps"][self.active]["status"] == "running":
            self.value["steps"][self.active]["status"] = "completed"

    def start(self, name):
        self.finish_step()
        self.active = next(i for i, value in enumerate(self.value["steps"])
                           if (self.active is None or i > self.active) and value["id"] == name)
        self.value["steps"][self.active].update(status="running", persistence="may_have_committed")
        self.value["changes_may_have_committed"] = True
        self.save()  # Persist intent before the next potentially mutating call.


def run_operation(root, operation, job_id, log=None, publish=None):
    """Serialize web/native jobs and return a persisted report, never auto-retry."""
    if operation not in {"sync", "rollover"}:
        raise ValueError("Unsupported operation")
    job_id = _identifier(job_id)
    with operation_lock(root) as directory:
        path = directory / f"{job_id}.json"
        if path.exists():
            value = _read(path)
            if value["operation"] != operation:
                raise ValueError("Operation identity conflict")
            if value["status"] == "running":
                value["status"] = "interrupted"
                value["recovery"] = "review_saved_changes"
                for current in value["steps"]:
                    if current["status"] == "running":
                        current["status"] = "unknown"
            return value  # A lost response is not permission to repeat mutations.
        latest = directory / "latest.json"
        if latest.exists():
            previous = _read(directory / f"{_identifier(_read(latest)['job_id'])}.json")
            if previous["status"] != "completed" and not previous.get("reviewed"):
                raise OperationBusy("Review the previous operation's saved changes before starting another")
        report = _Report(directory, operation, job_id, publish)
        report.save()
        atomic_json(latest, {"job_id": job_id})
        token = _current.set(report)
        try:
            from services import sync_engine
            from services.sync_engine import execute_git_backup, run_midnight_rollover
            if Path(sync_engine.NAVIS_ROOT).resolve() != Path(root).resolve():
                raise ValueError("Operation runtime root mismatch")
            execute_git_backup(log_callback=log)
            # Do not start the rollover after a partial/failed backup sequence.
            if operation == "rollover" and not any(s["status"] == "failed" for s in report.value["steps"]):
                run_midnight_rollover(log_callback=log)
            if not any(s["status"] == "failed" for s in report.value["steps"]):
                step("cache")
                cache = Path(root) / "Bridge/.navis_cache/sector_cache.json"
                cache.unlink(missing_ok=True)
            report.finish_step()
            failed = any(s["status"] == "failed" for s in report.value["steps"])
            report.value["status"] = "partial" if failed else "completed"
        except Exception:
            failure()
            report.value["status"] = "partial" if report.value["changes_may_have_committed"] else "failed"
        finally:
            _current.reset(token)
        report.value["recovery"] = "review_saved_changes" if report.value["status"] != "completed" else "none"
        report.save()
        return report.value
