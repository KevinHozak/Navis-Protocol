---
depends_on: ["NAVIS-S022","NAVIS-S023"]
id: "NAVIS-S024"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "in_review"
title: "Add a read-only Completed today view grouped by operation area"
type: "enhancement"
---
## Outcome

Provide a read-only Completed today view grouped by operation area, with navigation to original journal evidence.

## Context and target areas

Parent: [NAVIS-E004](NAVIS-E004.md). Depends on [NAVIS-S022](NAVIS-S022.md) and [NAVIS-S023](NAVIS-S023.md) for shared completion semantics and timestamps. Targets: task/journal read models, Daily Journal/task UI, canonical directive provenance and web/Tauri routes. Existing checked journal entries include logged activities; define their presentation explicitly.

## Acceptance criteria

- [x] Define today using the configured Navis timezone with America/Chicago fallback. Include actual completion occurrences for that day, including tasks originating in older journals.
- [x] Group by original operation area; show task text, available completion time and a working source link that opens the original journal entry.
- [x] Define coverage for ad hoc journal tasks, active directives and recurring occurrences; deduplicate multiple representations of one completion using stable provenance without merging distinct same-text tasks.
- [x] Show unknown-time legacy checked items separately as journal-day evidence; do not assert they were completed today. Label or exclude activity logs explicitly rather than silently counting them as completed tasks.
- [x] Exclude cancelled/deferred/pending items; reflect reopen/recomplete and successful mutations after refresh without creating duplicate rows.
- [x] Reading/filtering the view never moves, copies, rewrites or reorders journal entries, changes headings, strips checkboxes, awards XP or advances recurrence.
- [x] Distinguish empty, loading, unavailable and partial results; do not silently omit unreadable sources.
- [x] Verify source navigation, grouping, deduplication, midnight/DST, legacy records, refresh and byte-for-byte read-only behavior on synthetic Vault fixtures in web and Tauri.

## Implementation and verification checkpoint - 2026-10-27

Read model and UI implemented; see [contract](../docs/completed-today.md) and
[sanitized evidence](../docs/trials/s024-completed-today.json). The final affected
Python suite passed 247 tests; the full frontend regression suite and 77 serial
native tests passed. The native suite initially failed because the default
backend environment lacked the newly declared tzdata dependency; installing
tzdata==2026.5 resolved it. Earlier interrupted/sandbox runs are not passing runs.

Actual web fixtures displayed four timestamped completions across Domestic,
Front and Outland, two distinct same-text tasks, separate unknown-time activity
evidence and an explicit unreadable-source partial warning. Area filtering and
navigation opened the original older journal with its attached note intact.
All 11 fixture Vault files were byte-identical after these reads. One task was
intentionally reopened via the existing journal picker and saved as Pending;
the subsequent Completed today refresh could not be observed because browser
control timed out. All 14 files remained unchanged after that intentional edit.

Release 1.11.28 and installer built with matching file/product versions; all 42
packaged backend resources match source. Packaged UI acceptance remains pending:
Windows window discovery timed out, including its documented reset/recovery.
Do not mark ready until fresh packaged source/filter/refresh/read-only checks
and the remaining physical web refresh pass. Automated refresh and native bridge
parity are verified separately. No personal Vault or live integrations were used.
Owned fixture roots/descendants and listeners were absent after cleanup.


## Resumed acceptance passed - 2026-10-27

Fresh synthetic Vaults and a new packaged WebView profile completed the remaining
journeys on the unchanged 1.11.28 executable (SHA-256 59dc94ff91f0212f45417df29bda55c212e1f335c2b5157d7bd3be35c828386c).
All 42 bundled backend resources match the implementation. Windows helper discovery
and input worked in this run; no helper or application source repair was needed.
The earlier timeout's underlying cause remains unconfirmed. Running native and web
fixtures sequentially and allowing initial web compilation/reload completed acceptance.

Packaged Tauri displayed four completions grouped Domestic 1 / Front 1 / Outland 2,
separate unknown-time activity evidence and the deliberate unreadable-source partial
warning. Text and area filters preserved distinct same-text rows. Source navigation
opened the older original journal with attached note intact; all 13 Vault files
were byte-identical after those reads. Reopening one task through the native picker
saved Pending, and reload/manual Refresh showed three completions and Outland 1.
Returning through Command refreshed three pre-existing Holocron cache files; this
invalidated the first post-edit whole-Vault baseline and is retained as an observation,
not a passing read-only check. After dashboard writes settled, an isolated Completed
today Refresh preserved all 16 files byte-for-byte, including journals, XP and recurrence.

The fresh web view showed four completions before a fixture-only canonical API
reopening while the view stayed open. Manual Refresh showed three; the Outland
filter showed one, without duplicates. All 11 pre-edit and 14 post-edit files were
unchanged by view reads. Original note and task location were retained. Owned native
window/process and both web process trees were cleaned up; dedicated ports were
absent, and final snapshots still matched. All eight S024 acceptance criteria now
have evidence. S024 remains in review pending merge; E004 remains in progress.
