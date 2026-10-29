from services.operation_outcomes import committed as operation_committed, failure as operation_failure, note as operation_note, step as operation_step
import os
import re
import json
import subprocess
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from services.recurrence import calculate_next_due
from services.directive_completion import complete_section_item
from services.combat_completion import atomic_bytes

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
SETTINGS_FILE = os.path.join(NAVIS_ROOT, "Bridge", "settings.json")
ENGINE_ROOT = os.path.join(NAVIS_ROOT, "Engine")


def _process_error_text(error):
    """Return subprocess failure output regardless of text/bytes capture mode."""
    output = error.stderr or error.output
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output or str(error)


def _git_identity_args(repo_root):
    """Build commit identity flags without changing global Git configuration."""
    identities = (
        ("user.name", "NAVIS_GIT_USER_NAME", "Navis Protocol"),
        ("user.email", "NAVIS_GIT_USER_EMAIL", "navis-protocol@localhost"),
    )
    args = []
    for config_key, env_key, fallback in identities:
        configured = subprocess.run(
            ["git", "config", "--local", "--get", config_key],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        value = configured.stdout.strip() or os.environ.get(env_key) or fallback
        args.extend(["-c", f"{config_key}={value}"])
    return args


def _biometrics_script_path():
    """Resolve the bundled helper, allowing an explicit local override."""
    configured = os.environ.get("NAVIS_BIOMETRICS_SCRIPT")
    if configured:
        return configured
    backend_root = Path(__file__).resolve().parents[1]
    return str(backend_root / "scripts" / "sync_biometrics.py")


def _run_biometrics_sync(script_path):
    """Run the helper with this engine's Vault root and inherited credential paths."""
    import sys

    child_env = os.environ.copy()
    child_env["NAVIS_ROOT"] = NAVIS_ROOT
    return subprocess.run(
        [sys.executable, script_path],
        check=True,
        capture_output=True,
        text=True,
        env=child_env,
    )


def sync_work_journal(defer_missing_until=None):
    """Natively synchronizes the work journal from Daily_Work.md to the current daily log."""
    if not os.path.exists(SETTINGS_FILE):
        return "Error: settings.json not found."

    with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
        paths = settings.get("paths", {})

    office_log_path = paths.get(
        "office_work_log", r"S:\My Drive\Documents\Journal\Daily_Work.md"
    )
    fixture_mode = os.environ.get("NAVIS_NATIVE_FIXTURE_MODE") == "1"
    if fixture_mode:
        if "office_work_log" not in paths:
            raise ValueError("fixture settings must define paths.office_work_log")
        vault_root = os.path.realpath(NAVIS_ROOT)
        office_root = os.path.realpath(office_log_path)
        if os.path.commonpath([vault_root, office_root]) != vault_root:
            raise ValueError("fixture office work log must be inside NAVIS_ROOT")
    status_path = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
    journal_root = os.path.join(NAVIS_ROOT, "Journal")

    if not os.path.exists(office_log_path):
        if fixture_mode:
            raise FileNotFoundError("fixture office work log is unavailable")
        operation_failure()
        return f"Office log not found at {office_log_path}. Skipping work sync."

    if not os.path.exists(status_path):
        return "Error: status.json not found."

    with open(status_path, "r", encoding="utf-8-sig") as f:
        status = json.load(f)

    target_date = status.get("last_updated")
    if not target_date:
        return "Error: last_updated not set in status."

    with open(office_log_path, "r", encoding="utf-8-sig") as f:
        work_content = f.read().strip()

    if not work_content:
        return "Office log is empty. Nothing to sync."

    # Find all date headers. A date may appear in multiple blocks after an
    # import, so collect duplicate blocks before syncing them.
    dates_found = list(
        re.finditer(r"^## (\d{4}-\d{2}-\d{2})\s*$", work_content, re.MULTILINE)
    )
    if not dates_found:
        operation_failure()
        return "No valid dates found in work log."

    total_items_added = 0
    date_sections = {}
    date_order = []
    for i, match in enumerate(dates_found):
        current_date = match.group(1)
        start_idx = match.end()
        end_idx = (
            dates_found[i + 1].start()
            if i + 1 < len(dates_found)
            else len(work_content)
        )
        if current_date not in date_sections:
            date_sections[current_date] = []
            date_order.append(current_date)
        date_sections[current_date].append(work_content[start_idx:end_idx])

    synced_dates = set()

    for current_date in date_order:
        section_content = "\n".join(date_sections[current_date])
        # Extract items
        new_raw_items = re.findall(r"^- (.*)", section_content, re.MULTILINE)
        if not new_raw_items:
            continue

        # Find the target journal file for this date
        dt = datetime.strptime(current_date, "%Y-%m-%d")
        daily_path = os.path.join(
            journal_root, dt.strftime("%Y"), dt.strftime("%m"), f"{current_date}.md"
        )

        if not os.path.exists(daily_path):
            if (defer_missing_until is not None and target_date < current_date
                    and dt.date() <= defer_missing_until):
                operation_note(f"Work journal for {current_date} retained until rollover creates its journal.")
                continue
            operation_failure()
            print(f"Daily log not found for {current_date} at {daily_path}. Skipping.")
            continue

        with open(daily_path, "r", encoding="utf-8-sig") as f:
            daily_content = f.read()

        # Find the High-Velocity Front section
        section_pattern = r"(## .*? The High-Velocity Front)"
        section_match = re.search(section_pattern, daily_content)
        if not section_match:
            operation_failure()
            print(
                f"Could not find 'The High-Velocity Front' section in daily log for {current_date}."
            )
            continue

        section_header = section_match.group(1)

        # Extract current body of the section
        pattern_body = re.escape(section_header) + r"(.*?)((?=\n## |\n---|\Z))"
        body_match = re.search(pattern_body, daily_content, re.DOTALL)
        if not body_match:
            operation_failure()
            continue

        current_section_body = body_match.group(1)

        # Strip existing lines and clean out legacy mandate header if present
        legacy_mandate_pattern = re.compile(r"- \*\*🧭 Commander's Triage\*\*.*")
        clean_body = legacy_mandate_pattern.sub("", current_section_body).strip()

        existing_lines = [
            line.strip() for line in clean_body.split("\n") if line.strip()
        ]

        items_added = 0
        for item in new_raw_items:
            clean_item = re.sub(r"^\[[ xX]\]\s*", "", item).strip()
            # Simple duplicate check
            is_duplicate = False
            for existing in existing_lines:
                if clean_item[:30] in existing:
                    is_duplicate = True
                    break

            if not is_duplicate:
                ledger_item = f"- [x] 🛡️ {clean_item} 📋"
                existing_lines.append(ledger_item)
                items_added += 1
                total_items_added += 1

        if items_added > 0:
            # Automatic sync and rollover remain local-only.

            # Build updated section content
            final_body = ""
            for line in existing_lines:
                final_body += line + "\n"

            updated_section_text = f"{section_header}\n{final_body.strip()}\n"
            new_daily_content = (
                daily_content[: body_match.start()]
                + updated_section_text
                + daily_content[body_match.end() :]
            )

            # Redundant local backup copy of the active journal entry before edits
            try:
                ts = datetime.now().strftime("%H%M%S")
                backup_path = f"{daily_path}.backup_{ts}"
                import shutil

                shutil.copy2(daily_path, backup_path)
                print(f"✅ BACKUP COPY: {backup_path}")
            except Exception as e:
                operation_failure()
                print(
                    f"⚠️ BACKUP COPY ERROR in sync_work_journal for {current_date}: {e}"
                )

            with open(daily_path, "w", encoding="utf-8-sig") as f:
                f.write(new_daily_content)
            operation_committed()
        synced_dates.add(current_date)

    # Remove only successfully merged date blocks; preserve pending work when
    # a journal is missing or malformed.
    if not synced_dates:
        return "0 work items merged. Any pending entries retained unchanged."
    try:
        remaining_sections = [
            f"## {current_date}\n{''.join(date_sections[current_date]).rstrip()}"
            for current_date in date_order
            if current_date not in synced_dates
        ]
        updated_work = "\n\n".join(remaining_sections).strip()
        if not updated_work:
            updated_work = f"## {target_date}"
        updated_work += "\n"
        with open(office_log_path, "w", encoding="utf-8-sig") as f:
            f.write(updated_work)
    except Exception as e:
        operation_failure()
        print(f"Error purging work log: {e}")

    return f"✅ SYNCED: {total_items_added} work items merged into High-Velocity Front across dates."


def execute_git_backup(log_callback=None):
    """Natively executes a Git commit to backup the Vault state."""
    logs = []

    def _log(msg):
        operation_note(msg)
        logs.append(msg)
        if log_callback:
            log_callback(msg)

    fixture_mode = os.environ.get("NAVIS_NATIVE_FIXTURE_MODE") == "1"

    operation_step("work")
    # 1. Sync work journal
    try:
        if log_callback:
            log_callback("⏳ Syncing Work Journal...")
        from services.operation_outcomes import is_rollover
        sync_res = (sync_work_journal(defer_missing_until=datetime.now().date())
                    if is_rollover() else sync_work_journal())
        _log(sync_res)
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"work journal sync failed: {e}") from e
        _log(f"⚠️ WORK SYNC ERROR: {str(e)}")

    operation_step("xp")
    # 2. Apply XP
    try:
        if log_callback:
            log_callback("⏳ Processing XP Accrual...")
        from services.rpg_engine import calculate_and_apply_xp

        calculate_and_apply_xp()
        _log("📊 XP ACCRUAL: Processed current cycle achievements...")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"XP processing failed: {e}") from e
        _log(f"⚠️ XP ERROR: {e}")

    operation_step("watch")
    # 2.5 Sync Jellyfin watch history into journals
    try:
        if log_callback:
            log_callback("⏳ Syncing Jellyfin Watch History...")
        if fixture_mode:
            _log("🧪 FIXTURE MODE: Jellyfin watch history integration disabled.")
        else:
            from scripts.sync_watch_history import sync_watch_history

            sync_watch_history()
            _log("🎬 WATCH HISTORY: Jellyfin history synced into The Sanctum.")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"watch history sync failed: {e}") from e
        _log(f"⚠️ WATCH HISTORY ERROR: {e}")

    operation_step("backup")
    # 3. Git commit
    if log_callback:
        log_callback("⏳ Anchoring State to Git Void...")
    fixture_git = os.environ.get("NAVIS_FIXTURE_GIT_DIR")
    git_environment = None
    if fixture_mode:
        if not fixture_git:
            raise ValueError("fixture mode requires NAVIS_FIXTURE_GIT_DIR")
        git_environment = os.environ.copy()
        for key in list(git_environment):
            if key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_"):
                git_environment.pop(key, None)
        git_environment.pop("GIT_DIR", None)
        git_environment.pop("GIT_WORK_TREE", None)
        git_environment.update({
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "4",
            "GIT_CONFIG_KEY_0": "user.name",
            "GIT_CONFIG_VALUE_0": "Navis Fixture",
            "GIT_CONFIG_KEY_1": "user.email",
            "GIT_CONFIG_VALUE_1": "fixture@localhost",
            "GIT_CONFIG_KEY_2": "protocol.allow",
            "GIT_CONFIG_VALUE_2": "never",
            "GIT_CONFIG_KEY_3": "fetch.recurseSubmodules",
            "GIT_CONFIG_VALUE_3": "false",
        })
    if not os.path.isdir(os.path.join(NAVIS_ROOT, ".git")) and not fixture_mode:
        _log("❌ ERROR: Git repository not initialized in Vault.")
        return "\n".join(logs)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if fixture_mode:
            subprocess.run(["git", "init", "--bare", fixture_git], check=True, capture_output=True, env=git_environment)
            subprocess.run(
                ["git", "--git-dir", fixture_git, "--work-tree", NAVIS_ROOT, "commit", "--allow-empty", "-m", "fixture baseline"],
                check=True,
                capture_output=True,
                text=True,
                env=git_environment,
            )
        subprocess.run(
            (["git", "--git-dir", fixture_git, "--work-tree", NAVIS_ROOT] if fixture_mode else ["git"])
            + (["add", "--", "Bridge", "Journal", "Companions", ":(exclude)Bridge/.navis_operations"]
               if fixture_mode else ["add", "--all", "--", ".", ":(exclude)Bridge/.navis_operations"]),
            cwd=NAVIS_ROOT,
            check=True,
            capture_output=True,
            **({"env": git_environment} if git_environment else {}),
        )
        status = subprocess.run(
            (["git", "--git-dir", fixture_git, "--work-tree", NAVIS_ROOT] if fixture_mode else ["git"])
            + ["diff", "--cached", "--name-only"],
            cwd=NAVIS_ROOT,
            check=True,
            capture_output=True,
            text=True,
            **({"env": git_environment} if git_environment else {}),
        )

        if not status.stdout.strip():
            _log("🌑 NO CHANGES DETECTED: Tactical state is already synchronized.")
            return "\n".join(logs)

        commit_message = f"feat(backup): automated tactical save {timestamp}"
        result = subprocess.run(
            [
                "git",
                *( ["--git-dir", fixture_git, "--work-tree", NAVIS_ROOT] if fixture_mode else [] ),
                *([] if fixture_mode else _git_identity_args(NAVIS_ROOT)),
                "commit",
                "-m",
                commit_message,
            ],
            cwd=NAVIS_ROOT,
            check=True,
            capture_output=True,
            text=True,
            **({"env": git_environment} if git_environment else {}),
        )
        operation_committed()
        _log(
            f"✅ SAVE COMPLETE: State anchored in the Git Void.\n📜 LOG: {result.stdout.splitlines()[0] if result.stdout else 'Success'}"
        )
    except subprocess.CalledProcessError as e:
        operation_failure()
        _log(f"❌ GIT ERROR: {_process_error_text(e)}")
        if fixture_mode:
            raise RuntimeError(f"Vault backup failed: {_process_error_text(e)}") from e
    except Exception as e:
        operation_failure()
        _log(f"❌ BACKUP FAILED: {str(e)}")
        if fixture_mode:
            raise RuntimeError(f"Vault backup failed: {e}") from e

    return "\n".join(logs)


