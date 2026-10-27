---
depends_on: []
id: "NAVIS-E004"
parent: []
priority: "medium"
schema_version: 1
status: "in_progress"
title: "Add task status controls, completion timestamps and a Completed today view"
type: "epic"
---
## Outcome

Make task progress, completion time and today's accomplishments easy to review while keeping original journal entries in their existing files, sections and positions.

## Context and scope

Inspired by [Task Collector](https://github.com/ebullient/obsidian-task-collector). Borrow status selection and completion visibility, without physically collecting or relocating journal entries. This is a Navis feature proposal, not plugin installation.

Source inspection found binary checkbox handling in backend/services/task_toggle.py, directive completion provenance in backend/services/directive_completion.py, exact-text recurrence matching in backend/services/sync_engine.py, and section-based checked-item XP in backend/services/rpg_engine.py. Reinspect before implementation. Existing checked journal logs include activities as well as completed tasks; do not silently classify all of them as task completions.

## Acceptance criteria

- [ ] Deliver an accessible status picker with explicit completion, cancellation, deferral and reopening semantics.
- [ ] Persist and display trustworthy completion timestamps without breaking text matching, recurrence, task identity or XP.
- [ ] Provide a read-only Completed today view grouped by operation area with links to original entries.
- [ ] Preserve original journal locations, headings, order, nested notes, provenance, BOM and newline style; no collection moves, checkbox stripping or duplicate log copies.
- [ ] Verify affected journeys across web and Tauri with disposable fixtures, including concurrent edits, retries, midnight boundaries and legacy records.
- [ ] Reconcile child acceptance evidence before closing this epic; no implementation is authorized by issue creation.

## Stories

- [NAVIS-S022](NAVIS-S022.md): Accessible status picker and shared transitions
- [NAVIS-S023](NAVIS-S023.md): Reliable completion timestamps
- [NAVIS-S024](NAVIS-S024.md): Completed today view

## S022 checkpoint

S022 implements the shared status contract and picker with isolated web/native verification. Completion timestamps (S023) and the read-only Completed today view (S024) remain separate, unimplemented stories. See [task status semantics](../docs/task-status-semantics.md).
