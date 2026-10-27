---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S014"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "open"
title: "Explain partial sync failures and offer safe recovery"
type: "enhancement"
---
## Outcome

Explain partial sync failures and offer safe recovery.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Audit-selected sync/rollover orchestration, operation progress/result reporting and native compatibility paths.

## Acceptance criteria

- [ ] Before implementation, link confirmed audit findings and inventory existing job progress, durable checkpoints and idempotent recovery mechanisms.
- [ ] Show which steps completed, failed or were skipped and whether changes already committed; preserve actionable progress rather than replacing it with a misleading overall success.
- [ ] Offer retry or reconciliation only when safe for the specific step; prevent duplicate journal items, XP awards and overlapping jobs; explain manual recovery when safe automatic retry cannot be established.
- [ ] Verify mid-pipeline failure, committed-before-response failure, unavailable dependencies and retry behavior with disposable fixtures and affected web/native workflows; restarting UI must not misrepresent durable results.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. Repair acceptance remains unchecked; no application implementation is authorized by this issue update.


## S009 audit disposition - 2026-10-27

T06/T07: propagate per-step committed/failed/skipped outcomes through web jobs and native exit/events; handle warning-prefixed failures and distinguish status reconnect from operation retry. Preserve progress, process supervision and canonical idempotency. Establish safe step-specific reconciliation before any restart.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.
