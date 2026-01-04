#!/usr/bin/env bash
#
# Simple launcher script for BSides FW 2025 Badge Simulator
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}BSides FW 2025 Badge Simulator${NC}"
echo "================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

# Check MicroPython
if ! command -v micropython &> /dev/null; then
    echo -e "${YELLOW}Warning: micropython not found in PATH${NC}"
    echo "You may need to specify the path with -m flag"
    echo ""
fi

# Check dependencies
echo "Checking dependencies..."
python3 -c "import pygame" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: pygame not installed${NC}"
    echo "Install with: pip install pygame"
    exit 1
fi

python3 -c "import PIL" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Pillow not installed${NC}"
    echo "Install with: pip install Pillow"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies OK${NC}"
echo ""

# Run simulator
echo "Starting simulator..."
echo ""

python3 main_improved.py "$@"

exit $?
