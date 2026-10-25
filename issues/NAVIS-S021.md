---
depends_on: ["NAVIS-S020"]
id: "NAVIS-S021"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "open"
title: "Add guarded journal appends after a passing read-only trial"
type: "enhancement"
---
## Outcome

Add guarded journal appends after a passing read-only trial.

## Target areas

Navis-Protocol backend Vault services, MCP adapter, configuration, fixture tests and operational documentation; exact modules are selected after inspection.

## Context and boundaries

Proposal from the Navis-Vault MCP discussion. Existing local skills describe direct file access and FTS5 search; current index health, backend reuse and client compatibility require verification. Reference: https://github.com/ebullient/obsidian-vault-mcp (Obsidian-hosted alternative, not a selected dependency). Prefer an independently runnable Navis-Protocol adapter if the evaluation supports it. Reuse authoritative services; do not create a second journal or XP authority.

Use disposable Vault fixtures and sanitized evidence. Keep private note content and credentials out of repository logs and fixtures. Local service access does not prevent an authorized client from sending retrieved text to its configured model. No hosted generation or schedules are introduced by this work.

Parent: [NAVIS-E003](NAVIS-E003.md).

## Acceptance criteria

- [ ] Proceed only after the trial records adoption and the journal mutation design reuses authoritative Navis services; otherwise retain this story open with an explicit scope decision.
- [ ] Expose only an explicitly enabled append_journal_entry operation with validated date/section and existing-file-only behavior; generic overwrite, delete and periodic-note creation remain unavailable.
- [ ] Preserve user content, UTF-8 BOM and line endings; detect conflicting edits, reject duplicate submissions and use atomic persistence with read-back verification.
- [ ] Reuse required ledger/sync semantics without duplicate XP or a competing write authority; report partial persistence accurately and provide safe retry/recovery behavior.
- [ ] Verify concurrent edits, retries, unavailable Drive, interrupted writes and encoding preservation in disposable fixtures before enabling writes on personal data.