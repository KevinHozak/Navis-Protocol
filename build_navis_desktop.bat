@echo off
setlocal
pushd "%~dp0frontend"
call npm ci
if errorlevel 1 exit /b 1
call npm run desktop:build:release
if errorlevel 1 exit /b 1
popd
endlocal
