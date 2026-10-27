# 🔌 API Endpoint Registry

Source-derived HTTP/native route registry at `85b3db6` (2026-09-30). The table inventories every explicit FastAPI HTTP route decorator without importing or starting the backend. Contract notes below cover selected workflows; it is not a complete OpenAPI schema. Native coverage is implementation evidence, not a claim of packaged or live-Vault verification.

---

## Complete explicit FastAPI route inventory

HTTP routes are registered in [backend/main.py](../backend/main.py). Native dispatch is in [desktopApi.js](../frontend/src/lib/desktopApi.js) and [lib.rs](../frontend/src-tauri/src/lib.rs); handlers are [Vault](../frontend/src-tauri/src/vault.rs), [P3](../frontend/src-tauri/src/p3.rs), [progression](../frontend/src-tauri/src/progression.rs), [Lounge](../frontend/src-tauri/src/lounge.rs), and [P5](../frontend/src-tauri/src/p5.rs). FastAPI's automatic `/docs`, `/redoc`, and `/openapi.json` are HTTP-only framework routes, outside the explicit decorators below.

| Method | HTTP path | FastAPI handler | Native coverage |
| --- | --- | --- | --- |
| GET | `/api/battle/state` | `get_battle_state` | p3_request |
| POST | `/api/battle/link` | `link_battle_task` | p3_request → bundled Python completion service |
| POST | `/api/battle/resolve` | `resolve_battle_task` | p3_request → bundled Python completion service |
| POST | `/api/battle/rest` | `battle_short_rest` | p3_request → bundled Python completion service |
| GET | `/` | `root` | healthcheck command; apiFetch root remains HTTP |
| GET | `/api/events/stream` | `events_stream` | Unavailable: HTTP streaming only |
| GET | `/api/status` | `get_status` | vault_request |
| GET | `/api/settings` | `get_settings` | vault_request |
| GET | `/api/navigation` | `get_navigation` | vault_request |
| GET | `/api/readiness` | `get_readiness` | vault_request |
| GET | `/api/ops` | `get_ops` | vault_request |
| GET | `/api/companions` | `get_companions` | vault_request |
| GET | `/api/antagonists` | `get_antagonists` | vault_request |
| GET | `/api/beasts` | `get_beasts` | vault_request |
| GET | `/api/journal/recent` | `get_recent_journals` | Unavailable: no native handler |
| GET | `/api/journal/month` | `get_journal_month` | vault_request |
| POST | `/api/journal/entry/polish` | `polish_journal_entry` | polish_journal_entry; local Ollama required |
| POST | `/api/journal/entry` | `append_journal_entry` | vault_request |
| POST | `/api/journal/rollover` | `journal_rollover` | start_sync_operation; event jobs, not HTTP polling |
| POST | `/api/sync` | `execute_sync` | start_sync_operation; event jobs, not HTTP polling |
| POST | `/api/squad/deploy` | `deploy_squad_member` | vault_request |
| POST | `/api/squad/bench` | `bench_squad_member` | vault_request |
| POST | `/api/realm/hop` | `execute_realm_hop_endpoint` | vault_request |
| GET | `/api/realm/options` | `get_realm_options` | vault_request |
| GET | `/api/realm/draft` | `get_realm_draft` | vault_request |
| GET | `/api/recurring` | `get_recurring_tasks` | vault_request |
| POST | `/api/recurring` | `create_recurring_task` | vault_request |
| PUT | `/api/recurring/{task_id}` | `update_recurring_task` | vault_request |
| DELETE | `/api/recurring/{task_id}` | `delete_recurring_task` | vault_request |
| GET | `/api/active_tasks` | `get_active_tasks` | vault_request |
| POST | `/api/active_tasks` | `create_active_task` | vault_request |
| PUT | `/api/active_tasks/{task_id}` | `update_active_task` | vault_request |
| DELETE | `/api/active_tasks/{task_id}` | `delete_active_task` | vault_request |
| GET | `/api/navigation/pillars` | `get_navigation_pillars` | vault_request |
| GET | `/api/entities` | `get_entities` | vault_request |
| GET | `/api/entity/{entity_type}/{entity_name}` | `get_entity_profile` | vault_request |
| GET | `/api/vault/{file_path:path}` | `get_vault_file` | vault_request; assets use custom protocol |
| PUT | `/api/vault/{file_path:path}` | `save_vault_file` | vault_request; assets use custom protocol |
| GET | `/api/combat/log` | `get_combat_log` | vault_request |
| POST | `/api/combat/target` | `set_combat_target` | vault_request |
| POST | `/api/squad/vanguard` | `set_vanguard` | vault_request |
| POST | `/api/tasks/toggle` | `toggle_task` | Partial: checkbox only; no native XP sync |
| POST | `/api/bio/adjust` | `adjust_bio` | vault_request |
| POST | `/api/settings/save` | `save_settings` | Unavailable: no native handler |
| GET | `/api/ai/experiments` | `get_ai_experiment_status` | Unavailable: no native handler |
| PUT | `/api/ai/experiments` | `update_ai_experiment_settings` | Unavailable: no native handler |
| POST | `/api/neural/chat` | `neural_chat` | Explicitly unavailable (503) in p5_request |
| GET | `/api/neural/banter` | `get_banter` | Unavailable: no native handler |
| GET | `/api/neural/banter/history` | `get_banter_history` | p5_request; local data/runtime required |
| POST | `/api/neural/banter/generate` | `trigger_banter_generation` | p5_request; local data/runtime required |
| GET | `/api/neural/warroom/history` | `get_warroom_history` | Explicitly unavailable (503) in p5_request |
| POST | `/api/neural/warroom/clear` | `clear_warroom_history` | Explicitly unavailable (503) in p5_request |
| POST | `/api/neural/warroom/chat` | `warroom_chat` | Explicitly unavailable (503) in p5_request |
| POST | `/api/forge/submit` | `forge_submit` | p5_request → bundled Python Forge service |
| POST | `/api/forge/discard` | `forge_discard` | p5_request → bundled Python Forge service |
| POST | `/api/forge/approve` | `forge_approve` | p5_request → bundled Python Forge service |
| POST | `/api/ops/execute` | `execute_ops_script` | Unavailable HTTP path; allowlisted start_p5_operation instead |
| GET | `/api/ops/jobs/{job_id}` | `get_ops_job_status` | Unavailable HTTP path; native operation events instead |
| GET | `/api/v1/progression/xp` | `get_progression_xp` | progression_request |
| POST | `/api/v1/progression/xp` | `log_progression_xp` | progression_request |
| POST | `/api/v1/progression/xp/corrections` | `correct_progression_xp` | progression_request |
| GET | `/api/v1/progression/achievements` | `get_progression_achievements` | progression_request |
| GET | `/api/v1/biometrics/vitals/latest` | `get_latest_biometrics` | p5_request; local data/runtime required |
| GET | `/api/v1/biometrics/vitals/history` | `get_biometrics_history` | p5_request; local data/runtime required |
| GET | `/api/v1/biometrics/exercises/recent` | `get_recent_exercises` | p5_request; local data/runtime required |
| GET | `/api/v1/lounge/media` | `get_lounge_media_endpoint` | lounge_request |
| GET | `/api/v1/lounge/media/{media_id}/poster` | `get_lounge_media_poster` | Unavailable: no native handler |
| GET | `/api/v1/library/dashboard` | `get_library_dashboard` | lounge_request |
| GET | `/api/v1/library/search` | `search_library_endpoint` | lounge_request |
| POST | `/api/reid/chat` | `reid_chat_endpoint` | Explicitly unavailable (503) in p5_request |
| GET | `/api/reid/history` | `reid_history_endpoint` | p5_request; local data/runtime required |
| GET | `/api/missions/all` | `get_all_missions` | p3_request |
| POST | `/api/status/mission` | `set_active_mission` | vault_request |

