---
depends_on: ["NAVIS-S021"]
id: "NAVIS-S025"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "done"
title: "Remove serial Drive inventory bottlenecks and verify broader read-only MCP coverage"
type: "bug"
---
## Outcome

Fix the measured broad-Vault timeout while retaining fail-closed freshness and access checks; rerun the authorized real-Vault read-only pilot with broader coverage.

## Evidence

The initial full-policy pilot exceeded a 30-second inventory deadline. Profiling reached only 418 readability opens: 12.9 seconds opening files and 15.2 seconds repeatedly resolving paths. A metadata-only walk found 2,160 allowed Markdown notes in 0.8 seconds. The working 45-note pilot and index must remain recoverable until broader setup is verified.

## Acceptance criteria

- [x] Bound concurrent filesystem work and memory; retain readability checks for every allowed note, path/link/root identity checks, file/inventory caps, pre/post freshness inventories and atomic generation publication.
- [x] Verify unreadable nonmatches, changed/replaced directories/files, deadline failures, exclusions, stale results and failed-build generation retention with disposable fixtures.
- [x] Rebuild and search all configured broad roots within an explicit capped scan budget; retain the ten-second default, configure broader scopes deliberately, and never expose a stale-result cache.
- [x] Run a broader actual-Codex read-only pilot against direct source provenance; report scope, latency, omissions/unresolved context and integrity without private text or source names.
- [x] Preserve unrelated client configuration and the working narrow setup; keep append disabled and record remaining human/Drive limits.

## Measured scope adjustment

The optimized complete inventory takes 10.5 seconds for 2,160 notes and an atomic rebuild takes 52.9 seconds on this real Drive. Keeping exhaustive readability checks under a fixed ten-second budget is not supported by the measurements. The implementation therefore retains the ten-second default and adds a validated 1–120 second opt-in budget for exhaustive search/mission discovery and operator rebuilds. The broad pilot uses 60 seconds; ordinary note/journal reads retain ten seconds. No TTL cache or stale evidence is introduced.

## Verification and delivery

209 affected Python tests passed (47.55 seconds), including race, readability, path/link, short-read, cleanup and scan-budget isolation cases. Backend Ruff and whitespace checks pass. MCP version is 0.4.1; the unchanged frontend app-source profile reuses desktop version 1.11.18.

The broader actual-Codex pilot indexed all 2,160 notes under Journal/Operations/Documentation and verified 19 real sources over three repetitions. It checked seven recent journals and an archived range with four present and three genuinely absent dates. Four mission links remain explicitly unresolved; no observed scoped source changes, write tools or model turns occurred. Median exhaustive search was 15,714.832 ms within the explicit 60-second budget; ordinary read deadlines and fail-closed freshness/readability remain intact. The earlier narrow index and pre-expansion configuration backup are retained privately. See docs/vault-mcp-inventory-performance.md and docs/trials/vault-mcp-broad-pilot-2026-10-27.json for source-bound evidence and remaining limits. Independent external review remains unavailable.


## Closeout — 2026-10-27

PR #13 merged as 900c8bf735fb1ca53abe20749a57f70cbfa14f51. All retained acceptance criteria are checked and the merged verification evidence is recorded above. S026 additionally passed three actual current-chat post-restart searches in 226–284 ms. Remaining human workflow and broader runtime evaluation belongs to NAVIS-E003; personal writes remain disabled.
