# AI-P5 verification evidence

The explicitly authorized comparison completed on 2026-09-30 (America/Chicago). Each model received the same three fictional JSON tasks, twice, at temperature 0, seed 95 and a 512-token output limit. Local thinking was disabled; online thinking used `minimal`. No private inputs or raw outputs are retained.

| Model | Samples / errors | Mean latency | Mean strict score | Input / output tokens | List-price estimate |
| --- | --- | ---: | ---: | ---: | ---: |
| `gemma3:4b` | 6 / 0 | 4.883136 s | 0/3 | 272 / 170 | $0 |
| `gemini-3.1-flash-lite` | 6 / 0 | 1.216973 s | 3/3 | 212 / 146 | $0.0002720 |
| `gemini-3.5-flash-lite` | 6 / 0 | 1.121922 s | 2/3 | 212 / 156 | $0.0004536 |

All repeated tasks had identical output hashes and rubric scores within each model. Gemini 3.1 Flash-Lite achieved all three rubric points on every sample; 3.5 Flash-Lite passed ordering and constraints but failed the JSON-only arithmetic contract. The strict rubric first requires the entire response to parse as JSON, so prose or code fences score zero. A zero does not establish that the underlying factual answer was wrong.

Official [standard text pricing](https://ai.google.dev/gemini-api/docs/pricing) was reviewed 2026-09-30 before candidate selection: 3.1 Flash-Lite costs $0.25/$1.50 and 3.5 Flash-Lite $0.30/$2.50 per million input/output tokens, including reasoning. The twelve-request maximum reservation was **$0.0142372**. Before dispatch, the operator checked this plus $0.0005048 of retained earlier error reservations against the approved **$0.05** total allowance. Shared P2 monthly accounting and its 95% safety margin remained enforced.

The completed comparison's usage estimate was **$0.0007256**. Including earlier retained reservations, total accounted experiment cost was **$0.0012304**. These are list-price estimates and conservative reservations, not verified invoice charges; actual billed cost remains null.

Two earlier runs stopped on the first Gemini 2.5 Flash-Lite request and made no later online calls. Each retained a $0.0002524 reservation with unknown usage. The first report captured a generic provider error; the second captured HTTP 404 / NOT_FOUND. Read-only model metadata access succeeded. Google's [availability guidance](https://ai.google.dev/gemini-api/docs/deprecations) now restricts 2.5 generation to projects that previously used those models, consistent with this result. The current candidates were selected after rechecking pricing and supported [minimal thinking configuration](https://ai.google.dev/gemini-api/docs/generate-content/thinking). Both attempts are preserved as separate reports; no refunds or ledger resets were performed.

Earlier local-only reports are also retained: the default `Kimiko-20B:latest` stopped on one empty response (0.797388 s; 32 input / 1 output tokens), while a six-sample Gemma baseline completed with stable hashes, 0/3 strict scores and 7.781940 s mean latency. Historical reports preserve the candidate plan that existed at their execution time. UTC report timestamps fall on 2026-10-01, corresponding to the local date above.

Gemma used a process-local model override. Experiment enablement was temporary, Vault-content permission remained off, and prior configuration bytes were restored and read back after every run. Production provider selection and Forge's explicit Vault-write approval remain unchanged. No benchmark result activates a model.

**Assessment:** the synthetic evidence supports a separate human-reviewed proposal for Gemini 3.1 Flash-Lite for these JSON contract tasks. It does not establish companion personality, creative or therapeutic quality, general reliability, or future provider behavior. Six samples per model, local hardware/quantization, different reasoning implementations, fixed temperature and unverified billing limit the conclusions. Native hosted controls remain disabled.

Validation: 56 focused/provider/Forge/banter tests passed, one existing test skipped. Repository-wide backend Ruff, frontend lint (existing warnings), and whitespace checks pass. Mocked tests cover caps, concurrent reservations, opt-ins, usage settlement, unknown usage, safe error metadata, privacy and early stopping; the live comparison supplies separate provider evidence.
