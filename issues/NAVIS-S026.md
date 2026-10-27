---
depends_on: ["NAVIS-S025"]
id: "NAVIS-S026"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "in_review"
title: "Bound explicit-root MCP search freshness work to its declared scope"
type: "bug"
---
## Outcome

Fix the live Documentation-root search timeout without implying that unchecked Vault roots are fresh.

## Evidence

The live chat returned deadline_exceeded after PR #13. A later identical live retry succeeded in 31,250 ms, demonstrating variability rather than a permanently broken connection. The explicit Documentation filter still ran both readability/freshness inventories over all 2,160 notes. A candidate scoped implementation returned the real result in 778 ms and performed only 34 Documentation probes (17 notes twice).

## Acceptance criteria

- [x] Explicit-root searches validate the requested subtree in both freshness passes, retain source digest checks and exclusions, and do not probe unrelated note trees.
- [x] Return current_for_scope plus validated/unvalidated roots; omitted-root search retains whole-index current/fail-closed semantics. Preserve file-prefix and case/Unicode matching behavior.
- [x] Fixture checks cover in-scope edits/additions/removals, unreadable nonmatches, post-query changes, policy boundaries, missing scopes and case handling; out-of-scope changes never become a false global-current claim.
- [x] Rerun the affected regression suite and current-source real-data search through an actual client; verify the current chat connection after reloading its old process, or keep that acceptance explicitly pending.
- [x] Document the scoped freshness contract and remaining exhaustive-query latency; keep writes disabled and private source content out of repository evidence.


## Verification

217 affected tests passed with one POSIX-only case-alias skip on Windows (63.30 seconds). Backend Ruff and whitespace checks pass. A fresh actual installed Codex client discovered MCP 0.4.2 and returned three source-verified Documentation searches in 291.153, 250.172 and 247.663 ms, with unchanged private index, four read tools, no model turn and a clean client exit. After the user restarted only navis_vault_readonly, three actual current-chat searches passed in 284, 247 and 226 ms, including lowercase-root matching. Each returned current_for_scope with Documentation validated and Journal/Operations unvalidated. The post-restart acceptance is complete. See docs/vault-mcp-live-search.md and docs/trials/vault-mcp-live-scope-2026-10-27.json. Independent external review remains unavailable.
