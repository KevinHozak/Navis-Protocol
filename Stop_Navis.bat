@echo off
title Stop Navis Services
if not "%NAVIS_LAUNCH_DRY_RUN%"=="" (
    echo DRY_RUN: STOP_PORTS=8000,3000
    echo DRY_RUN: STOP_PROCESSES=navis-protocol.exe
    exit /b 0
)
echo 🛑 Terminating local Navis processes...
taskkill /IM navis-protocol.exe /T /F > nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8000, 3000 -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
echo ✅ Stopped.
ping -n 3 127.0.0.1 > nul
