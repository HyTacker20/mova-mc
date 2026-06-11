#!/bin/bash

echo "===================================="
echo "  MovaMC Setup"
echo "===================================="
echo

cd "$(dirname "$0")/.."

if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install uv"
        exit 1
    fi
    echo "uv installed. Please restart your shell or run setup again."
    exit 0
fi

echo "Syncing dependencies..."
uv sync
if [ $? -ne 0 ]; then
    echo "Error: Failed to sync dependencies"
    exit 1
fi

echo
echo "===================================="
echo "      Setup Complete!"
echo "===================================="
echo

uv run mova --help
