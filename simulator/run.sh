#!/usr/bin/env bash
#
# BSides FW 2025 Badge Simulator
#
# Quick launcher for the badge simulator with binary protocol and enhanced GUI.
# Run with --setup for first-time configuration.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  BSides FW 2025 Badge Simulator               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Show help if requested
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: ./run.sh [options]"
    echo ""
    echo "Setup:"
    echo "  --setup              Run first-time setup wizard"
    echo ""
    echo "Common Options:"
    echo "  -p PATH              Project directory (default: ../src)"
    echo "  -v                   Verbose output"
    echo "  --help               Show this help"
    echo ""
    echo "Advanced Options:"
    echo "  -c FILE              Custom config file"
    echo "  --port PORT          JSON protocol port (default: 4455)"
    echo "  --binary-port PORT   Binary protocol port (default: 4456)"
    echo "  --no-logs            Disable file logging"
    echo ""
    echo "Features (always enabled):"
    echo "  • Binary protocol (10-20x faster rendering)"
    echo "  • Hardware control panel (mock sensors)"
    echo "  • Dual circular displays (240x240)"
    echo "  • Full button emulation (keyboard 0-7)"
    echo ""
    echo "Examples:"
    echo "  ./run.sh                    # Run with defaults"
    echo "  ./run.sh --setup            # First-time setup"
    echo "  ./run.sh -p ../src -v       # Custom project, verbose"
    echo ""
    exit 0
fi

# Check if setup is needed
if [ ! -f "config.json" ] && [[ "$1" != "--setup" ]]; then
    echo -e "${YELLOW}⚠ First time running? You should run setup first!${NC}"
    echo ""
    echo "  ./run.sh --setup"
    echo ""
    echo "Or continue with defaults (../src as project directory)"
    echo ""
    read -p "Continue anyway? [y/N]: " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Run: ./run.sh --setup"
        exit 0
    fi
fi

# Show startup info
if [ $# -eq 0 ]; then
    echo -e "${BLUE}Features:${NC}"
    echo "  ✓ Binary protocol (10-20x faster)"
    echo "  ✓ Hardware control panel"
    echo "  ✓ Dual circular displays"
    echo ""
fi

# Run simulator
exec uv run python3 simulator.py "$@"
