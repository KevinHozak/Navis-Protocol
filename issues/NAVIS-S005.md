---
depends_on: ["NAVIS-S003"]
id: "NAVIS-S005"
parent: ["NAVIS-E001"]
priority: "medium"
schema_version: 1
status: "done"
title: "Compare decision-focused Holocrons across three weekly cycles"
type: "enhancement"
---
## Outcome

Compare decision-focused Holocrons across three weekly cycles.

Parent: [NAVIS-E001](NAVIS-E001.md). Depends on [NAVIS-S003](NAVIS-S003.md).

## Target areas

backend/services/holocron_engine.py, existing Holocron outputs and selected supporting records; manual comparison.

## Acceptance criteria

- [x] After the first two trial decisions, compare current and candidate debriefs across three weekly cycles using the same available evidence.
- [x] Candidate states what changed, unresolved matters and one suggested adjustment; link factual claims to records or telemetry and mark unsupported conclusions unknown.
- [x] Do not treat XP or task counts alone as proof of meaningful outcomes or sustainable workload; identify evidence missing for blocker/outcome claims.
- [x] Candidate is rated more useful for choosing an adjustment in at least two of three cycles, with no more than one factual correction round per candidate.
- [x] Record review effort and elapsed time for both versions and retain a sanitized keep/revise/drop decision; introduce no scheduled generation.

## Evaluation, privacy and scope

Follow the parent epic's evaluation record, privacy requirements and trial gates. This issue records planned work only. Conditional implementation requires separately selected work after passing evidence; no trial results are claimed.

## Trial started - 2026-10-28

S001 and S003 keep decisions are recorded; S004 merged in PR #33. Retrospective paired comparison uses completed weeks W41-W43 (October 5-25), with identical copied journals and Keeper ledger evidence for both versions. Current baseline is the corrected rule-based debrief on merged main, not legacy schema-1 cached summaries with unsupported victory/work-hour claims. No scheduled generation or application changes.

Three candidate pairs prepared for human review. Personal samples and exact source hashes are in a private temporary directory outside Git; 25 live input hashes verified unchanged. MCP reported vault_unavailable; a narrowly elevated read-only copy succeeded. Human usefulness, corrections and review effort remain pending; S006 implementation gate stays closed. See [sanitized trial record](../docs/trials/s005-holocron-comparison-2026-10-28.json).

## Human acceptance - 2026-10-28

Candidates preferred in all three cycles; no corrections; review time unknown. User explicitly chose keep and closeout. Retrospective trial passed; no time savings or prospective intervention outcome claimed. S006 gate opens.
