# Combat task completion: P3 verification

Issue #87 verifies the completion implementation delivered by #86. All automated
tests use synthetic temporary Vaults. No personal journals or release data are
committed or edited by this suite.

## Workflow and recovery

`POST /api/battle/link` binds exactly one Markdown checklist line to two cards.
The server saves a source fingerprint and a resolution UUID. The client reuses
that saved UUID and source on `POST /api/battle/resolve`. The shared
`services/combat_completion.py` service owns HTTP and local desktop writes.
Tauri's `p3::combat_request` starts the allowlisted `native_combat.py` JSON
stdin/stdout adapter, without starting or contacting FastAPI.

The journal checkbox remains completion evidence. A pre-edit backup and
same-directory atomic replacement preserve its BOM, newline style, and all bytes
outside the checkbox. Battle intent is persisted before changing the task;
checkpoints are `prepared`, `task_written`, `battle_committed`,
`xp_sync_pending`, and `complete`. Each retry reloads durable state. Journal
failure leaves the task unchecked and cards linked. A failure after the task
write returns `pending_recovery`; cards may already be committed, so the response
explicitly includes `cards_resolved`. Retry with the same request to finish.
Rest and a competing outcome are blocked while recovery remains pending.

XP synchronization uses the existing RPG daily producer and canonical source
ledger, rather than a separate combat award. A synthetic first daily completion
produces 12 XP (10 daily base plus 2 for the checked task); a second task that
day contributes only the additional 2. Retrying after an award committed but
before the combat outcome was saved does not award again. The ledger preserves
the original award cohort if squad membership changes before replay.

## Invalid references and visible outcomes

| Outcome | Persistence and UI behavior |
| --- | --- |
| `completed` | Task checked, cards committed, RPG sync confirmed; refresh task/status views. |
| Same-request replay | Recorded result with `idempotent_replay: true`, `xp_sync: not_repeated`; no second transition. |
| `already_completed` | No XP sync or card transition; UI asks the user to cancel the link to release cards. |
| `cancelled` (`is_completed: false`) | Cards transition without touching the checkbox or XP. Use a separate stable cancellation key. |
| `pending_recovery` | UI shows the message and persisted **Retry completion** action, including after reload when the link is already gone. |
| Missing, moved, edited, ambiguous, unsafe or legacy source | HTTP/native validation error (400); cards retained, no guessing or fuzzy match. Cancel the link and relink a refreshed source. |
| Resolution key conflict | 400; do not reuse a key for a different task, source or outcome. |
| Intent write failure | 500 before the journal mutation; retry the original saved request after repairing storage. |
| Missing required HTTP fields | FastAPI schema validation (422); native JSON adapter validation uses 400. |
| Missing Python runtime | Native command error; repair runtime and retry the saved operation. |

## Automated evidence

- `backend/tests/test_combat_completion.py`: service, native JSON adapter, and
  HTTP TestClient workflows; BOM/LF/CRLF preservation and backups, matching
  committed response fixtures, repeated requests, cancellation, invalid sources,
  intent/journal/battle/XP failures and protected card state.
- `backend/tests/test_combat_workflow.py`: actual HTTP POST/GET routes read back
  journal, battle and ledger state; recovery in a fresh process after each
  battle checkpoint; XP interruptions before/after an award; preserved original
  cohort; four concurrent native processes resolving one request; exact single
  card transition and single award assertions.
- `frontend/src-tauri/src/p3.rs`:
  `shared_combat_bridge_completes_and_recovers_without_http` runs the Rust
  subprocess bridge and native battle read route with synthetic success,
  missing, already-completed and durable partial-write cases. Each request starts
  a fresh process; there is no HTTP client/server in this workflow.
- `docs/fixtures/combat_task_completion.json` supplies response expectations.

Verified on 2026-09-30:

```text
python -m pytest backend/tests/test_combat_completion.py backend/tests/test_combat_workflow.py backend/tests/test_progression_ledger.py -q -p no:cacheprovider
99 passed (two existing FastAPI startup deprecation warnings)

cargo test --manifest-path frontend/src-tauri/Cargo.toml p3::tests -- --test-threads=1
3 passed; 39 unrelated unit tests filtered out
```

The native test used `NAVIS_PYTHON=C:\Python314\python.exe`, the existing Cargo
target cache and frontend export. It exercises development source resources,
not an installed release bundle. TestClient does not run application lifespan
jobs. Native fixtures do not stop any personal running service.

`cargo fmt --check` reports pre-existing formatting differences in `p5.rs` and
`vault.rs`, neither changed here. The `npm run lint` executable shim is missing
from the local dependency installation. Direct
`node node_modules/next/dist/bin/next lint` also cannot start because `@next/env`
is missing. No frontend source changed in this issue; lint remains unverified.
The generated `.husky/_/husky.sh` is also absent, so the commit hook cannot
start; delivery uses a per-command hook override after the checks above.
Backend lint is unverified because the available test interpreter has no `ruff`.

One intermediate suite run returned `pending_recovery` during a synthetic
cancellation storage write (98 passed, 1 failed). The complete rerun passed all
99 checks. No production logic was changed to hide that storage outcome.

## Release-runtime smoke tests not performed

Packaged Tauri installer launch with FastAPI explicitly stopped, visual clicking
of Execute/Retry/Cancel, packaged Python dependency/resource discovery, actual
application restart, and real Google Drive interruption remain manual release
checks. Automated Rust command/process restarts are separate evidence and do not
claim those release checks passed.
