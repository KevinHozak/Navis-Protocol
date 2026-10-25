---
depends_on: ["NAVIS-S022","NAVIS-S023"]
id: "NAVIS-S024"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "open"
title: "Add a read-only Completed today view grouped by operation area"
type: "enhancement"
---
## Outcome

Provide a read-only Completed today view grouped by operation area, with navigation to original journal evidence.

## Context and target areas

Parent: [NAVIS-E004](NAVIS-E004.md). Depends on [NAVIS-S022](NAVIS-S022.md) and [NAVIS-S023](NAVIS-S023.md) for shared completion semantics and timestamps. Targets: task/journal read models, Daily Journal/task UI, canonical directive provenance and web/Tauri routes. Existing checked journal entries include logged activities; define their presentation explicitly.

## Acceptance criteria

- [ ] Define today using the configured Navis timezone with America/Chicago fallback. Include actual completion occurrences for that day, including tasks originating in older journals.
- [ ] Group by original operation area; show task text, available completion time and a working source link that opens the original journal entry.
- [ ] Define coverage for ad hoc journal tasks, active directives and recurring occurrences; deduplicate multiple representations of one completion using stable provenance without merging distinct same-text tasks.
- [ ] Show unknown-time legacy checked items separately as journal-day evidence; do not assert they were completed today. Label or exclude activity logs explicitly rather than silently counting them as completed tasks.
- [ ] Exclude cancelled/deferred/pending items; reflect reopen/recomplete and successful mutations after refresh without creating duplicate rows.
- [ ] Reading/filtering the view never moves, copies, rewrites or reorders journal entries, changes headings, strips checkboxes, awards XP or advances recurrence.
- [ ] Distinguish empty, loading, unavailable and partial results; do not silently omit unreadable sources.
- [ ] Verify source navigation, grouping, deduplication, midnight/DST, legacy records, refresh and byte-for-byte read-only behavior on synthetic Vault fixtures in web and Tauri.