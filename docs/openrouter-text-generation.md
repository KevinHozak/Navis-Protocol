# Configured text generation (S028)

Cloud generation ships **disabled**. The user explicitly requested that it stay
disabled until configured. No API key, model choice, live paid call or personal-Vault
transmission was authorized during implementation. Configuration examples below do
not enable anything automatically. Do not put keys into browser variables or Vault
documents. No new subscriptions or scheduled generation are introduced.

## Path inventory

| Path | Disposition |
| --- | --- |
| Forge, Reid, Neural chat, War Room | Shared `get_provider`; default OpenRouter adapter, denied without complete configuration. Existing validators, proposal approval and saved-context rules retained. |
| Actionable briefs | Direct local HTTP sender replaced with shared `brief` route; numbered source selection, original retention and explicit save unchanged. |
| Journal polishing | Web/native share `journal_polish`; original recovery, formatting/checklist validation and explicit append retained. Old native polish IPC command is unregistered and its socket sender retired. |
| Squad banter | Shared `banter` route; explicit native request delegates to packaged Python. Legacy native socket sender retired. Rollover passes `background=True` and separately requires permission. Failed/disabled generation is no longer logged as generated successfully. |
| Weekly Holocron | Explicit synthesis uses shared `holocron` route; rule-based fallback remains. OpenRouter output labelled AI interpretation, including exports and persisted regeneration. Opening a view only reads/aggregates deterministic data. |
| Dynamic single quote GET | Generation retired; saved/profile/deterministic quotes only. No paid view-triggered request. |
| Tray startup preload | Retired. No empty generation request on startup. |
| Local rollback and historical benchmark | Ollama adapter remains only when `NAVIS_AI_PROVIDER=ollama` is explicitly selected. No automatic local/cloud fallback. Historical benchmark/legacy Gemini accounting is separate; migrated shared features reject `gemini`. |
| Portal Forge | Its previously delivered, explicitly configured and separately budgeted Portal provider injection is unchanged. S028 does not enable it or certify its private configuration. Its existing approval and accounting remain separate from the new shared text ledger. |
| Knowledge notes, Vault/MCP reads, biometrics | Deterministic/source-preserving services; no new generation. |

## Private server/native configuration

Use `NAVIS_OPENROUTER_CONFIG` as an absolute private JSON-file path outside source
control and the personal Vault. Use `OPENROUTER_API_KEY` only in the backend/native
environment. Tauri passes these server-owned values to packaged Python on stdin-based
routes; IPC callers cannot supply URLs, credentials or configuration paths. The only
remote endpoint is `https://openrouter.ai/api/v1/chat/completions`; redirects are denied.
Browser bundles receive no key. Hosted clients retain their local-runtime boundary.

Minimal disabled configuration:

```json
{"enabled": false, "allow_vault_content": false, "allow_background": false,
 "daily_budget_usd": 0, "features": {}}
```

Enabling later is a separate operator action: explicitly set `enabled` and
`allow_vault_content`, a positive global daily USD cap, and each desired feature's
route. Each route requires `enabled`, an exact `model` ID, pinned `provider` endpoint,
matching `reviewed_model`/`reviewed_provider`, `pricing_reviewed` (UTC date no older
than 30 days), reviewed `input_usd_per_million` and `output_usd_per_million`,
`request_budget_usd`, `daily_budget_usd`, integer `max_input_chars` (UTF-8 byte bound,
up to 12000), integer `max_output_tokens` (up to 2048), and `timeout_seconds` (1–90).
If applicable, include reviewed fixed/extra costs in `request_overhead_usd`.
No model, endpoint or current price is guessed. Features are `forge`, `brief`,
`polish`, `banter`, `holocron`, `reid`, `neural_chat`, `warroom` and `general`.
Model/provider changes require matching new review fields and a new pricing review.
Provider fallback is disabled; required parameters and no-data-collection routing
are requested. Unsupported model parameters fail rather than silently downgrading.