def run_midnight_rollover(log_callback=None):
    """Natively initializes missing daily journal files since the last rollover and sweeps active tasks."""
    logs = []

    def _log(msg):
        operation_note(msg)
        logs.append(msg)
        if log_callback:
            log_callback(msg)

    fixture_mode = os.environ.get("NAVIS_NATIVE_FIXTURE_MODE") == "1"

    if not os.path.exists(SETTINGS_FILE):
        raise FileNotFoundError(f"settings.json unavailable at {SETTINGS_FILE}")

    with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
        paths = settings.get("paths", {})
    if fixture_mode:
        if not isinstance(paths, dict) or not paths.get("office_work_log"):
            raise ValueError("fixture settings must define paths.office_work_log")
        vault_root = os.path.realpath(NAVIS_ROOT)
        office_root = os.path.realpath(paths["office_work_log"])
        if os.path.commonpath([vault_root, office_root]) != vault_root:
            raise ValueError("fixture office work log must be inside NAVIS_ROOT")
        if not os.environ.get("NAVIS_FIXTURE_GIT_DIR"):
            raise ValueError("fixture mode requires NAVIS_FIXTURE_GIT_DIR")

    journal_root = os.path.join(NAVIS_ROOT, "Journal")
    future_path = os.path.join(NAVIS_ROOT, "Journal", "Future.md")
    template_path = os.path.join(NAVIS_ROOT, "Journal", "daily_template.md")
    status_path = os.path.join(NAVIS_ROOT, "Bridge", "status.json")

    operation_step("sweep")
    # 1. Sweep active tasks natively
    try:
        if log_callback:
            log_callback("⏳ Sweeping active tasks...")
        sweep_res = sync_active_tasks()
        _log(sweep_res)
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"active task sweep failed: {e}") from e
        _log(f"⚠️ SWEEP ERROR: {e}")

    operation_step("journals")
    # 3. Determine missing days from last_updated through today
    status = {}
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8-sig") as f:
            status = json.load(f)

    last_date_str = status.get("last_updated")
    if not last_date_str:
        last_date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        last_dt = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    except ValueError:
        last_dt = datetime.now().date()

    today_dt = datetime.now().date()
    current_dt = last_dt + timedelta(days=1)
    latest_processed = last_dt.strftime("%Y-%m-%d")

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"daily journal template unavailable at {template_path}")

    with open(template_path, "r", encoding="utf-8-sig") as f:
        template_content = f.read()

    squad_lines = [f"    - {m['name']}" for m in status.get("squad", [])]
    squad_block = (
        "\n".join(squad_lines)
        if squad_lines
        else "    - *No active squad members tracked.*"
    )

    ops_state_path = os.path.join(NAVIS_ROOT, "Bridge", "ops_state.json")
    ops_state = {}
    if os.path.exists(ops_state_path):
        with open(ops_state_path, "r", encoding="utf-8-sig") as f:
            ops_state = json.load(f)

    future_content = ""
    if os.path.exists(future_path):
        with open(future_path, "r", encoding="utf-8-sig") as f:
            future_content = f.read()

    mapping = {
        "Sanctum": "Paladin",
        "Domestic": "Father",
        "Front": "Commander",
        "Gauntlet": "Finance",
        "Bureaucratic": "Finance",
        "Realm": "Realm",
        "World": "Realm",
        "Outland": "Realm",
    }

    initialized_any = False
    while current_dt <= today_dt:
        current_date_str = current_dt.strftime("%Y-%m-%d")
        year = current_dt.strftime("%Y")
        month = current_dt.strftime("%m")
        target_dir = os.path.join(journal_root, year, month)
        os.makedirs(target_dir, exist_ok=True)
        current_path = os.path.join(target_dir, f"{current_date_str}.md")

        if os.path.exists(current_path):
            latest_processed = current_date_str
            current_dt += timedelta(days=1)
            continue

        today_tasks = {
            "Wanderer": "",
            "Paladin": "",
            "Sage": "",
            "Commander": "",
            "Father": "",
            "Finance": "",
            "Realm": "",
        }

        try:
            if log_callback:
                log_callback(f"⏳ Initializing {current_date_str}...")
            for task in ops_state.get("tasks", []):
                if task.get("next_due", "") <= current_date_str:
                    key = mapping.get(task.get("area"))
                    if key:
                        today_tasks[key] += f"- [ ] {task['text']}\n"
            if ops_state:
                _log(
                    f"🛰️ OPS ENGINE: Injected due recurring mandates for {current_date_str}"
                )
        except Exception as e:
            operation_failure()
            _log(f"⚠️ OPS INJECT ERROR for {current_date_str}: {e}")

        try:
            if log_callback:
                log_callback(
                    f"⏳ Extracting Future Buffer Tasks for {current_date_str}..."
                )
            if future_content:
                match = re.search(
                    rf"^## {re.escape(current_date_str)}(.*?)(?=\n##|\Z)",
                    future_content,
                    re.DOTALL | re.IGNORECASE | re.MULTILINE,
                )
                if match:
                    extracted = match.group(1).strip()
                    future_content = future_content.replace(match.group(0), "").strip()
                    today_tasks["Commander"] += extracted + "\n"
                    _log(f"✅ Future Buffer: Extracted tasks for {current_date_str}")
        except Exception as e:
            operation_failure()
            _log(f"⚠️ FUTURE BUFFER ERROR for {current_date_str}: {e}")

        new_content = template_content.replace("{{DATE}}", current_date_str)
        new_content = new_content.replace(
            "{{REALM}}", status.get("current_realm", "Unknown")
        )
        new_content = new_content.replace(
            "{{ANTAGONIST}}", status.get("current_antagonist", "None")
        )
        new_content = new_content.replace(
            "{{BEAST}}", status.get("current_beast", "None")
        )
        new_content = new_content.replace("{{SQUAD}}", squad_block)

        for key, tasks in today_tasks.items():
            new_content = new_content.replace(f"{{{{{key.upper()}_TASKS}}}}", tasks)

        try:
            with open(current_path, "w", encoding="utf-8-sig") as f:
                f.write(new_content)
            operation_committed()
            latest_processed = current_date_str
            initialized_any = True
            _log(f"✅ Link Start: {current_date_str}.md initialized and anchored.")
        except Exception as e:
            operation_failure()
            if fixture_mode:
                raise RuntimeError(f"journal write failed for {current_date_str}") from e
            _log(f"⚠️ JOURNAL WRITE ERROR for {current_date_str}: {e}")

        current_dt += timedelta(days=1)

    if future_content != "" and (future_content != template_content if False else True):
        try:
            with open(future_path, "w", encoding="utf-8-sig") as f:
                f.write(future_content)
        except Exception as e:
            operation_failure()
            if fixture_mode:
                raise RuntimeError(f"future buffer write failed at {future_path}") from e
            _log(f"⚠️ FUTURE BUFFER SAVE ERROR: {e}")

    if latest_processed != last_date_str and initialized_any:
        status["last_updated"] = latest_processed
        try:
            with open(status_path, "w", encoding="utf-8-sig") as f:
                json.dump(status, f, indent=4, ensure_ascii=False)
            _log(f"🗓️ ROLLOVER: Advanced last_updated to {latest_processed}.")
        except Exception as e:
            operation_failure()
            if fixture_mode:
                raise RuntimeError(f"status write failed at {status_path}") from e
            _log(f"⚠️ STATUS WRITE ERROR: {e}")

    operation_step("work")
    # 1.5 Sync work journal
    try:
        if log_callback:
            log_callback("⏳ Syncing Work Journal...")
        sync_res = sync_work_journal()
        _log(sync_res)
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"work journal sync failed: {e}") from e
        _log(f"⚠️ WORK SYNC ERROR: {str(e)}")

    operation_step("xp")
    # 2. Apply XP via native imported module
    try:
        if log_callback:
            log_callback("⏳ Processing XP Accrual...")
        from services.rpg_engine import calculate_and_apply_xp

        calculate_and_apply_xp()
        _log("📊 XP ACCRUAL: Processed current cycle achievements...")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"XP processing failed: {e}") from e
        _log(f"⚠️ XP ERROR: {e}")

    operation_step("watch")
    # 2.5 Sync Jellyfin watch history into journals
    try:
        if log_callback:
            log_callback("⏳ Syncing Jellyfin Watch History...")
        if fixture_mode:
            _log("🧪 FIXTURE MODE: Jellyfin watch history integration disabled.")
        else:
            from scripts.sync_watch_history import sync_watch_history

            sync_watch_history()
            _log("🎬 WATCH HISTORY: Jellyfin history synced into The Sanctum.")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"watch history sync failed: {e}") from e
        _log(f"⚠️ WATCH HISTORY ERROR: {e}")

    operation_step("indexes")
    # 7. Update Legacy Indexes natively
    try:
        if log_callback:
            log_callback("⏳ Reindexing Journal entries...")
        reindex_res = reindex_journal()
        _log(reindex_res)

        if log_callback:
            log_callback("⏳ Calculating Tactical Readiness...")
        readiness_res = update_readiness()
        _log(readiness_res)
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"journal indexing/readiness update failed: {e}") from e
        _log(f"⚠️ INDEX/READINESS ERROR: {e}")

    operation_step("banter")
    # 7.5. Generate fresh squad banter for the new day
    try:
        if log_callback:
            log_callback("⏳ Generating fresh squad banter...")
        if fixture_mode:
            _log("🧪 FIXTURE MODE: squad banter integration disabled.")
        else:
            from services.banter_generator import generate_squad_banter

            generate_squad_banter(count=3)
            _log("🗣️ NEURAL RESONANCE: Generated fresh daily banter threads.")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"squad banter generation failed: {e}") from e
        _log(f"⚠️ BANTER GENERATION ERROR: {e}")

    operation_step("biometrics")
    # 8. Sync Biometrics
    try:
        if log_callback:
            log_callback("⏳ Syncing Biometrics...")
        biometrics_script = _biometrics_script_path()
        if fixture_mode:
            _log("🧪 FIXTURE MODE: biometrics integration disabled.")
        elif os.path.exists(biometrics_script):
            _run_biometrics_sync(biometrics_script)
            _log("⚕️ BIOMETRICS: Synced latest Google Health/Fitbit telemetry.")
        else:
            _log("⚠️ BIOMETRICS: sync_biometrics.py not found.")
    except subprocess.CalledProcessError as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError("biometrics integration failed") from e
        _log(f"⚠️ BIOMETRICS ERROR: {e.stderr if e.stderr else e.output}")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError("biometrics integration failed") from e
        _log(f"⚠️ BIOMETRICS ERROR: {e}")

    operation_step("holocron")
    # 8.5. Compile Weekly Holocron if crossing week boundary or previous week missing
    try:
        if log_callback:
            log_callback("⏳ Checking Weekly Holocron synthesis...")
        if fixture_mode:
            _log("🧪 FIXTURE MODE: Holocron synthesis disabled in fixture mode.")
        else:
            from services.holocron_engine import build_weekly_holocron, get_previous_iso_week
            prev_week = get_previous_iso_week()
            holocron_file = os.path.join(NAVIS_ROOT, "Bridge", "Holocron", "Weekly", f"{prev_week}.json")
            if not os.path.exists(holocron_file):
                build_weekly_holocron(NAVIS_ROOT, week_id=prev_week)
                _log(f"💠 HOLOCRON: Synthesized concluded cycle {prev_week}.")
            else:
                _log(f"💠 HOLOCRON: Concluded cycle {prev_week} already anchored.")
    except Exception as e:
        operation_failure()
        if fixture_mode:
            raise RuntimeError(f"holocron synthesis failed: {e}") from e
        _log(f"⚠️ HOLOCRON SYNTHESIS ERROR: {e}")

    return "\n".join(logs)


