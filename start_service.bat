@echo off
setlocal
cd /d "D:\arena-gateway-workspace"

:: Check if already listening on port 9000
netstat -ano | findstr /R /C:":9000 .*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    exit /b 0
)

:: Ensure data directory exists for logging
if not exist "data" mkdir "data"

:: Run Uvicorn server
venv\Scripts\python.exe -m uvicorn agw.main:app --host 127.0.0.1 --port 9000 >> "data\service.log" 2>&1
