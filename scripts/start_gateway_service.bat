@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "LOGDIR=%ROOT%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%ROOT%"

rem Prefer the packaged executable; fall back to the project virtualenv.
if exist "%ROOT%\dist\GeminiAPI.exe" (
  "%ROOT%\dist\GeminiAPI.exe" >> "%LOGDIR%\gateway-service.log" 2>&1
) else if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHONPATH=%ROOT%\src"
  "%ROOT%\.venv\Scripts\python.exe" -m agw.main >> "%LOGDIR%\gateway-service.log" 2>&1
) else (
  echo [%date% %time%] No packaged executable or project virtualenv found >> "%LOGDIR%\gateway-service.log"
  exit /b 1
)
