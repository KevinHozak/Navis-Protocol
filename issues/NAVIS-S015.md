---
depends_on: ["NAVIS-S009","NAVIS-S010","NAVIS-S011","NAVIS-S012","NAVIS-S013","NAVIS-S014"]
id: "NAVIS-S015"
parent: ["NAVIS-E002"]
priority: "medium"
schema_version: 1
status: "in_progress"
title: "Verify trust journeys across web and packaged desktop"
type: "enhancement"
---
## Outcome

Verify trust journeys across web and packaged desktop.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md). Depends on [NAVIS-S010](NAVIS-S010.md). Depends on [NAVIS-S011](NAVIS-S011.md). Depends on [NAVIS-S012](NAVIS-S012.md). Depends on [NAVIS-S013](NAVIS-S013.md). Depends on [NAVIS-S014](NAVIS-S014.md).

## Target areas

Integrated audit matrix and retained repair stories; packaged runtime evidence and user-facing journeys.

## Acceptance criteria

- [x] Reconcile audit findings and repair dispositions; select representative retained freshness/data-state, journal/task save, Holocron evidence and partial-sync journeys.
- [ ] Demonstrate that the user can recognize stale/unavailable data, verify a saved change, inspect source support and understand failure/recovery without logs.
- [ ] Record relevant automated results and separate web and packaged-desktop manual observations, with build/version and fixture details; source tests alone cannot pass packaged acceptance.
- [ ] Verify no duplicate writes/awards, false-zero displays or false completion under selected failure cases. Any unavailable runtime or unresolved confirmed defect remains explicit and blocks affected acceptance.
- [x] Retain sanitized evidence and update existing relevant verification documentation; do not create a second issue index or imply production Vault migration was exercised.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The S009 audit selected the confirmed scope below. The user selected S015 after PR #21 merged and explicitly approved a codex branch and PR.


## S009 audit disposition - 2026-10-27

Retain the full web/packaged trust matrix from S009. Reconcile the two manifest tests assuming one row while current WTD is injected; validate/install declared watcher dependencies in an isolated test environment before claiming watcher acceptance. Packaged offline/reconnect, navigation-during-save, partial outcomes, cancel/close, keyboard and source navigation remain unrun blockers, not passed tests.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). Integrated checkpoint: [trust journeys](../docs/trust-journey-verification.md). Retained incomplete gates block completion.


## S014 packaged subset - 2026-10-27

The targeted 1.11.20 operation fixture matrix now passes; see [S014 acceptance](../docs/sync-operation-outcomes.md).
The declared watchfiles 1.1.1 dependency and watcher shutdown are verified.
Installer execution, clean-machine setup, remaining trust journeys, production
integrations and physical Drive races remain open. An unavailable root still
receives Holocron startup cache writes; sync/rollover preflight rejects operation
writes. Do not infer whole-epic acceptance from the S014 subset.

## Integrated checkpoint - 2026-10-27

Real browser freshness/offline/reconnect, delayed journal-save navigation, keyboard saved-source/XP recovery, checkbox feedback and Holocron source inspection passed with isolated fixtures. Confirmed unavailable-status and false startup-catchup completion gaps and stale composer XP feedback are repaired with regression evidence. Prior packaged evidence keeps its original versions. Clean-machine installation and remaining physical runtime journeys are explicit blockers; this story is not complete.

Final selected 1.11.25 packaged check passed XP recovery/message reconciliation with one entry, one 12-XP award and preserved journal bytes. 94 Python, 51 adapter/full frontend regression and 76 native unit/one parity checks passed. Physical web partial-sync/cancel/close, conclusive packaged delayed-navigation and clean-machine installation remain incomplete. Keep the PR draft.
