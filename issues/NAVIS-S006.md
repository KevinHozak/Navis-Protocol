---
depends_on: ["NAVIS-S005"]
id: "NAVIS-S006"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "in_review"
title: "Implement a decision-focused Holocron section after a passing trial"
type: "enhancement"
---
## Outcome

Implement a decision-focused Holocron section after a passing trial.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S005](NAVIS-S005.md).

## Target areas

backend/services/holocron_engine.py, Weekly Holocron UI/export and native bridge.

## Acceptance criteria

- [x] Before starting, link a passing three-cycle comparison and explicit keep decision.
- [x] Add changed/unresolved/suggested-adjustment content within the existing Weekly Holocron; distinguish deterministic metrics from AI interpretation.
- [x] Expose supporting references, represent missing evidence as unknown and retain the rule-based fallback without fabricating blocker or outcome claims.
- [x] Keep suggestions editable and prevent automatic task creation or commitments; preserve local-first generation controls and existing presentation conventions.
- [x] Verify source links, interpretation boundaries, missing data and fallback behavior with relevant checks plus web/desktop and export smoke; review fresh output after delivery.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

S013 implements the shared [evidence schema, panel and export contract](../docs/holocron-evidence.md)
for factual trust corrections. Reuse that presentation after the S005 gate;
S013 does not satisfy this issue's trial or decision-feature criteria.

## Selected scope

S005 passed 3/3 human preferences with zero corrections and explicit keep decision; review time unknown. See [trial](../docs/trials/s005-holocron-comparison-2026-10-28.json). Extend existing Holocron with source-linked deterministic observations, unknowns and editable proposed adjustments. No automatic task creation or scheduled generation.

## Verified candidate

Release 1.11.32, affected backend/transport/full frontend checks, isolated web/native editing, source inspection, native journal navigation and edited HTML exports passed. Three fresh synthetic outputs passed primary-agent factual review; human feature usefulness and timing unmeasured. Owned fixture processes/tab cleaned up and inputs preserved. [Verification](../docs/trials/s006-holocron-decisions-2026-10-28.json) and [behavior/limits](../docs/holocron-decisions.md). Pending publication and merge; no S006 closeout.
