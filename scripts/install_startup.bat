@echo off
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
cd /d "%PROJECT_DIR%"
set ABS_PROJECT_DIR=%CD%

echo Registering Antigravity Gateway to Windows Startup...
powershell -NoProfile -Command "$wsh = New-Object -ComObject WScript.Shell; $s = $wsh.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\AntigravityGateway.lnk\"); $s.TargetPath = 'wscript.exe'; $s.Arguments = \"`\"$env:ABS_PROJECT_DIR\scripts\start_silent.vbs`\"\"; $s.WorkingDirectory = \"`\"$env:ABS_PROJECT_DIR`\"\"; $s.Save()"

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Antigravity Gateway will now automatically start in the background when Windows boots!
) else (
    echo [ERROR] Failed to register startup shortcut.
)
pause
