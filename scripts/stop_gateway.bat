@echo off
echo Stopping Antigravity Gateway on port 8999...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8999 ^| findstr LISTENING') do (
    taskkill /F /PID %%a
)
echo Gateway stopped.
pause
