@echo off
title Antigravity Gateway - 1-Click Installer
setlocal enabledelayedexpansion

echo =====================================================================
echo           ANTIGRAVITY GATEWAY - ZERO-TOUCH PC INSTALLER              
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.11+.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 3. Install Dependencies
echo [*] Installing gateway dependencies...
.venv\Scripts\pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: 4. Auto-Configure PC Environment & IDEs
echo [*] Auto-configuring PC environment and developer tools...
.venv\Scripts\python -m agw.cli.main setup-pc

:: 5. Copy config if missing
if not exist "config.yaml" (
    copy config.example.yaml config.yaml >nul
)

echo.
echo =====================================================================
echo  [SUCCESS] Antigravity Gateway is ready!
echo  Next Steps:
echo    1. Start the gateway: run.bat (or scripts\install_startup.bat for auto-boot)
echo    2. Open http://localhost:8999 in your browser and click "+ Add Google Account"
echo    3. All tools on your PC (Claude Code, Cursor, OpenCode, Aider) are already wired!
echo =====================================================================
echo.
pause
