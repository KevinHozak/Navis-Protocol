# Local-first AI generation (AI-P1)

Forge blueprint generation and background squad banter use the local Ollama provider. Neither path reads cloud API credentials or falls back to an online provider. A missing or unavailable local model produces a bounded diagnostic and the operation stops.

## Ollama setup

1. Install Ollama and start its local service.
2. Pull the configured model, or set `NAVIS_OLLAMA_MODEL` to another model already installed in Ollama. The default is `Kimiko-20B:latest`.
3. Optional settings:
   - `NAVIS_OLLAMA_URL`: Ollama base URL, default `http://localhost:11434`.
   - `NAVIS_OLLAMA_TIMEOUT`: request timeout in seconds, default `90`, clamped to 1–600 seconds.
   - `NAVIS_AI_PROVIDER`: leave unset or set to `ollama`. Unsupported providers fail closed.

The provider offers a connectivity check against `/api/tags`. Generation uses Ollama's non-streaming `/api/generate` endpoint. Cloud API keys are not needed for application initialization or these features.

## Privacy and data flow

- Provider selection and model settings are read by the backend; renderer code does not receive provider credentials.
- Forge sends its submitted name/context to the configured local Ollama endpoint to produce a blueprint. The endpoint may receive user-supplied context, including Vault-derived text. Approval remains a separate action before Forge scripts write to the Vault.
- Banter generation sends realm lore and companion Banter Protocol text already assembled by the existing workflow to local Ollama. It no longer retrieves journal-vector memories for generation.
- Squad banter generation is bounded to three threads per run. Sync avoids another local request for 24 hours when the active realm and exact party already have a complete, usable thread. Responses are persisted only when every active party member appears exactly once in the requested order.
- Local prompts and responses are not written to provider diagnostics. This phase does not add an online provider or an online fallback.
- Reid and War Room use the AI-P2 experiment policy; War Room remains local-only because its prompt includes substantial Vault-derived context.

## Online AI experiments (AI-P2)

Local Ollama stays the default after restart and upgrade. Hosted Gemini text generation is available only for interactive Neural chat and other explicitly selected guarded text-provider calls after both `enabled` and the separate `allow_vault_content` option have been set in **System → Online AI Experiments**. The Vault-content option is off by default. Disable `enabled` at any time to stop new online requests. Reid uses the same gate because its context includes therapy notes and journals. War Room, explicit squad banter, realm-hop banter, synchronization, and midnight rollover remain local-only, regardless of an installed API key. Gemini image-card generation is blocked because image pricing/usage is not covered by the text budget.

The web control panel reports key availability without exposing it, provider/model, the monthly UTC reservation total, request caps, pricing review date, and current reset period. Native Tauri has no hosted provider/accounting adapter, so its online controls are disabled; squad banter and journal polishing use local Ollama on the loopback interface. Requests are limited to 12,000 input characters and 2,048 output tokens. A four-tokens-per-character upper-bound estimate plus maximum output is reserved in a SQLite `BEGIN IMMEDIATE` transaction before the provider call, so simultaneous requests cannot exceed the configured $0.01–$100 monthly hard budget. Successful requests settle against returned token usage; missing usage, provider failure after dispatch, or usage exceeding the reservation keeps the full reservation held for that month. Old periods stop counting at the next UTC month boundary; no manual reset can erase current-period usage.

Gemini 2.5 Flash paid-tier list pricing is configured at $0.30 per million input tokens and $2.50 per million output tokens, last reviewed 2026-09-27 against the [official Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing). Pricing older than 30 days blocks new online requests until reviewed in code. Requests also fail closed when there is no API key, the provider is disabled, the input is oversized, or the worst-case reservation exceeds the remaining budget.

### Cost examples

The following estimates use paid-tier list prices and count the model's reasoning tokens as output. Google lists free-tier use for eligible models/projects; if a request qualifies, the provider bill may be lower or $0. The app uses paid-tier rates for its conservative budget accounting because it cannot establish an account's billing tier from the API key alone.

| Example usage | Estimated cost per request | Approximate monthly cost |
| --- | ---: | ---: |
| 2,000 input + 500 output tokens | $0.00185 (0.185¢) | 1/day: $0.06; 10/day: $0.56 |
| 10,000 input + 1,000 output tokens | $0.00550 (0.55¢) | 1/day: $0.17; 10/day: $1.65 |

Formula: `(input_tokens × $0.30 + output_tokens × $2.50) / 1,000,000`. For example, `2,000 × $0.30 / 1,000,000 + 500 × $2.50 / 1,000,000 = $0.00185`. These are usage-based estimates, not a subscription fee; conversation length and generated reasoning/output can change the total.

Budget reservations are intentionally higher than typical request estimates: before sending a request, the app reserves four tokens per input character plus the full 2,048-token output allowance. After a successful response with usage metadata, it replaces that reservation with a token-based estimate at the paid rates. If a request fails after dispatch or usage metadata is missing, the full reservation stays held until the monthly UTC reset. At the maximum 12,000 input characters, the worst-case reservation is about $0.01952 (1.95¢). The System panel's month-to-date figure includes both settled estimates and outstanding reservations.

