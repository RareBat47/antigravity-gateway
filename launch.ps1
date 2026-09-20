# Antigravity Gateway PowerShell Launcher
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Antigravity Gateway - Control Console"

Set-Location -Path $PSScriptRoot

Clear-Host

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "         ANTIGRAVITY MULTI-ACCOUNT GATEWAY & LIVE QUOTA CONTROLLER              " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Detect Python executable
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -Path $venvPython) {
    $pythonExe = $venvPython
    Write-Host "[OK] Virtual Environment: " -NoNewline -ForegroundColor Green
    Write-Host ".venv ($pythonExe)" -ForegroundColor Gray
} else {
    $sysCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($sysCmd) {
        $pythonExe = $sysCmd.Source
        Write-Host "[INFO] System Python: " -NoNewline -ForegroundColor Yellow
        Write-Host "$pythonExe" -ForegroundColor Gray
    } else {
        Write-Host "[ERROR] Python 3.11+ not found! Please create .venv or install Python." -ForegroundColor Red
        Write-Host ""
        Read-Host "Press Enter to exit..."
        exit 1
    }
}

# Add src to PYTHONPATH
$srcPath = Join-Path $PSScriptRoot "src"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$srcPath;$($env:PYTHONPATH)"
} else {
    $env:PYTHONPATH = "$srcPath"
}

Write-Host "[OK] Environment configured: " -NoNewline -ForegroundColor Green
Write-Host "PYTHONPATH set to $srcPath" -ForegroundColor Gray
Write-Host ""

Write-Host "================================================================================" -ForegroundColor DarkCyan
Write-Host "                             SERVICE ACCESS LINKS                               " -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor DarkCyan
Write-Host "  Admin Dashboard : " -NoNewline -ForegroundColor Yellow
Write-Host "http://127.0.0.1:8999/admin/dashboard" -ForegroundColor Green
Write-Host "  Live Quota UI   : " -NoNewline -ForegroundColor Yellow
Write-Host "http://127.0.0.1:8999/admin/dashboard (Gemini & Claude 5h Meters)" -ForegroundColor Cyan
Write-Host "  Swagger API Docs: " -NoNewline -ForegroundColor Yellow
Write-Host "http://127.0.0.1:8999/docs" -ForegroundColor Green
Write-Host "  Health Check    : " -NoNewline -ForegroundColor Yellow
Write-Host "http://127.0.0.1:8999/health" -ForegroundColor Green
Write-Host "  OpenAI API Base : " -NoNewline -ForegroundColor Yellow
Write-Host "http://127.0.0.1:8999/v1" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "[INFO] Starting Gateway Server... Live logs will stream below." -ForegroundColor Cyan
Write-Host "[INFO] Press Ctrl+C at any time to stop the server." -ForegroundColor DarkGray
Write-Host ""

# Open browser dashboard in background after short delay
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8999/admin/dashboard"
} | Out-Null

# Run Server
try {
    & $pythonExe -m agw.main
} catch {
    Write-Host ""
    Write-Host "[ERROR] Server stopped: $_" -ForegroundColor Red
    Write-Host ""
}

Write-Host ""
Write-Host "Gateway stopped." -ForegroundColor Yellow
Read-Host "Press Enter to close this window..."
