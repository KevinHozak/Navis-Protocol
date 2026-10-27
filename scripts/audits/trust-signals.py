"""Read production functions against disposable synthetic inputs only."""
import ast
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory(prefix="navis-trust-audit-") as tmp:
    os.environ["NAVIS_ROOT"] = tmp
    import sys
    sys.path.insert(0, "backend")
    import native_operations as native
    from services import holocron_engine as h
    root = Path(tmp)
    (root / "Journal/2026/10").mkdir(parents=True)
    note = root / "Journal/2026/10/2026-10-05.md"
    note.write_text("## The Sanctum\n- [x] Synthetic completed task\nPrime Beast: Fixture Beast\n", encoding="utf-8")
    payload = h.build_weekly_holocron(week_id="2026-W41", vault_root=tmp, force=True)
    print(json.dumps({"case":"derived_metrics", "readiness":payload["summary"]["avg_readiness"], "deep_work_hours":payload["summary"]["deep_work_hours"], "combat_xp":payload["combat"]["beasts_neutralized"][0]["xp_awarded"], "mvp_deployments":payload["squad_mvp"]["deployments"], "is_synthetic":payload["is_synthetic"]}))
    empty = root / "empty.md"
    empty.write_text("", encoding="utf-8")
    readable = h.parse_daily_journal(str(empty), "2026-10-05")
    with patch("builtins.open", side_effect=PermissionError("synthetic unreadable")):
        unreadable = h.parse_daily_journal(str(note), "2026-10-05")
    print(json.dumps({"case":"unreadable_equals_empty", "same_result":readable==unreadable, "availability_field_present":any(k in unreadable for k in ["error","status","available"])}))
    (root / "Keeper").mkdir()
    missing_db = h.query_progression_telemetry(tmp, "2026-10-05", "2026-10-11")
    (root / "Keeper/navis_progression.db").write_bytes(b"not a database")
    corrupt_db = h.query_progression_telemetry(tmp, "2026-10-05", "2026-10-11")
    print(json.dumps({"case":"missing_corrupt_ledger", "both_zero":missing_db["total_xp"]==corrupt_db["total_xp"]==0, "same_result":missing_db==corrupt_db}))
    warnings = "⚠️ XP ERROR: synthetic failure\n⚠️ WORK SYNC ERROR: synthetic failure\n✅ SAVE COMPLETE: fixture"
    print(json.dumps({"case":"native_warning_classifier", "failure_count":len(native._failed_result_lines(warnings))}))
    tree = ast.parse(Path("backend/main.py").read_text(encoding="utf-8-sig"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=="run_sync_sequence_in_background")
    jobs={"fixture":{"status":"running","output":""}}
    namespace={"active_jobs":jobs,"NAVIS_ROOT":tmp,"os":os}
    # Only the reviewed local production function is compiled, never Vault input.
    exec(compile(ast.Module(body=[fn],type_ignores=[]),"backend/main.py","exec"),namespace)  # noqa: S102
    with patch("services.sync_engine.execute_git_backup", side_effect=lambda log_callback: log_callback("❌ GIT ERROR: synthetic failure")):
        namespace[fn.name]("fixture",{},[])
    print(json.dumps({"case":"web_sync_failed_step", "job_status":jobs["fixture"]["status"], "failure_retained_in_log":"GIT ERROR" in jobs["fixture"]["output"]}))
