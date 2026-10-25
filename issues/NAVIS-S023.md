---
depends_on: ["NAVIS-S022"]
id: "NAVIS-S023"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "open"
title: "Persist and display reliable task completion timestamps"
type: "enhancement"
---
## Outcome

Persist and show trustworthy completion times for tasks and recurring occurrences without changing task labels.

## Context and target areas

Parent: [NAVIS-E004](NAVIS-E004.md). Depends on [NAVIS-S022](NAVIS-S022.md) for shared transitions and identity. Directive completion already stores completed_at; reuse existing provenance where valid. Targets: directive_completion.py, task_toggle.py, sync_engine.py, completion metadata and task/journal UI.

## Acceptance criteria

- [ ] Record a timezone-aware instant on a successful transition to Done through canonical journal, directive, recurring and combat completion paths; distinguish completion time from later sync/import time.
- [ ] Reuse existing timestamps; define behavior for reopen/recomplete and recurrence occurrences while preserving history. Idempotent retries do not overwrite the original completion instant.
- [ ] Display local date/time consistently using the configured Navis timezone with America/Chicago fallback; define rollover, midnight and DST behavior.
- [ ] Keep task text unchanged: store metadata without breaking exact-text recurrence matching, source identity, combat links, nested notes or XP reconciliation.
- [ ] Legacy/manual completions without reliable time remain explicitly time unknown; never invent an exact instant from file modification time or sync time.
- [ ] Persist safely with concurrency guards and verify saved values; preserve original journal locations, order, BOM and newlines.
- [ ] Verify web/Tauri parity with synthetic midnight/DST, reopen/recomplete, recurrence, replay and unknown-time cases.