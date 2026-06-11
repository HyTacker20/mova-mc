#!/bin/bash

cd "$(dirname "$0")/.."

if ! command -v uv &> /dev/null; then
    echo "Error: uv not found. Please run setup.sh first."
    exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
    echo "Error: Virtual environment not found. Please run setup.sh first."
    exit 1
fi

uv run mova app "$@"

echo
echo "Press Enter to exit..."
read