`allow_background` must separately be true for rollover banter, in addition to the
normal feature and content opt-ins. Leave it false unless explicitly authorized.
`GET /api/ai/text/status` exposes only enablement/key-presence/feature names. It is
read-only and makes no remote call or accounting-file write. Generation still
rechecks all configuration and budget limits before sending anything.

## Transmitted content

- Briefs: the selected composer draft as numbered excerpts and selection instructions.
- Polish: the selected draft, section name and copy-edit instructions.
- Forge: the selected concept and its bounded context, as before; no retrieval expansion.
- Reid/chat/War Room: the existing bounded conversation and selected personas/context.
- Banter: active squad names/persona protocols and realm briefing.
- Holocron: the existing summarized weekly telemetry/context, not a new Vault crawl.

All are treated as potentially Vault-derived and require the content opt-in and
their own enabled feature route. Opening a view, diagnostics, startup and retries
of status reads cannot authorize a paid generation. Suggestions never create tasks,
rewrite originals or save themselves.

## Accounting, errors and rollout

Accounting is private SQLite beside the configuration (`.usage.sqlite3`). It stores
request ID, UTC day, feature, model, reservation, cost and state, never prompts or
responses. A transaction reserves a conservative text/token upper bound plus reviewed
overhead against global and per-feature daily caps and the per-request cap. This
extends the existing online-generation reservation/settlement design in a separate
ledger, without changing historical Gemini records. It is an application guard,
not a substitute for a provider account hard limit.

Only one cloud request is allowed while a reservation is unresolved. Nonstreaming
responses must report token usage, cost, exact model and a complete text answer.
Unknown/ambiguous usage, timeout, malformed output, HTTP error, model mismatch or
cost overrun retains the reservation and locks new generation, including automatic
retries. Known overruns retain their observed cost. There are no internal retries.
Do not delete the ledger or toggle providers to hide an unresolved charge. Reconcile
the request against provider billing, preserve the record and have the operator
review before explicitly settling it through a private audited maintenance step;
no automatic reconciliation/paid retry UI is provided. Errors omit remote bodies,
headers, credentials and source text. Configuration disablement does not clear holds.

Rollback: unset the config or leave it disabled. Deterministic features continue.
An explicit local rollback may set `NAVIS_AI_PROVIDER=ollama`; never silently fall
back from an ambiguous cloud request. Historical cloud holds remain for reconciliation.
No live smoke call should occur without separate synthetic input and a declared
spending limit. A mocked migration is not proof of a configured model's quality.

Protocol reference: [OpenRouter request/response and usage documentation](https://openrouter.ai/docs/api_reference/overview),
retrieved 2026-10-31. No live price assertion is made.


## Implementation verification - 2026-10-31

95 affected Python tests and 5 subtests passed; one platform symlink test skipped.
81 native library tests and the full frontend suite (including 53 transport cases)
passed. Ruff passed. Release and NSIS 1.11.36 were built and metadata verified;
all 51 packaged Python resources matched final source. Fresh web UI smoke denied
both polish and brief generation, showing the disabled diagnostic without changing
the synthetic draft. Copied packaged Python routes independently denied generation
without writes to their fresh Vault/accounting paths. Mocked responses cover success,
missing key/model, disabled generation, stale pricing, model/provider review changes,
budgets, authentication/rate limiting, timeout, malformed/empty/truncated/tool output,
unknown usage, cost overrun and retry blocking. Live calls were not authorized or run.

The final copied executable started a fixture process/window, but native UI smoke
is blocked by failed window activation/restore and unavailable document accessibility.
This remains a draft-PR readiness gate. It is not a passed keyboard/native workflow
check or a clean-machine installation result. Configuration and live model quality
remain deliberately untested. No personal Vault data or credentials were modified.

The native startup preserved every original synthetic Vault file. It added only
the deterministic weekly Holocron HTML/JSON and manifest cache; this was not a
zero-write startup. The web generation-denial checks preserved all fixture bytes.
