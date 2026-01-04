# Simulator Phase 0: Infrastructure & Tooling

## Overview

Phase 0 establishes the foundation for simulator development with improved logging, configuration management, and standardized workflows. This enables better debugging and AI-assisted development.

## New Files

### Core Infrastructure

- **`config.json`** - Configuration file for simulator settings
- **`logger.py`** - Structured logging system
- **`main_improved.py`** - Enhanced main entry point with better error handling
- **`run.sh`** - Convenient launcher script

### Key Improvements

1. **Structured Logging**
   - All events logged to timestamped files in `logs/`
   - JSON Lines format (`.jsonl`) for machine parsing
   - Human-readable text logs (`.log`)
   - Separate streams for MicroPython stdout/stderr

2. **Configuration Management**
   - Single `config.json` for all settings
   - Command-line overrides
   - Sensible defaults

3. **Better Error Handling**
   - Validation before startup
   - Clear error messages with hints
   - Graceful shutdown

4. **AI-Friendly Output**
   - Structured logs for parsing
   - Event types: startup, micropython, command, error, warning, info
   - Timestamp on all events

## Usage

### Quick Start

```bash
cd simulator
./run.sh
```

### With Options

```bash
# Verbose output
./run.sh -v

# Custom project path
./run.sh -p /path/to/badge/code

# Show FPS counter
# Edit config.json: "show_fps": true

# Different port
./run.sh --port 4456
```

### Configuration

Edit `config.json` to customize:

```json
{
  "project_path": "../src",           // Project to simulate
  "micropython_path": "micropython",   // MicroPython executable
  "socket_port": 4455,                 // IPC port
  "logging": {
    "enabled": true,                   // Enable file logging
    "log_micropython": true,           // Log MP output
    "log_gui_commands": false,         // Log GUI commands
    "log_button_polling": false,       // Log button polls (noisy)
    "structured_output": true          // JSON logs
  },
  "gui": {
    "window_title": "Badge Simulator",
    "show_fps": false,                 // Show FPS counter
    "target_fps": 60                   // Frame rate limit
  },
  "debug": {
    "verbose": false,                  // Print all logs to console
    "print_commands": false,           // Print commands as received
    "print_startup": true              // Print startup info
  }
}
```

## Log Files

Logs are written to `simulator/logs/`:

```
logs/
├── simulator_20260103_143022.log      # Human-readable
└── simulator_20260103_143022.jsonl   # Machine-readable
```

### Log Format

**Text Log** (`.log`):
```
[2026-01-03T14:30:22] [STARTUP] {"project_path": "../src", ...}
[2026-01-03T14:30:22] [INFO] Setting up project directory...
[2026-01-03T14:30:23] [MP] Initializing BSP
[2026-01-03T14:30:24] [COMMAND] {"module": "gc9a01", "command": "fill", ...}
```

**JSON Lines** (`.jsonl`):
```json
{"timestamp": "2026-01-03T14:30:22", "type": "startup", "project_path": "../src", ...}
{"timestamp": "2026-01-03T14:30:22", "type": "info", "message": "Setting up..."}
{"timestamp": "2026-01-03T14:30:23", "type": "micropython", "stream": "stdout", "line": "Initializing BSP"}
{"timestamp": "2026-01-03T14:30:24", "type": "command", "module": "gc9a01", "command": "fill", ...}
```

## AI Analysis

The structured logs enable AI-powered debugging:

### Parse Logs

```python
import json

# Read JSON logs
with open('logs/simulator_20260103_143022.jsonl') as f:
    events = [json.loads(line) for line in f]

# Find errors
errors = [e for e in events if e['type'] == 'error']

# Track commands
commands = [e for e in events if e['type'] == 'command']
print(f"Total commands: {len(commands)}")

# Analyze MicroPython output
mp_output = [e for e in events if e['type'] == 'micropython']
```

### Example Queries

**"What errors occurred?"**
```bash
grep '"type": "error"' logs/simulator_*.jsonl | jq .
```

**"What display commands were sent?"**
```bash
grep '"module": "gc9a01"' logs/simulator_*.jsonl | jq '{command: .command}'
```

**"How many button polls?"**
```bash
grep '"command": "get_inputs"' logs/simulator_*.jsonl | wc -l
```

## Command-Line Reference

```
usage: main_improved.py [-h] [-p PROJECT] [-m MICROPYTHON] [-c CONFIG]
                        [-v] [--no-gui] [--port PORT] [--no-logs]

BSides FW 2025 Badge Simulator

optional arguments:
  -h, --help            show this help message and exit
  -p PROJECT, --project PROJECT
                        Project directory containing main.py
  -m MICROPYTHON, --micropython MICROPYTHON
                        MicroPython executable path
  -c CONFIG, --config CONFIG
                        Configuration file (default: config.json)
  -v, --verbose         Verbose output
  --no-gui              Run without GUI (testing mode)
  --port PORT           Socket port (default: from config or 4455)
  --no-logs             Disable logging to files
```

## Troubleshooting

### Port Already in Use

```bash
# Use different port
./run.sh --port 4456

# Or kill existing process
lsof -ti:4455 | xargs kill
```

### MicroPython Not Found

```bash
# Specify full path
./run.sh -m /path/to/micropython

# Or update config.json
```

### Dependencies Missing

```bash
# Install pygame and Pillow
pip install pygame Pillow
```

### Logs Too Large

Edit `config.json`:
```json
{
  "logging": {
    "log_gui_commands": false,    // Disable noisy logs
    "log_button_polling": false
  }
}
```

## Migration from Old main.py

The old `main.py` still works, but `main_improved.py` offers:

- ✅ Better error messages
- ✅ Structured logging
- ✅ Configuration file
- ✅ Graceful shutdown
- ✅ Output capture for debugging

To migrate:
1. Keep your old workflow: `python3 main.py -p ../src`
2. Or try new: `./run.sh` (uses config.json)
3. Eventually: `mv main_improved.py main.py`

## Next Steps: Phase 1

With Phase 0 infrastructure in place, we can now:
- Implement framebuffer support with confidence
- Debug issues using structured logs
- Track performance metrics
- Capture AI feedback loops

See [SIMULATOR_UPDATE_DESIGN.md](../../docs/SIMULATOR_UPDATE_DESIGN.md) for Phase 1 details.
