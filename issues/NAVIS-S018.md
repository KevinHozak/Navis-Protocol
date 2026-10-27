---
depends_on: ["NAVIS-S017"]
id: "NAVIS-S018"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "done"
title: "Expose source-linked Vault search and bounded note reads"
type: "enhancement"
---
## Outcome

Expose source-linked Vault search and bounded note reads.

## Target areas

Navis-Protocol backend Vault services, MCP adapter, configuration, fixture tests and operational documentation; exact modules are selected after inspection.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

Parent: [NAVIS-E003](NAVIS-E003.md).

## Acceptance criteria

- [x] Deliver search_vault and read_note using verified existing services/indexing where appropriate, with bounded snippets, relative source paths and section references.
- [x] Report index freshness and handle changed, removed or unreadable notes; document refresh behavior without silently presenting stale results as current.
- [x] Verify keyword/phrase retrieval, selected-section reads, output limits and excluded-path enforcement using synthetic notes.
- [x] Distinguish no matches, missing notes, stale indexes and unavailable Drive/Vault errors without leaking excluded content.

## Completion evidence

- [search_vault service](../backend/services/vault_index.py) reuses the shared access policy, snapshot/provenance readers and SQLite FTS5. The [stdio adapter](../backend/navis_vault_mcp.py) advertises only read_note and search_vault; the [rebuild CLI](../backend/navis_vault_index.py) is an explicit local operator action, not an MCP tool.
- [Operating guide](../docs/vault-mcp.md) documents private state, refresh/error states, file/inventory/response/deadline bounds, literal keyword/phrase syntax and remaining freshness limits.
- Synthetic acceptance verifies source snippets and physical section references, selected-section note reads, Unicode/budget behavior, missing/empty/stale/unavailable states, added/removed/renamed/unreadable notes, exclusions and actual junctions, failed-generation retention, incomplete/corrupt indexes and real CLI/stdio search.
- Source audit found and repaired incomplete-index detection, plural credential/secret exclusions, Windows directory metadata identity and heading/hash/fence handling. Final affected tests, backend Ruff, frontend lint (existing warnings) and dependency checks passed. Independent external review is unavailable.
- No personal Vault was indexed or read. Only disposable fixtures and a private test-state directory were used. No write tools, schedules, model calls, XP mutations or automatic Vault synchronization were introduced.
- S019 journal/mission retrieval, S020 client/adoption trial and S021 guarded writes remain open. Frontend/Tauri sources and prepared version remain unchanged; the standalone MCP adapter reports 0.2.0.