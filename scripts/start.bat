@echo off
setlocal enabledelayedexpansion
title MovaMC

cd /d "%~dp0\.."

where uv >nul 2>&1
if errorlevel 1 (
    echo Error: uv not found. Please run setup.bat first.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Error: Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

uv run mova app %*

echo.
echo Press Enter to exit...
pause > nul
