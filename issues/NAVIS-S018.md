---
depends_on: ["NAVIS-S017"]
id: "NAVIS-S018"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "open"
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

- [ ] Deliver search_vault and read_note using verified existing services/indexing where appropriate, with bounded snippets, relative source paths and section references.
- [ ] Report index freshness and handle changed, removed or unreadable notes; document refresh behavior without silently presenting stale results as current.
- [ ] Verify keyword/phrase retrieval, selected-section reads, output limits and excluded-path enforcement using synthetic notes.
- [ ] Distinguish no matches, missing notes, stale indexes and unavailable Drive/Vault errors without leaking excluded content.