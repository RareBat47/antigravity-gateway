@echo off
setlocal
echo Looking for Arena Gateway running on port 9000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":9000 .*LISTENING"') do (
    echo Terminating PID %%a...
    taskkill /F /PID %%a
)
echo Done.
