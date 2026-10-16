# Navis Protocol Desktop

The Windows production app uses Tauri v2, a static Next.js export, Rust IPC adapters, and local Python subprocesses for selected workflows. It launches no Next.js or FastAPI server. The web/FastAPI stack remains a compatibility and development mode.

## Prerequisites and commands

Development/build requires Node/npm, Rust/Cargo, Windows C++ build tools, and WebView2. Packaging also requires NSIS. The installed app requires WebView2, an accessible Vault, and Python 3.11+ with [backend requirements](../backend/requirements.txt) for Python-backed operations. Python is external to the installer.

Run from `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm ci` | Install locked frontend dependencies |
| `npm run desktop` | Tauri development window; starts Next.js on 127.0.0.1:3000 |
| `npm run build:desktop` | Static export into `out/` using `NAVIS_TAURI_BUILD=true` |
| `npm run desktop:build` | Native build with the configured static-export hook |
| `npm run desktop:build:release` | Static export and NSIS release bundle |
| `npm run typecheck:desktop` | Cargo check, without producing an installer |
| `npm run desktop:diagnostics` | Tauri toolchain information |

From the repository root, `build_navis_desktop.bat` runs dependency installation and the NSIS build. Installers are under `frontend/src-tauri/target/release/bundle/nsis/`. Web mode uses `npm run dev`, or `npm run build` then `npm run start`, with FastAPI separately; `start_all.vbs` starts the compatibility stack.

## Runtime and configuration

`desktopApi.js` selects IPC in Tauri and HTTP in web mode. Native modules provide Vault/journal/task access, realms, missions, squad and combat deployment controls, battle state and recoverable combat completion, entity-scoped progression and bio adjustments, Lounge/library reads, local banter and Forge proposals. Sync and rollover use event-driven native jobs. Coverage is route-specific: general task toggle lacks the web route's XP synchronization, and settings writes, hosted AI controls and several chat capabilities are unavailable. See the [endpoint registry](../docs/api_endpoints.md).

Set `NAVIS_ROOT` to the canonical Vault directory containing `Bridge` and `Journal`; the native resolver defaults to `G:\My Drive\Navis-Vault`. Python discovery uses `NAVIS_PYTHON` first, the backend virtualenv in development, then the launching account's PATH in releases. Restart the app after changing environment variables. Installed resources supply the checked-in backend entrypoints and selected services; they do not supply Python or every Vault integration script.

Local journal polishing, banter and Forge generation require an available Ollama service/model. Forge writes require explicit proposal approval. Native War Room, Reid chat and general neural chat return unavailable. P5 script operations require their allowlisted files in the Vault. See [local AI](../docs/local-first-ai.md), [Forge](../docs/forge-local-generation.md), and [architecture](../docs/architecture.md).

## Diagnostics and recovery

The cockpit's `startup_diagnostics` command reports Vault availability, required Bridge files, Companions, status-file write access, lock warnings and failed migration markers. WebView availability is inferred from successful Tauri startup; this is not a full prelaunch prerequisite audit or a universal write gate.

Close the app before repairing dependencies or configuration. Preserve Vault files and inspect diagnostics before retrying. Use `Stop_Navis.bat` if compatibility services were started. A faulty release can be uninstalled and replaced with a previous installer; this alone does not undo Vault writes. Run compatibility mode separately when needed.

The [release guide](../docs/desktop-release.md) records build evidence and disposable-fixture smoke procedures. A built installer or passing unit test does not establish clean-machine installation, live-Vault correctness or shutdown safety; those manual checks remain separate.
