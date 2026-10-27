---
depends_on: ["NAVIS-S019"]
id: "NAVIS-S020"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "done"
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

- [x] Connect and verify the intended primary MCP client; verify a second intended client or explicitly record unsupported compatibility before claiming cross-client support.
- [x] Compare finding a past decision, reviewing a week of journals and retrieving a mission with related context against the existing file/search workflow.
- [x] Record source correctness, omissions, retrieval latency, correction time, index freshness and setup/maintenance effort using a predefined evaluation rubric and sanitized results.
- [x] Record adopt, revise or stop with evidence and known runtime limits; document operating instructions and keep all write tools disabled during the trial.

## Completion evidence

- [Predefined rubric](../docs/vault-mcp-trial-rubric.md), [repeatable runner](../backend/scripts/vault_mcp_trial.py), [sanitized report](../docs/trials/vault-mcp-s020.json) and [decision/operating record](../docs/vault-mcp-trial-results.md).
- Actual desktop-bundled Codex app-server 0.164.0-alpha.11.1 connected to Navis MCP 0.3.0, discovered all four read-only tools and executed the decision/week/mission workflows through Codex's own MCP client. An ephemeral technical context had no history path; no model turn was requested and persistent MCP configuration remained unchanged.
- Five alternating repetitions compared scripted direct file/search reads with Codex MCP. All ten required sources per repetition were correct with zero unexpected omissions. Latency, setup and recovery measurements are recorded in the source-bound machine report; the predefined fixture latency gate passed.
- A deliberately modified note produced index_stale without stale evidence. Explicit rebuild plus retry recovered within the measured bound in the linked machine report. Fixture/XP hashes were preserved apart from that intentional edit. Human correction time and preference were not measured; setup/runtime/maintenance limits are explicit.
- Decision: adopt a controlled read-only pilot on the verified Codex runtime and synthetic corpus. Running desktop settings/composer UI, personal-Vault scale and Claude Desktop are unverified and outside the supported adoption scope. No cross-client support or production configuration is claimed.
- Final verification: 157 oracle/retrieval/search/MCP/shared HTTP tests passed; backend Ruff, dependency checks, source audit, document links and source-identity checks passed. Independent external review is unavailable.
- S021 guarded journal writes remain open and disabled. No personal Vault access, persistent client registration, scheduled monitor or model generation was introduced. Frontend/Tauri source and prepared version are unchanged.