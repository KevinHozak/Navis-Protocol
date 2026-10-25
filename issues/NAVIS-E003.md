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