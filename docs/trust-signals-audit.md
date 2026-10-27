# Trust signals audit (NAVIS-S009)

Audit date: 2026-10-27. Application source: `279a614182ed48c946ac9724aac484e023472f40`.
**Verdict:** existing persistence/transport safeguards are substantial, but seven
confirmed presentation/orchestration gaps prevent at-a-glance trust. Prioritize
S014 and S013, then S011/S012/S010. No application fixes were made by this audit.
The parent [E002](../issues/NAVIS-E002.md) remains open.

## Journeys and authority boundaries

| Journey | Web path | Desktop path | Authoritative data and projections |
| --- | --- | --- | --- |
| Command dashboard | `app/page.js:92` refreshStatus -> apiFetch -> GET `/api/status` (`main.py:489`) | Same React/adapter -> vault_request -> `vault.rs:320` status | Bridge/status.json plus CompanionStats projection; last_updated is an operational marker, not proof of a successful current read. Readiness bars use commandTelemetry missing-value semantics. |
| Weekly Holocron | WeeklyHolocronView -> manifest/current/week routes -> holocron_engine | Same component -> vault_request -> native_holocron.py for synthesis/current; native artifact routes for reads/export | Dated journal Markdown and Keeper/navis_progression.db -> weekly JSON/HTML and manifest. generated_at is artifact generation time, not input freshness. |
| Journal append | JournalEntryComposer -> POST `/api/journal/entry` -> journal_entry.append | vault_request interception in `lib.rs:134` -> p3::journal_entry_request -> native_journal_entry.py -> same service | Existing dated journal is authoritative; durable request record, atomic persistence and snapshot readback precede XP projection. HTTP 200 can mean saved_xp_pending. |
| Journal checkbox | page.js handleToggleCheckbox -> POST `/api/tasks/toggle` -> canonical toggle/completion services | `lib.rs:148` -> native_task_toggle.py -> same service; direct Rust bypass rejected | Exact source content/path/line identity, journal bytes and canonical completion/XP ledger. Returned authoritative content and pending-XP state are consumed by UI. |
| Active/recurring task boards | useTaskBoard -> taskBoardStore -> list/mutate/refetch routes | Same store/adapter; supported vault/native routes | Canonical directive/recurrence state and completion provenance. Store validates list shape, retains failure state and guards concurrent/stale requests. |
| Sync and rollover | POST async job -> main.py background functions -> sync_engine; poll `/api/ops/jobs/id` | start_sync_operation -> operations.rs supervised Python native_operations.py -> same engine; native progress events | Multiple journal/status/XP/backup effects can commit independently. Process exit/job completed is not sufficient evidence every step succeeded. |

Source paths above are relative to backend/, frontend/src/ or
frontend/src-tauri/src/ as applicable. Specific references follow below.

## Confirmed findings

Priority is impact-based audit triage, not a claim of production data corruption.
Each reproduction uses disposable synthetic inputs or mocked transports.

### T01 (high): derived or fixed Holocron values look measured — S013

`backend/services/holocron_engine.py:471` assigns every encountered Prime Beast
300 XP; `:488` invents seven MVP deployments when no squad data exists; `:514`
sets is_synthetic false; `:527` fixes readiness at 85; `:528` estimates deep work
as completed count * 0.75; `:553` estimates damage. A journal Prime Beast is also
counted as neutralized without a victory record. The UI labels readiness and
hours as actual values (`WeeklyHolocronView.js:321`), and HTML export repeats them
(`holocron_engine.py:791`). No metric-level source navigation explains the rules;
daily dates and a Bestiary button are not links to the contributing journal/awards.

Reproduction: one completed synthetic task and one Prime Beast, no readiness,
squad or combat-award source -> readiness 85%, focus 0.8h, beast XP 300 and MVP
seven deployments, is_synthetic false. Expected: evidence-derived metrics or
explicit estimate/unavailable labels, with supporting rules and source identity.
Do not fix this by adding invented provenance. Coordinate shared presentation
with S006; S006's AI trial is not a prerequisite for correcting factual labels.

### T02 (high): unavailable sources collapse into valid zeros/empty — S011

`holocron_engine.py:118-130` returns the ordinary zero record for missing or
unreadable journals; `:199-200,284` returns zero XP for absent or corrupt ledger
inputs. It may retain partial accumulations after later query failure without a
partial-coverage marker. The caller increments logged_days when a path exists,
even if it could not be read (`:375`). Coverage is not represented per source/day.

Reproduction: force both reads of a synthetic journal to raise PermissionError;
the returned object equals a valid empty journal's object, with no availability
field. Missing and corrupt synthetic SQLite files both yield indistinguishable
zero XP. Separately, `JournalCalendar.js:89-99` does not check response.ok and
clears activeDates on failure: a mocked HTTP error JSON becomes an empty month
with no error state. Expected: preserve valid zero, distinguish missing/unreadable/
partial, and provide explicit recovery. Do not globally replace zero with errors.
Status defaults (`main.py:491-493`, `vault.rs:273`) warrant the same scoped review;
the executable probe establishes the Holocron/calendar cases, not all consumers.

