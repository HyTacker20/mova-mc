#!/bin/bash

echo "===================================="
echo "  MovaMC Compiler"
echo "===================================="
echo

cd "$(dirname "$0")/.."

if ! command -v uv &> /dev/null; then
    echo "Error: uv not found. Please run setup.sh first."
    exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
    echo "Error: Virtual environment not found. Please run setup.sh first."
    exit 1
fi

echo "Syncing dependencies with build group..."
uv sync --group build
if [ $? -ne 0 ]; then
    echo "Error: Failed to sync dependencies"
    exit 1
fi

if [ -d "build" ]; then rm -rf build; fi
if [ -d "dist" ]; then rm -rf dist; fi
mkdir -p dist

echo "Finding pyfiglet fonts location..."
PYFIGLET_PATH=$(uv run python -c "import pyfiglet; import os; print(os.path.dirname(pyfiglet.__file__))")
echo "Pyfiglet path: $PYFIGLET_PATH"

echo
echo "===================================="
echo "    Compiling CLI Application..."
echo "===================================="
echo

uv run pyinstaller --onefile \
    --name "mova" \
    --distpath dist \
    --workpath build \
    --specpath . \
    --clean \
    --noconfirm \
    --console \
    --add-data "src:src" \
    --add-data "$PYFIGLET_PATH/fonts:pyfiglet/fonts" \
    --hidden-import "app" \
    --hidden-import "app.commands" \
    --hidden-import "app.commands.command_line" \
    --hidden-import "app.commands.app" \
    --hidden-import "app.commands.translate" \
    --hidden-import "app.core" \
    --hidden-import "app.core.settings" \
    --hidden-import "app.core.translator" \
    --hidden-import "app.core.file_manager" \
    --hidden-import "app.parsers" \
    --hidden-import "app.parsers.json_parser" \
    --hidden-import "app.parsers.lang_parser" \
    --hidden-import "app.parsers.mcfunction_parser" \
    --hidden-import "app.services" \
    --hidden-import "app.data" \
    --hidden-import "deep_translator" \
    --hidden-import "rich" \
    --hidden-import "questionary" \
    --hidden-import "pyfiglet" \
    --hidden-import "pyfiglet.fonts" \
    --collect-data pyfiglet \
    --hidden-import "argparse" \
    --hidden-import "json" \
    --paths src \
    src/app/__main__.py

if [ $? -ne 0 ]; then
    echo
    echo "===================================="
    echo "     CLI Compilation FAILED!"
    echo "===================================="
    exit 1
fi

echo "CLI application compiled successfully."

echo "Creating wrapper script for app version..."
cat > temp_app_wrapper.py << 'EOF'
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.argv.append('app')
from app.commands.app import main
if __name__ == '__main__':
    main()
EOF

echo
echo "===================================="
echo "  Compiling Interactive Application..."
echo "===================================="
echo

uv run pyinstaller --onefile \
    --name "MovaMC" \
    --distpath dist \
    --workpath build \
    --specpath . \
    --clean \
    --noconfirm \
    --console \
    --add-data "src:src" \
    --add-data "$PYFIGLET_PATH/fonts:pyfiglet/fonts" \
    --hidden-import "app" \
    --hidden-import "app.commands" \
    --hidden-import "app.commands.command_line" \
    --hidden-import "app.commands.app" \
    --hidden-import "app.commands.translate" \
    --hidden-import "app.core" \
    --hidden-import "app.core.settings" \
    --hidden-import "app.core.translator" \
    --hidden-import "app.core.file_manager" \
    --hidden-import "app.parsers" \
    --hidden-import "app.parsers.json_parser" \
    --hidden-import "app.parsers.lang_parser" \
    --hidden-import "app.parsers.mcfunction_parser" \
    --hidden-import "app.services" \
    --hidden-import "app.data" \
    --hidden-import "deep_translator" \
    --hidden-import "rich" \
    --hidden-import "questionary" \
    --hidden-import "pyfiglet" \
    --hidden-import "pyfiglet.fonts" \
    --collect-data pyfiglet \
    --hidden-import "argparse" \
    --hidden-import "json" \
    --paths src \
    temp_app_wrapper.py

if [ $? -ne 0 ]; then
    echo
    echo "===================================="
    echo "     APP Compilation FAILED!"
    echo "===================================="
    rm -f temp_app_wrapper.py
    exit 1
fi

rm -f temp_app_wrapper.py

echo "Interactive application compiled successfully."

CLI_EXISTS=0
APP_EXISTS=0

if [ -f "dist/mova" ]; then CLI_EXISTS=1; fi
if [ -f "dist/MovaMC" ]; then APP_EXISTS=1; fi

if [ $CLI_EXISTS -eq 1 ] && [ $APP_EXISTS -eq 1 ]; then
    echo
    echo "===================================="
    echo "     Compilation SUCCESSFUL!"
    echo "===================================="
    echo
    echo "CLI Executable: dist/mova"
    ls -la "dist/mova"
    echo
    echo "APP Executable: dist/MovaMC"
    ls -la "dist/MovaMC"
    echo
    echo "Usage:"
    echo "  CLI: \"dist/mova\" [commands]"
    echo "  APP: \"dist/MovaMC\""
    echo
else
    echo
    echo "===================================="
    echo "     Compilation FAILED!"
    echo "===================================="
    if [ $CLI_EXISTS -eq 0 ]; then echo "Error: CLI executable not found in dist directory"; fi
    if [ $APP_EXISTS -eq 0 ]; then echo "Error: APP executable not found in dist directory"; fi
    exit 1
fi

echo "Cleaning build artifacts..."
rm -rf build
rm -f "mova.spec" "MovaMC.spec"

echo
echo "===================================="
echo "     Compilation Complete!"
echo "===================================="
echo

read -p "Press Enter to continue..."