`GET /api/cache/sector` is native-only in `p3_request`; no explicit FastAPI route exists. Native `GET /api/vault/` returns an empty object, distinct from file reads. Native Lounge poster-by-ID and `GET /api/neural/banter` have no handler. Settings save, squad deploy/bench/vanguard, combat target/log, bio adjustment, recent journal and AI experiment controls are HTTP-only today.

P5 jobs allow only `backup`, `apply_xp`, `daily_rollover`, and `sync_bridge`, mapped to scripts beneath the Vault's `Engine/`; missing scripts fail. They are distinct from bundled native sync/rollover jobs. Local AI needs Ollama/model availability. Native hosted-provider accounting is unavailable. GET biometrics reads cached SQLite data; it does not establish a live device uplink.

Unsupported module routes can reject the IPC promise instead of returning an HTTP-shaped 404. Chat routes listed as explicitly unavailable return 503. Preserve these distinctions when handling errors. NativeResponse exposes `status`, `ok`, `json()` and `text()`; it is not a streaming Fetch Response. API abort after dispatch only stops waiting; use explicit native job cancellation for work already started.


## 🏥 Vitals & System

## 📈 Progression ledger contract (P1)

`xp_logs` remains a legacy append-only table with `date`, `amount`, and `details`; those fields do not identify an entity or make retries safe. Its rows remain unresolved and excluded from canonical totals until P3. The P2 writer contract is backed by the per-entity `xp_ledger`. An award command/event must include `award_id` (stable idempotency key), `entity_id` (`keeper` or `companion:<stable-name>`), signed integer `amount`, `source_type`, `source_ref`, timezone-qualified ISO-8601 `source_event_at`, persisted Navis `local_date`, `rule_version`, and object `provenance`. Manual adjustments also require `reason` and `provenance.actor`. Repeating an `award_id` with identical content is an idempotent no-op; conflicting content is a validation error. Corrections append a linked compensating award; reads return entity-scoped totals, derived level, and ordered history. Journal replay retains the original recipient set, never present-day squad membership.

