---
depends_on: ["NAVIS-S016"]
id: "NAVIS-S017"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "done"
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

- [x] Implement the chosen adapter under Navis-Protocol with no dependency on a running Obsidian app unless the prior decision explicitly justifies it.
- [x] Honor configured NAVIS_ROOT; expose only approved read capabilities and bounded responses. Reject traversal, absolute-path escapes and symlink escapes in disposable-fixture checks.
- [x] Document and verify start, stop, reconnect and unavailable-Vault behavior for the selected transport; use loopback binding and authentication for HTTP, or explicit process access for stdio.
- [x] Credentials and private content are excluded from logs; no generic shell execution, write tools, automatic sync, XP changes or model calls are exposed.

## Completion evidence

- Implemented [standalone stdio adapter](../backend/navis_vault_mcp.py) with official MCP SDK 2.3.0 in a separate requirements file. The only advertised tool is the bounded, source-linked read_note operation.
- Shared path containment extracted without changing the HTTP contract; MCP policy adds explicit root/exclusion configuration, reparse-point denial, strict inputs, file/response/deadline limits and redacted errors.
- [Operating guide](../docs/vault-mcp.md) documents startup, EOF shutdown, fresh-process reconnect, unavailable roots, cancellation limits and client ownership.
- Final isolated Windows verification: 68 MCP/HTTP path/journal tests passed; backend Ruff passed; frontend lint passed with existing warnings; pip dependency check passed. Includes real stdio subprocesses, actual symlinks/junctions, denied paths, unavailable roots, malformed frames, timeout recovery, lossless continuation and fixture-byte preservation.
- Source audit complete with no remaining actionable findings; independent external review unavailable. No personal Vault access, client configuration install, hosted model call, state sync or write tool was used/enabled.
- S018 search, S019 journal/mission tools, S020 client adoption and S021 guarded writes remain open. Desktop app sources/version are unchanged; this is a separate Python MCP entrypoint.