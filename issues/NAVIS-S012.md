---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S012"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "open"
title: "Verify saved journal and task changes against authoritative state"
type: "enhancement"
---
## Outcome

Verify saved journal and task changes against authoritative state.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Audit-selected journal/task mutation paths, canonical stores and derived projections in web/native flows.

## Acceptance criteria

- [ ] Before implementation, link reproducible audit gaps and identify authoritative persistence and projection boundaries for each selected mutation.
- [ ] Confirm success through authoritative saved-state readback or an equivalent evidence-backed committed-state contract; distinguish committed changes from delayed or failed projections.
- [ ] Provide a usable link or navigation back to the saved journal/task record; preserve stable record identity and communicate verification failures without falsely claiming the mutation failed.
- [ ] Prevent duplicate writes or XP awards on ambiguous responses/retry using existing idempotency and reconciliation mechanisms; do not blindly resubmit a possibly committed mutation.
- [ ] Verify success, pre-commit failure, ambiguous response, readback mismatch and projection failure with isolated fixtures plus affected web/native workflows; preserve journal content and canonical XP authority.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. Repair acceptance remains unchecked; no application implementation is authorized by this issue update.


## S009 audit disposition - 2026-10-27

T05: isolate late journal-append responses from a different selected record; provide navigation to the actual saved source without overwriting another view. Retain canonical snapshot readback, durable request identity, authoritative checkbox responses and pending-XP recovery. No general rewrite of save services is justified.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.
