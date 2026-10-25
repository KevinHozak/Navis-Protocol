---
depends_on: ["NAVIS-S016"]
id: "NAVIS-S017"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "open"
title: "Implement the read-only MCP server and access boundary"
type: "enhancement"
---
## Outcome

Implement the read-only MCP server and access boundary.

## Target areas

Navis-Protocol backend Vault services, MCP adapter, configuration, fixture tests and operational documentation; exact modules are selected after inspection.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

Parent: [NAVIS-E003](NAVIS-E003.md).

## Acceptance criteria

- [ ] Implement the chosen adapter under Navis-Protocol with no dependency on a running Obsidian app unless the prior decision explicitly justifies it.
- [ ] Honor configured NAVIS_ROOT; expose only approved read capabilities and bounded responses. Reject traversal, absolute-path escapes and symlink escapes in disposable-fixture checks.
- [ ] Document and verify start, stop, reconnect and unavailable-Vault behavior for the selected transport; use loopback binding and authentication for HTTP, or explicit process access for stdio.
- [ ] Credentials and private content are excluded from logs; no generic shell execution, write tools, automatic sync, XP changes or model calls are exposed.