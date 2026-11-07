# Quarterly Holocron preview — proposed contract

Planning record for [NAVIS-S029](../issues/NAVIS-S029.md), drafted 2026-11-07.
**Not implemented or runtime-verified.** This document defines the proposed JSON
contract and future synthetic verification; none of the cases below has been
executed for this feature. Existing weekly results do not certify this command.

## Invocation and boundaries

Proposed interface (command/file name remains a proposal):

```text
python -B backend/quarterly_holocron_preview.py --root <explicit-synthetic-root> --quarter 2026-Q1
```

Both arguments are required. Do not fall back to `NAVIS_ROOT`, the working
directory or the personal Vault. Accept exactly four-digit Gregorian years
0001–9999 and `Q1`–`Q4`, with the form `YYYY-QN`; reject malformed values before
opening any root. Resolve the supplied root and reject unsafe symlink/junction
traversal. An inaccessible/non-directory root is a command error; do not create it.

The command reads only selected dated journals and the canonical Keeper ledger.
It does not call the weekly builder, regenerate snapshots, scan weekly caches,
initialize progression services or discover broader Vault context. Shared pure
parsing/path rules may be reused after their side effects are checked. Importing
a module is not proof that its execution is read-only.

Emit one UTF-8 JSON document to stdout, without progress text or BOM. Successful
previews, including partial/unavailable evidence, exit 0. Argument/root failures
exit 2 with the error envelope below. Diagnostics must not reveal root paths,
journal text, SQL, task titles, credentials or raw exceptions. No output file is
created; shell redirection is outside this command's contract.

## Calendar-quarter semantics

| Quarter | Inclusive start | Inclusive end | Days |
| --- | --- | --- | --- |
| Q1 | January 1 | March 31 | 90, or 91 in a leap year |
| Q2 | April 1 | June 30 | 91 |
| Q3 | July 1 | September 30 | 92 |
| Q4 | October 1 | December 31 | 92 |

Dates are calendar dates already assigned to journal filenames and canonical
ledger `local_date` values. Do not reassign them using UTC timestamps, the weekly
03:00 cutoff or the execution host timezone. This is not an elapsed-time report.
Future and unfinished quarters are accepted as selected ranges; absent dates
remain missing, with no extrapolation or projected completion. Do not label a
quarter complete merely because the command succeeded.

## JSON schema 1

Top-level fields are `schema_version`, `ok`, `preview`, `error`. On success,
`ok` is true, `error` is null, and `preview` has the fields defined below. Schema 1
does not allow undeclared fields or generated prose. Arrays are deterministically
sorted by date, with journal references before the ledger. No wall-clock timestamp
is required: identical settled inputs produce identical JSON values.

| Field within `preview` | Type and meaning |
| --- | --- |
| `quarter` | Validated `YYYY-QN` string. |
| `period` | `{start_date, end_date, calendar_days, date_basis}`; ISO dates, integer day count, `date_basis: "recorded_local_date"`. |
| `coverage` | `{readable_days, missing_days, unreadable_days, status}`; nonnegative integer counts summing to `calendar_days`. Status is `complete` if all are readable, `partial` if some are readable, otherwise `unavailable`. |
| `checklist` | `{status, completed_entries, pending_entries, total_entries, completion_percent, reason}`. Counts are observed nonnegative integers; total equals completed plus pending. Status follows coverage when at least one entry was observed; otherwise `unavailable` with null percentage and `reason: "no_observed_entries"`. With entries, reason is null and percentage is `round(100 * completed / total, 1)`. |
| `keeper_xp` | `{status, signed_total, matched_rows, reason}`. Status is `available` or `unavailable`. Available total is a signed integer, matched rows a nonnegative integer, reason null. Unavailable total and row count are null with a reason code. Journal coverage never determines ledger availability. |
| `sources` | Bounded array of source records described below; no journal bodies or absolute paths. |
| `rules` | Exact identifiers: `["calendar-quarter-v1", "observed-checklist-entries-v1", "signed-keeper-local-date-v1", "coverage-not-inferred-v1"]`. These identify aggregation rules, not a generated interpretation. |