### T03 (medium): late Holocron response changes the wrong week — S010

`WeeklyHolocronView.js:45-78` has no request revision/cancellation guard for week
data. Reproduction mounts the actual component using React test renderer and
the installed SWC transformer: request W40, select W41, resolve W41 then W40.
Selector remains W41 while displayed debrief is W40. Expected: selected identity,
payload identity and source period agree; ignore obsolete responses. This also
applies to late failures hiding the newer result. Regenerate/debrief responses
should be checked for the same identity boundary when implementing repair.

### T04 (medium): dashboard failed refresh silently retains old data — S010

`app/page.js:92-103` logs transport failure and does not expose read/error state;
non-OK responses are ignored. Reproduction executes that production function
with a previous status and rejected fixture transport: previous value remains,
one console error, undefined return. Expected: retained data may remain visible,
but failed refresh and last successful read must be visible separately from
source last_updated. `commandTelemetry.mjs:44` preserves the operational marker;
do not relabel it as a successful fetch timestamp. Holocron generated_at exists
but is not displayed; neither timestamp establishes freshness of underlying inputs.

### T05 (high): late journal save can overwrite a different selection — S012

`app/page.js:580-590` applies append result.content without checking result.path
against the currently selected record/ref. Reproduction executes the actual
callback captured for A after a simulated selection/read of B: A's content and
loaded ID overwrite B's display state. This is callback/state reproduction, not
a full-page or packaged interaction. Expected: acknowledge A's committed save,
but apply content only to A's current view; retain navigation back to its source.
The checkbox loaded-ID/date guards reduce wrong-target mutation risk, so this
does not establish a wrong-file disk write. Preserve service readback, idempotency
and saved_xp_pending handling; do not build a second persistence authority.

### T06 (high): completed sync can contain failed steps — S014

`sync_engine.py:245-290` logs production work/XP/watch failures and continues;
backup failures can also be returned as strings. `main.py:3133-3160` discards the
return and marks the job completed if no exception escapes. Reproduction executes
the production background function with a fake backup logging a Git error: final
job status completed, failure remains only in output. No sync, Git or provider
action is executed. `native_operations.py:78-84` catches some error-string forms
but misses warning-prefixed XP/work failures; those same strings yield zero
classified failures. The native runner can consequently exit successfully and
`operations.rs:440-446` emits completed. Expected: structured per-step committed/
failed/skipped outcomes and truthful overall result, with safe reconciliation.
Fixture-mode exception escalation differs from production, so passing fixture
sync tests alone does not disprove this production-path finding.

### T07 (medium): operation Retry only reconnects status — S014

`AsyncJobModal.js:78-84,125` labels a button Retry, resets status and polls the same
failed job. Current sync/rollover callers provide no onRetry operation restart.
Mounted component reproduction with a terminal failed job: click Retry -> one
additional GET of the same failed job, no restarted operation. Expected: label
status reconnection clearly; restart/reconcile only with established per-step
idempotency. Blindly replaying a multi-write sequence is not an acceptable fix.
Cancelled-state labeling is an additional source-review concern, not separately
runtime-verified here.

## Existing safeguards / scopes to preserve

- `journal_entry.py:148-193`: request identity/conflict checks, durable preparation,
  atomic bytes, snapshot readback, original-byte digest and saved_xp_pending.
  Composer retains draft on failures and offers pending-XP retry. No general
  missing-readback backend defect was established.
- `app/page.js:496-555`: checkbox selected-date/loaded-source alignment, revision
  guards, authoritative result, error-path readback and explicit pending-XP retry.
- `taskBoardStore.mjs`: validates lists, serializes mutations, ignores old list
  replies, reports list/mutation failures and checks uncertain creates before retry.
  Refresh failure is already visible; a new global task-board error system is
  not justified. Post-write refetch does not prove every mutation's desired state;
  further semantic verification is a proposal, not a confirmed defect here.
- Command readiness maps absent values to unavailable and preserves valid zero
  (`commandTelemetry.mjs`). Do not duplicate this implemented distinction.
- Native operations supervise process lifetime/cancellation and sanitize bounded
  diagnostics; AsyncJobModal displays progress and errors. S014 should repair
  outcome/recovery semantics rather than replace this transport infrastructure.
- Holocron explicitly labels rule-based versus Ollama debriefs and has unavailable/
  retry UI for primary payload failures. Manifest failures remain console-only;
  extend existing states instead of adding a parallel framework.

## Web/native verification matrix

