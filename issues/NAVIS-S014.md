---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S014"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "in_review"
title: "Explain partial sync failures and offer safe recovery"
type: "enhancement"
---
## Outcome

Explain partial sync failures and offer safe recovery.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Audit-selected sync/rollover orchestration, operation progress/result reporting and native compatibility paths.

## Acceptance criteria

- [x] Before implementation, link confirmed audit findings and inventory existing job progress, durable checkpoints and idempotent recovery mechanisms.
- [x] Show which steps completed, failed or were skipped and whether changes already committed; preserve actionable progress rather than replacing it with a misleading overall success.
- [x] Offer retry or reconciliation only when safe for the specific step; prevent duplicate journal items, XP awards and overlapping jobs; explain manual recovery when safe automatic retry cannot be established.
- [x] Verify mid-pipeline failure, committed-before-response failure, unavailable dependencies and retry behavior with disposable fixtures and affected web/native workflows; restarting UI must not misrepresent durable results.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. Repair acceptance remains unchecked; no application implementation is authorized by this issue update.


## S009 audit disposition - 2026-10-27

T06/T07: propagate per-step committed/failed/skipped outcomes through web jobs and native exit/events; handle warning-prefixed failures and distinguish status reconnect from operation retry. Preserve progress, process supervision and canonical idempotency. Establish safe step-specific reconciliation before any restart.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.


## Implementation checkpoint - 2026-10-27

S009 audit and T06/T07 evidence merged in PR #16 as 5fb6b7ea934a91a17d202bbd19a6802b35327129. S014 implements
one shared durable outcome runner for web/native sync and rollover, step-level
intent/outcomes, conservative saved/uncertain states, cross-process serialization,
stable request identity, read-only reconnect and explicit review acknowledgement
without step replay. Root mismatch, unavailable state and unresolved previous
operations fail closed. Existing journal/XP services and process supervision are
retained. Receipt files/locks are excluded from backup staging.

Separate codex-branch/PR publication is explicitly authorized. PR #17 is retargeted to main after the S009 merge.
Version 1.11.19 is prepared, not a packaged release. See
[partial-operation contract](../docs/sync-operation-outcomes.md) for protocol,
recovery and retained runtime limits. Acceptance is verified within the documented fixture/transport scope; packaged interaction remains under S015. No personal Vault operation was executed.


## Verification - 2026-10-27

81 affected Python tests, seven mounted operation scenarios, 49 adapter tests and
the complete frontend regression runner passed. 71 serial Rust tests passed;
the personal-Vault availability probe was excluded. Backend Ruff, frontend lint
(existing warnings), whitespace and desktop frontend production build passed.
The known missing-watchfiles test is explicitly excluded; unrelated Holocron
manifest test failures remain recorded under S009/S015. No production sync,
packaged installer or physical Drive-race verification was performed. See
[operation contract](../docs/sync-operation-outcomes.md) and
[sanitized verification](../docs/trials/sync-operation-outcomes-2026-10-27.json).
Independent external review remains unavailable. Status remains in_review until
delivery is accepted; audit PR #16 is merged.


## Main reconciliation - 2026-10-27

PR #16 merged as 5fb6b7e. PR #17 now targets main; its issue conflict was reconciled by retaining both the audit scope and S014 verification. Application source hashes remain identical to the verified S014 report. Packaged runtime/installer and Drive-race checks remain unverified under S015.


## Final packaged fixture gate - 2026-10-27

Release 1.11.20 passed the targeted packaged fixture acceptance, including actual
partial writes, cancellation, active close, restart, read-only reconnect and review
without replay. Bundled resource resolution and fixture isolation are verified.
The watcher shutdown and Windows receipt-sharing defects exposed by smoke were
fixed and verified. See [acceptance and retained limits](../docs/sync-operation-outcomes.md#packaged-fixture-acceptance---2026-10-27-11120).
Status remains in_review pending PR #17 acceptance; clean-machine installation and
production/Drive checks are retained under S015.
