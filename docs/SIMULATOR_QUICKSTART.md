# Simulator Refactor - Quick Start Guide

**For developers implementing the refactor**

---

## Before You Start

### Read These First (in order)

1. [SIMULATOR_REFACTOR_SUMMARY.md](./SIMULATOR_REFACTOR_SUMMARY.md) - High-level overview (5 min read)
2. [SIMULATOR_DESIGN.md](./SIMULATOR_DESIGN.md) - Complete architecture (20 min read)
3. [SIMULATOR_DIAGRAMS.md](./SIMULATOR_DIAGRAMS.md) - Visual reference (10 min scan)
4. [SIMULATOR_IMPLEMENTATION_PLAN.md](./SIMULATOR_IMPLEMENTATION_PLAN.md) - Step-by-step guide (refer during work)

### Prerequisites

```bash
# Verify you have the repo
cd /home/sheindel/workspace/BSidesFW2025Badge

# Check current simulator status
cd simulator/
uv run ./run.sh 2>&1 | head -50

# You should see the KeyError: 'module' error
# That's what we're fixing!
```

---

## Quick Implementation Checklist

### ✅ Phase 1: Critical Fixes (Start Here!)

**Goal:** Stop the crashes

#### Step 1: Fix `gui.py` command handler

**File:** `simulator/gui.py`

**Find this code:**
```python
def handle_command(self, command):
    screens = [self.screen1, self.screen2]
    if command['module'] == 'gc9a01':  # ← CRASHES HERE
        if command['command'] == 'fill':
            # ...
```

**Replace with:**
```python
def handle_command(self, command):
    """Handle JSON protocol commands with robust error handling"""
    
    # VALIDATION
    if not isinstance(command, dict):
        if self.logger:
            self.logger.log_error(f'Invalid command type: {type(command)}')
        return {'status': 'error', 'error': 'invalid_type'}
    
    # Support both 'device' (new) and 'module' (old)
    device = command.get('device') or command.get('module')
    cmd = command.get('command')
    
    if not device:
        if self.logger:
            self.logger.log_error(f'Missing device/module: {command}')
        return {'status': 'error', 'error': 'missing_device'}
    
    if not cmd:
        if self.logger:
            self.logger.log_error(f'Missing command: {command}')
        return {'status': 'error', 'error': 'missing_command'}
    
    # ROUTING (wrap in try/except)
    try:
        if device == 'gc9a01':
            return self._handle_gc9a01(cmd, command)
        elif device == 'pca9535':
            return self._handle_pca9535(cmd, command)
        elif device in ('lis3dh', 'accelerometer'):
            return self._handle_accelerometer(cmd, command)
        elif device == 'pin':
            return self._handle_pin(cmd, command)
        elif device == 'neopixel':
            return self._handle_neopixel(cmd, command)
        elif device == 'adc':
            return self._handle_adc(cmd, command)
        else:
            if self.logger:
                self.logger.log_warning(f'Unknown device: {device}')
            return {'status': 'error', 'error': f'unknown_device: {device}'}
    
    except Exception as e:
        if self.logger:
            self.logger.log_error(f'Error handling {device}.{cmd}: {e}')
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'error': str(e)}
```

**Then add handler methods** (see [SIMULATOR_IMPLEMENTATION_PLAN.md](./SIMULATOR_IMPLEMENTATION_PLAN.md) Step 1.1 for full code)

**Test:**
```bash
uv run simulator/run.sh -v
# Should boot without KeyError!
```

---

#### Step 2: Update `emulator.py`

**File:** `simulator/libraries/emulator.py`

**Find the `send_command()` function in `EmulatorJSONCommunication` class**

**Update to use 'device' key:**
```python
def send_command(self, device, command, **kwargs):
    """Send JSON command and receive response"""
    if self.socket is None:
        return {'status': 'error', 'error': 'no_connection'}
    
    with self.lock:
        try:
            # Build message with 'device' key (NEW STANDARD)
            data = {
                'device': device,      # ← Changed from 'module'
                'command': command,
                **kwargs
            }
            
            json_data = json.dumps(data)
            self.socket.send(json_data.encode())
            
            # ... rest of receive logic
```

**Test:**
```bash
# Simulator should still work
uv run simulator/run.sh
```

---

#### Step 3: Update shims (optional for now)

**Files:** `simulator/libraries/gc9a01.py`, etc.

**Add response validation** (can be done later, not critical for Phase 1)

---

### ✅ Phase 2: Consolidation

**Goal:** Clean up duplicate files

#### Step 1: Check what files exist

```bash
cd simulator/
ls -la gui*.py
# Output:
# gui.py
# gui_enhanced.py  ← duplicate?
# gui_binary.py    ← duplicate?
```

#### Step 2: Compare files

```bash
# Are they different?
diff gui.py gui_enhanced.py | head -20

# Which one is imported?
grep -r "import gui" .
grep -r "from gui" .
```

#### Step 3: Decision Matrix

**Scenario A:** `gui.py` has everything → Delete `gui_enhanced.py` and `gui_binary.py`

**Scenario B:** `gui_enhanced.py` is the real one → Rename it to `gui.py`

**Scenario C:** They're different → Carefully merge (see implementation plan)

#### Step 4: Merge if needed

**If files need merging:**

```python
# Final structure in gui.py:

# === Imports ===
import pygame
import pygame_gui
# ...

# === Helper Functions ===
def get_vga_text(font, string):
    # ...

# === Main GUI ===
class GUIEnhanced:
    # ... all methods from gui_enhanced.py

# === Binary Handler ===
class BinaryProtocolHandler:
    # ... all methods from gui_binary.py

# === Constants ===
CMD_FILL = 0x01
# ...
```

