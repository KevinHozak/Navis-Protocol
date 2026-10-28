---
depends_on: ["NAVIS-S022","NAVIS-S023"]
id: "NAVIS-S024"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "in_progress"
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
- [ ] Verify source navigation, grouping, deduplication, midnight/DST, legacy records, refresh and byte-for-byte read-only behavior on synthetic Vault fixtures in web and Tauri.

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
