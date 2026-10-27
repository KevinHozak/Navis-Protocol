---
depends_on: ["NAVIS-S020"]
id: "NAVIS-S021"
parent: ["NAVIS-E003"]
priority: "medium"
schema_version: 1
status: "done"
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

- [x] Proceed only after the trial records adoption and the journal mutation design reuses authoritative Navis services; otherwise retain this story open with an explicit scope decision.
- [x] Expose only an explicitly enabled append_journal_entry operation with validated date/section and existing-file-only behavior; generic overwrite, delete and periodic-note creation remain unavailable.
- [x] Preserve user content, UTF-8 BOM and line endings; detect conflicting edits, reject duplicate submissions and use atomic persistence with read-back verification.
- [x] Reuse required ledger/sync semantics without duplicate XP or a competing write authority; report partial persistence accurately and provide safe retry/recovery behavior.
- [x] Verify concurrent edits, retries, unavailable Drive, interrupted writes and encoding preservation in disposable fixtures before enabling writes on personal data.

## Verification and delivery

S020's adoption gate is recorded in docs/vault-mcp-trial-results.md and merged PR #11 (99266467f2c9c5927f2fafe19e7b8de8461808aa).

Implemented one shared HTTP/desktop/MCP append service, disabled-by-default MCP opt-in, hash conflicts, durable intent/replay recovery, byte-preserving insertion and read-back, and canonical RPG/ledger reconciliation with explicit saved_xp_pending. See docs/vault-mcp-journal-appends.md for operation, recovery and noncooperating-writer limits. No personal-data enablement or installer deployment occurred.

Verification: 188 affected Python tests passed, including real ledger projection failure/retry and real stdio writes on synthetic fixtures. All 71 native library tests passed with --test-threads=1; the parallel suite races on existing process-wide environment changes. Corrected an existing provider-redaction test fixture to establish War Room's required active squad while retaining its empty-squad 400 assertion. Frontend unit/regression suite, lint (existing warnings), backend Ruff and diff whitespace checks passed. Desktop version prepared as 1.11.18. Build and PR checks are recorded separately after completion; independent external review remains unavailable unless observed.

Desktop frontend production build (npm --prefix frontend run build:desktop) passed. Source-level delivery audit found no remaining actionable findings. Personal Vault writes, packaged installer execution, real Drive synchronization races and independent external review were not exercised; writes remain opt-in and disabled in the delivered configuration.


## Closeout — 2026-10-27

PR #12 merged at 2026-10-27T07:07:07Z as 3a11dc064dcd81f8234d2c03f34486e0239166f1. Final audited source passed 191 affected Python tests and 71 serial native library tests, frontend regressions/lint/build and both GitHub secret-scan checks. All retained story criteria are accepted within the documented disposable-fixture and cooperating-writer scope. Personal-data writes remain disabled; read-only real-Vault pilot is a separate follow-up requested by the user.
