---
depends_on: ["NAVIS-S018"]
id: "NAVIS-S019"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "done"
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

- [x] Deliver get_journal_range with explicit inclusive date bounds, configured Navis timezone, result limits and canonical Journal/YYYY/MM/YYYY-MM-DD.md resolution.
- [x] Missing dates are reported explicitly; reads never initialize journals, trigger rollover, synchronize state or award XP.
- [x] Deliver get_mission using existing mission structure and return source-linked details and bounded related-note context; ambiguous mission names require disambiguation.
- [x] Verify month/year boundaries, missing journals, duplicate mission names and unavailable Vault behavior with disposable fixtures.

## Completion evidence

- [Retrieval service](../backend/services/vault_retrieval.py) and [stdio adapter](../backend/navis_vault_mcp.py) add get_journal_range and get_mission through the existing access policy and source-linked note reader.
- Journal reads use strict inclusive calendar dates, configured timezone metadata, canonical paths, explicit missing dates and byte/character/line continuation. They never create journals, run rollover/sync or award XP.
- Mission reads cover the existing Main/Side directory structure, exact selectors, bounded duplicate-name candidates and bounded context from explicit internal links. Related context does not recursively expand or fetch external URLs; denied/unresolved targets disclose no additional path metadata.
- [Operating guide](../docs/vault-mcp.md) documents the tools, limits, pagination, ambiguity, link semantics and remaining client/adoption boundaries.
- Final isolated Windows acceptance: 149 retrieval/search/MCP/shared HTTP tests passed. Includes month/year/leap-day/maximum-date boundaries, missing versus unreadable/denied journals, pagination/continuation, duplicate missions, Unicode paths, budgets, junctions, internal-only context and real stdio calls without an index.
- Backend Ruff, frontend lint (existing warnings), dependency checks, source audit and document-link checks passed. Independent external review is unavailable. No personal Vault was accessed; fixture files and XP-state sentinels remained unchanged.
- S020 client/adoption trial and S021 guarded writes remain open. The standalone MCP adapter reports 0.3.0; frontend/Tauri source and prepared version are unchanged.