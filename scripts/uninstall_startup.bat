@echo off
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
del /Q "%STARTUP%\AntigravityGateway.vbs" >nul 2>&1
del /Q "%STARTUP%\AntigravityGateway.lnk" >nul 2>&1
echo [SUCCESS] Antigravity Gateway startup trigger removed.
