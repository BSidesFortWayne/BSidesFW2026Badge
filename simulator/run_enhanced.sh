#!/bin/bash

# BSides FW 2025 Badge Simulator - Enhanced Version
# Run from the simulator directory

cd "$(dirname "$0")"

# Install pygame_gui if not already installed
pip install pygame-gui 2>/dev/null || pip3 install pygame-gui 2>/dev/null

# Run the enhanced simulator
python3 main_enhanced.py -p ../src
