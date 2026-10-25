---
depends_on: []
id: "NAVIS-S016"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "open"
title: "Evaluate MCP reuse and define the Navis-Vault access contract"
type: "enhancement"
---
## Outcome

Evaluate MCP reuse and define the Navis-Vault access contract.

## Target areas

Navis-Protocol backend Vault services, MCP adapter, configuration, fixture tests and operational documentation; exact modules are selected after inspection.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

Parent: [NAVIS-E003](NAVIS-E003.md).

## Acceptance criteria

- [ ] Inspect existing backend Vault services, FTS5 tooling and configured NAVIS_ROOT; distinguish verified capabilities from stale descriptions.
- [ ] Compare the linked Obsidian plugin with an independent Navis-Protocol adapter, including Obsidian uptime, transports, supported clients, maintenance and access controls; record the decision.
- [ ] Specify search_vault, read_note, get_journal_range and get_mission inputs, bounded outputs, provenance, error states and index freshness behavior.
- [ ] Define allowed roots/exclusions, symlink and path traversal policy, credential storage, logging redaction and client data-disclosure boundaries.