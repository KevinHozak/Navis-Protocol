---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S013"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "done"
title: "Make Holocron metrics and interpretations traceable to evidence"
type: "enhancement"
---
## Outcome

Make Holocron metrics and interpretations traceable to evidence.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Audit-selected Holocron payload/UI/export and source navigation; coordinate with NAVIS-S006.

## Acceptance criteria

- [x] Before implementation, link confirmed evidence-navigation gaps and reconcile overlap with [decision-focused Holocron work](NAVIS-S006.md); keep one shared evidence presentation.
- [x] Allow inspection of supporting date ranges, source references and relevant aggregation/rule context for selected metrics; separate deterministic values from generated interpretations.
- [x] Provide valid source navigation without exposing unnecessary personal content or private absolute paths in exported/shared artifacts; represent missing or inaccessible references explicitly.
- [x] Do not manufacture provenance or treat source presence as proof of an interpretation. Verify source mapping, deleted/unavailable references and privacy behavior in affected web/native and export paths.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The user selected implementation after the S009 audit and explicitly authorized a separate codex branch and PR.


## S009 audit disposition - 2026-10-27

T01: replace or explicitly label fixed readiness, estimated deep-work/damage, invented squad fallback and inferred combat outcomes/XP; expose genuine contributing evidence and rules in UI and HTML export. Do not manufacture source references. Share evidence presentation with S006, but factual corrections do not wait for its AI trial.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.


## Packaged observation - 2026-10-27

S014 unavailable-root smoke observed Holocron startup creating weekly cache files
under a root without a Journal, while the dashboard displays zero-based WTD
claims. Sync preflight rejects the root. Preserve this source-availability/cache
behavior in the S013/S015 repair matrix; no Holocron fix is claimed by PR #17.

## Implementation and verification - 2026-10-27

S013 repairs T01 with schema 2 source states/fingerprints, bounded inspection,
relative journal navigation, factual Keeper/checklist aggregation and safe HTML
snapshots. Native reads revalidate through Python. Unsupported historical metrics
are unavailable; journal mentions do not establish combat outcomes. S006 retains
its separate trial gate and reuses this presentation.

42 affected Python tests, 50 adapter tests, mounted evidence/navigation checks,
the complete frontend regression runner and 74 serial Rust tests passed (personal
Vault probe excluded). Ruff, lint with existing warnings, secret scan and release
packaging passed. The isolated 1.11.21 native UI and all 38 bundled resources were
verified. See [contract, artifact identity and retained limits](../docs/holocron-evidence.md).
Physical web-browser/download-dialog and clean-machine installer checks are not
claimed. Status is in_review pending PR acceptance; external review is unavailable.

## Accepted merge - 2026-10-27

Both current-head scans passed; the user requested merge after readiness. PR #18
merged as `cc0584231442f580110badfd7280e04eefdca7f3`, and local main was verified
clean and synchronized. S013 closes within the documented fixture/runtime limits;
broader S015 journeys and S010 selection gaps remain open.
