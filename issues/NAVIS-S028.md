---
depends_on: []
id: "NAVIS-S028"
parent: []
priority: "medium"
schema_version: 1
status: "in_review"
title: "Migrate Navis text generation from Ollama to OpenRouter"
type: "enhancement"
---
## Outcome

Replace Navis-Protocol's Ollama-dependent text generation with an explicitly configured OpenRouter provider across web and packaged Tauri workflows, preserving feature-specific validation and user control over external data transmission and spend.

## Context

User requested the migration after New Day reported local Ollama unavailable/timed out. Source inspection confirms a shared TextProvider/get_provider boundary, plus direct Ollama calls that would bypass a simple provider switch. No matching local migration issue was found. The original record authorized planning only. The user selected implementation on 2026-10-31, explicitly requiring cloud generation to remain disabled until configured.

## Target areas

- backend/services/ai_provider.py and the existing online_ai accounting/guard design.
- Forge, Reid/conversation services, squad banter and Weekly Holocron synthesis.
- Actionable briefs, journal polishing, tray/background generation and remaining direct localhost:11434 call sites.
- frontend/src/lib/desktopApi.js, provider capability checks, provider-specific labels/errors, native p5/ollama routes and packaged resources.

## Acceptance criteria

- [x] Inventory every Ollama-dependent text-generation path and document whether it migrates, remains intentionally local, or is retired. Cover shared-provider and direct HTTP/native callers; exclude unrelated deterministic Vault/MCP functions.
- [x] Implement a shared OpenRouter adapter with explicit server/native configuration for credentials, model IDs, feature routing, timeouts and output limits. Replace hard-coded Ollama bypasses for migrated features; absent/invalid configuration fails visibly rather than silently choosing another provider or model.
- [x] Keep API keys out of browser bundles, NEXT_PUBLIC variables, Vault documents, tracked files, logs and exports. Backend/native code owns authenticated requests; UI receives safe provider/capability diagnostics only.
- [x] Define and document which selected source text or telemetry each feature transmits externally. Require explicit enablement for cloud generation and separately configurable background/rollover generation; opening a view, starting the app or retrying status reads must not introduce unapproved paid requests.
- [x] Reuse or extend the existing online-generation safeguards for bounded requests, usage/cost accounting and per-feature budgets. Handle unknown usage/cost honestly, prevent retries after ambiguous paid outcomes from silently multiplying charges, and define model-change/pricing-review behavior without assuming current prices.
- [x] Preserve reviewed brief source constraints, original retention, knowledge-note provenance, editable suggestions and explicit saves. Generation must not create tasks/commitments, rewrite originals or broaden retrieval permissions. Retain deterministic Holocron fallback and do not label unavailable/failed banter as generated successfully.
- [x] Update web and packaged Tauri capability gating, controls, labels, documentation and diagnostics to reflect the configured provider rather than assuming local Ollama. Preserve hosted-client boundaries; do not expose arbitrary remote endpoints or secrets through IPC.
- [ ] Cover success, missing key/model, authentication/rate-limit errors, timeout, malformed/empty/unsupported output, disabled generation, budget exhaustion and ambiguous retry behavior with mocked provider responses. Verify migrated features and fallback/source-preservation behavior with fresh isolated web/native fixtures and packaged resource checks.
- [x] Perform only explicitly authorized live smoke calls with synthetic input and a declared spending limit; keep personal-Vault content out of provider trials unless separately authorized. Document rollout, configuration migration and rollback without silently enabling a second provider.

## Scope and limits

One standalone migration story; no inferred dependency on S007/S008 or the completed MCP epic. Choose exact model IDs and budgets during implementation/configuration review, not by guessing a default here. The historical local-first rules in S002/S006 describe their delivered behavior; update those contracts deliberately for the selected cloud path while preserving their factual and save safeguards. Retaining Ollama as an optional provider is an implementation decision to document, not an automatic paid fallback or a requirement to keep the daemon running.

## Implementation selected - 2026-10-31

User authorized implementation and a codex PR after verification. All cloud generation must remain disabled until explicitly configured; no model, key, budget or paid smoke call was authorized. Mock-only verification.

## Verified implementation and retained gate - 2026-10-31

Shared OpenRouter provider, feature/model/endpoint/price review and budget guards,
safe unknown-cost holds, web/native Python routing, original-preserving polishing
and briefs, provider-neutral labels, explicit background gating and truthful banter
availability are implemented. The native local socket bypass and startup preload
are retired. Explicit local rollback is loopback-only; no automatic provider fallback.
The separately delivered Portal Forge injection remains under its own existing
configuration and budget contract, not silently enabled or recertified here.

[Inventory, configuration, transmission and rollback](../docs/openrouter-text-generation.md).
Final affected Python checks: 95 passed, 1 symlink skip, 5 subtests; 81 native tests;
full frontend suite including 53 transport cases; Ruff; release/NSIS 1.11.36 and
51 resource hashes match source. Fresh web UI denied polish/brief generation and
preserved the synthetic draft. Copied packaged Python helpers denied generation
without Vault/accounting writes. No live OpenRouter call, model choice, key setup,
configuration enablement or personal-Vault transmission occurred.

Native executable UI smoke remains unverified: the fixture window/process exists,
but the computer-use helper could not activate/restore it or expose its document.
Do not substitute copied Python helper tests for this UI check. Publish as draft
and retain this gate; do not close S028 or claim live provider/model quality.
