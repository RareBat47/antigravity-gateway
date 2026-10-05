@echo off
echo Removing Antigravity Gateway from Windows Startup...
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AntigravityGateway.lnk" >nul 2>&1
echo [SUCCESS] Removed Antigravity Gateway from Windows Startup.
pause