def check_startup_holocron_catchup(vault_root=None, log_callback=None):
    """
    On application launch, checks if the previous completed ISO week's Holocron exists.
    If missing, automatically backfills the synthesis.
    """
    root = vault_root or NAVIS_ROOT
    if os.environ.get("NAVIS_NATIVE_FIXTURE_MODE") == "1":
        return "Fixture mode: skipping startup Holocron catchup."
        
    try:
        from services.holocron_engine import build_weekly_holocron, get_previous_iso_week
        prev_week = get_previous_iso_week()
        holocron_file = os.path.join(root, "Bridge", "Holocron", "Weekly", f"{prev_week}.json")
        if not os.path.exists(holocron_file):
            if log_callback:
                log_callback(f"Backfilling missing Weekly Holocron for {prev_week}...")
            build_weekly_holocron(root, week_id=prev_week)
            if not os.path.isfile(holocron_file):
                return "Startup Holocron unavailable: no artifact persisted. Restore the Vault source, then retry."
            return f"Synthesized missing Holocron for {prev_week}."
        return f"Holocron for {prev_week} is up to date."
    except Exception as e:
        return f"Startup Holocron check encountered: {e}"


def sync_active_tasks():
    """Natively sweeps completed tasks from Tasks.md and updates recurring task frequencies."""
    if not os.path.exists(SETTINGS_FILE):
        return "Error: settings.json not found."

    with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
        paths = settings.get("paths", {})

    ops_dir = paths.get("operations_dir")
    journal_root = paths.get("journal_root")
    status_path = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
    ops_state_file = os.path.join(NAVIS_ROOT, "Bridge", "ops_state.json")

    if not ops_dir or not journal_root or not os.path.exists(status_path):
        return "Missing paths or status manifold."

    with open(status_path, "r", encoding="utf-8-sig") as f:
        status = json.load(f)
    target_date = status.get("last_updated")
    if not target_date:
        return "last_updated not set in status."

    dt = datetime.strptime(target_date, "%Y-%m-%d")
    daily_log_path = os.path.join(
        journal_root, dt.strftime("%Y"), dt.strftime("%m"), f"{target_date}.md"
    )

    if not os.path.exists(daily_log_path):
        return f"Daily log not found at {daily_log_path}"

    daily_raw = Path(daily_log_path).read_bytes()
    daily_content = daily_raw.decode('utf-8-sig')

    total_synced = 0
    modified_daily = False

    # 1. Sweep one-off tasks from Tasks.md
    if os.path.exists(ops_dir):
        for op_folder in os.listdir(ops_dir):
            op_path = os.path.join(ops_dir, op_folder)
            tasks_path = os.path.join(op_path, "Tasks.md")

            if os.path.isdir(op_path) and os.path.exists(tasks_path):
                try:
                    tasks_raw = Path(tasks_path).read_bytes()
                    tasks_content = tasks_raw.decode('utf-8-sig').splitlines(keepends=True)
                except Exception as e:
                    print(f"Error reading {tasks_path}: {e}")
                    continue

                new_tasks_content = []
                completed_tasks = []

                for line in tasks_content:
                    match = re.match(r"^\s*-\s*\[[xX]\]\s*(.*)", line)
                    if match and "<!-- navis-task:" not in line and "<!-- navis-completion:" not in line:
                        completed_tasks.append(match.group(1).strip())
                    else:
                        new_tasks_content.append(line)

                if completed_tasks:
                    section_pattern = r"^(## [^\r\n]*?" + re.escape(op_folder) + r"[^\r\n]*)\r?$"
                    section_match = re.search(section_pattern, daily_content, re.MULTILINE)

                    if section_match:
                        section_header = section_match.group(1)
                        body_pattern = (
                            re.escape(section_header) + r"(.*?)((?=\n## |\n---|\Z))"
                        )
                        body_match = re.search(body_pattern, daily_content, re.DOTALL)

                        if body_match:
                            updated = daily_content
                            for task in completed_tasks:
                                updated = complete_section_item(updated, section_header, task)
                                total_synced += 1
                            if updated != daily_content:
                                journal = Path(daily_log_path)
                                if journal.read_bytes() != daily_raw:
                                    raise ValueError('Journal changed during task sweep; retry')
                                shutil.copy2(journal, journal.with_name(journal.name + f'.backup_sweep_{uuid.uuid4().hex}'))
                                encoded = (b'\xef\xbb\xbf' if daily_raw.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
                                # Commit evidence before removing source tasks, so a restart can retry safely.
                                atomic_bytes(journal, encoded)
                                daily_raw = encoded
                                daily_content = updated
                                modified_daily = True
                            source = Path(tasks_path)
                            if source.read_bytes() != tasks_raw:
                                raise ValueError('Task source changed during sweep; retry')
                            shutil.copy2(source, source.with_name(source.name + f'.backup_sweep_{uuid.uuid4().hex}'))
                            remaining = ''.join(new_tasks_content)
                            atomic_bytes(source, (b'\xef\xbb\xbf' if tasks_raw.startswith(b'\xef\xbb\xbf') else b'') + remaining.encode('utf-8'))

    # 2. Sync recurring tasks back to ops_state.json
    if os.path.exists(ops_state_file):
        try:
            with open(ops_state_file, "r", encoding="utf-8-sig") as f:
                ops_state = json.load(f)

            modified_state = False
            for task in ops_state.get("tasks", []):
                task_text = task.get("text")
                if not task_text:
                    continue

                escaped_text = re.escape(task_text)
                completion_pattern = rf"^\s*-\s*\[[xX]\]\s*{escaped_text}(?:\s+<!-- navis-task:[^>]+ -->)?(?:\s+<!-- navis-completion:[^>]+ -->)?(?:\s+<!-- navis-directive:[^>]+ -->)?[ \t]*\r?$"

                matched = re.search(completion_pattern, daily_content, re.MULTILINE)
                if matched and '<!-- navis-task:' in matched[0]:
                    # Managed rows belong to an explicit occurrence, never a
                    # same-text mandate guessed by this legacy sweep.
                    import hashlib
                    identity = hashlib.sha256(f"{task.get('id')}:{target_date}".encode()).hexdigest()
                    if f'<!-- navis-directive:{identity} -->' not in matched[0]:
                        matched = None
                if matched:
                    if task.get("last_done") != target_date:
                        next_due = calculate_next_due(task["frequency"], target_date)
                        task["last_done"] = target_date
                        task["next_due"] = next_due
                        modified_state = True

            if modified_state:
                with open(ops_state_file, "w", encoding="utf-8-sig") as f:
                    json.dump(ops_state, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error syncing recurring tasks: {e}")

    if modified_daily:
        return f"🧹 TASK SWEEP: Swept {total_synced} completed tasks to {target_date}."
    return "🧹 TASK SWEEP: No one-off tasks completed."


def reindex_journal():
    """Natively rebuilds the journal entries database index (Chronicle.db)."""
    import sqlite3

    if not os.path.exists(SETTINGS_FILE):
        return "Error: settings.json not found."

    with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
        paths = settings.get("paths", {})
        journal_root = paths.get("journal_root")
        db_path = paths.get("chronicle_db")
        if not db_path:
            db_path = os.path.join(
                paths.get("status_manifold").replace("status.json", "Chronicle.db")
            )

    if not journal_root:
        return "Error: journal_root missing from settings."

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS journal_entries")
    cursor.execute("""
        CREATE TABLE journal_entries (
            date TEXT PRIMARY KEY,
            path TEXT,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            realm TEXT,
            tasks_total INTEGER,
            tasks_done INTEGER
        )
    """)

    count = 0
    for root, dirs, files in os.walk(journal_root):
        for file in files:
            if file.endswith(".md") and re.match(r"\d{4}-\d{2}-\d{2}\.md", file):
                date_str = file.replace(".md", "")
                full_path = os.path.join(root, file)

                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    realm = "Unknown"
                    tasks_total = 0
                    tasks_done = 0

                    with open(full_path, "r", encoding="utf-8-sig") as f:
                        content = f.read()
                        realm_match = re.search(
                            r"🌀 Realm:.*?(?:🗼|\]|:)\s*(.*)", content, re.IGNORECASE
                        )
                        if realm_match:
                            realm = realm_match.group(1).strip()

                        tasks_total = len(re.findall(r"- \[ \]", content)) + len(
                            re.findall(r"\[[xX]\]|✅", content)
                        )
                        tasks_done = len(re.findall(r"\[[xX]\]|✅", content))

                    cursor.execute(
                        """
                        INSERT INTO journal_entries (date, path, year, month, day, realm, tasks_total, tasks_done)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            date_str,
                            full_path,
                            dt.year,
                            dt.month,
                            dt.day,
                            realm,
                            tasks_total,
                            tasks_done,
                        ),
                    )
                    count += 1
                except Exception as e:
                    print(f"Error indexing {file}: {e}")

    conn.commit()
    conn.close()
    return f"🛰️ CHRONICLE INDEXING: {count} entries indexed in the Chronicle."


def update_readiness():
    """Natively recalculates tactical readiness scores based on past completions."""
    import sqlite3

    if not os.path.exists(SETTINGS_FILE):
        return "Error: settings.json not found."

    with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as f:
        settings = json.load(f)
        paths = settings.get("paths", {})
        db_path = paths.get("chronicle_db")
        if not db_path:
            db_path = paths.get("status_manifold").replace(
                "status.json", "Chronicle.db"
            )
        out_path = os.path.join(
            os.path.dirname(paths.get("status_manifold")), "readiness.json"
        )
        thresholds = settings.get("readiness_thresholds", {})

    if not db_path or not os.path.exists(db_path):
        return "Error: Chronicle.db not found for readiness calculation."

    ops_config = {
        "The Sanctum": {"label": "Sanctum Integrity", "regex": r"## .*? The Sanctum"},
        "The Domestic Breach": {
            "label": "Domestic Readiness",
            "regex": r"## .*? The Domestic Breach",
        },
        "The High-Velocity Front": {
            "label": "Frontline Status",
            "regex": r"## .*? The High-Velocity Front",
        },
        "The Bureaucratic Gauntlet": {
            "label": "Gauntlet Flow",
            "regex": r"## .*? The Bureaucratic Gauntlet",
        },
        "The Kinetic Outland": {
            "label": "Outland Mastery",
            "regex": r"## .*? The Kinetic Outland",
        },
    }

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    today_dt = datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT date, path FROM journal_entries WHERE date < ? ORDER BY date DESC",
        (today_str,),
    )
    historical_entries = cursor.fetchall()
    conn.close()

    op_counts = {name: 0 for name in ops_config}
    last_activity_days = {name: None for name in ops_config}

    limit = 10
    standard_limit_entries = historical_entries[:limit]

    for i, (date_str, path) in enumerate(standard_limit_entries):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()

            for op_name in [
                "The Sanctum",
                "The Domestic Breach",
                "The High-Velocity Front",
            ]:
                op_info = ops_config[op_name]
                pattern = op_info["regex"] + r"(.*?)((?=\n## |\n---|\Z))"
                match = re.search(pattern, content, re.DOTALL)

                if match:
                    section_body = match.group(1).strip()
                    has_completion = re.search(
                        r"\[[xX]\]|✅|\[RESOLVED\]", section_body
                    )
                    is_pending_placeholder = (
                        "[PENDING]" in section_body and len(section_body) < 150
                    )

                    if has_completion or (
                        not is_pending_placeholder and len(section_body) > 20
                    ):
                        op_counts[op_name] += 1
        except Exception:
            pass

    for op_name in ["The Bureaucratic Gauntlet", "The Kinetic Outland"]:
        found = False
        for i, (date_str, path) in enumerate(historical_entries):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    content = f.read()

                op_info = ops_config[op_name]
                pattern = op_info["regex"] + r"(.*?)((?=\n## |\n---|\Z))"
                match = re.search(pattern, content, re.DOTALL)

                if match:
                    section_body = match.group(1).strip()
                    has_completion = re.search(
                        r"\[[xX]\]|✅|\[RESOLVED\]", section_body
                    )
                    is_pending_placeholder = (
                        "[PENDING]" in section_body and len(section_body) < 150
                    )

                    if has_completion or (
                        not is_pending_placeholder and len(section_body) > 20
                    ):
                        entry_dt = datetime.strptime(date_str, "%Y-%m-%d")
                        days_diff = (today_dt.date() - entry_dt.date()).days
                        last_activity_days[op_name] = max(0, days_diff - 1)
                        found = True
                        break
            except Exception:
                pass

        if not found:
            last_activity_days[op_name] = limit

    results = {}

    def get_color(val):
        if val < 30:
            return "#e74c3c"
        if val < 70:
            return "#f1c40f"
        return "#00d4ff"

    for op_name, op_info in ops_config.items():
        if op_name in ["The Bureaucratic Gauntlet", "The Kinetic Outland"]:
            penalty = last_activity_days[op_name] * 5
            percentage = max(0, 100 - penalty)
        else:
            target = thresholds.get(op_name, len(standard_limit_entries))
            percentage = (
                min(100, int((op_counts[op_name] / target) * 100)) if target > 0 else 0
            )

        results[op_name] = {
            "label": op_info["label"],
            "value": percentage,
            "color": get_color(percentage),
        }

    if out_path:
        with open(out_path, "w", encoding="utf-8-sig") as f:
            json.dump(
                {"readiness": results, "last_calculated": datetime.now().isoformat()},
                f,
                indent=4,
            )
        return "📊 READINESS ENGINE: Calculated tactical readiness levels."
    return "Error updating readiness.json"


def sync_status_to_today_journal():
    import os
    import json
    import re
    from datetime import datetime

    NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
    status_path = os.path.join(NAVIS_ROOT, "Bridge", "status.json")
    if not os.path.exists(status_path):
        return
    with open(status_path, "r", encoding="utf-8-sig") as f:
        status = json.load(f)

    today = datetime.now()
    year = today.strftime("%Y")
    month = today.strftime("%m")
    day_str = today.strftime("%Y-%m-%d")

    journal_path = os.path.join(NAVIS_ROOT, "Journal", year, month, f"{day_str}.md")
    if not os.path.exists(journal_path):
        return

    # Full backup before any journal edits so in-flight content is preserved in git
    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=NAVIS_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=NAVIS_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        if status_proc.stdout.strip():
            commit_message = f"feat(backup): automated tactical save before journal sync {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=NAVIS_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            print(
                "✅ BACKUP: committed journal state before sync_status_to_today_journal edits."
            )
    except Exception as e:
        print(f"⚠️ BACKUP ERROR in sync_status_to_today_journal: {e}")

    # Redundant local backup copy of the active journal entry before edits
    try:
        ts = datetime.now().strftime("%H%M%S")
        backup_path = f"{journal_path}.backup_{ts}"
        import shutil

        shutil.copy2(journal_path, backup_path)
        print(f"✅ BACKUP COPY: {backup_path}")
    except Exception as e:
        print(f"⚠️ BACKUP COPY ERROR in sync_status_to_today_journal: {e}")

    with open(journal_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # Reconstruct the header block
    squad_block = ""
    squad = status.get("squad", [])
    if squad:
        for m in squad:
            squad_block += f"    - {m.get('name')}\n"
    else:
        squad_block = "    - None\n"

    squad_block = squad_block.rstrip("\n")

    realm = status.get("current_realm", "Unknown")
    antagonist = status.get("current_antagonist", "None")
    if not antagonist:
        antagonist = "None"
    beast = status.get("current_beast", "None")
    if not beast:
        beast = "None"

    new_header = (
        f"# {day_str}\n\n"
        f"- **🌀 Realm:** {realm}\n"
        f"- **🛡️ Active Squad**\n"
        f"{squad_block}\n"
        f"- **👹 Antagonist:** {antagonist}\n"
        f"- **👾 Prime Beast:** {beast}\n\n"
        f"---"
    )

    # Use positive lookahead for the first section header instead of '---'
    # to prevent a missing '---' from deleting the entire file contents.
    match = re.match(rf"(# {day_str}\n\n).*?(?=\n## )", content, flags=re.DOTALL)
    if not match:
        return

    new_content = content[: match.start()] + new_header + content[match.end() :]

    if new_content != content:
        new_body = new_content[match.end() + len(new_header) - len(match.group(0)) :]
        old_body = content[match.end() :]
        if new_body == old_body:
            with open(journal_path, "w", encoding="utf-8-sig") as f:
                f.write(new_content)
        else:
            print(
                f"⚠️ sync_status_to_today_journal: body content mismatch for {journal_path}, "
                "skipping write to preserve user content."
            )
