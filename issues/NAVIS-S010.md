---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S010"
parent: ["NAVIS-E002"]
priority: "medium"
schema_version: 1
status: "open"
title: "Expose freshness and failed-refresh state for confirmed gaps"
type: "enhancement"
---
## Outcome

Expose freshness and failed-refresh state for confirmed gaps.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Only dashboard, Holocron and related data paths identified by the audit.

## Acceptance criteria

- [ ] Before implementation, link confirmed audit findings and select affected views; reuse existing timestamps and status contracts where adequate.
- [ ] Display last successful data read and available source freshness with clear semantics and timezone; unavailable source timestamps stay unknown rather than being inferred from view render time.
- [ ] Show failed or in-progress refresh without presenting retained data as newly refreshed; communicate retained data age and provide a bounded user-triggered retry.
- [ ] Verify initial load, successful refresh, failed refresh and retained stale data across affected web/native views using controlled fixtures and relevant checks.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. Repair acceptance remains unchecked; no application implementation is authorized by this issue update.


## S009 audit disposition - 2026-10-27

T03/T04: protect Holocron selected-week identity against out-of-order replies; expose dashboard failed refresh and last successful read separately from operational/source timestamps. Reuse current loading/error/retry UI and generated_at; do not infer source freshness from render time.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.