An observed count of zero means zero entries found in readable inputs, not proof
of no activity on missing/unreadable days. Even a 100% observed completion rate
retains `partial` status if coverage is partial. A readable journal without any
checklist entries contributes to readable-day coverage, not an artificial task.

### Source records and unavailable evidence

Each journal candidate record contains `id: "journal-YYYY-MM-DD"`, `kind:
"journal"`, `date`, `path`, `status`, and `reason`. `path` is a normalized
root-relative path for a discovered, safe candidate, or null if unsafe. Status
is `readable` or `unreadable`; reason is null when readable. Missing days are
represented by coverage counts rather than invented source paths. At most one
journal reference is emitted per date, plus one ledger reference (maximum 93).

Resolve journals in this order, matching the weekly path convention:
`Journal/YYYY/MM/YYYY-MM-DD.md`, then `Journal/YYYY-MM-DD.md`. Choose the first
existing candidate; count each date once. If that candidate is unreadable or
unsafe, do not silently substitute a different copy. If both are absent, the day
is missing. UTF-8 with optional BOM and LF/CRLF are supported. Preserve the
existing weekly checkbox rule: trimmed lines beginning `- [x]` are completed;
`- [ ]` are pending. Do not deduplicate entries by task text or infer lifecycle
events, unique tasks, focus hours or wins. Other checkbox forms do not contribute.

Unreadable-day reason codes: `read_error`, `invalid_encoding`, `oversized_source`,
`unsafe_path`, `changed_during_read`. A journal over 2 MiB is unreadable rather
than partially counted. Reject source symlinks/junctions without following them.
If a read changes while being observed, exclude its counts and mark that day
unreadable; do not silently combine bytes from different reads. Coverage and
counts must come from the same accepted read for each source.

Always include ledger source `id: "keeper-ledger"`, `kind: "ledger"`, `path:
"Keeper/navis_progression.db"`, `status`, `reason`, and `date: null`. For an unsafe
path, emit null path instead. Status/reason match `keeper_xp`.

Use only canonical rows where `lower(entity_id) = 'keeper'` and the strict valid
ISO `local_date` is within the inclusive quarter. Sum the signed integer `amount`
once per stored ledger row, including negative corrections. Do not infer dates
from event timestamps, read another entity's XP or sum weekly summaries. A usable
ledger with no qualifying rows is available with total 0 and matched_rows 0;
rows +20 and -20 give available total 0 with matched_rows 2.

Ledger reason codes: `missing_ledger`, `read_error`, `invalid_ledger`,
`unsupported_schema`, `unsafe_path`, `unsafe_database_state`,
`changed_during_read`. Missing required canonical columns, legacy unscoped
schemas or invalid Keeper date/amount values make the result unavailable rather
than silently dropping questionable Keeper rows. Other optional tables such as
achievements are not required. No schema migration, ledger initialization,
integrity repair, checkpoint or sidecar creation is permitted. If a stable,
read-only SQLite snapshot cannot be opened without writes, return unavailable.
Do not force `immutable` mode on an active database to conceal uncheckpointed WAL
data. Unsafe or changing WAL/database states are unavailable, not an invented zero.

### Complete illustrative JSON

Synthetic Q1 2026: one readable journal with one completed and one pending entry,
89 missing journals, and two signed Keeper rows (+20 and -5). This is an example,
not output from an implemented command.

