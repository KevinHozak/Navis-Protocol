---
depends_on: ["NAVIS-S005"]
id: "NAVIS-S006"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "open"
title: "Implement a decision-focused Holocron section after a passing trial"
type: "enhancement"
---
## Outcome

Implement a decision-focused Holocron section after a passing trial.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S005](NAVIS-S005.md).

## Target areas

backend/services/holocron_engine.py, Weekly Holocron UI/export and native bridge.

## Acceptance criteria

- [ ] Before starting, link a passing three-cycle comparison and explicit keep decision.
- [ ] Add changed/unresolved/suggested-adjustment content within the existing Weekly Holocron; distinguish deterministic metrics from AI interpretation.
- [ ] Expose supporting references, represent missing evidence as unknown and retain the rule-based fallback without fabricating blocker or outcome claims.
- [ ] Keep suggestions editable and prevent automatic task creation or commitments; preserve local-first generation controls and existing presentation conventions.
- [ ] Verify source links, interpretation boundaries, missing data and fallback behavior with relevant checks plus web/desktop and export smoke; review fresh output after delivery.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

S013 implements the shared [evidence schema, panel and export contract](../docs/holocron-evidence.md)
for factual trust corrections. Reuse that presentation after the S005 gate;
S013 does not satisfy this issue's trial or decision-feature criteria.
