---
depends_on: []
id: "NAVIS-S022"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "in_review"
title: "Add an accessible task status picker with shared transition semantics"
type: "enhancement"
---
## Outcome

Offer one compact, keyboard-accessible picker for Pending, In progress, Deferred, Cancelled and Done.

## Context and target areas

Parent: [NAVIS-E004](NAVIS-E004.md). Current task_toggle.py accepts blank/x/X only. Define shared status semantics and durable identity before exposing richer states. Targets: task/directive UI, backend task_toggle, directive_completion, combat completion, recurrence, and Tauri bridge.

## Acceptance criteria

- [x] Document canonical status storage and Markdown interoperability for journal tasks, active directives and recurring occurrences; preserve existing blank/x/X behavior.
- [x] Expose labelled, keyboard-accessible status choices with focus handling and saved/error feedback; follow existing sci-fi styling.
- [x] Define allowed transitions: cancellation is not successful completion; deferral alone does not reschedule a recurrence; completing a recurring occurrence does not cancel its series.
- [x] Done uses existing canonical completion and XP paths; reopening reconciles completion evidence without duplicate awards or loss of provenance.
- [x] Preserve original journal file, section and position, task text, attached notes, BOM and newlines; do not move entries or strip checkboxes.
- [x] Reject stale, missing or ambiguous targets and handle duplicate submissions safely; read back persisted status.
- [x] Verify transitions, legacy tasks, duplicate text, concurrent edits and retry behavior with disposable fixtures across web and Tauri; keep private Vault content out of evidence.

## Implementation checkpoint

Shared contract: [task status semantics](../docs/task-status-semantics.md). HTTP and native bridges share canonical task/directive completion writers. Isolated automated and physical runtime verification is in progress; no personal Vault writes are authorized by this story.


## Verified delivery checkpoint - 2026-10-27

Release 1.11.26 and selected real web/packaged Tauri fixtures passed status selection, keyboard access, save/readback, completion, reopening and recurring cancellation. Final journals are byte-identical with preserved BOM/CRLF/notes, one completion history item and 12 net XP after reopening; recurring next_due is unchanged. 174 affected Python cases plus two focused packaging/concurrency cases, 51 adapters/full frontend regressions, 76 native unit cases and one parity case passed. The missing native directive entrypoint found by the packaged check is repaired and covered by a resource regression; 39 bundled backend resources matched source. One earlier injected combat recovery failure passed isolated and full reruns; the trial retains it. Fixture windows/processes were closed and listeners absent. Personal Vault and provider integrations were not exercised. Independent external review is unavailable; primary-agent source review found no remaining actionable issue. S023 and S024 remain separate. See the [sanitized trial](../docs/trials/s022-task-status-2026-10-27.json).