```json
{
  "schema_version": 1,
  "ok": true,
  "preview": {
    "quarter": "2026-Q1",
    "period": {"start_date": "2026-01-01", "end_date": "2026-03-31", "calendar_days": 90, "date_basis": "recorded_local_date"},
    "coverage": {"readable_days": 1, "missing_days": 89, "unreadable_days": 0, "status": "partial"},
    "checklist": {"status": "partial", "completed_entries": 1, "pending_entries": 1, "total_entries": 2, "completion_percent": 50.0, "reason": null},
    "keeper_xp": {"status": "available", "signed_total": 15, "matched_rows": 2, "reason": null},
    "sources": [
      {"id": "journal-2026-01-01", "kind": "journal", "date": "2026-01-01", "path": "Journal/2026/01/2026-01-01.md", "status": "readable", "reason": null},
      {"id": "keeper-ledger", "kind": "ledger", "date": null, "path": "Keeper/navis_progression.db", "status": "available", "reason": null}
    ],
    "rules": ["calendar-quarter-v1", "observed-checklist-entries-v1", "signed-keeper-local-date-v1", "coverage-not-inferred-v1"]
  },
  "error": null
}
```

Unavailable XP example: `{"status":"unavailable","signed_total":null,
"matched_rows":null,"reason":"missing_ledger"}`. This never becomes zero to make
a chart convenient. Missing journals do not prevent independently available XP.

Error envelope: `{"schema_version":1,"ok":false,"preview":null,
"error":{"code":"invalid_quarter","message":"Quarter must be YYYY-Q1 through YYYY-Q4."}}`.
Other command error codes are `root_required`, `invalid_root`, `root_unavailable`,
`unsafe_root`, `invalid_arguments`, and `internal_error`; messages are fixed safe
descriptions. Internal errors exit 1, not 2, without raw exception text. An explicit
safe root containing no Journal or Keeper subtree is still a successful preview
with unavailable evidence, not a reason to initialize those subtrees.

## Synthetic verification matrix — proposed, not executed

All fixtures are generated under a disposable test-owned directory; no personal
Vault, production database, provider credentials, network or application startup.
Every case includes the zero-write checks in the next section.

| Case | Fixture/input | Required observation |
| --- | --- | --- |
| C01: quarter boundaries | First/last day and immediately adjacent days for every quarter | Only inclusive quarter dates contribute; Q4 does not require computing year 10000 for valid 9999-Q4. |
| C02: leap rules | 2024-Q1, 2026-Q1, 2000-Q1, 2100-Q1 | Day counts 91, 90, 91, 90; February 29 included only where valid. |
| C03: invalid input | Missing root/quarter, `2026-Q0`, `2026-Q5`, `26-Q1`, `0000-Q1`, extra suffix, path-like quarter | Safe error, exit 2, no root discovery or source opens; environment/default personal root never consulted. |
| C04: operational versus calendar dates | Boundary rows with event timestamps in adjacent UTC days, unchanged local_date; different execution timezones | Inclusion follows recorded local dates and output is identical across host timezones. |
| C05: partial coverage | 90-day Q1: one readable, one unreadable, 88 absent | Counts 1/88/1; observed entry percentage retained as partial; no inferred activity for other days. |
| C06: no observed entries | Readable empty journal and missing dates; then no journals at all | Zero observed counts, null completion percentage, no_observed_entries; coverage remains independently accurate. |
| C07: entry counting | Duplicate task text on separate days; lowercase checked, unchecked, uppercase/custom forms; BOM/LF/CRLF | Each supported observed entry counted once; other forms excluded; equivalent encodings yield equal counts. |
| C08: signed XP | Keeper +20/-5; other entity +999; adjacent-date +500 | Signed total 15, matched_rows 2; out-of-scope values excluded. |
| C09: known zero | Empty compatible ledger; then +20/-20 Keeper rows | Both available total 0, row counts 0 and 2; independent of journal availability. |
| C10: unavailable ledger | Missing, corrupt, unreadable, legacy unscoped or missing-column database; invalid Keeper date/amount | Null total/row count with exact reason; no partial sum, new database, repairs or schema writes. |
| C11: irrelevant optional tables | Compatible XP table without achievements; contradictory weekly caches | Canonical XP still available; no optional-table dependency and no cache reads. |
| C12: bounded/path-safe reads | Oversized/invalid UTF-8 journal, traversal symlink/junction, outside-root canary | Unreadable with reason, no body leakage, no outside-root source reads. Unsupported link-fixture setup is recorded as skipped, not passed. |
| C13: duplicate layouts | Both supported journal paths present, with conflicting counts | Preferred nested path used once; an unreadable preferred candidate is not masked by the flat copy. |
| C14: unavailable root | Nonexistent, inaccessible, file instead of directory, linked unsafe root | Safe root error; no directory creation or fallback. |
| C15: concurrent/unsafe database | Changing journal/ledger, locked DB, WAL state that requires sidecar writes | Changed/unavailable evidence reported; no retry writes, checkpoint or forced-immutable stale result. |
| C16: output privacy | Canary task text, root paths and exception text embedded in fixture inputs | Exact schema and valid JSON; no bodies, titles, absolute paths, credentials or raw exceptions on stdout/stderr. Relative references only. |
| C17: repeatability and future range | Same settled inputs read twice; entirely absent future quarter | Identical JSON values; future dates missing, no extrapolation or automatic generation. |
| C18: zero-write enforcement | Writable fixture plus read-only fixture; forbidden write/network/process APIs instrumented | Same facts when readable; no attempted forbidden effects and unchanged inventories. A denied write is a test failure, not proof of a read-only design. |