Fixture contract for P2–P4: same-ID retry; repeated event replay; same-day distinct entries; checked-to-unchecked and edited journal evidence; companion join/leave between event and replay; missing/unavailable Vault; legacy rows with unknown entity; conflicting totals/opening balance; correction/reversal; manual adjustment; local-date boundary. Unknown ownership stays unresolved, and unavailable source data must not become an empty/zero ledger.

P3 historical XP inventory, reviewed mapping manifests, backup/apply/recovery, and rollback are documented in [XP history reconciliation](xp-reconciliation.md). The CLI defaults to a non-mutating dry run and refuses to initialize a missing progression database during inventory.

`GET /api/v1/progression/xp?entity_id=keeper&limit=100` returns an entity-scoped canonical total, level, ordered history, and `legacy_history_unresolved` flag. `entity_id` defaults to `keeper` for the existing Keeper dashboard. `POST /api/v1/progression/xp` accepts the award fields above. Use `POST /api/v1/progression/xp/corrections` for a correction and include `source_type: "correction"` plus `correction_of`. An identical retry succeeds without adding XP; conflicting IDs or invalid attribution return a validation error. Projection failures report that the ledger commit succeeded and a replay is needed to repair the JSON/Markdown projections.

The Keeper interface generates a unique `award_id` for every manual submission, persists the selected local date, and records the entered reason and actor. Legacy `CompanionStats.json.xp` and `.level` fields are preserved until reconciliation; P2 writes the canonical projection into `.ledger_xp` and `.ledger_level`. Existing XP Markdown remains intact outside the replaceable `NAVIS XP LEDGER` block.

### `GET /`
- **Purpose:** Health check to verify API online.
- **Response:** `{"status": "online", "manifold": "Navis Bridge API"}`

### `GET /api/events/stream`
- **Purpose:** Server-Sent Events (SSE) Bus Endpoint (Reactive-P2). Streams formatted SSE messages (`event`, `data`, `id`), periodic keepalive pings (every 15s), and filesystem/vault change notifications.
- **Protocol:** `text/event-stream` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
- **Wire Format:**
  - Event payloads: `id: <monotonic_id>\nevent: <event_name>\ndata: <json_or_text>\n\n`
  - Keepalive ping comments: `: ping\n\n` (broadcast every 15 seconds to prevent idle socket closure).
- **Concurrency & Lifecycle:** Manages multiple concurrent browser connections via internal `asyncio.Queue` channels; safely evicts disconnected subscribers upon socket close to prevent memory leaks.

### `GET /api/status`
- **Purpose:** Loads the active `status.json` manifold.
- **Response:** Complete JSON state structure (current realm, active squad, targeted threats, keeper XP).

### `POST /api/bio/adjust`
- **Purpose:** Atomically applies delta numeric adjustments to tracked values.
- **Request Body:**
  ```json
  {
    "field": "STR",
    "delta": 5,
    "companion_name": "Arwen"
  }
  ```

---

## ✍️ Tasks & Files

