# Navis Protocol Desktop Release

Issue #7 establishes the native Windows cockpit as the production runtime. The Next.js/FastAPI pair remains a compatibility and development mode only; it is not launched by the installed desktop artifact.

## Build a release

From a clean checkout on Windows:

1. Install Python 3.11 or newer and the packages in `backend/requirements.txt` for the account that will run Navis Protocol
2. If Python is not on the account's `PATH`, set `NAVIS_PYTHON` to the full path of that installation's Python executable
3. Set `NAVIS_ROOT` to the canonical Vault directory (it must contain `Bridge` and `Journal`)
4. Run build_navis_desktop.bat from the repository root
5. Run the generated installer from frontend/src-tauri/target/release/bundle/nsis/
6. Launch the installed Navis Protocol application, not start_all.vbs

The build runs npm ci, creates the static Next.js export, and invokes tauri build --bundles nsis. The NSIS installer uses current-user install mode and checked-in Tauri icons. No backend server is started by the native application.

## Native synchronization runtime

The Tauri resource map includes `backend/native_operations.py`, `native_combat.py`, the sync, combat, battle, RPG, progression and AI/Forge services, and four Forge scripts. See [tauri.conf.json](../frontend/src-tauri/tauri.conf.json) for the exact file map. It does not bundle every integration script or Vault-side `Engine/` operation. Release builds resolve these files from Tauri's installed resource directory; they do not depend on a source checkout. Python itself is an external runtime and is not copied into the installer. All native Tauri Python subprocesses use the shared runtime resolver: `NAVIS_PYTHON` takes precedence, otherwise development builds prefer the backend virtual environment and release builds search the launching account's `PATH` for Python 3.11 or newer. The selected interpreter must have `backend/requirements.txt` installed. If discovery fails, add Python to `PATH` or set `NAVIS_PYTHON` in the account environment before launching the app. Changing environment variables does not affect an already running app; restart it after configuration.

`NAVIS_ROOT` may be set to the Vault directory containing `Bridge` and `Journal`. If it is unset, the native desktop shell uses the established default `G:\My Drive\Navis-Vault`; an unavailable or invalid root is rejected before a sync or rollover job starts. Native operations and approved P5 scripts receive the resolved `NAVIS_ROOT`; their child processes also receive `PYTHONPATH`, UTF-8 output configuration, and only the minimal platform process variables they need. Python backend subprocesses launched by FastAPI use `sys.executable` so they run under the same interpreter as the server.

## Runtime boundary

- Native production: the Tauri shell uses Rust IPC and selected Python services for implemented Vault, Lounge, combat, progression, and P5 workflows; route coverage is partial (see [endpoint registry](api_endpoints.md))
- Web/dev compatibility: `start_all.vbs` starts FastAPI on 127.0.0.1:8000 and Next.js on 127.0.0.1:3000 for legacy routes and development; `backend/start_backend.vbs` starts only the FastAPI backend for backend development. Both launchers honor `NAVIS_PYTHON` and `NAVIS_ROOT`.
- The two modes must not be started together for production use because they can present different state boundaries

## Startup diagnostics

The native shell exposes startup_diagnostics and checks embedded WebView availability, NAVIS_ROOT, required Bridge files, the Companions directory, status-file write access, stale lock files, and failed migration markers. Treat failed error-level checks as recovery guidance before writes. The diagnostic report is not a universal runtime write gate, and it does not validate every Python dependency, model or integration. WebView availability is inferred from Tauri having started.

## Recovery and rollback

1. Close the native application
2. Run Stop_Navis.bat if compatibility-mode services were started
3. Preserve the Vault and inspect the diagnostic result before retrying
4. If a release is faulty, uninstall it from Windows Apps, install the previous NSIS artifact, and keep the Vault unchanged
5. Use start_all.vbs or backend/start_backend.vbs only as development/compatibility fallbacks

## Documentation reconciliation scope (2026-09-30)

Current source declares version `1.6.2`. The `1.3.0` artifact record below is retained as historical build evidence, not a claim that the current version was installed or tested. This reconciliation inspected source, commands and links only; it did not invoke sync/rollover, write Vault data, build an installer or perform clean-machine/live-Vault checks. Native general task toggle has no XP sync, several squad/settings routes are absent, and native War Room/Reid/general chat is explicitly unavailable. Use the endpoint registry before choosing a workflow.

Build prerequisites include Node/npm, Rust/Cargo, Windows C++ build tools, WebView2 and NSIS. Installed runtime prerequisites differ: WebView2, accessible Vault data and external Python/dependencies for Python-backed features. Local generation also requires Ollama and a configured model. Allowlisted P5 scripts and integration dependencies must exist separately; bundled entrypoints alone do not prove every sync substep works.

## Verification gates

- npm run typecheck:desktop from frontend
- npm run desktop:build:release from frontend
- cargo test --manifest-path frontend/src-tauri/Cargo.toml
- Manual clean-machine smoke test: launch, telemetry, journal/task write, combat/progression, Lounge, close
- Confirm Task Manager has no navis-protocol.exe, Node, or Uvicorn child process after shutdown

## Native sync and rollover release smoke test

Run this check on a Windows machine with WebView2 and Python 3.11 or newer installed (NSIS is required on the build host). Use a disposable Vault fixture created outside the source checkout. The installed application must be launched from its install location after the source checkout has been made unavailable to the test process; this proves the backend comes from the installed resource directory. Do not point the fixture at a personal Vault or include fixture content in logs or issue artifacts.

