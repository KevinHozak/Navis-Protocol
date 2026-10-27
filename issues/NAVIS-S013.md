---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S013"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "open"
title: "Make Holocron metrics and interpretations traceable to evidence"
type: "enhancement"
---
## Outcome

Make Holocron metrics and interpretations traceable to evidence.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Audit-selected Holocron payload/UI/export and source navigation; coordinate with NAVIS-S006.

## Acceptance criteria

- [ ] Before implementation, link confirmed evidence-navigation gaps and reconcile overlap with [decision-focused Holocron work](NAVIS-S006.md); keep one shared evidence presentation.
- [ ] Allow inspection of supporting date ranges, source references and relevant aggregation/rule context for selected metrics; separate deterministic values from generated interpretations.
- [ ] Provide valid source navigation without exposing unnecessary personal content or private absolute paths in exported/shared artifacts; represent missing or inaccessible references explicitly.
- [ ] Do not manufacture provenance or treat source presence as proof of an interpretation. Verify source mapping, deleted/unavailable references and privacy behavior in affected web/native and export paths.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. Repair acceptance remains unchecked; no application implementation is authorized by this issue update.


## S009 audit disposition - 2026-10-27

T01: replace or explicitly label fixed readiness, estimated deep-work/damage, invented squad fallback and inferred combat outcomes/XP; expose genuine contributing evidence and rules in UI and HTML export. Do not manufacture source references. Share evidence presentation with S006, but factual corrections do not wait for its AI trial.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.
