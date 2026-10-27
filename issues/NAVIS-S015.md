---
depends_on: ["NAVIS-S009","NAVIS-S010","NAVIS-S011","NAVIS-S012","NAVIS-S013","NAVIS-S014"]
id: "NAVIS-S015"
parent: ["NAVIS-E002"]
priority: "medium"
schema_version: 1
status: "done"
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
- [x] Demonstrate that the user can recognize stale/unavailable data, verify a saved change, inspect source support and understand failure/recovery without logs.
- [x] Record relevant automated results and separate web and packaged-desktop manual observations, with build/version and fixture details; source tests alone cannot pass packaged acceptance.
- [x] Verify no duplicate writes/awards, false-zero displays or false completion under selected failure cases. Any unavailable runtime or unresolved confirmed defect remains explicit and blocks affected acceptance.
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

Final selected 1.11.25 packaged check passed XP recovery/message reconciliation with one entry, one 12-XP award and preserved journal bytes. 94 Python, 51 adapter/full frontend regression and 76 native unit/one parity checks passed. Fresh packaged delayed-navigation now passes: A completed before its response was held, B was visibly selected before release, and A receipt left B unchanged; one append/12-XP row and preserved BOM/CRLF were verified. The earlier web confirmation blocker is superseded by the fresh passing checkpoint below. Fixture process trees were cleaned up. Clean-machine installation remains incomplete. Keep the PR draft.


## Fresh web checkpoint

The confirmation blocker was resolved with a fresh Edge InPrivate window and
native controls; production confirmation behavior is unchanged. Real confirmation
dismissal, running lock, partial-sync outcome, reconnect and Close Bridge passed
on a fresh isolated synthetic Vault. One sync POST, one work merge, one 14-XP
row and one backup-hook entry remained unchanged through reconnect and close.
The partial receipt stayed unreviewed. The isolated browser window and owned
fixture services were closed. Earlier blocked web attempts are superseded.

Remaining: clean-machine installation, physical Drive races/production integration
coverage and independent external review retain their documented limits. Keep
S015 and E002 open and PR #22 draft until affected acceptance passes or is
explicitly dispositioned. See the integrated report and sanitized JSON record.


## Accepted limits and final review

The user accepted the clean-machine installer and Drive/production integration
limits; they remain untested, not passed. Selected retained web and packaged
journeys passed. Final primary-agent review of PR #22 found no actionable issues;
no GitHub reviews, inline threads or conversation feedback were present.
Independent external review remains unavailable. Current application source is
unchanged from the verified release. S015 is in review; readiness does not close
this story or E002, and merge remains a separate action. This disposition
supersedes earlier draft/blocker statements above.


## Delivered closeout - 2026-10-27

PR #22 merged at 32cd24b6e0e7797e4e47b9869123177349ab4a7d and local main was fast-forwarded to that merge. The final review found no actionable issues; current-head CI passed before merge. Selected web and packaged journeys pass with sanitized evidence. Clean-machine installation and physical Drive/production integration coverage are user-accepted untested limits; independent external review remains unavailable. No untested limit is relabelled as passed. All retained S015 acceptance is reconciled under that disposition. Historical in-review and draft statements above are superseded.
