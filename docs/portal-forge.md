# Protocol Forge integration (0.2.2)

The first Protocol feature is the existing FastAPI Forge preview (`POST /api/forge/submit`). It generates a proposed blueprint; it does not approve or manifest an entity. Portal is selected only for this request. The global Ollama default and guarded Gemini routes are unchanged. No frontend selector, native bundle, startup task, scheduler or live rollout is installed.

## Explicit activation

Keep `NAVIS_PORTAL_ENABLED` unset for the default disabled state. An operator must separately review and provision a private profile, a scoped Windows Credential Manager app key under `Navis-Portal/Protocol/`, an installed reviewed Portal 0.2.2 release and route commitment, and a new Forge feature budget. Set `NAVIS_PORTAL_ENABLED=1` and `NAVIS_PORTAL_PROFILE` to the protected profile only after that review. Existing Protocol online settings must also have both `enabled` and `allow_vault_content` explicitly true. S013 created none of these live settings or credentials and authorizes no inference spending.

An authenticated existing backend caller sends the original `entity_type`, `name` and `prompt` plus `provider: "portal"`, `portal_opt_in: true`, `allow_external_text: true`, and a persisted unique `operation_id` (1-128 ASCII letters, numbers, dot, underscore, colon or dash; first character alphanumeric). Unknown Portal request fields, including tools, streaming, images, keys and budget overrides, are rejected. No secret belongs in a `NEXT_PUBLIC` variable. The caller is responsible for reviewing the submitted text before external transmission.

The private JSON profile has exactly these fields:

| Field | Requirement |
| --- | --- |
| schema_version / feature | `1` / `forge` |
| portal_release_root / portal_release_id | Absolute installed release directory / reviewed manifest SHA-256 |
| portal_state | Private installed service state directory |
| app_key_target | Scoped Windows Credential Manager target, never the raw key |
| commitment | Reviewed route commitment SHA-256 |
| alias / canonical_model_id / endpoint_tag | Reviewed alias and exact expected route identities |
| feature_ledger | Absolute private SQLite path outside the Vault, Portal state, installation and package trees |
| feature_caps | Positive integer `usd_micros`, `calls`, `tokens`; persistent lifetime caps |
| max_input_bytes / max_input_tokens | Positive integers at most 16,384 each |
| max_tokens | Positive integer at most 8,192 |
| timeout_seconds | Positive integer at most 120 |
| call_ceiling_micros | Positive integer at most 1,000,000,000 |

Bounds are schema limits, not an approved budget. Provision only separately approved smaller limits. Profile, installed code, state and ledger need private ACLs; SQLite sidecars are checked. The loader verifies the reviewed installed payload before import. The client uses the qualified Windows CPython 3.14.8 runtime; Protocol may use its own virtualenv executable. Operator service launch still requires the recorded executable identity. Other runtimes are unqualified.

## Failure and billing behavior

There are two bounded backend workers; an additional concurrent request gets `PORTAL_FEATURE_BUSY`. Cancellation signals the worker and retains its slot until exit. Timeout, capability, privacy, budget and unavailable errors produce an explicit safe receipt and never invoke direct Gemini/OpenRouter, retry, or silently switch models. Incomplete/ambiguous attempts retain their full reservation across restart; reuse of the operation ID is rejected. Do not manufacture a new ID to retry an unknown result. A process kill is not proof of no charge.

The separate Forge ledger reserves the full per-call USD ceiling and input-plus-output token ceiling before dispatch. It records `accounting_role: portal-cap-reference`; it is a second cap over Portal's authoritative usage, not an additional provider purchase. Existing Google usage records are neither imported nor modified and existing grants do not carry over. Missing cost remains null/unknown. A charged invalid blueprint preserves its settled cost while returning `PORTAL_BLUEPRINT_INVALID`. Successful previews include `portal_receipt` with model-validated usage cost, correlation and operation ID.

## Invocation inventory

| Existing path | Current transport and S013 behavior |
| --- | --- |
| Forge preview | Global provider by default; the only new explicit Portal branch |
| Neural chat, Warroom, Reid | Existing global provider; local Ollama default with guarded optional Gemini, unchanged |
| GET neural banter fallback | Existing global provider, including its existing optional guarded cloud path; unchanged |
| Journal polish | Explicit local Ollama; unchanged |
| Squad banter on rollover / moongate | Explicit local Ollama; unchanged |
| Holocron startup catch-up and narrative | Explicit Ollama then rule fallback; unchanged |
| Startup lifespan, proactive biometrics, watcher, rollover and recurring tasks | No Portal hook added; existing side effects remain as implemented |
| Synthetic operator benchmark | Existing explicit guarded Gemini comparison and local baseline; not routed to Portal |
| Health and page loading | No new Portal dispatch or worker submission |

The integration does not claim that all pre-existing paths are always local. No changes were made to global provider selection, legacy pricing freshness, online settings or background scheduling. Protocol's Tauri 1.11.34 resources and UI are unchanged; this is a FastAPI backend integration, not native-app qualification.

## Offline qualification

`tests/test_protocol_client.py` runs Protocol's real FastAPI endpoint in its own virtualenv against an installed temporary Portal package, authenticated loopback service and fake upstream. Fixtures use an empty disposable Vault, dummy scoped app credential (removed afterward), separate cap ledger and unchanged sentinel Google usage bytes. External sockets and fallback providers are forbidden. Cases cover completion, duplicate/restart, missing usage, disabled/privacy gates, unsupported capability, budget cap, stale commitment, unavailable gateway and backend termination with retained holds. Protocol's own `test_portal_forge.py` additionally covers admission, bounded concurrency, cancellation and invalid charged blueprints. No real Vault, provider credential, paid inference, deployment or live trial is part of qualification.

## Session-only Portal previews

Portal-generated previews are not written to disk. Up to 32 active reviews are retained in process memory for ten minutes, with scheduled expiry. Discard, failure and successful explicit manifestation remove the review body. A server restart loses the preview; it never automatically retries generation or releases billing holds. Only an explicit approval writes the requested final entity. Default/local-provider Forge preview storage is unchanged.

Historical proposal files have no provider marker, so this change does not inspect or delete ambiguous existing private files. Any legacy cleanup needs operator identification. Tests use generated empty Vaults only; no live provider, real import or route activation is involved.
