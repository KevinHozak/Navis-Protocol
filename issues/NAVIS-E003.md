---
depends_on: []
id: "NAVIS-E003"
parent: []
priority: "medium"
schema_version: 1
status: "open"
title: "Provide safe, consistent Navis-Vault access through MCP"
type: "epic"
---
## Outcome

Provide consistent, source-linked Navis-Vault access to MCP clients, beginning with read-only retrieval and adding narrowly scoped journal writes only after a successful trial.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

## Acceptance criteria

- [ ] Evidence-backed reuse/build decision defines the service boundary, supported clients and deployment lifecycle.
- [ ] Read-only search, note reads, journal ranges and mission retrieval preserve source provenance and distinguish unavailable data from empty results.
- [ ] A measured trial demonstrates retrieval accuracy and correction time against the existing workflow, with an explicit adoption decision.
- [ ] Any retained write scope passes append-only integrity, concurrency, duplicate-submit and persistence verification gates before enablement.
- [ ] All retained child criteria and runtime evidence are reconciled before completion; unsupported client/runtime cases remain explicit.

## Stories

- [NAVIS-S016](NAVIS-S016.md): Evaluate MCP reuse and define the Navis-Vault access contract
- [NAVIS-S017](NAVIS-S017.md): Implement the read-only MCP server and access boundary
- [NAVIS-S018](NAVIS-S018.md): Expose source-linked Vault search and bounded note reads
- [NAVIS-S019](NAVIS-S019.md): Expose date-bounded journal and mission retrieval
- [NAVIS-S020](NAVIS-S020.md): Trial MCP retrieval against the existing Vault workflow
- [NAVIS-S021](NAVIS-S021.md): Add guarded journal appends after a passing read-only trial

## Real-Vault pilot checkpoint — 2026-10-27

All six implementation stories are merged; S021 is now done following PR #12 (3a11dc064dcd81f8234d2c03f34486e0239166f1). The requested real-Vault read-only pilot configured navis_vault_readonly in the installed Codex client and verified MCP 0.4.0 using the persisted entry. See [pilot record](../docs/vault-mcp-real-pilot.md) and [sanitized results](../docs/trials/vault-mcp-real-pilot-2026-10-27.json).

The scoped pilot indexed 45 real notes and independently verified 14 sources over three repetitions, including seven journal dates and one mission with related context. Scoped source hashes remained unchanged, only four read tools were available, and no model turn or Vault write was requested. An initial broad-policy inventory exceeded a 30-second deadline; the retained configuration covers the recent journal month, Documentation and one canonical mission directory. Four mission links remain explicitly unresolved. Human correction time, preference, interactive desktop setup and broader real-Vault performance remain unverified. The epic remains open pending acceptance reconciliation of these limits; personal writes remain disabled.


## Broad coverage follow-up

- [NAVIS-S025](NAVIS-S025.md): Remove serial Drive inventory bottlenecks and verify broader read-only MCP coverage. The retained configuration now covers 2,160 notes across Journal, Operations and Documentation with an explicit 60-second exhaustive-scan budget (ten-second default retained). The final pilot verified 19 sources, recent and archived journal ranges, and unchanged scoped source hashes. [Performance and pilot evidence](../docs/vault-mcp-inventory-performance.md). Human effort, interactive desktop use and simultaneous-client/physical Drive concurrency remain unverified; writes remain disabled.


## Live scoped-search follow-up

- [NAVIS-S026](NAVIS-S026.md): Explicit-root queries now validate their own subtree and report current_for_scope with unvalidated roots. A live pre-fix Documentation retry took 31.25 seconds; a fresh actual Codex connection with the candidate took 248–291 ms with source provenance verified. After the user restarted the server, three current-chat searches passed in 226–284 ms with the expected scoped coverage; post-restart acceptance is complete. [Contract and evidence](../docs/vault-mcp-live-search.md). Unfiltered searches retain exhaustive validation and their existing latency/deadline limits.
