---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S011"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "open"
title: "Distinguish unavailable data from valid empty and zero results"
type: "enhancement"
---
## Outcome

Distinguish unavailable data from valid empty and zero results.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Only confirmed response/UI gaps in affected backend/native contracts and consumers.

## Acceptance criteria

- [ ] Before implementation, link confirmed audit findings and document the affected state contract without assuming all views need changes.
- [ ] Represent loading, valid empty results, measured zero, missing records, dependency failure and unsupported native routes accurately where applicable; do not coerce failures to zero or an empty success.
- [ ] Provide clear user-facing states and applicable recovery actions while preserving legitimate existing empty/zero behavior and retained data provenance.
- [ ] Exercise representative missing/corrupt source, unavailable backend/native dependency, empty result and real zero fixtures; verify web/native behavior and meaningful regression checks.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. Repair acceptance remains unchecked; no application implementation is authorized by this issue update.


## S009 audit disposition - 2026-10-27

T02: distinguish missing/unreadable/partial Holocron journal and progression inputs from valid zero; retain day/source coverage. Repair calendar HTTP/error handling so unavailable months do not appear empty. Preserve command readiness and task-board unavailable/zero handling already implemented.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.
