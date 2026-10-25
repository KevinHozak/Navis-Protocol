---
depends_on: ["NAVIS-S019"]
id: "NAVIS-S020"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "open"
title: "Trial MCP retrieval against the existing Vault workflow"
type: "enhancement"
---
## Outcome

Trial MCP retrieval against the existing Vault workflow.

## Target areas

Navis-Protocol backend Vault services, MCP adapter, configuration, fixture tests and operational documentation; exact modules are selected after inspection.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

Parent: [NAVIS-E003](NAVIS-E003.md).

## Acceptance criteria

- [ ] Connect and verify the intended primary MCP client; verify a second intended client or explicitly record unsupported compatibility before claiming cross-client support.
- [ ] Compare finding a past decision, reviewing a week of journals and retrieving a mission with related context against the existing file/search workflow.
- [ ] Record source correctness, omissions, retrieval latency, correction time, index freshness and setup/maintenance effort using a predefined evaluation rubric and sanitized results.
- [ ] Record adopt, revise or stop with evidence and known runtime limits; document operating instructions and keep all write tools disabled during the trial.