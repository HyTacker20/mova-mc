@echo off
setlocal enabledelayedexpansion
title MovaMC - Compilation Script

echo ====================================
echo  MovaMC Compiler
echo ====================================
echo.

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

echo Syncing dependencies with build group...
uv sync --group build
if errorlevel 1 (
    echo Error: Failed to sync dependencies
    pause
    exit /b 1
)

if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
mkdir dist 2>nul

echo Finding pyfiglet fonts location...
for /f "delims=" %%i in ('uv run python -c "import pyfiglet; import os; print(os.path.dirname(pyfiglet.__file__))"') do set PYFIGLET_PATH=%%i
echo Pyfiglet path: %PYFIGLET_PATH%

echo.
echo ====================================
echo    Compiling CLI Application...
echo ====================================
echo.

uv run pyinstaller --onefile ^
    --name "mova" ^
    --distpath dist ^
    --workpath build ^
    --specpath . ^
    --clean ^
    --noconfirm ^
    --console ^
    --add-data "src;src" ^
    --add-data "%PYFIGLET_PATH%\fonts;pyfiglet\fonts" ^
    --hidden-import "app" ^
    --hidden-import "app.commands" ^
    --hidden-import "app.commands.command_line" ^
    --hidden-import "app.commands.app" ^
    --hidden-import "app.commands.translate" ^
    --hidden-import "app.core" ^
    --hidden-import "app.core.settings" ^
    --hidden-import "app.core.translator" ^
    --hidden-import "app.core.file_manager" ^
    --hidden-import "app.parsers" ^
    --hidden-import "app.parsers.json_parser" ^
    --hidden-import "app.parsers.lang_parser" ^
    --hidden-import "app.parsers.mcfunction_parser" ^
    --hidden-import "app.services" ^
    --hidden-import "app.data" ^
    --hidden-import "deep_translator" ^
    --hidden-import "rich" ^
    --hidden-import "questionary" ^
    --hidden-import "pyfiglet" ^
    --hidden-import "pyfiglet.fonts" ^
    --collect-data pyfiglet ^
    --hidden-import "argparse" ^
    --hidden-import "json" ^
    --paths src ^
    src/app/__main__.py

if errorlevel 1 (
    echo.
    echo ====================================
    echo     CLI Compilation FAILED!
    echo ====================================
    pause
    exit /b 1
)

echo CLI application compiled successfully.

echo Creating wrapper script for app version...
echo import sys > temp_app_wrapper.py
echo import os >> temp_app_wrapper.py
echo sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src')) >> temp_app_wrapper.py
echo sys.argv.append('app') >> temp_app_wrapper.py
echo from app.commands.app import main >> temp_app_wrapper.py
echo if __name__ == '__main__': >> temp_app_wrapper.py
echo     main() >> temp_app_wrapper.py

echo.
echo ====================================
echo  Compiling Interactive Application...
echo ====================================
echo.

uv run pyinstaller --onefile ^
    --name "MovaMC" ^
    --distpath dist ^
    --workpath build ^
    --specpath . ^
    --clean ^
    --noconfirm ^
    --console ^
    --add-data "src;src" ^
    --add-data "%PYFIGLET_PATH%\fonts;pyfiglet\fonts" ^
    --hidden-import "app" ^
    --hidden-import "app.commands" ^
    --hidden-import "app.commands.command_line" ^
    --hidden-import "app.commands.app" ^
    --hidden-import "app.commands.translate" ^
    --hidden-import "app.core" ^
    --hidden-import "app.core.settings" ^
    --hidden-import "app.core.translator" ^
    --hidden-import "app.core.file_manager" ^
    --hidden-import "app.parsers" ^
    --hidden-import "app.parsers.json_parser" ^
    --hidden-import "app.parsers.lang_parser" ^
    --hidden-import "app.parsers.mcfunction_parser" ^
    --hidden-import "app.services" ^
    --hidden-import "app.data" ^
    --hidden-import "deep_translator" ^
    --hidden-import "rich" ^
    --hidden-import "questionary" ^
    --hidden-import "pyfiglet" ^
    --hidden-import "pyfiglet.fonts" ^
    --collect-data pyfiglet ^
    --hidden-import "argparse" ^
    --hidden-import "json" ^
    --paths src ^
    temp_app_wrapper.py

if errorlevel 1 (
    echo.
    echo ====================================
    echo     APP Compilation FAILED!
    echo ====================================
    del temp_app_wrapper.py 2>nul
    pause
    exit /b 1
)

del temp_app_wrapper.py 2>nul

echo Interactive application compiled successfully.

set CLI_EXISTS=0
set APP_EXISTS=0

if exist "dist\mova.exe" set CLI_EXISTS=1
if exist "dist\MovaMC.exe" set APP_EXISTS=1

if %CLI_EXISTS%==1 if %APP_EXISTS%==1 (
    echo.
    echo ====================================
    echo     Compilation SUCCESSFUL!
    echo ====================================
    echo.
    echo CLI Executable: dist\mova.exe
    dir "dist\mova.exe" | find "mova.exe"
    echo.
    echo APP Executable: dist\MovaMC.exe
    dir "dist\MovaMC.exe" | find "MovaMC.exe"
    echo.
    echo Usage:
    echo   CLI: "dist\mova.exe" [commands]
    echo   APP: "dist\MovaMC.exe"
    echo.
) else (
    echo.
    echo ====================================
    echo     Compilation FAILED!
    echo ====================================
    if %CLI_EXISTS%==0 echo Error: CLI executable not found in dist directory
    if %APP_EXISTS%==0 echo Error: APP executable not found in dist directory
    pause
    exit /b 1
)

echo Cleaning build artifacts...
if exist "build" rmdir /s /q build
if exist "mova.spec" del "mova.spec"
if exist "MovaMC.spec" del "MovaMC.spec"

echo.
echo ====================================
echo     Compilation Complete!
echo ====================================
echo.

pause
