ï»¿---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S012"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "in_review"
title: "Verify saved journal and task changes against authoritative state"
type: "enhancement"
---
## Outcome

Verify saved journal and task changes against authoritative state.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Audit-selected journal/task mutation paths, canonical stores and derived projections in web/native flows.

## Acceptance criteria

- [x] Before implementation, link reproducible audit gaps and identify authoritative persistence and projection boundaries for each selected mutation.
- [x] Confirm success through authoritative saved-state readback or an equivalent evidence-backed committed-state contract; distinguish committed changes from delayed or failed projections.
- [x] Provide a usable link or navigation back to the saved journal/task record; preserve stable record identity and communicate verification failures without falsely claiming the mutation failed.
- [x] Prevent duplicate writes or XP awards on ambiguous responses/retry using existing idempotency and reconciliation mechanisms; do not blindly resubmit a possibly committed mutation.
- [x] Verify success, pre-commit failure, ambiguous response, readback mismatch and projection failure with isolated fixtures plus affected web/native workflows; preserve journal content and canonical XP authority.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The user selected S012 after PR #19 and explicitly authorized a separate codex branch and PR. [Persistence boundaries and receipt contract](../docs/journal-save-verification.md) narrow this repair to T05 and its saved-source feedback; existing append/XP services and checkbox/task authority are retained. The false pending-XP toast observed in prior packaged fixtures is also confirmed: optional ID equality allowed two absent IDs to match.


## S009 audit disposition - 2026-10-27

T05: isolate late journal-append responses from a different selected record; provide navigation to the actual saved source without overwriting another view. Retain canonical snapshot readback, durable request identity, authoritative checkbox responses and pending-XP recovery. No general rewrite of save services is justified.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). Scoped repair criteria passed the automated and packaged fixture checks documented in the save contract. S012 awaits PR review and merge; broader physical web/installation journeys remain under S015.
