# Holocron evidence contract

S013 repairs S009 finding T01. A Prime Beast mention is not a victory, completed
items are not measured focus hours or damage, and no historical readiness or
level measurement is supplied by this aggregator. These values are unavailable.
Squad counts describe journal mentions, with no invented fallback member or XP.

Schema 2 records the ISO week, seven daily source states, readable-day coverage,
input fingerprints and aggregation rules. Checklist completion uses only readable
journals and remains unavailable with no checklist items. Partial coverage is
explicit. XP sums signed canonical Keeper ledger rows by inclusive local date;
other entities and other weeks are excluded. A readable empty ledger yields zero;
missing, unreadable or unscoped legacy ledgers yield unavailable.

Web and native reads revalidate inputs rather than trusting historical cached
claims. Explicit regeneration refreshes saved snapshots. A cached AI debrief is
retained only when schema, summary and source fingerprints match. Interpretation
labels distinguish the factual fallback from optional existing Ollama output;
references establish inputs, not the truth of generated conclusions. No new AI
decision feature, provider call, background job or task commitment is introduced.

The shared Evidence & rules panel inspects only allowlisted week/source IDs.
It returns bounded counts and relative journal navigation, never a journal body
or an arbitrary file read. Changed fingerprints require regeneration; deleted
or inaccessible sources cannot expose an Open source journal action. Missing
coverage remains visible. Local source navigation uses the existing journal
selection flow. Symlinks and paths outside the configured root are rejected.

Standalone HTML contains escaped metric/rule details and internal source anchors.
Its reference statuses are a generation-time snapshot, not live filesystem links.
Private absolute paths are omitted; journal bodies and local navigation paths are
not embedded. HTML is generated from revalidated inputs, not an older HTML cache.
Unavailable roots do not create weekly artifacts or manifests.

## Relationship to S006

[S006](../issues/NAVIS-S006.md) remains conditional on S005's passing three-cycle
trial and keep decision. It should extend this evidence schema, panel and export
snapshot rather than introducing a second provenance interface. S013 makes no
claim that those trial gates or decision-focused features are complete.

## Verification

The affected 42 Python checks cover aggregation, missing/deleted inputs, privacy,
HTML escaping, canonical XP corrections, web/native source parity and existing
Holocron/talent behavior. The mounted evidence fixture exercises inspection,
changed/deleted references and journal navigation callbacks for web/native
response paths. Fifty desktop adapter checks and the full frontend regression
runner pass. Seventy-four serial Rust checks pass with the personal-Vault
availability probe excluded; a native test proves cached files cannot bypass
Python revalidation. Backend Ruff and frontend lint pass with existing warnings.

Release packaging and physical fixture observations are recorded separately below.
These fixtures do not certify personal-Vault data quality, live Ollama output,
clean-machine installer behavior or broader S015 trust journeys.

## Packaged fixture acceptance - 2026-10-27

Windows release 1.11.21 executable FileVersion and ProductVersion both match.
MSI and NSIS packaging completed. All 38 mapped backend resources match source
byte-for-byte; the copied app runs outside the source backend with an isolated
synthetic Vault, Python runtime and WebView profile.

The packaged bridge returned 50% checklist completion and 90 signed Keeper XP
(100 task XP minus a 10 XP correction; another entity's 800 XP excluded). Native
UI displayed W40, 1/7 readable days, unavailable readiness/focus/combat outcomes
and an unverified Hydra mention. Expanding the precision rule and inspecting its
source showed 1/2 checked items. Temporarily removing that fixture reference
produced missing status and removed source navigation; restoring it allowed the
exact September 28 journal to open. The fixture app was closed after verification.
Packaged HTML returned evidence anchors and unavailable labels without root paths.

Executable SHA-256: `2751d47aa5c32612fc962e495e7444fdda91717082e17df57b4814c984054198`.
NSIS SHA-256: `580a5f316f8241182cc5bb086ee4c3bc17ae4272fec7d0bd4b7963d9ff40a280`.

Web verification uses FastAPI fixture parity and mounted React interactions;
a separate physical web-browser journey was not run. Export content/privacy was
verified programmatically, not through a download dialog. The existing first-load
cycle-selector/loaded-cycle mismatch was observed before explicitly selecting W40;
refresh/selection behavior remains under S010. Sparse-fixture diagnostics and an
existing pending-XP toast are outside this evidence inspection acceptance. No live
provider, personal Vault operation or clean-machine installation was performed.