**Test:**
```bash
python3 -c "import gui; print('✓')"
uv run simulator/run.sh
```

---

### ✅ Phase 3: Validation

**Goal:** Ensure everything works

#### Test Checklist

```bash
# 1. Simulator boots
uv run simulator/run.sh

# 2. No errors in first 10 seconds
timeout 10 uv run simulator/run.sh 2>&1 | grep -i error

# 3. Navigate menu (use keyboard 1-9)
# Should be able to move through apps

# 4. Check logs
tail -f simulator/logs/simulator_*.log

# 5. Run for 5 minutes
# Watch for memory leaks, crashes
```

---

## Common Issues & Fixes

### Issue: `KeyError: 'module'`

**Cause:** Old JSON format, handler expects 'module' key

**Fix:** Update `handle_command()` to support both 'device' and 'module' (Step 1)

---

### Issue: `AttributeError: 'GUIEnhanced' object has no attribute '_handle_gc9a01'`

**Cause:** Handler methods missing

**Fix:** Add all handler methods from implementation plan

---

### Issue: Import errors after merging files

**Cause:** `simulator.py` still imports old file names

**Fix:** Update imports:
```python
# simulator.py
import gui  # Not gui_enhanced or gui_binary

gui_instance = gui.GUIEnhanced(config, logger)
binary_handler = gui.BinaryProtocolHandler(gui_instance)
```

---

### Issue: `TypeError: '_handle_gc9a01() takes 2 positional arguments but 3 were given'`

**Cause:** Handler signature wrong

**Fix:** All handlers should accept `(self, cmd, params)`:
```python
def _handle_gc9a01(self, cmd, params):
    # cmd is the command string
    # params is the full command dict
```

---

## Testing Strategy

### Smoke Test (2 minutes)

```bash
# Does it boot?
timeout 10 uv run simulator/run.sh

# Exit code 124 = timeout (good, means it ran)
# Exit code 1 = error (bad)
```

### Functional Test (10 minutes)

1. Boot simulator
2. Navigate to analog_clock app (use keyboard)
3. Watch for smooth rendering
4. Press buttons 0-9
5. Check LED rendering
6. Let run for 5 minutes
7. Close cleanly

### Regression Test (30 minutes)

Run all badge apps from menu:
- [ ] Menu
- [ ] Analog Clock
- [ ] Digital Clock
- [ ] LED Animations
- [ ] Games (if any)
- [ ] Settings
- [ ] About

---

## Rollback Procedure

### If something breaks:

```bash
# Stash changes
git stash save "simulator-refactor-wip"

# Restore original
git checkout HEAD -- simulator/

# Test original
uv run simulator/run.sh

# If original also broken, report issue
# If original works, review what changed:
git diff stash@{0} -- simulator/
```

---

## Progress Tracking

### Commit Strategy

Make small, testable commits:

```bash
# After Step 1 (fix handler)
git add simulator/gui.py
git commit -m "simulator: Add error handling to JSON command handler"

# After Step 2 (update emulator)
git add simulator/libraries/emulator.py
git commit -m "simulator: Standardize on 'device' key in JSON protocol"

# After Phase 2 (consolidation)
git add simulator/
git commit -m "simulator: Consolidate GUI files into single gui.py"
```

### When to Stop and Review

**Stop if:**
- Simulator crashes immediately on boot
- More than 3 test failures
- Unsure about code merge conflicts
- Breaking existing badge apps

**Get help from:**
- Review design documents again
- Check implementation plan for details
- Ask team for code review
- Create issue with error logs

---

## Success Indicators

### You're Done When:

- [ ] Simulator boots without errors
- [ ] No KeyError crashes
- [ ] All badge apps work
- [ ] Only one gui.py file exists
- [ ] Logs show clear error messages (not silent failures)
- [ ] Performance: blit_buffer < 20ms
- [ ] All commits pushed to branch

### Create PR When:

- [ ] All success indicators met
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Changes reviewed by team

---

## Time Estimates (Reality Check)

| Task | Planned | Reality |
|------|---------|---------|
| Read docs | 1h | ? |
| Phase 1 (fixes) | 4h | ? |
| Phase 2 (consolidate) | 3h | ? |
| Phase 3 (test) | 5h | ? |
| **Total** | **12h** | **?** |

**Track your time** and update estimates for future developers!

---

## Quick Commands

```bash
# Start simulator
uv run simulator/run.sh

# Verbose mode (debugging)
uv run simulator/run.sh -v

# Check for errors
uv run simulator/run.sh 2>&1 | grep -i error

# View logs
tail -f simulator/logs/simulator_*.log

# Test import
python3 -c "import sys; sys.path.insert(0, 'simulator'); import gui"

# Syntax check
python3 -m py_compile simulator/gui.py

# Benchmark
python3 simulator/tests/benchmark_blit.py

# Run tests
python3 simulator/tests/test_protocol.py
```

---

## Next Steps After Implementation

1. **Create PR** with all changes
2. **Update user documentation** (README.md)
3. **Demo to team** - show it working
4. **Gather feedback** from badge app developers
5. **Plan future features** (hot reload, debugger, etc.)

---

## Questions?

Refer to:
- [SIMULATOR_DESIGN.md](./SIMULATOR_DESIGN.md) - Architecture details
- [SIMULATOR_IMPLEMENTATION_PLAN.md](./SIMULATOR_IMPLEMENTATION_PLAN.md) - Detailed steps
- [SIMULATOR_DIAGRAMS.md](./SIMULATOR_DIAGRAMS.md) - Visual reference

---

**Ready to start? Begin with Phase 1, Step 1!** 🚀

Good luck! Remember to commit frequently and test after each change.
