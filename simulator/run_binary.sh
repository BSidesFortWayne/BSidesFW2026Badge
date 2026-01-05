#!/bin/bash
# Binary protocol simulator launcher
# Usage: ./run_binary.sh [--json-fallback]

set -e

cd "$(dirname "$0")"

# Check if JSON fallback is requested
if [[ "$1" == "--json-fallback" ]]; then
    echo "Running in JSON mode (legacy compatibility)"
    exec python main.py -p ../src -m micropython
else
    echo "Running with BINARY PROTOCOL for maximum performance"
    echo "FPS should be significantly higher with less artifacting"
    echo ""
    exec python main_binary.py -p ../src -m micropython --binary-only
fi