Usage records in `Bridge/ai_usage.sqlite3` contain only feature, provider/model, timestamp, token counts, estimated/actual cost, period, and status. Prompts, responses, Vault text, credentials, and personal content are never included. Configuration is stored in `Bridge/ai_experiments.json`. Forge still requires its existing explicit approval before scripts write generated content to the Vault.

## Synthetic online benchmark (AI-P5)

Run the operator CLI from the repository root. With no execution flag it prints a plan without reading the Vault, credentials, configuration or ledger and without making network requests:

```powershell
python backend/scripts/benchmark_ai.py
```

The fixed `navis-synthetic-v1` prompt set contains three fictional exact-answer JSON tasks: arithmetic, ordering and proposal constraints. Each task is repeated twice by default (only two or three repeats are permitted). No custom prompts, companion profiles, journals, memories, Forge context, files or system instructions are accepted. The baseline calls the configured Ollama model directly, regardless of `NAVIS_AI_PROVIDER`. Both local and online requests use temperature 0, seed 95 and a 512-token output limit. Local thinking is disabled; Gemini uses its supported `minimal` thinking level, with reasoning included in output accounting. Requests time out after 90 seconds. There are no retries or fallback requests.

Candidates were selected after checking the [official Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing) on **2026-09-30**, using standard paid text rates, without caching, tools, grounding, batch or priority service:

| Model | Input USD / million tokens | Output USD / million tokens | Maximum cost for six requests |
| --- | ---: | ---: | ---: |
| `gemini-3.1-flash-lite` | $0.25 | $1.50 | $0.0054940 |
| `gemini-3.5-flash-lite` | $0.30 | $2.50 | $0.0087432 |

The default full online run has **12 paid requests**, conservatively reserving four tokens per input character plus maximum output, for at most **$0.0142372**. The experiment limit defaults to $0.05 and cannot exceed $0.10; the full maximum estimate must remain strictly below it. Pricing older than 30 days fails closed. These limits bound a single run; reruns consume the same aggregate monthly P2 budget.

The original 2.5 candidate attempt returned HTTP 404 despite successful model metadata access. Google's [model availability guidance](https://ai.google.dev/gemini-api/docs/deprecations) limits 2.5 access to projects that previously used those models. The operator rechecked current pricing and the combined remaining experiment allowance before selecting the current candidates above. This changes benchmark selection only; production provider selection is unchanged. See [recorded results](benchmarks/README.md).

Run the local baseline alone and save its report outside the Vault:

```powershell
python backend/scripts/benchmark_ai.py --run-local --output C:\Projects\Temp\navis-ai-local.json
```

To run the paid experiment, explicitly enable P2 in System → Online AI Experiments, set its monthly cap, configure the API key only in the backend environment, then pass the separate benchmark opt-in:

```powershell
python backend/scripts/benchmark_ai.py --enable-online --experiment-limit-usd 0.05 --output C:\Projects\Temp\navis-ai-benchmark.json
```

The separate Vault-content option can stay **off**; benchmark inputs are synthetic. Full-run preflight checks current aggregate reservations against 95% of the monthly cap. Every paid call then atomically reserves its candidate-specific worst-case cost in the existing P2 SQLite ledger, including concurrent Neural/Forge usage. Disabling P2 between calls prevents the next reservation. Each successful call settles at that candidate's prices. Missing usage and provider failures retain the full reservation. The first error stops the run; a failed local baseline prevents all paid requests. Interrupted calls also retain their reservation, and the last completed sample is available in the checkpoint report. There is no reset or refund command.

Reports checkpoint atomically after each sample. They record prompt-set version/hash, provider/model, pricing date/source, generation settings, latency, input/output tokens including reported reasoning tokens, reserved/accounted costs, safe error codes, scores and output hashes. Three binary rubric points assess JSON-only formatting, exact keys/value types and correct fictional facts. The summary compares quality and latency with local Ollama, counts errors and missing usage, and measures identical output hashes and rubric agreement across repeats. Raw prompts, outputs, provider error bodies and keys are never saved. `actual_billed_cost_usd` is null: provider invoices/billing tiers cannot be verified, and the P2 ledger's historical `actual_cost_usd` field is a token-based list-price estimate, not an invoice.

This tiny exact-answer benchmark does not assess creative prose, therapeutic quality or companion personality. Local hardware/quantization and provider revisions also affect comparability. A stable perfect rubric score at least as good as local may justify **a separate human-reviewed proposal**, never production activation. The runner never changes provider selection, online settings, Forge approval or Vault artifacts. Native Tauri still has no hosted accounting adapter; execute this backend CLI separately rather than adding paid generation to native controls.

Implementation verification uses mocked providers and temporary ledgers. A no-network plan is not a live performance result, and live results should be reviewed separately before making a proposal.