## Zero-write proof obligations

1. Finish fixture setup and close all seeding connections before measurement.
   Record every file and directory, byte length and SHA-256, plus modification
   times where stable. Include SQLite main DB, any supplied WAL/SHM sidecars and
   pre-existing Holocron caches. Hash/snapshot the dedicated sandbox working,
   home, temp and cache directories as well as the synthetic root.
2. Run with an explicit synthetic root, isolated environment and no keys/config.
   Disable Python bytecode writes (`-B`/`PYTHONDONTWRITEBYTECODE`); do not import
   FastAPI app startup, sync, rollover, provider initialization or schema setup.
   Opening SQLite read-only is necessary but does not alone establish zero writes.
3. Instrument the command and imported helpers to fail on attempted filesystem
   mutation, write-capable database opens/SQL, process launches and network calls.
   Only the requested root's safe dated inputs may be read. Test-owned canaries
   stand in for forbidden external roots; never probe the personal Vault itself.
   The runner must not write log/temp files; stdout is captured by the separate
   test harness outside the measured command. Instrumentation must not accidentally
   block legitimate read-only SQLite opens and label the resulting null XP a pass.
4. After success and failure cases, compare complete inventories: no added,
   changed, removed or renamed files/directories, caches, lock files, SQLite
   journals or sidecars. Creation-then-deletion must also be caught by mutation
   instrumentation; final hashes alone are insufficient. Read-access timestamps
   may be updated by the OS and are excluded from the content-write assertion.
5. Repeat with filesystem write permissions denied where supported. Require zero
   forbidden-operation attempts as well as correct output. Report unsupported
   permission/link instrumentation as a verification limit; never certify an
   unexercised platform case. Persist only the test harness's evidence outside
   the measured directories, including command, source fingerprint, return code,
   parsed JSON, guard results and before/after inventories.

No snapshot hash here is a live production guarantee. Cross-file atomic quarter
snapshots are not supplied by this story; per-source consistency checks must not
be described as a transaction spanning the whole quarter.

## Exclusions and selection state

No implementation, UI integration, annual/comparative analytics, AI narrative,
inferred readiness/focus/combat outcomes, export files, caching, scheduling,
background work, task creation, journal edits, XP migration, sync/rollover,
personal-Vault qualification, production-data migration, credentials or provider
calls. The issue remains open with all acceptance criteria unchecked. A later
implementation request is required; this draft authorizes no runtime action.
