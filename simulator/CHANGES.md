# Simulator Cleanup - January 2026

## Latest Changes

### 2026-01-06: Boot Sequence Replication

**Changes:**
- ✅ Simulator now replicates hardware boot sequence: runs `boot.py` first, then `main.py`
- ✅ Auto-generates `_boot_then_main.py` script that executes both files in the same global namespace
- ✅ Variables created in `boot.py` (like `displays`) are now available to `main.py`
- ✅ Matches actual hardware behavior where boot.py runs on power-up before main.py

**Technical Details:**
- Modified `start_micropython()` in simulator.py to create and execute `_boot_then_main.py`
- Script uses `exec()` with `globals()` to maintain variable context between boot.py and main.py
- Added `_boot_then_main.py` to .gitignore (auto-generated file)

**Migration Notes:**
- Removed workaround code from main.py that was checking for simulator mode
- Code now assumes `displays` exists from boot.py (with fallback warning if not)

---

## Summary

The BSides FW 2025 Badge Simulator has been consolidated and simplified. The binary protocol and enhanced GUI features are now always enabled by default, and legacy code has been removed.

## What Changed

### Removed Files (9 files)
These deprecated files have been removed:
- `main.py` - Old JSON-only simulator
- `main_binary.py` - Binary protocol variant
- `main_enhanced.py` - Enhanced GUI variant
- `main_improved.py` - Another variant
- `_deprecated_main_binary.py` - Already marked deprecated
- `_deprecated_main_enhanced.py` - Already marked deprecated
- `run_binary.sh` - Binary protocol launcher
- `run_enhanced.sh` - Enhanced GUI launcher
- `gui.py` - Basic GUI implementation

### Removed Documentation (7 files)
Redundant or outdated documentation removed:
- `BINARY_PROTOCOL_README.md`
- `ENHANCED_SIMULATOR_README.md`
- `MIGRATION_GUIDE.md`
- `PHASE0_README.md`
- `QUICK_REFERENCE.md`
- `SIMPLIFICATION_SUMMARY.md`
- `INTERRUPT_ARCHITECTURE.md`

### Kept Files (Clean Structure)

**Core Files:**
- ✅ `simulator.py` - Main entry point (binary + enhanced always on)
- ✅ `run.sh` - Simplified launcher script
- ✅ `gui_enhanced.py` - Enhanced GUI with hardware controls
- ✅ `gui_binary.py` - Binary protocol handler
- ✅ `setup_wizard.py` - Interactive setup
- ✅ `logger.py` - Logging utilities

**Supporting Files:**
- ✅ `config.json` - Configuration
- ✅ `README.md` - Simplified user guide
- ✅ `BUTTON_MAPPING.md` - Button reference
- ✅ `libraries/` - Hardware shims
- ✅ `fonts/` - Bitmap fonts
- ✅ `logs/` - Runtime logs

## New User Experience

### Before (Confusing)
```bash
# Which one do I use?
python3 main.py -p ../src
python3 main_binary.py -p ../src
python3 main_enhanced.py -p ../src
./run.sh
./run_binary.sh
./run_enhanced.sh
```

### After (Simple)
```bash
# One way to run, all features enabled
./run.sh

# Or with options
./run.sh -p ../src -v
./run.sh --setup
```

## Features Always Enabled

These features are now always active:
- ⚡ **Binary protocol** - 10-20x faster rendering
- 🎮 **Hardware controls** - Mock accelerometer, battery, etc.
- 📺 **Dual displays** - Both circular screens
- 🎹 **Button emulation** - Full keyboard controls

No need to choose modes or variants anymore!

## Upgrade Path

If you were using the old system:

**Old commands:**
```bash
python3 main_enhanced.py -p ../src         # Enhanced mode
python3 main_binary.py -p ../src           # Binary mode
./run_enhanced.sh                          # Enhanced launcher
./run_binary.sh                            # Binary launcher
```

**New command (does both):**
```bash
./run.sh -p ../src
```

All functionality is preserved, just simplified!

## Configuration

No changes to `config.json` format. All existing configurations still work.

The following config options are now always enabled:
- `binary_protocol: true`
- `enhanced_gui: true`

## Documentation

**Single source of truth:**
- `README.md` - Complete user guide with quick start, usage, troubleshooting

**Additional references:**
- `BUTTON_MAPPING.md` - Hardware button mapping
- `../docs/SIMULATOR_*.md` - Architecture documentation (if needed)

## Benefits

1. **Simpler** - One way to run, not six different scripts
2. **Faster** - Binary protocol always active (10-20x speedup)
3. **Cleaner** - 16 fewer files, easier to navigate
4. **Better UX** - Clear help text and startup messages
5. **Maintainable** - Single codebase to update

## Testing

All features have been verified:
- ✅ Help command works
- ✅ Config loading works
- ✅ File structure is clean
- ✅ Binary protocol enabled
- ✅ Enhanced GUI enabled
- ✅ Setup wizard still available

## For Developers

If you're maintaining this code:
- Main entry point: `simulator.py`
- GUI implementation: `gui_enhanced.py`
- Binary handler: `gui_binary.py`
- All features are mandatory (not optional)

## Migration Notes

If you have scripts that call the old simulators:

```bash
# Change this:
python3 main_enhanced.py -p ../src

# To this:
python3 simulator.py -p ../src
# or just:
./run.sh -p ../src
```

## Questions?

See `README.md` for full usage documentation.

---

**Cleanup completed:** January 5, 2026
