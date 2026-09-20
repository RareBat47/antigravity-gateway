@echo off
title Antigravity Gateway Launcher
cd /d "%~dp0"

:: Launch dedicated PowerShell control console
start "Antigravity Gateway Console" powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0launch.ps1"
