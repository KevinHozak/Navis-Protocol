---
depends_on: []
id: "NAVIS-E003"
parent: []
priority: "medium"
schema_version: 1
status: "done"
title: "Provide safe, consistent Navis-Vault access through MCP"
type: "epic"
---
## Outcome

Provide consistent, source-linked Navis-Vault access to MCP clients, beginning with read-only retrieval and adding narrowly scoped journal writes only after a successful trial.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

## Acceptance criteria

- [x] Evidence-backed reuse/build decision defines the service boundary, supported clients and deployment lifecycle.
- [x] Read-only search, note reads, journal ranges and mission retrieval preserve source provenance and distinguish unavailable data from empty results.
- [x] A measured trial and controlled read-only adoption are recorded; the user explicitly accepts unmeasured human correction time and documented evidence limits.
- [x] Any retained write scope passes append-only integrity, concurrency, duplicate-submit and persistence verification gates before enablement.
- [x] All retained child criteria and runtime evidence are reconciled before completion; unsupported client/runtime cases remain explicit.

## Stories

- [NAVIS-S016](NAVIS-S016.md): Evaluate MCP reuse and define the Navis-Vault access contract
- [NAVIS-S017](NAVIS-S017.md): Implement the read-only MCP server and access boundary
- [NAVIS-S018](NAVIS-S018.md): Expose source-linked Vault search and bounded note reads
- [NAVIS-S019](NAVIS-S019.md): Expose date-bounded journal and mission retrieval
- [NAVIS-S020](NAVIS-S020.md): Trial MCP retrieval against the existing Vault workflow
- [NAVIS-S021](NAVIS-S021.md): Add guarded journal appends after a passing read-only trial

## Completion and accepted scope - 2026-10-27

The user explicitly accepted controlled read-only adoption with documented limits
and requested closure. All eight child stories are done, including
[S025](NAVIS-S025.md) after PR #13 and [S026](NAVIS-S026.md) after PR #14.
S016/S017 define service/client lifecycle; S018/S019 verify provenance and
unavailable/empty distinctions; S020 records fixture comparison and adoption;
S021 verifies guarded append integrity on disposable fixtures.

The real workflow completed journal pagination, mission context and a
user-confirmed topic match. User feedback is useful/no corrections needed.
The trial criterion is accepted with explicit exceptions: human correction time
remains unmeasured; topic confirmation after retrieval is not a blinded accuracy
test; no fresh direct-source/baseline comparison was made in this run. Prior
source-verified fixture/pilot evidence is retained separately. Automatic approval
review rejected private-text duplication, which was not pursued.

Four mission omissions are reviewed: one non-Markdown target, two external URIs
and one missing Markdown note. No target was fetched or repaired. Stale-index
recovery required a failed 60-second rebuild and a successful 66.143-second retry
under a temporary 120-second budget. Saved client settings were unchanged.

Adoption covers the verified local Codex read-only connection. Claude Desktop,
simultaneous clients, cold hydration, multi-device Drive races and personal-data
writes remain unverified. Broad search remains slower; scoped freshness covers
only the declared scope. Writes remain disabled. These limits are explicitly
accepted for closure, not converted into passing tests or write enablement.

See [adoption record](../docs/vault-mcp-real-workflow.md),
[sanitized report](../docs/trials/vault-mcp-real-workflow-2026-10-27.json),
[broad pilot](../docs/vault-mcp-inventory-performance.md) and
[live search](../docs/vault-mcp-live-search.md).
