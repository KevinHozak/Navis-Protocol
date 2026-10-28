---
depends_on: []
id: "NAVIS-E004"
parent: []
priority: "medium"
schema_version: 1
status: "done"
title: "Add task status controls, completion timestamps and a Completed today view"
type: "epic"
---
## Outcome

Make task progress, completion time and today's accomplishments easy to review while keeping original journal entries in their existing files, sections and positions.

## Context and scope

Inspired by [Task Collector](https://github.com/ebullient/obsidian-task-collector). Borrow status selection and completion visibility, without physically collecting or relocating journal entries. This is a Navis feature proposal, not plugin installation.

Source inspection found binary checkbox handling in backend/services/task_toggle.py, directive completion provenance in backend/services/directive_completion.py, exact-text recurrence matching in backend/services/sync_engine.py, and section-based checked-item XP in backend/services/rpg_engine.py. Reinspect before implementation. Existing checked journal logs include activities as well as completed tasks; do not silently classify all of them as task completions.

## Acceptance criteria

- [x] Deliver an accessible status picker with explicit completion, cancellation, deferral and reopening semantics.
- [x] Persist and display trustworthy completion timestamps without breaking text matching, recurrence, task identity or XP.
- [x] Provide a read-only Completed today view grouped by operation area with links to original entries.
- [x] Preserve original journal locations, headings, order, nested notes, provenance, BOM and newline style; no collection moves, checkbox stripping or duplicate log copies.
- [x] Verify affected journeys across web and Tauri with disposable fixtures, including concurrent edits, retries, midnight boundaries and legacy records.
- [x] Reconcile child acceptance evidence before closing this epic; no implementation is authorized by issue creation.

## Stories

- [NAVIS-S022](NAVIS-S022.md): Accessible status picker and shared transitions
- [NAVIS-S023](NAVIS-S023.md): Reliable completion timestamps
- [NAVIS-S024](NAVIS-S024.md): Completed today view

## S022 checkpoint

S022 is done after PR #24 merged at `2f85317`, with all seven child acceptance criteria satisfied by automated and isolated web/packaged Tauri verification. The status-picker criterion is accepted; epic-wide preservation and verification criteria remain open until S023/S024 are verified. Completion timestamps (S023) and the read-only Completed today view (S024) remain separate, unimplemented stories. See [task status semantics](../docs/task-status-semantics.md).

## S023 checkpoint

S023 is done after merged PR #26 (`3049232`), with timestamp persistence, history, configured-zone and fallback/DST display verified in isolated web and packaged fixtures. S024 Completed today remains open work; epic-wide acceptance remains in progress.


## Reassessment after S024 merge - 2026-10-27

All three children are now done: S022 after PR #24 (`2f85317`), S023 after PR #26
(`3049232`), and S024 after PR #27 (`d9bdb58`). This is a local issue-store epic;
its parent/dependency relationships, rather than GitHub issue numbers, define
membership. All six epic acceptance criteria are reconciled:

| Criterion | Accepted evidence |
| --- | --- |
| Status controls and transitions | S022 shared semantics, canonical web/native writers, keyboard picker and reopening fixtures. |
| Trustworthy completion times | S023 UTC persistence, idempotent replay, retained history, configured-zone/Chicago fallback and midnight/DST fixtures. |
| Completed today by original area | S024 shared read model, distinct same-text identities, source navigation and explicit unknown-time activity separation. |
| Journal/XP/recurrence preservation | S022/S023 BOM/CRLF, notes, identity, position and recovery tests; S024 complete-byte comparisons around isolated reads. No collection/copy workflow. |
| Web/Tauri affected journeys | Recorded automated suites plus isolated physical status, timestamps, completion evidence, filtering, reopening and refresh; concurrent-edit/retry/legacy/time-boundary cases are covered by linked child evidence. |
| Child acceptance reconciled | S022 7/7, S023 7/7 and S024 8/8 criteria checked and implementations merged. |

See [status semantics](../docs/task-status-semantics.md),
[completion times](../docs/task-completion-times.md) and
[Completed today](../docs/completed-today.md) for contracts and sanitized trials.
No retained implementation or selected verification gap remains for E004.
Clean-machine installation, personal-Vault/live-provider trials and
independent external review remain unverified limits, not passing checks. The
S024 reader remains bounded with explicit partial coverage; dashboard navigation
can refresh existing Holocron caches, separately from its read-only projection.
No new application build or runtime changes are required for this closeout.


## Closeout - 2026-10-27

Accepted and closed with 3/3 children done and all six epic criteria satisfied.
The merged deliveries are S022 PR #24 (`2f85317`), S023 PR #26 (`3049232`), and
S024 PR #27 (`d9bdb5886b98e3cba5eb735d931e2660cb48d1be`). Child acceptance,
preservation invariants, isolated web/packaged verification and the explicit
limits above were reconciled before closure. No retained implementation or
selected acceptance work remains. This documentation-only closeout does not
change application behavior or require a version bump.
