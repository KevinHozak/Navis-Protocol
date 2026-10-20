---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S014"
parent: ["NAVIS-E002"]
priority: "medium"
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

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. Current deficiencies are unconfirmed until the audit establishes them. Issue creation authorizes persistence only; no audit execution or application implementation is performed now.
