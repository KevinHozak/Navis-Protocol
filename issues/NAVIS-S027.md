---
depends_on: []
id: "NAVIS-S027"
parent: []
priority: "medium"
schema_version: 1
status: "in_progress"
title: "Share Vault retrieval services across web, Tauri and MCP adapters"
type: "enhancement"
---
## Outcome

Use the same import-safe Vault domain functions for matching read operations in the web, Tauri and MCP interfaces, while keeping MCP as a separate client transport.

## Context

The MCP work added a standalone stdio adapter and bounded Vault access/retrieval services. The web and Tauri app use HTTP and native IPC adapters for broader application workflows. Journal append already uses the shared `services/journal_entry` implementation across HTTP, Tauri and the opt-in MCP adapter; MCP append remains disabled by default.

Do not route application calls through the MCP process or protocol. Share domain behavior directly, preserve each interface contract, and keep the MCP allow/deny policy narrower than general app access. App-specific sync, rendering and state workflows can remain in their current services.

## Target areas

`backend/services/vault_access.py`, `vault_retrieval.py`, `vault_index.py`, FastAPI endpoints, Tauri/Python bridges, the MCP adapter, isolated fixture coverage and Vault MCP documentation.

## Acceptance criteria

- [ ] Inventory current HTTP, native IPC and MCP Vault read operations; select one or more operations with matching domain semantics and document intentionally separate workflows.
- [ ] Ensure each selected operation has one import-safe domain implementation with an explicit Vault root and caller access context; have HTTP, Tauri and MCP adapters call it directly without an MCP JSON-RPC subprocess hop.
- [ ] Preserve existing HTTP and IPC response shapes, error behavior, bounded reads and source provenance. Keep MCP allow/deny roots and sensitive-path rules enforced at the MCP boundary; sharing must not broaden MCP access.
- [ ] Verify the selected operation through isolated fixtures on HTTP, native IPC/Python bridge and MCP stdio, checking equivalent domain results plus each interface's access denials and missing/unreadable behavior. Confirm no live Vault data is required or changed.
- [ ] Retain the existing shared journal-append authority and keep MCP append disabled by default; do not add general write, sync or XP behavior to this work.
- [ ] Update the architecture guide with the shared service, transport adapters, explicit access-policy differences and excluded app-specific operations.

## Privacy and scope

Use disposable synthetic Vaults for verification. Do not enable personal-data MCP writes, add another Vault index or data authority, or restructure unrelated direct Vault operations without evidence that they share the selected domain semantics.