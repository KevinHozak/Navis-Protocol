---
depends_on: ["NAVIS-S018"]
id: "NAVIS-S019"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "open"
title: "Expose date-bounded journal and mission retrieval"
type: "enhancement"
---
## Outcome

Expose date-bounded journal and mission retrieval.

## Target areas

Navis-Protocol backend Vault services, MCP adapter, configuration, fixture tests and operational documentation; exact modules are selected after inspection.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

Parent: [NAVIS-E003](NAVIS-E003.md).

## Acceptance criteria

- [ ] Deliver get_journal_range with explicit inclusive date bounds, configured Navis timezone, result limits and canonical Journal/YYYY/MM/YYYY-MM-DD.md resolution.
- [ ] Missing dates are reported explicitly; reads never initialize journals, trigger rollover, synchronize state or award XP.
- [ ] Deliver get_mission using existing mission structure and return source-linked details and bounded related-note context; ambiguous mission names require disambiguation.
- [ ] Verify month/year boundaries, missing journals, duplicate mission names and unavailable Vault behavior with disposable fixtures.