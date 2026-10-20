---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S011"
parent: ["NAVIS-E002"]
priority: "medium"
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

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. Current deficiencies are unconfirmed until the audit establishes them. Issue creation authorizes persistence only; no audit execution or application implementation is performed now.
