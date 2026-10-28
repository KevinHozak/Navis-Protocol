---
depends_on: ["NAVIS-S022"]
id: "NAVIS-S023"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "in_review"
title: "Persist and display reliable task completion timestamps"
type: "enhancement"
---
## Outcome

Persist and show trustworthy completion times for tasks and recurring occurrences without changing task labels.

## Context and target areas

Parent: [NAVIS-E004](NAVIS-E004.md). Depends on [NAVIS-S022](NAVIS-S022.md) for shared transitions and identity. Directive completion already stores completed_at; reuse existing provenance where valid. Targets: directive_completion.py, task_toggle.py, sync_engine.py, completion metadata and task/journal UI.

## Acceptance criteria

- [x] Record a timezone-aware instant on a successful transition to Done through canonical journal, directive, recurring and combat completion paths; distinguish completion time from later sync/import time.
- [x] Reuse existing timestamps; define behavior for reopen/recomplete and recurrence occurrences while preserving history. Idempotent retries do not overwrite the original completion instant.
- [x] Display local date/time consistently using the configured Navis timezone with America/Chicago fallback; define rollover, midnight and DST behavior.
- [x] Keep task text unchanged: store metadata without breaking exact-text recurrence matching, source identity, combat links, nested notes or XP reconciliation.
- [x] Legacy/manual completions without reliable time remain explicitly time unknown; never invent an exact instant from file modification time or sync time.
- [x] Persist safely with concurrency guards and verify saved values; preserve original journal locations, order, BOM and newlines.
- [ ] Verify web/Tauri parity with synthetic midnight/DST, reopen/recomplete, recurrence, replay and unknown-time cases.

## Implementation and verification checkpoint - 2026-10-27

Shared storage and display contract: [completion times](../docs/task-completion-times.md). The final affected synthetic suite passed 232 cases; the full frontend adapters/regressions and 76 serial native unit cases passed. Actual web completion/reopen/recompletion displayed the configured Asia/Tokyo zone, retained the earlier instant, cleared the current time on reopen and left a legacy date-only completion explicitly unknown. Original BOM/CRLF, notes, position and one task occurrence were preserved.

Packaged 1.11.27 UI acceptance remains blocked: window discovery timed out through the documented helper recovery. Cleanup observed an unexpectedly large descendant process tree; cause is unconfirmed. All owned fixture windows/process roots and dedicated web listeners were subsequently absent. Initial backend subprocess timeout and native cancellation timing failures during the slowdown passed clean serial reruns; the old native byte assertion was updated to validate metadata and original content independently. These failures are retained as observations, not counted as passing runs. A draft PR is required until the packaged timestamp workflow passes. Personal Vault and live providers were not exercised. S024 remains separate.