| Journey | Audit execution | Native/source coverage | Remaining runtime verification |
| --- | --- | --- | --- |
| Dashboard | Production refresh function with rejected fixture fetch reproduces T04 | Shared adapter tests pass; native status route inspected | Browser visual/keyboard, offline/reconnect and packaged source timestamps unrun. |
| Holocron | Actual React component with deferred responses reproduces T03; temporary Markdown/SQLite reproduces T01/T02 | Existing API/native Python bridge tests included; native routes inspected | Packaged rendering/export/source navigation unrun; two existing manifest tests fail. |
| Journal save | Production callback with stale selection reproduces T05; existing append safety tests pass in selected suite | Shared Python append bridge and Rust dispatch inspected | Full-page navigation during a save and packaged persistence feedback unrun. |
| Checkbox/tasks | Existing fixture toggle/directive tests plus 72 task-board failure/race cases; no new backend defect claimed | 48 complete-adapter tests include native invocation doubles | Packaged web/native saved/error/XP feedback and source navigation unrun. |
| Sync/rollover | Production web function with fake backup reproduces T06; warning classifier and mounted Retry reproduce T06/T07 | Rust process/event mapping inspected; Python fixture tests mostly pass | Native watcher dependency missing; real packaged cancel/close/partial-recovery unrun. |

No running app connected to the personal Vault was launched. No personal data,
hosted generation, schedules or production migrations were used. These fixtures
are not browser, WebView2, installed-resource or clean-machine evidence. S015 must
retain those runtime checks as blockers; E002 is not complete after S009.

## Reproduce and observed checks

Run from the repository root with existing declared dependencies:

```powershell
.tools/mcp-venv/Scripts/python.exe scripts/audits/trust-signals.py
node scripts/audits/trust-signals.cjs
.tools/mcp-venv/Scripts/python.exe -m pytest backend/tests/test_weekly_holocron.py backend/tests/test_native_operations.py backend/tests/test_journal_entry.py backend/tests/test_journal_append_safety.py backend/tests/test_task_toggle_safety.py backend/tests/test_directive_completion.py -q
npm.cmd --prefix frontend run test:unit
npm.cmd --prefix frontend run test:task-boards
npm.cmd --prefix frontend run test:journal-entry
```

The two audit probes reproduced ten expected defect cases (five Python and five
JavaScript); they assert current observed defects, not regression acceptance for
future fixes. They execute real production functions/component code with doubles,
and must be revised or retired when fixes land. Python temporary-directory ACLs
blocked the sandbox probe initially; the same fixture probe succeeded elevated.
An initial probe used a wrong function name, corrected before final execution.

Existing Python suite: **73 passed, 3 failed (39.95 s)**. Two failures assert a
single manifest row although get_holocron_manifest injects the current WTD row
(`test_weekly_holocron.py:130,181`, engine `:926-940`); record as fixture-contract
mismatch, not proof that current-week injection is wrong. The watcher test fails
before READY because watchdog is absent in both inspected Python environments.
No dependency was installed or test expectation changed to obtain a pass.
Frontend: **48 transport tests**, **72 task-board scenarios**, journal-entry source
contract passed. Rust suite, lint/build and packaged smoke were not run in this
audit; no application source changes justify claiming new release acceptance.
External review is unavailable. [Sanitized check/source record](trials/navis-trust-audit-2026-10-27.json).

## Backlog disposition

| Story | Selected audit scope | Order / dependency |
| --- | --- | --- |
| S010 | T03/T04 selected-identity guards and freshness/failed-read signals; retain existing timestamps correctly | After S009; medium. |
| S011 | T02 source/day availability, partial coverage and calendar failure states | After S009; high. |
| S012 | T05 journal-save selection isolation and navigation; preserve canonical persistence/XP safeguards | After S009; high. No rewrite of already verified save services. |
| S013 | T01 factual/estimated/unavailable labels and inspectable evidence/rules in UI/export; share with S006 | After S009; high. |
| S014 | T06/T07 structured partial outcomes and safe reconnect/reconcile semantics | After S009; high; recommended first repair. |
| S015 | Retained web + packaged matrix, manifest test-contract reconciliation and missing watcher dependency validation | After repairs; do not declare runtime coverage from source tests. |

S022's richer task states and S023/S024 timestamps/completed view remain separate
enhancements. S001's brief experiment remains gated on its own sample evaluation.
The MCP epic is done within accepted read-only limits; it is not reopened by this
audit. Roadmap MCP and native-checkbox descriptions are reconciled to delivered
evidence. S009 can close as an audit with documented runtime unknowns; no repair
story acceptance is marked implemented by this report.

## S015 integrated checkpoint - 2026-10-27

Repairs S010-S014 are merged through PR #21 (`17c23ca`). The original matrix
above is the S009 audit baseline, not the current runtime disposition. See the
[integrated trust-journey record](trust-journey-verification.md) for versioned
packaged evidence, new physical browser observations, S015-F01/F02 repairs and
remaining gates. Do not rerun historical defect-assertion probes as acceptance.
S015 and E002 remain in progress.
