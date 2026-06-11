@echo off
setlocal enabledelayedexpansion
title MovaMC - Setup Script

echo ====================================
echo  MovaMC Setup
echo ====================================
echo.

cd /d "%~dp0\.."

where uv >nul 2>&1
if errorlevel 1 (
    echo uv not found. Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo Error: Failed to install uv
        pause
        exit /b 1
    )
    echo uv installed successfully. Please restart your terminal or run setup again.
    pause
    exit /b 0
)

echo Syncing dependencies...
uv sync
if errorlevel 1 (
    echo Error: Failed to sync dependencies
    pause
    exit /b 1
)

echo.
echo ====================================
echo      Setup Complete!
echo ====================================
echo.

uv run mova --help

pause
