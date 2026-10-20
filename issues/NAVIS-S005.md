---
depends_on: ["NAVIS-S003"]
id: "NAVIS-S005"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "open"
title: "Compare decision-focused Holocrons across three weekly cycles"
type: "enhancement"
---
## Outcome

Compare decision-focused Holocrons across three weekly cycles.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S003](NAVIS-S003.md).

## Target areas

backend/services/holocron_engine.py, existing Holocron outputs and selected supporting records; manual comparison.

## Acceptance criteria

- [ ] After the first two trial decisions, compare current and candidate debriefs across three weekly cycles using the same available evidence.
- [ ] Candidate states what changed, unresolved matters and one suggested adjustment; link factual claims to records or telemetry and mark unsupported conclusions unknown.
- [ ] Do not treat XP or task counts alone as proof of meaningful outcomes or sustainable workload; identify evidence missing for blocker/outcome claims.
- [ ] Candidate is rated more useful for choosing an adjustment in at least two of three cycles, with no more than one factual correction round per candidate.
- [ ] Record review effort and elapsed time for both versions and retain a sanitized keep/revise/drop decision; introduce no scheduled generation.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.
