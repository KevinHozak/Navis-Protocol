# Cockpit-P6 Launcher Verification and Runtime Prerequisites

**Reference Issue:** [#157](https://github.com/KevinHozak/Navis-Protocol-Private/issues/157)  
**Parent Epic:** #144  
**Date:** 2026-10-02  

---

## 1. Summary of Changes

During the September 30 audit, `backend/start_backend.vbs` was identified as having stale paths pointing to `C:\Projects\Navis-Web` and targeting `G:\My Drive\Navis-Protocol` as the Vault root.

The following changes were implemented:
1. **`backend/start_backend.vbs`:**
   - Updated from obsolete `Navis-Web` to dynamically resolve the `backend` folder relative to the script location (fallback `C:\Projects\Navis-Protocol\backend`).
   - Standardized `NAVIS_ROOT` default to `G:\My Drive\Navis-Vault`, while respecting any pre-existing `NAVIS_ROOT` environment override.
   - Standardized Python interpreter discovery: respects `NAVIS_PYTHON`, falls back to local `.venv\Scripts\python.exe` if present, then system `python.exe`.
   - Windows remain hidden (`0, False`) for production/compatibility startup.
   - Added `NAVIS_LAUNCH_DRY_RUN` smoke-testing mode to report resolved variables without starting processes or touching the personal Vault.
2. **`start_all.vbs`:**
   - Updated directory resolution dynamically from the script location.
   - Updated Python runtime discovery consistent with Tauri and `start_backend.vbs` (`NAVIS_PYTHON` -> local `.venv` -> `python.exe`).
   - Honors `NAVIS_ROOT` override before defaulting to `G:\My Drive\Navis-Vault`.
   - Added `NAVIS_LAUNCH_DRY_RUN` smoke-testing mode.
3. **`Stop_Navis.bat`:**
   - Added `NAVIS_LAUNCH_DRY_RUN` smoke-testing mode (echoes targeted ports `8000, 3000` and process `navis-protocol.exe` without terminating live processes).
4. **`backend/verify_battle.py` & `backend/verify_services.py`:**
   - Removed hardcoded `c:\Projects\Navis-Web\backend` in favor of `Path(__file__).resolve().parent`.
5. **Documentation:**
   - Updated `AGENTS.md` and `docs/desktop-release.md` documenting launcher targets, runtime precedence, and smoke testing.
6. **Automated Smoke Tests:**
   - Created `backend/tests/test_launchers.py` covering static path audits, hidden-window flags, dry-run default resolution, synthetic directory/python overrides, stop targets, and runtime prerequisites.

---

## 2. Runtime Prerequisites

### Required Software & Interpreters
- **Python:** Version 3.11 or newer (tested on Python 3.14.3 win32).
  - Runtime resolution order:
    1. Environment variable `NAVIS_PYTHON` pointing to a valid python executable.
    2. Virtual environment at `backend/.venv/Scripts/python.exe`.
    3. `python.exe` found on system `PATH`.
- **Node.js & npm:** Required for frontend dev server (`npm run dev`) when running `start_all.vbs`.
- **Windows Script Host (`cscript.exe` / `wscript.exe`):** Built into Windows; used for executing `.vbs` launchers.

### Target Network Ports
- **Backend:** `127.0.0.1:8000` (FastAPI / Uvicorn).
- **Frontend:** `127.0.0.1:3000` (Next.js dev server).

### Vault Precedence
- If `NAVIS_ROOT` is configured in the environment, all launchers honor it.
- Default: `G:\My Drive\Navis-Vault`.
- No operations silently target `Navis-Web` or `G:\My Drive\Navis-Protocol`.

---

## 3. Verification Test Matrix

Run via pytest:
```powershell
python -m pytest backend/tests/test_launchers.py -v
```

| Test Name | Status | Verified Condition |
| :--- | :--- | :--- |
| `test_no_obsolete_paths_in_launchers_and_scripts` | PASS | Zero occurrences of `Navis-Web` or `G:\My Drive\Navis-Protocol` across launchers, batch scripts, and verification utilities. |
| `test_window_hidden_convention` | PASS | Window state parameter `0, False` verified for all VBScript launchers. |
| `test_start_backend_vbs_dry_run_defaults` | PASS | Correct directory, `G:\My Drive\Navis-Vault`, and uvicorn invocation. |
| `test_start_backend_vbs_synthetic_overrides` | PASS | Synthetic `NAVIS_ROOT` and `NAVIS_PYTHON` correctly honored. |
| `test_start_all_vbs_dry_run_defaults` | PASS | Root, backend, and frontend directories correctly resolved. |
| `test_start_all_vbs_synthetic_overrides` | PASS | Both targets honor synthetic root and python path. |
| `test_stop_navis_bat_dry_run` | PASS | Targets ports 8000, 3000, and process `navis-protocol.exe`. |
| `test_runtime_prerequisites` | PASS | Python >= 3.11 validated; FastAPI and Uvicorn packages verified. |
