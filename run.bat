@echo off
title Antigravity Gateway Launcher

:: Detect repository directory
if exist "%~dp0launch.ps1" (
    cd /d "%~dp0"
    start "Antigravity Gateway Console" powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0launch.ps1"
) else (
    cd /d "D:\Unlimited\AGY"
    start "Antigravity Gateway Console" powershell.exe -NoExit -ExecutionPolicy Bypass -File "D:\Unlimited\AGY\launch.ps1"
)