### `GET /api/vault/{file_path:path}`
- **Purpose:** Safely reads a markdown file, json, log, or image relative to `NAVIS_ROOT`.
- **Response:** For files, returns `{"content": text, "path": path}`. For images, returns a raw `FileResponse`.

### `POST /api/journal/entry`
- **Purpose:** Appends a checked Markdown list item (`- [x] ...`) to one of the selected day's existing journal sections. Plain text is automatically formatted as a checked item, and an existing unchecked checkbox is marked complete.
- **Request Body:** `{"date":"2026-09-22","section":"sanctum","entry":"Example completed item"}`
- **Sections:** `sanctum`, `domestic`, `front`, `gauntlet`, or `outland`.
- **Response:** `{"status":"success","date":"2026-09-22","path":"Journal/2026/09/2026-09-22.md","content":"...updated Markdown..."}`
- **Validation:** Requires a real `YYYY-MM-DD` date, a non-empty entry of at most 10,000 characters, a supported section, and an existing journal file. It never creates a journal file.
- **Side Effects:** Atomically replaces the existing dated Markdown file while preserving its UTF-8-SIG encoding and line-ending style.

### `POST /api/tasks/toggle`
- **Purpose:** Web uses a line number, then exact/fuzzy text fallback and rewrites the file; native requires a usable line number and atomically replaces the file. This general toggle is distinct from recoverable combat completion.
- **Request Body:**
  ```json
  {
    "file_path": "Journal/2026/05/2026-05-23.md",
    "target_text": "Tactical Ledger Review",
    "is_checked": true,
    "line_number": 42
  }
  ```
- **Side Effects:** Web calls `services.rpg_engine.calculate_and_apply_xp()` after a modification and reports an error if XP fails after saving. Native toggle currently changes the checkbox without invoking XP synchronization.

---

## 🛡️ Squad & Navigation

### `POST /api/squad/deploy` / `POST /api/squad/bench`
- **Purpose:** Adds/removes a companion to the active squad array (subject to the web squad-capacity rules).
- **Request Body:** `{"name": "CompanionName"}`

### `POST /api/squad/vanguard`
- **Purpose:** Designates an active squad member as the Vanguard (leader).
- **Request Body:** `{"name": "CompanionName"}`

### `POST /api/realm/hop`
- **Purpose:** Initiates the Moongate anchor protocol to jump realms.
- **Request Body:** `{"realm_name": "RealmName", "squad_names": ["A", "B", "C"]}`

---

## ⚔️ Combat & AI

### Battle task routes (HTTP and native desktop)

`GET /api/battle/state` includes hydrated cards, `active_links`, and durable
`resolutions`. `POST /api/battle/link` accepts `task_id`, `top_card_id`,
`bottom_card_id`, optional `resolution_id`, and `source` with Vault-relative
`path` (or `file_path`), exact `target_text`, and optional 1-based `line_number`.
The saved response returns the bound source (including its fingerprint) and
resolution UUID. If path is omitted, the current journal date must be available
in `Bridge/status.json`.

`POST /api/battle/resolve` accepts `task_id`, the saved `resolution_id`, optional
saved `source`, and boolean `is_completed` (default true). It returns
`completed`, `already_completed`, `cancelled`, or `pending_recovery`, with
`cards_resolved` and `xp_sync`. A repeated completed request includes
`idempotent_replay: true` and does not repeat XP synchronization. Cancellation
uses a separate stable resolution key and changes cards only. Invalid source
references and key conflicts return 400; failures persisting initial intent
return 500. Later storage/XP failures return 200 with `pending_recovery`,
`retryable: true`, and a message, so clients must inspect the body before
reporting success. FastAPI missing-field schema errors use 422; the native JSON
adapter uses 400 for invalid required fields.

`POST /api/battle/rest` refuses while a recovery operation remains incomplete.
Retry resolve with the same request after repairing the indicated problem.
Missing/moved/edited/ambiguous sources keep cards linked; cancel and relink the
refreshed task rather than selecting a similar line. See
[combat task verification](combat-task-verification.md) for persistence, UI
outcomes, automated evidence, and unperformed release smoke checks.

### `POST /api/combat/target`
- **Purpose:** Sets the current active target coordinate (antagonist or beast), or clears it if `name` is empty.
- **Request Body:** `{"type": "beast", "name": "TargetName"}` (type is `beast` or `antagonist`; name is optional)

