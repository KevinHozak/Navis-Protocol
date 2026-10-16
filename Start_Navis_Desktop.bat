@echo off
setlocal
if not defined NAVIS_PYTHON (
  if exist "%~dp0backend\.venv\Scripts\python.exe" (
    "%~dp0backend\.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if errorlevel 0 if not errorlevel 1 set "NAVIS_PYTHON=%~dp0backend\.venv\Scripts\python.exe"
  )
)
set "APP=%~dp0frontend\src-tauri\target\release\navis-protocol.exe"
if not exist "%APP%" (
  echo Desktop artifact not found. Run build_navis_desktop.bat first.
  exit /b 1
)
start "Navis Protocol" "%APP%"
endlocal
