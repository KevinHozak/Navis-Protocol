# 🤖 AGENTS.md

> [!IMPORTANT]
> Read this for project startup, architecture mapping, and system-wide directives when pair-programming on Navis-Protocol.

## 🛰️ Project Overview
**Navis-Protocol** is the web portal and cockpit dashboard for the **Navis Protocol** personal productivity and knowledge management system (PKM). It exposes high-fidelity controls for squad deployment, threat tracking, mental/physical readiness, and neural link cognitive arbiters in a unified, modern web interface.

### 💠 Domain Lexicon & Lore
- **Holocron:** In Navis Protocol, all infographics, visual HUD summaries, and telemetry syntheses are canonically called **Holocrons** (e.g. *Weekly Holocron*, *Annual Holocron*). Located under **Chronicle (📜) ➔ Weekly Holocron (💠)** in the UI.

---

## 🗂️ Workspace Architecture

The workspace is organized as a multi-tier codebase:

1. **`frontend/` (Next.js + React)**
   - Immersive sci-fi UI with Glassmorphism, CSS animations, and reactive widgets.
   - Communicates with the backend using the environment variable `NEXT_PUBLIC_API_URL`.
2. **`backend/` (FastAPI + Python)**
   - Acts as the primary interface to the Obsidian-based Vault located on Google Drive.
   - Manages state manifolds, combat registries, and system config.
3. **`docs/` (Documentation)**
   - Houses the master roadmaps, architectural guides, and component blueprints.

---

## ⚙️ Environmental Context & Startup

### 1. Launchers & Processes
- **Unified Startup:** [start_all.vbs](file:///c:/Projects/Navis-Protocol/start_all.vbs) launches both the FastAPI backend and Next.js frontend concurrently in detached processes with hidden windows.
- **Backend Compatibility Launcher:** [start_backend.vbs](file:///c:/Projects/Navis-Protocol/backend/start_backend.vbs) launches only the FastAPI backend in detached mode with a hidden window for backend-specific development and compatibility.
- **Stop Script:** [Stop_Navis.bat](file:///c:/Projects/Navis-Protocol/Stop_Navis.bat) kills active uvicorn/node listener instances on port 8000 and 3000 as well as `navis-protocol.exe`.
- **Desktop Production App:** [Start_Navis_Desktop.bat](file:///c:/Projects/Navis-Protocol/Start_Navis_Desktop.bat) launches the native release Tauri executable.

### 2. Runtime & Vault Mapping
- **Vault Mapping (`NAVIS_ROOT`):** Defaults to `G:\My Drive\Navis-Vault`. Launchers honor `NAVIS_ROOT` if set in the environment before applying the default.
- **Python Runtime (`NAVIS_PYTHON`):** Honors `NAVIS_PYTHON` if set; otherwise defaults to `backend/.venv/Scripts/python.exe`, falling back to `python.exe` on `PATH`. Requires Python 3.11+.
- **Smoke Testing (`NAVIS_LAUNCH_DRY_RUN`):** Setting `NAVIS_LAUNCH_DRY_RUN=1` causes `start_all.vbs`, `backend/start_backend.vbs`, and `Stop_Navis.bat` to echo resolved paths and targets without launching background processes or accessing the personal Vault.

---

## 🎨 Styling & Design Aesthetics

Any modifications to components in [frontend/src/components/](file:///c:/Projects/Navis-Protocol/frontend/src/components) must adhere to these premium styling mandates:
1. **Sci-Fi Glassmorphism:** Use dark modes with semi-transparent backdrops (`bg-zinc-950/90`, `backdrop-blur-md`) and subtle white border highlights (`border-white/10`).
2. **Vibrant Accents:** Tailor accents to the specific pillar.
   - Sanctum/Command: `#00d4ff` (cyan)
   - Combat/Threats: `#ff4d4d` (red)
   - Beasts: `#f59e0b` (amber)
3. **Animations:** Use `framer-motion` for transitions.
4. **No Placeholders:** All assets must resolve to correct URLs or safe alternate error fallbacks (`onError` loaders).

---

## 🛡️ Git Commit Conventions

When staging changes in `Navis-Protocol`:
- Scope prefix: `feat(precision-state):`, `fix(combat):`, `docs:`, `refactor(backend):`.
- Keep commit messages descriptive and atomic.