### Fixture and safety boundary

Create `Bridge`, `Journal/YYYY/MM`, `Companions`, `Operations`, a minimal `Bridge/settings.json`, `Bridge/status.json`, `Bridge/ops_state.json`, a daily journal template, and fixture journal files. Set `NAVIS_ROOT` to the fixture before launching the app, and use an office work log path inside the fixture. Ensure the fixture's status date is yesterday and that one due task is available to test rollover. Record only whether expected files/fields changed, not their contents.

Set `NAVIS_NATIVE_FIXTURE_MODE=1` and `NAVIS_FIXTURE_GIT_DIR` to enable the dedicated fixture boundary. Fixture mode requires an office log under `NAVIS_ROOT`, creates a separate bare Git repository, stages only `Bridge`, `Journal`, and `Companions`, disables watch-history, squad-banter, and biometrics integrations, and redirects root-sensitive XP/journal modules to the fixture. It treats required backup, XP, journal-write, status-write, and indexing errors as failures. The ordinary production path retains its existing integration ordering.

### Scenarios and evidence

| Scenario | Procedure | Record |
| --- | --- | --- |
| Packaged resources | Build the NSIS installer, install it, make the source backend path unavailable to the launched process, and start the installed app. | Installer name/version, resource resolution outcome, startup error if any. |
| Connected fixture | With integration isolation enabled, run sync and rollover using the disposable fixture. | Operation status, elapsed time, whether fixture journal/status/cache changed as expected, and whether a bounded terminal event was emitted. |
| Disconnected fixture | Close the app, point `NAVIS_ROOT` at a nonexistent path, relaunch, and request sync and rollover. | Confirm preflight failure is actionable, occurs before fixture mutation, and returns a failed operation event rather than success. |
| Cancel and close | Start an isolated fixture operation with a controllable delay, cancel once, then repeat and close the app during the delay. | Cancellation/exit duration, child-process tree after shutdown, job registry cleanup, and successful subsequent launch. |

### Evidence record

Append a dated record here after the packaged checks actually run. Include Windows edition/build, architecture, WebView2 version, installer version and SHA-256, Python version and executable source, fixture-only Vault layout, scenarios completed, outcomes and elapsed times, and any remaining clean-machine checks. Mark source-level/unit coverage separately from packaged/manual evidence; do not infer clean-machine results from a Rust test or development build.

**Current evidence (2026-09-29):** `python -m pytest backend/tests/test_native_operations.py -q -p no:cacheprovider -p no:tmpdir` passed (6 tests). This exercises sync and rollover in a disposable Vault with isolated Git, verifies fixture state changes and integration suppression, rejects an unavailable root without creating state, rejects missing fixture Git configuration before mutation, rejects an office-log path outside the fixture, and checks bounded/redacted errors. `python -m py_compile` passed for the entrypoint, sync engine, and new tests. The existing progression ledger suite did not run: its `tmp_path` setup/teardown is blocked by this managed Windows environment's pytest temporary-directory ACL behavior. Ruff was unavailable in the active Python environment. The release build then succeeded from `main` commit `81020ec` with `python C:\Users\<user>\.codex\skills\tauri-build\scripts\build_tauri.py --repo C:\Projects\Navis-Protocol`: Next.js production build, optimized Rust executable, MSI, and NSIS bundles completed. Declared Tauri, Cargo, and frontend versions agree at `1.3.0`; the executable reports FileVersion and ProductVersion `1.3.0`. Artifacts: `frontend/src-tauri/target/release/navis-protocol.exe` (SHA-256 `5857D27D5AB68623C404AD0349BB78F596FFCED68C2DEC0564F0550B7F804AF6`), `frontend/src-tauri/target/release/bundle/msi/Navis Protocol_1.3.0_x64_en-US.msi` (SHA-256 `B8A300AA3E525AD4B03FE81C6EDA9C3470D1D0F509FA509D6B4454AD23673A6E`), and `frontend/src-tauri/target/release/bundle/nsis/Navis Protocol_1.3.0_x64-setup.exe` (FileVersion and ProductVersion `1.3.0`, SHA-256 `D9334CD95310F58F61A58765E895056E40A3F573F65B1CA762D2E17881538CF1`). Build host: Windows 10.0.26200 x64. Source inspection confirms the Tauri config bundles the standalone entrypoint and current service dependencies; Rust-side tests cover backend-entrypoint presence, Vault-root validation, operation-state cleanup, bounded diagnostics, child cancellation/reaping, and nonzero child exits. The installers were built but not launched. WebView2 version, Python runtime from the installed package, resource resolution without a source checkout, connected/disconnected packaged fixture behavior, window close during an active operation, orphan-process absence, and later launch usability remain **unverified packaged checks**. Record those outcomes only after performing the release smoke test above.


## Targeted S014 release fixture evidence - 2026-10-27

Version 1.11.20 release executable and NSIS/MSI bundles built. The standalone
release resource-directory smoke passed sync, rollover, generated partial-write
recovery, reconnect/review, cancel, active close and restart, and unavailable-root
operation rejection. All 37 resource hashes match source; no fixture process
remains. This is build-host executable evidence, not installer or clean-machine
acceptance. See [S014 acceptance](sync-operation-outcomes.md#packaged-fixture-acceptance---2026-10-27-11120)
and its [artifact hashes and limits](trials/s014-packaged-smoke-1.11.20-2026-10-27.json).