### `GET /api/combat/log`
- **Purpose:** Reads the last 50 lines of `Combat_Log.md` for terminal output.

### `POST /api/settings/save`
- **Purpose:** Merges partial settings payloads, supporting nested objects and dot-notation paths (e.g. `ui.appearance_mode`).

### P4 dashboard contract

XP reads supply `level`, `current_level_xp`, `next_level_xp`, `xp_into_level`,
`xp_for_next_level`, and clamped `progress_percent`. The dashboard consumes these
values directly. Signed totals remain visible even below zero. `history.provenance`
is an object in HTTP and IPC responses; ownership, source reference, actor, reason,
and correction links remain available on each record. History stays ordered by
local date, creation time, then award ID descending.

The Keeper dashboard refreshes on mount, status changes, window focus, relevant
successful API writes, and completed sync/rollover jobs. Refresh ledger retries
reads; Commit retries an unconfirmed adjustment using the same award ID while
its inputs remain unchanged. Inputs are disabled during submission. A confirmed
write followed by a failed refresh reports a read error, without resubmitting.
Loading and unavailable reads show no fabricated zero total. Empty history is
explicit, and unresolved legacy history remains visibly flagged.

## 💠 Weekly Holocron Telemetry & Cockpit Endpoints

### `GET /api/holocron/weekly/latest`
- **Purpose:** Compiles or reads the most recent concluded or available 7-day Weekly Holocron.
- **Response:** JSON payload containing `week_id`, `start_date`, `end_date`, `summary` (precision rate, completed/total tasks, XP yield, threats neutralized), `daily_telemetry`, `sector_distribution`, `combat`, `progression`, `squad_mvp`, and `tactical_debrief`.

### `GET /api/holocron/weekly/current`
- **Purpose:** Computes live Week-to-Date (WTD) telemetry for the active in-flight 7-day operating cycle.
- **Response:** JSON payload with `is_in_flight: true`, `cycle_status: "in_flight"`, `days_elapsed`, `days_remaining`, and day statuses (`concluded`, `active`, `upcoming`).

### `GET /api/holocron/weekly/manifest`
- **Purpose:** Lists all concluded weekly cycles from `Bridge/Holocron/weekly_manifest.json` plus the active in-flight cycle.

### `GET /api/holocron/weekly/{week_id}`
- **Purpose:** Revalidates source inputs for a specific ISO week (e.g. `2026-W40`), returning schema 2 metrics, unavailable states and `evidence` rules/references. Existing historical artifacts are refreshed only through explicit regeneration.

### `GET /api/holocron/weekly/{week_id}/evidence/{source_id}`
- **Purpose:** Inspects `journal-YYYY-MM-DD` within the selected week or `keeper-ledger`; arbitrary paths are rejected. Returns source status, fingerprint and bounded checklist counts or signed Keeper XP. Available journal references include a relative navigation path; journal bodies and private absolute paths are excluded. See [evidence contract](holocron-evidence.md).

### `POST /api/holocron/weekly/{week_id}/regenerate`
- **Purpose:** Forces re-aggregation of 7-day journal evidence and Keeper progression data, updating `Bridge/Holocron/Weekly/{week_id}.json` and the manifest.

### `POST /api/holocron/weekly/{week_id}/debrief/ai`
- **Purpose:** Triggers local Ollama AI synthesis of a military-sci-fi/RPG commander debrief. Guarded by `NAVIS_AI_PROVIDER` (strict local privacy, zero cloud egress). Falls back deterministically to rule-based debrief if Ollama is unreachable or times out.
- **Response:** `{ "week_id": str, "tactical_debrief": str, "debrief_source": "ollama" | "rule_based_fallback", "holocron": dict }`.

### `GET /api/holocron/weekly/{week_id}/html`
- **Purpose:** Generates a self-contained HTML dashboard from revalidated inputs, with escaped evidence rules and internal source-status anchors; no private filesystem links.

### Desktop Tauri IPC Bridge: Holocron Contract
- **Invocation:** Dispatched via `invokeNative('vault_request', { path, method, body })`.
- **Handling:** Tauri routes `/api/holocron/*` to `vault::holocron_request`, which executes `backend/native_holocron.py` as an allowlisted UTF-8 JSON subprocess without an HTTP server. GET and HTML requests use shared Python source revalidation; native cache files cannot bypass it.

