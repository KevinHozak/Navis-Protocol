---
depends_on: []
id: "NAVIS-S022"
parent: ["NAVIS-E004"]
priority: "medium"
schema_version: 1
status: "open"
title: "Add an accessible task status picker with shared transition semantics"
type: "enhancement"
---
## Outcome

Offer one compact, keyboard-accessible picker for Pending, In progress, Deferred, Cancelled and Done.

## Context and target areas

Parent: [NAVIS-E004](NAVIS-E004.md). Current task_toggle.py accepts blank/x/X only. Define shared status semantics and durable identity before exposing richer states. Targets: task/directive UI, backend task_toggle, directive_completion, combat completion, recurrence, and Tauri bridge.

## Acceptance criteria

- [ ] Document canonical status storage and Markdown interoperability for journal tasks, active directives and recurring occurrences; preserve existing blank/x/X behavior.
- [ ] Expose labelled, keyboard-accessible status choices with focus handling and saved/error feedback; follow existing sci-fi styling.
- [ ] Define allowed transitions: cancellation is not successful completion; deferral alone does not reschedule a recurrence; completing a recurring occurrence does not cancel its series.
- [ ] Done uses existing canonical completion and XP paths; reopening reconciles completion evidence without duplicate awards or loss of provenance.
- [ ] Preserve original journal file, section and position, task text, attached notes, BOM and newlines; do not move entries or strip checkboxes.
- [ ] Reject stale, missing or ambiguous targets and handle duplicate submissions safely; read back persisted status.
- [ ] Verify transitions, legacy tasks, duplicate text, concurrent edits and retry behavior with disposable fixtures across web and Tauri; keep private Vault content out of evidence.