"""Recoverable combat writes shared by HTTP and the local desktop bridge."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

TASK = re.compile(rb"^(\s*[-*+]\s+\[)([ xX])(\]\s+.*?)(\r?\n)?$")


def atomic_bytes(path, content):
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path, value):
    atomic_bytes(Path(path), b"\xef\xbb\xbf" + json.dumps(value, ensure_ascii=False, indent=2).encode())


@contextlib.contextmanager
def battle_lock(root):
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Vault root unavailable")
    directory = base / "Battle"
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".completion.lock", "a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def safe_source(root, relative):
    relative = str(relative).replace("\\", "/")
    if not relative or relative.startswith("/") or ":" in relative or any(p in ("", ".", "..") for p in relative.split("/")):
        raise ValueError("Source must be a relative Vault path")
    base = Path(root).resolve(strict=True)
    path = (base / relative).resolve(strict=True)
    if not path.is_relative_to(base) or not path.is_file() or path.suffix.lower() != ".md":
        raise ValueError("Source must be a Markdown file inside the Vault")
    return path


def normalized(line):
    # Ignore completion state when checking identity and surrounding task context.
    return re.sub(rb"^(\s*[-*+]\s+\[)[ xX](\])", rb"\1 \2", line)


def fingerprint(lines, index):
    context = b"".join(normalized(line) for line in lines[max(0, index - 1):index + 2])
    return "sha256:" + hashlib.sha256(context).hexdigest()


def read_source(root, source):
    path = safe_source(root, source["path"])
    raw = path.read_bytes()
    content = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    content.decode("utf-8")  # Fail closed on unsupported encoding.
    lines = content.splitlines(keepends=True)
    index = source["line_number"] - 1
    if not 0 <= index < len(lines) or fingerprint(lines, index) != source["fingerprint"]:
        raise ValueError("Task source changed or moved; relink the task")
    match = TASK.fullmatch(lines[index])
    if not match or normalized(lines[index]) != source["line"].encode():
        raise ValueError("Task source mismatch")
    if sum(normalized(line) == normalized(lines[index]) for line in lines) != 1:
        raise ValueError("Task source is ambiguous")
    return path, raw, lines, index, match


def bind_source(root, task_id, source):
    if not isinstance(source, dict) or not source.get("target_text"):
        raise ValueError("Task source and target_text are required; relink legacy cards")
    relative = source.get("path") or source.get("file_path")
    if not relative:
        status = json.loads((Path(root) / "Bridge/status.json").read_text(encoding="utf-8-sig"))
        date = status.get("last_updated", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("Journal date unavailable")
        relative = f"Journal/{date[:4]}/{date[5:7]}/{date}.md"
    path = safe_source(root, relative)
    raw = path.read_bytes()
    content = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    lines = content.splitlines(keepends=True)
    target = source["target_text"].strip()
    matches = []
    for index, line in enumerate(lines):
        match = TASK.fullmatch(line)
        if match and match[3][1:].decode("utf-8").strip() == target:
            matches.append(index)
    if len(matches) != 1:
        raise ValueError("Task source missing or ambiguous")
    index = matches[0]
    if source.get("line_number") and source["line_number"] != index + 1:
        raise ValueError("Task source line changed")
    bound = {"path": str(path.relative_to(Path(root).resolve())).replace("\\", "/"), "task_id": task_id,
             "line_number": index + 1, "line": normalized(lines[index]).decode(), "fingerprint": fingerprint(lines, index)}
    read_source(root, bound)
    return bound


def complete_checkbox(root, source):
    path, raw, lines, index, match = read_source(root, source)
    if match[2].lower() == b"x":
        return False
    offset = (3 if raw.startswith(b"\xef\xbb\xbf") else 0) + sum(len(line) for line in lines[:index]) + match.start(2)
    updated = raw[:offset] + b"x" + raw[offset + 1:]
    shutil.copy2(path, path.with_name(path.name + f".backup_combat_{uuid.uuid4().hex}"))
    if path.read_bytes() != raw:
        raise ValueError("Task source changed during completion")
    atomic_bytes(path, updated)
    if path.read_bytes() != updated:
        raise OSError("Task completion verification failed")
    return True


def resolve(engine, task_id, resolution_id, is_completed=True, source=None):
    if not resolution_id:
        raise ValueError("resolution_id is required")
    root = Path(engine.battle_dir).parent
    operations = engine.state.setdefault("resolutions", {})
    operation = operations.get(resolution_id)
    link = engine.state["active_links"].get(task_id)
    if operation:
        if operation["task_id"] != task_id or operation["is_completed"] != is_completed or (source is not None and source != operation["source"]):
            raise ValueError("Resolution key conflicts with its recorded request")
        if operation["phase"] == "complete":
            return {**operation["result"], "idempotent_replay": True, "xp_sync": "not_repeated"}
    else:
        if not link:
            raise ValueError("Task is not linked to any cards")
        if is_completed and link.get("resolution_id") != resolution_id:
            raise ValueError("Use the resolution_id saved with this link")
        if any(op.get("task_id") == task_id and op.get("phase") != "complete" for op in operations.values()):
            raise ValueError("Retry the pending resolution before starting another outcome")
        bound = link.get("source")
        if is_completed:
            if not bound:
                raise ValueError("Legacy link has no source; relink before completing")
            if source is not None and source != bound:
                raise ValueError("Source does not match linked task")
            _, _, _, _, match = read_source(root, bound)
            if match[2].lower() == b"x":
                result = {"status": "already_completed", "cards_resolved": False, "xp_sync": "not_repeated", "task_id": task_id, "resolution_id": resolution_id}
                operations[resolution_id] = {"task_id": task_id, "is_completed": True, "source": bound, "phase": "complete", "result": result}
                engine.save_state()
                return result
        tactical = None
        if is_completed and engine.state.get("encounter") is not None:
            from services.combat_service import evaluate_round, hydrate_encounter
            if any(op.get("phase") != "complete" for op in operations.values()):
                raise ValueError("Finish pending combat recovery before another round")
            before = hydrate_encounter(root, engine.state["encounter"])
            before.setdefault("history_id", uuid.uuid4().hex)
            tactical = evaluate_round(before,
                [engine.cards_db[link[slot]] for slot in ("top", "bottom")])
        operation = {"task_id": task_id, "is_completed": is_completed, "source": bound,
                     "link": link.copy(), "phase": "prepared"}
        if tactical is not None:
            operation["combat_before"] = before
            operation["tactical"] = tactical
            from services.rpg_engine import combat_bonus_event, combat_talent_bonus_events
            operation["combat_bonus"] = combat_bonus_event(resolution_id, bound, tactical)
            operation["talent_bonuses"] = combat_talent_bonus_events(resolution_id, bound, tactical, root=root)
        operations[resolution_id] = operation
        engine.save_state()  # Intent must be durable before the first task mutation.
    try:
        if operation["phase"] == "prepared":
            if is_completed:
                complete_checkbox(root, operation["source"])
            operation["phase"] = "task_written"
            engine.save_state()
        if operation["phase"] == "task_written":
            if is_completed:
                _, _, _, _, match = read_source(root, operation["source"])
                if match[2].lower() != b"x":
                    raise ValueError("Completed task was changed during recovery")
            # Reject changed link/card state instead of consuming another maneuver.
            if engine.state["active_links"].get(task_id) != operation["link"]:
                raise ValueError("Battle link changed during recovery")
            engine.transitionCards(task_id) if hasattr(engine, "transitionCards") else engine.transition_cards(task_id)
            if operation.get("tactical"):
                engine.state["encounter"] = operation["tactical"]["encounter"]
                engine.state["last_round"] = operation["tactical"]
            operation["phase"] = "battle_committed"
            engine.save_state()
        if is_completed:
            operation["phase"] = "xp_sync_pending"
            engine.save_state()
            if operation.get("tactical") and operation.get("combat_before"):
                from services.bestiary import record_round
                record_round(root, resolution_id, operation["combat_before"], operation["tactical"])
            from services.rpg_engine import calculate_and_apply_xp
            path = operation["source"]["path"]
            date = Path(path).stem if path.startswith("Journal/") else None
            calculate_and_apply_xp(date_override=date, root=root)
            if operation.get("combat_bonus"):
                from services.rpg_engine import apply_combat_bonus
                apply_combat_bonus(operation["combat_bonus"])
            if operation.get("talent_bonuses"):
                from services.rpg_engine import apply_combat_bonus
                for bonus_event in operation["talent_bonuses"]:
                    apply_combat_bonus(bonus_event)
        result = {"status": "completed" if is_completed else "cancelled", "task_id": task_id,
                  "resolution_id": resolution_id, "cards_resolved": True,
                  "xp_sync": "confirmed" if is_completed else "not_started"}
        if operation.get("tactical"):
            result["tactical"] = operation["tactical"]
        operation["phase"] = "complete"
        operation["result"] = result
        engine.save_state()
        return result
    except Exception as error:
        # Reload durable phase: an in-memory transition may have failed to persist.
        engine.load_state()
        durable = engine.state.get("resolutions", {}).get(resolution_id, {})
        committed = durable.get("phase") in ("battle_committed", "xp_sync_pending", "complete")
        return {"status": "pending_recovery", "task_id": task_id, "resolution_id": resolution_id,
                "cards_resolved": committed, "retryable": True, "message": str(error),
                "xp_sync": "pending_existing_rpg_sync" if committed else "not_started"}


def dispatch(path, body):
    from services.battle_engine import BattleEngine, NAVIS_ROOT
    if path == "/api/battle/bestiary":
        from services.bestiary import build_bestiary
        return build_bestiary(NAVIS_ROOT)
    with battle_lock(NAVIS_ROOT):
        engine = BattleEngine()
        if path == "/api/battle/state":
            return engine.get_full_state()
        if path == "/api/battle/link":
            ok, message = engine.link_task(body["task_id"], body["top_card_id"], body["bottom_card_id"], body.get("source"), body.get("resolution_id"))
            if not ok:
                raise ValueError(message)
            link = engine.state["active_links"][body["task_id"]]
            return {"status": "success", "message": message, "source": link["source"], "resolution_id": link["resolution_id"]}
        if path == "/api/battle/resolve":
            completed = body.get("is_completed", True)
            if not isinstance(completed, bool):
                raise ValueError("is_completed must be boolean")
            return resolve(engine, body["task_id"], body.get("resolution_id"), completed, body.get("source"))
        if path == "/api/battle/rest":
            ok, message = engine.short_rest()
            if not ok:
                raise ValueError(message)
            return {"status": "success", "message": message}
        raise ValueError("Unsupported combat mutation")
