# Testing audit and local test guide

Issue: [#131](https://github.com/KevinHozak/Navis-Protocol-Private/issues/131). Audited on
2026-09-30 against `51fdd01` (`origin/main` when this worktree was created).
This is a behavioral inventory, not a measured line-coverage report.

## What the existing checks prove

| Location | Classification | Coverage and limits |
| --- | --- | --- |
| `backend/tests/test_ai_provider.py` | Unit with fake providers | Local defaults, generation, provider failure, opt-in boundaries; no live provider |
| `test_banter_generator.py` | Unit plus temporary SQLite integration and API-function checks | Party validation, malformed output, deduplication, persistence failure, provider selection |
| `test_online_ai.py` | Unit plus temporary SQLite integration and source contracts | Opt-in, budgets, concurrent reservations, stale pricing, settlement, content boundaries; background-provider source check |
| `test_forge_service.py` | Unit, temporary filesystem integration, HTTP/native subprocess integration | Preview/approval separation, name validation, collisions, locking, symlinks, rollback/retry |
| `test_journal_entry.py` | Unit plus filesystem/API-function integration | Markdown normalization, dates/sections, BOM and CRLF preservation, missing target |
| `test_journal_polish.py` | Unit with fake HTTP sessions | Checklist state, unacceptable suggestions, formatting, empty input; no Ollama request |
| `test_progression_ledger.py`, `test_xp_reconciliation.py` | Unit plus temporary SQLite/filesystem and HTTP integration | Award idempotency, entity identity, projections, reviewed migration/recovery and rollback |
| `test_combat_completion.py`, `test_combat_workflow.py` | Unit plus filesystem, HTTP and native subprocess integration | Exact-task identity, retry/restart, staged failure recovery, XP, journal bytes; completed #87 supplies this evidence |
| `test_native_operations.py` | Unit plus fixture-mode subprocess/Git integration | Sync/rollover, missing storage, fixture path containment, failure summaries; not a live service smoke test |
| `test_weekly_holocron.py` | Unit plus filesystem/mock SQLite/FastAPI integration and stdio process piping | 7-day ISO bounds, Manor mapping, WTD status, progression XP query, Ollama debrief AI/fallback, HTML export, corrupted manifest recovery, empty journals, native_holocron stdio dispatch |
| Rust `command.rs` test module | Interpreter/process integration | Python discovery and override validation; needs Python 3.11+ on PATH |
| Rust `operations.rs` test module | Unit plus child-process integration | Job bookkeeping, allowed operations, diagnostic redaction, stream draining, cancellation, spawn/read failures; one test probes availability of the default Vault without writing it |
| Rust `vault.rs` test module | Unit plus temporary filesystem integration | Safe paths, assets, entities, journal writes, realm options/drafts/hops |
| Rust `lounge.rs` test module | Unit plus temporary SQLite integration | Media mapping, catalog/library routes without FastAPI |
| Rust `p3.rs` test module | Unit plus temporary filesystem/Python bridge integration | Native combat routes and recovery without an HTTP server |
| Rust `p5.rs` test module | Unit plus temporary SQLite/filesystem integration | Supported routes, unavailable response, ordered party validation, banter storage |
| Rust `progression.rs` test module | Python bridge/SQLite integration | Shared ledger response through the native adapter |
| `frontend/src-tauri/tests/parity_contracts.rs` | Static fixture consistency | Compares the two stored JSON shapes; does **not** execute both runtimes |
| `test-top-navigation-icons`, `test-navigation-view-loading`, `test-moongate-loading`, `test-map-realm-navigation`, `test-synthesis-lab`, `test-journal-entry-flow`, `test-native-capabilities` (`frontend/scripts/*.mjs`) | Source contracts | Regex/string checks for UI wiring; do **not** mount React or run a browser |
| `test-map-node-validation.mjs` | Unit plus source contracts | Executes the real map-node validator and inspects scene wiring |
| `test-map-telemetry.mjs` | Unit plus fixture/render-double integration | Real telemetry function, expiry/identity boundaries, scene marker methods against rendering doubles |
| `test-desktop-api-boundary.mjs` | Source contracts plus extracted-function checks | Routing references and asset URL mappings; not the complete adapter |
| `test-progression-flow.mjs` | Adapter behavior with a modified module | Web refresh behavior and native transport double; rewrites one import |

Python filenames in the table without a directory are under `backend/tests/`.
Rust test modules are compiled in the library test target, but many are
integration checks in behavior despite Cargo calling them unit tests.

### Manual probes are not the maintained test suite

`backend/test_api.py`, `test_character_assets.py`, `test_empty.py`,
`test_search.py`, `test_search_write.py`, root `test_books.py`, `test_gog.py`,
and `frontend/test_rm.js` are ad hoc probes. Some contact localhost/cloud,
read configured personal storage, reference missing modules, or write a
`search_results.json` file during import. Do not run them as automated tests.
The new root `pytest.ini` discovers only `backend/tests` and adds `backend`
to the import path. Explicitly asking pytest to collect a manual probe can
still bypass that default selection.

## Prioritized gaps and additions

| Priority | Risk | Work in this issue | Remaining evidence |
| --- | --- | --- | --- |
| P0 | Native request dispatched despite an already-aborted signal | Complete-module characterization test; filed production defect [#136](https://github.com/KevinHozak/Navis-Protocol-Private/issues/136) | Fix before treating abort as prevention of a mutation; follow-up test must assert zero invocations |
| P1 | Work-log content lost or duplicated on partial sync/retry | `test_sync_work_journal.py`: duplicate date blocks, pending missing/malformed target, successful retry/no-op, failed journal open, invalid settings, empty/undated input, backup bytes and unrelated sections, Git identity precedence | Partial disk writes, office-log purge failure after successful journal write, backup-copy failure and crash interruption are not covered; this service normalizes newlines, so tests do not claim byte preservation of the successful rewrite |
| P1 | Native canonical storage replacement/diagnostics lack focused failure boundaries | Two `vault.rs` atomic-write tests: existing-file replacement, BOM/Unicode, failed rename preserves occupied destination, removes staging file and retries. Two `operations.rs` tests: multibyte tail bound and repeated case-insensitive secrets | Power-loss durability, permissions during temporary-file creation, and cross-process concurrency need fault injection; rename failure uses an occupied directory, not a Windows ACL assumption |
| P1 | Frontend adapter checked mostly through source inspection | `test-desktop-api-runtime.mjs`: 18 complete-module tests for web/native routing, body parsing, response status, errors, explicit retry, abort/listener cleanup, sync jobs, polish and encoded assets | React component interactions, actual WebView IPC, operation-event subscriptions, native job cancellation, and all error shapes remain outside these mocks |
| P1 | Collection can reach personal storage or live integrations | Default discovery restricted; disposable import-time `NAVIS_ROOT`; socket guard with five self-tests; isolated test dependencies | Socket guard applies to the pytest process during tests, not arbitrary child executables. Existing native subprocess tests explicitly pass synthetic paths/fixture mode. Do not add live subprocess integrations to this default suite |
| P2 | Local biometrics reads/API failures untested | `test_biometrics.py`: absent/empty DB, ordering/limits, latest row, exercises, HTTP success/schema error, unchanged database bytes | Native biometrics parity, corrupted database, concurrent ingestion, and negative-limit API policy remain untested |
| P2 | Realm-hop and rollover multi-file writes, readiness/cache mutation | Existing native realm-hop and operation fixtures retained; no duplicate #87 implementation | Python Moongate transaction/retry behavior, rollover crash mid-sequence, concurrent journal writes, and per-section readiness require separate fixture sets |
| P2 | Library/cloud search, watch-history ingest and maintenance scripts lack an isolated suite | Manual probes excluded and inventory documents the boundary | Synthetic Jellyfin/Goodreads payloads, cloud-search doubles, deduplication and section preservation need focused follow-up tests |

No production service implementation is changed here. The already-aborted
request test deliberately captures the current defect rather than claiming
the behavior is correct. #136 must replace that characterization when fixed.
Aborting after dispatch rejects the frontend waiter; it does not guarantee
that a native mutation stopped or rolled back. Explicit native cancellation
and eventual state reconciliation require separate evidence.

## Repeatable local commands

Run these from the repository root in PowerShell. Python 3.11+ and Git on PATH
are required for bridge/operation fixtures. The verified environment used
Python 3.14.3, Node 24.14.0 and Windows. Node 22.8+ is needed for
`--test-isolation=none`; Node 24 is the tested choice. The frontend behavior
tests use Node's experimental VM module API and intentionally emit its warning.

```powershell
python -m venv .venv-test
& .\.venv-test\Scripts\python.exe -m pip install -r backend/requirements-test.txt
& .\.venv-test\Scripts\python.exe -m pip check
& .\.venv-test\Scripts\python.exe -m pytest --collect-only -q
& .\.venv-test\Scripts\python.exe -m pytest -q -p no:cacheprovider
& .\.venv-test\Scripts\python.exe -m ruff check backend

# Focused new backend behavior
& .\.venv-test\Scripts\python.exe -m pytest -q backend/tests/test_sync_work_journal.py backend/tests/test_biometrics.py backend/tests/test_test_isolation.py

Push-Location frontend
npm test
# Or: npm run test:unit / npm run test:regressions
Pop-Location

cargo test --manifest-path frontend/src-tauri/Cargo.toml --locked --no-default-features -- --test-threads=1
```

Frontend tests use built-in Node modules, so `npm ci` is not needed for these
commands; it is still needed for application build/lint. `npm test` executes
the behavior suite and an explicit list of all 11 regression scripts,
including the previously unwired progression check. Each VM behavior test
creates its own mocked runtime and invokes the entire unmodified production
module; fake Tauri imports and fake fetch prevent transport to live services.

Cargo's default `custom-protocol` feature embeds `frontend/out` and fails in
a clean checkout when that export does not exist. `--no-default-features`
uses dev context for unit/fixture verification without creating a fake export.
This is not validation of the production feature/build or packaged WebView.
Add `--offline` after `--locked` when Cargo dependencies are already cached
(used in this audit). A fresh machine needs dependency downloads and the
normal Rust/Tauri Windows build prerequisites. No FastAPI server is needed.

Use one Rust test thread: existing test modules mutate process-wide
`NAVIS_ROOT` and interpreter variables using separate module locks; parallel
execution can cause fixture cross-talk. A shared RAII environment fixture is
a remaining test-infrastructure improvement.

Python `requirements.txt` lacked pytest, httpx and aiohttp. The existing local
backend venv could not run pytest. `requirements-test.txt` supplies a separate
test environment with bounded dependencies instead of installing tray/UI
packages into the test environment. It is not a production dependency upgrade
or a fully frozen transitive lock. Verified resolved versions include pytest
9.1.1, FastAPI 0.142.2, httpx 0.28.1, aiohttp 3.14.3 and google-genai 1.75.0;
the declared production dependency versions are unchanged.

`backend/tests/conftest.py` assigns a temporary default Vault **before** test
modules import services, restoring the original environment at teardown.
Fixtures override service paths to their own temporary roots. Real socket
`connect`/`connect_ex` calls are denied, including localhost; only the internal
Windows `socketpair()` needed by asyncio is allowed during its construction.
FastAPI clients use in-process ASGI transport and do not enter lifespan contexts
that start real background jobs. Paid and local AI calls use provider doubles.
Native-operation fixtures now use pytest `tmp_path` rather than accumulating
UUID directories under `backend/sync_p3_fixture`; the old scratch location is
ignored so existing local runs do not pollute Git status.
The existing combat-workflow file explicitly re-exports its imported pytest
fixtures so Ruff recognizes their intentional discovery role; test behavior
and the completed #87 assertions are unchanged.

For commits in a fresh worktree, the existing Husky hook also expects root
`npm ci` (generates `.husky/_`), `npm ci` in `frontend`, and an interpreter
at `backend/.venv/Scripts/python.exe` with Ruff 0.4.5 installed. Create that
venv and install `backend/requirements-test.txt` there, or use an existing
local development venv with Ruff. The separate `.venv-test` commands above
remain sufficient for test-only runs. Do not disable the hook to compensate
for missing generated tooling.

On this managed Windows host the sandbox could create a temporary directory
but could not access its children (`WinError 5`); the same isolated tests passed
outside the sandbox. This is a host permission constraint, not a pytest failure.
Do not change ACLs or redirect tests into the personal Vault to work around it.
Node's process-isolated test mode also hit sandbox `spawn EPERM`; VM contexts
provide test isolation inside a single Node process. The legacy regression
runner still launches local child processes and required approved execution.

## Recorded results

| Command / scope | Result |
| --- | --- |
| Baseline pytest after discovery/isolation setup | 164 passed, 1 skipped |
| Full pytest in a newly created `.venv-test` installed only from `requirements-test.txt` | 184 passed, 1 skipped (20 new cases); 3 dependency/application deprecation warnings |
| `.venv-test` pip dependency check | No broken requirements |
| `npm test` | 18 behavior tests passed; all 11 regression scripts passed |
| Cargo offline, locked, no default features, one test thread | 47 library tests passed (5 new); one static parity-fixture check passed; binary/doc targets have zero tests |
| Ruff 0.4.5 backend check | Passed; imported combat fixtures recognized explicitly |
| Frontend `npm run lint` | Passed with existing image/hook warnings |
| Combat workflow after fixture-import lint repair | 27 passed |

The Python skip is Forge symlink creation unsupported on this Windows host.
Warnings cover FastAPI startup-event deprecation and the resolved Starlette
TestClient/httpx transition; they do not prevent tests. These results are
automated synthetic-fixture evidence. No live personal-Vault write, real AI
request, hosted-service smoke, browser-mounted React test, packaged-release
test, or release-signoff is claimed. Persisted synthetic file/DB assertions are
the evidence for state preservation, not console success messages alone.

## API abort behavior (#136)

`apiFetch` rejects an already-aborted signal with `AbortError` before routing
or invoking HTTP/native transport, including ordinary requests, sync, rollover,
and journal polish. No successful-write event is emitted. The runtime suite now
asserts zero native invocations for these requests and verifies that an explicit
retry with a fresh signal dispatches once.

After dispatch, aborting stops waiting for the response and suppresses the
successful-write event for that request. It does not undo a native mutation or
cancel a running job. Request native job cancellation explicitly with the
applicable `cancelSyncOperation`, `cancelLoungeOperation`, or `cancelP5Operation`
helper and its job ID.

Run from `frontend`: `npm run test:unit` (30 mocked behavior tests).
The earlier P0 characterization above records the audit baseline; this fix
replaces it with prevention assertions using synthetic fixtures only.
