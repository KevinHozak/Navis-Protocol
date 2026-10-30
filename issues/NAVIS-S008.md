---
depends_on: ["NAVIS-S007"]
id: "NAVIS-S008"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "in_progress"
title: "Implement only demonstrated workflow simplifications"
type: "enhancement"
---
## Outcome

Implement only demonstrated workflow simplifications.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S007](NAVIS-S007.md).

## Target areas

Only labels, repeated selections or preview controls identified by passing journey evidence.

## Acceptance criteria

- [x] Before starting, link passing journey results and explicit keep decision; identify which existing or delivered workflows each change actually targets.
- [x] Scope implementation to demonstrated improvements and list preserved requirements; dependencies on any conditional feature must be verified before modifying it.
- [x] Preserve original retention, source access, editing, explicit save and factual verification; follow existing component styling and transition conventions.
- [ ] Repeat the affected journey comparisons on the final implementation, complete relevant regression checks and web/desktop workflow smoke, and review fresh samples after delivery.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

## Gate retained - 2026-10-28

User explicitly requested that S008 remain gated while S007 is revised and rerun by a human. Agent-operated results do not satisfy unassisted human completion. No S008 implementation started.

## Authorized narrow implementation - 2026-10-30

S007 is closed under the explicit human-rehearsal waiver; see its closeout and
[trial limits](../docs/s007-journey-trial.md#accepted-agent-evidence-and-human-waiver).
Implement expanded original in ActionableBrief, expanded loaded sources and an
editable question-derived filename in KnowledgeNoteComposer, and supporting
decision-review rules/references beside the adjustment in WeeklyHolocronView.
S002/S004/S006 are delivered dependencies. Keep source selection/load, bounded
content, editing, destination choice, explicit save/export, digest rechecks,
non-overwrite and stale-source handling. Do not add automatic writes, source fetches,
task commitments, model calls or redesign unrelated controls. Production comparisons
and web/native smoke remain S008 verification, not inherited prototype evidence.

## Implementation checkpoint - 2026-10-30

Narrow source changes and release 1.11.35 are prepared; see [verification and limits](../docs/s008-workflow-simplifications.md). Frontend regression, 26 backend checks, isolated web/native knowledge-note and Holocron smoke passed. Brief browser smoke passed with a synthetic generation response and real isolated persistence. Full packaged brief generation/save and post-publication fresh-sample review remain pending. Human rehearsal is waived, not passed; S008 remains in_progress.
