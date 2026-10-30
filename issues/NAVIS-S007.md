---
depends_on: ["NAVIS-S005"]
id: "NAVIS-S007"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "done"
title: "Measure and simplify three capture-to-decision journeys"
type: "enhancement"
---
## Outcome

Measure and simplify three capture-to-decision journeys.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S005](NAVIS-S005.md).

## Target areas

Rough note to saved brief; selected sources to saved knowledge note; Holocron to chosen adjustment.

## Acceptance criteria

- [x] After earlier trial decisions, review the three journeys using available workflows or preserved trial outputs; do not require a failed conditional feature to be implemented.
- [x] Record baseline and candidate steps, completion time, correction effort and points of confusion; preserve originals and requirements.
- [x] Improve completion time or interaction count in at least two of three journeys without increasing factual errors or correction effort.
- [x] Retain original/source access, editing and explicit save controls; user completes each candidate journey without additional explanation.
- [x] Record exact demonstrated changes and a sanitized keep/revise/drop decision rather than proposing a general redesign.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

## Trial started - 2026-10-28

Earlier trial keep decisions are recorded and S002/S004/S006 are merged. Compare six synthetic preserved-output rehearsals (baseline/candidate for each journey), focusing on source-review/finalization controls. This is not a timed benchmark of production generation or end-to-end app navigation. Test originals/evidence shown inline and an editable suggested knowledge-note filename, without removing explicit source selection, editing or save controls. Human unassisted completion, correction effort, confusion and keep/revise/drop remain pending. S008 is unstarted and gated.

## Prepared rehearsal

[Trial design](../docs/s007-journey-trial.md), [standalone prototype](../docs/trials/s007-journey-rehearsal.html) and [sanitized preparation record](../docs/trials/s007-journey-rehearsal-2026-10-28.json). All six agent smoke runs completed in separate agent storage. Human trial opened fresh at 0/6; completion times, correction effort, confusion and decision pending. Agent counts do not satisfy human acceptance. Local loopback server intentionally retained for the human handoff; no production processes or personal Vault records touched.

## Revise and retest

Human attempt required explanation and remained incomplete (last observed 3/6); no passing human result or keep decision. User authorized all six agent-operated runs and rehearsal simplification while keeping S008 gated. [Agent evidence](../docs/trials/s007-agent-run-2026-10-28.json) records zero factual corrections, preserved originals and fewer candidate interactions; this is not human acceptance. Version 2 simplifies trial progression/feedback and clarifies source review and final completion. All six v2 agent smoke runs passed; fresh human trial opened at 0/6 with old v1 storage preserved. See [revision record](../docs/s007-journey-trial.md#rehearsal-revision). Status remains in_progress.

## Accepted closeout - 2026-10-30

The user explicitly waived the fresh human rehearsal and authorized closure using
the [six agent-operated comparisons](../docs/trials/s007-agent-run-2026-10-28.json).
Keep only inline original/source/evidence previews and an editable suggested
knowledge-note filename. Agent work interactions were brief 2→1, knowledge 4→2,
Holocron 2→1. All six retained originals/source review and explicit saves; primary
agent review recorded zero factual corrections and zero correction minutes.
The original record's Revise decision is retained: it concerned rehearsal confusion;
the current user decision supersedes the human retest gate for these narrow controls.

Human unassisted completion is waived, not passed. Agent/tool elapsed times do not
establish human or production time savings; general usability, learning effects and
independent factual review remain unverified. The first human attempt's confusion
remains recorded. Acceptance boxes reflect the explicit waiver, not a human result.
S008 may now implement only the accepted controls and must retain its own checks.
