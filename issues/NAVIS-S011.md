---
depends_on: ["NAVIS-S009"]
id: "NAVIS-S011"
parent: ["NAVIS-E002"]
priority: "high"
schema_version: 1
status: "done"
title: "Distinguish unavailable data from valid empty and zero results"
type: "enhancement"
---
## Outcome

Distinguish unavailable data from valid empty and zero results.

Parent: [NAVIS-E002](NAVIS-E002.md). Depends on [NAVIS-S009](NAVIS-S009.md).

## Target areas

Only confirmed response/UI gaps in affected backend/native contracts and consumers.

## Acceptance criteria

- [x] Before implementation, link confirmed audit findings and document the affected state contract without assuming all views need changes.
- [x] Represent loading, valid empty results, measured zero, missing records, dependency failure and unsupported native routes accurately where applicable; do not coerce failures to zero or an empty success.
- [x] Provide clear user-facing states and applicable recovery actions while preserving legitimate existing empty/zero behavior and retained data provenance.
- [x] Exercise representative missing/corrupt source, unavailable backend/native dependency, empty result and real zero fixtures; verify web/native behavior and meaningful regression checks.

## Scope and verification

Follow the parent epic's audit-first gate, privacy and runtime evidence requirements. The user selected S011 after accepting S013's PR #18 merge and explicitly authorized separate codex-branch/PR delivery. The affected [availability contract](../docs/journal-availability.md) narrows T02 to calendar failure/recovery and remaining parser/day/sector states; S013's implemented evidence/zero behavior is reused.


## S009 audit disposition - 2026-10-27

T02: distinguish missing/unreadable/partial Holocron journal and progression inputs from valid zero; retain day/source coverage. Repair calendar HTTP/error handling so unavailable months do not appear empty. Preserve command readiness and task-board unavailable/zero handling already implemented.

Evidence and fixture reproduction: [trust-signals audit](../docs/trust-signals-audit.md) and [sanitized source/check record](../docs/trials/navis-trust-audit-2026-10-27.json). All repair criteria remain pending.

## Implementation and verification - 2026-10-27

Calendar web/native reads now distinguish unavailable sources from readable empty
months. The shared UI validates responses, exposes loading/error/unsupported and
retry states, pauses unverified selection and rejects late month responses.
Holocron parser failures no longer count as readable zero-task days; missing daily
and sector counts are unavailable while genuine 0%/0 XP values remain valid.

50 affected Python tests, 51 adapter tests, the full frontend regression runner,
75 serial Rust unit tests and one parity integration test passed. The personal
Vault probe is excluded. Release 1.11.22 metadata, all 38 resources and actual
packaged unavailable-to-empty-to-entry recovery passed. Ruff, lint with existing
warnings and whitespace passed. See the [contract, artifact identity and retained
runtime limits](../docs/journal-availability.md). No personal Vault operation or live
provider call was performed. Status remains in_review pending PR acceptance;
independent external review is unavailable.

## Accepted merge - 2026-10-27

The user authorized merge after both current-head scans passed and PR readiness
was verified. PR #19 merged as `9408bd14dbdda3ce1fa7acca5f1e3efa46662c16`;
local main was fast-forwarded and verified clean at that commit. S011 closes
within the documented fixture/runtime limits; broader S015 journeys remain open.
