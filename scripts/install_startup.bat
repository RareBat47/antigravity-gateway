@echo off
setlocal
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if not exist "%STARTUP%" mkdir "%STARTUP%"
copy /Y "%~dp0start_gateway_service.vbs" "%STARTUP%\AntigravityGateway.vbs" >nul
if errorlevel 1 (
  echo [ERROR] Could not install startup trigger.
  exit /b 1
)
echo [SUCCESS] Antigravity Gateway will start silently when you sign into Windows.
echo Log: %~dp0..\logs\gateway-service.log

