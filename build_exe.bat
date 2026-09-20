@echo off
setlocal
cd /d "%~dp0"
title Build Gemini API Windows Executable

echo =====================================================================
echo                Building Standalone GeminiAPI.exe                     
echo =====================================================================
echo.

if exist "%~dp0.venv\Scripts\pyinstaller.exe" (
    "%~dp0.venv\Scripts\pyinstaller.exe" --noconfirm GeminiAPI.spec
) else (
    pyinstaller --noconfirm GeminiAPI.spec
)

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Binary built successfully at: dist\GeminiAPI.exe
) else (
    echo.
    echo [ERROR] Build failed with exit code %errorlevel%
)

echo.
pause
