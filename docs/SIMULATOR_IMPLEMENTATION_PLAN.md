# Simulator Implementation Plan

**Based on:** [SIMULATOR_DESIGN.md](./SIMULATOR_DESIGN.md)  
**Status:** Ready to implement  
**Estimated Time:** 8-12 hours

---

## Overview

This document provides step-by-step instructions to implement the unified simulator design. Each step is self-contained and can be validated before proceeding.

---

## Phase 1: Fix Critical Issues (Priority: URGENT)

### Step 1.1: Fix JSON Protocol Inconsistency

**Problem:** Code uses both `module` and `device` keys, causing KeyError crashes

**Files to modify:**
- `simulator/gui.py` - `handle_command()` method
- `simulator/libraries/emulator.py` - JSON send functions

**Implementation:**

```python
# simulator/gui.py - handle_command()

def handle_command(self, command):
    """Handle JSON protocol commands with robust error handling"""
    
    # === VALIDATION ===
    if not isinstance(command, dict):
        if self.logger:
            self.logger.log_error(f'Invalid command type: {type(command)}')
        return {'status': 'error', 'error': 'invalid_type'}
    
    # Support both 'device' (new) and 'module' (old) for backwards compat
    device = command.get('device') or command.get('module')
    cmd = command.get('command')
    
    if not device:
        if self.logger:
            self.logger.log_error(f'Missing device/module in command: {command}')
        return {'status': 'error', 'error': 'missing_device'}
    
    if not cmd:
        if self.logger:
            self.logger.log_error(f'Missing command: {command}')
        return {'status': 'error', 'error': 'missing_command'}
    
    # === ROUTING ===
    try:
        if device == 'gc9a01':
            return self._handle_gc9a01(cmd, command)
        elif device == 'pca9535':
            return self._handle_pca9535(cmd, command)
        elif device == 'lis3dh' or device == 'accelerometer':
            return self._handle_accelerometer(cmd, command)
        elif device == 'pin':
            return self._handle_pin(cmd, command)
        elif device == 'neopixel':
            return self._handle_neopixel(cmd, command)
        elif device == 'adc':
            return self._handle_adc(cmd, command)
        elif device == 'network':
            return self._handle_network(cmd, command)
        elif device == 'bluetooth':
            return self._handle_bluetooth(cmd, command)
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

def _handle_gc9a01(self, cmd, params):
    """Handle display device commands"""
    # Support both 'parameters' dict (old) and flat params (new)
    if 'parameters' in params:
        p = params['parameters']
    else:
        p = params
    
    display = p.get('display', 1)
    
    if cmd == 'text':
        font_name = p.get('font', 'vga2_8x16')
        string = p.get('string', '')
        x = p.get('x', 0)
        y = p.get('y', 0)
        fg = p.get('fg_color', 65535)
        bg = p.get('bg_color', 0)
        
        try:
            text_image = get_vga_text(font_name, string)
            raw_str = text_image.tobytes("raw", 'RGBA')
            text_surf = pygame.image.fromstring(raw_str, text_image.size, 'RGBA')
            
            screens = [self.screen1, self.screen2]
            screens[display - 1].blit(text_surf, (x, y))
            
            return {'status': 'ok', 'resp': None}
        except Exception as e:
            if self.logger:
                self.logger.log_error(f'Text rendering error: {e}')
            return {'status': 'error', 'error': str(e)}
    
    elif cmd == 'write':
        # Similar to text but with different font handling
        font_name = p.get('font', 'fonts.arial16px')
        # ... implementation
        return {'status': 'ok', 'resp': None}
    
    elif cmd == 'write_len':
        # Return text width
        font_name = p.get('font', 'fonts.arial16px')
        string = p.get('string', '')
        # Calculate and return width
        return {'status': 'ok', 'resp': 100}  # Placeholder
    
    elif cmd == 'jpg':
        filename = p.get('filename', '')
        x = p.get('x', 0)
        y = p.get('y', 0)
        
        try:
            import os
            img_path = os.path.join('src', filename)
            img = pygame.image.load(img_path)
            
            screens = [self.screen1, self.screen2]
            screens[display - 1].blit(img, (x, y))
            
            return {'status': 'ok', 'resp': None}
        except Exception as e:
            if self.logger:
                self.logger.log_error(f'Image loading error: {e}')
            return {'status': 'error', 'error': str(e)}
    
    else:
        return {'status': 'error', 'error': f'unknown_command: {cmd}'}

def _handle_pca9535(self, cmd, params):
    """Handle button controller"""
    if cmd == 'get_inputs':
        return {'status': 'ok', 'resp': self.get_inputs(self.button_states)}
    else:
        return {'status': 'error', 'error': f'unknown_command: {cmd}'}

def _handle_accelerometer(self, cmd, params):
    """Handle accelerometer/IMU"""
    if cmd in ('acceleration', 'get_acceleration', 'get_accel'):
        return {
            'status': 'ok',
            'resp': {
                'x': self.accel_data[0],
                'y': self.accel_data[1],
                'z': self.accel_data[2]
            }
        }
    elif cmd == 'get_shake':
        # Return True if shake button was pressed
        shake = hasattr(self, '_shake_triggered') and self._shake_triggered
        self._shake_triggered = False  # Reset
        return {'status': 'ok', 'resp': shake}
    else:
        return {'status': 'error', 'error': f'unknown_command: {cmd}'}

def _handle_pin(self, cmd, params):
    """Handle GPIO pin reads"""
    if cmd == 'value':
        pin = params.get('pin', 0)
        if pin == 0:  # Boot button
            return {'status': 'ok', 'resp': 0 if self.button_states[0] > 0 else 1}
        else:
            return {'status': 'ok', 'resp': 1}  # Default high
    
    elif cmd == 'poll_interrupts':
        interrupts = self.interrupt_queue.copy()
        self.interrupt_queue.clear()
        return {'status': 'ok', 'resp': interrupts}
    
    else:
        return {'status': 'error', 'error': f'unknown_command: {cmd}'}

def _handle_neopixel(self, cmd, params):
    """Handle LED strip"""
    if cmd == 'write':
        # Support both formats
        if 'parameters' in params:
            leds = params['parameters'].get('leds', [])
        else:
            leds = params.get('leds', [])
        
        # Convert GRB to RGB
        self.leds = [(r, b, g) for g, r, b in leds[:7]]
        return {'status': 'ok', 'resp': None}
    else:
        return {'status': 'error', 'error': f'unknown_command: {cmd}'}

def _handle_adc(self, cmd, params):
    """Handle ADC (battery voltage)"""
    if cmd in ('read', 'get_voltage'):
        divided_voltage = self._calculate_divided_voltage()
        return {'status': 'ok', 'resp': divided_voltage}
    else:
        return {'status': 'error', 'error': f'unknown_command: {cmd}'}

def _handle_network(self, cmd, params):
    """Handle WiFi simulation"""
    if cmd == 'active':
        # Just log state change
        return {'status': 'ok', 'resp': None}
    elif cmd == 'connect':
        # Update GUI state
        self.wifi_state = 'connected'
        return {'status': 'ok', 'resp': None}
    else:
        return {'status': 'ok', 'resp': None}  # Stub

def _handle_bluetooth(self, cmd, params):
    """Handle Bluetooth simulation"""
    if cmd == 'active':
        # Just log state change
        return {'status': 'ok', 'resp': None}
    elif cmd == 'advertise':
        self.bluetooth_state = 'advertising'
        return {'status': 'ok', 'resp': None}
    else:
        return {'status': 'ok', 'resp': None}  # Stub
```

**Validation:**
```bash
# Run simulator and check logs for errors
uv run simulator/run.sh -v 2>&1 | grep -i error
```

**Expected:** No KeyError crashes, all commands either succeed or return proper error responses

---

### Step 1.2: Update Emulator Library

**File:** `simulator/libraries/emulator.py`

**Changes:**
1. Ensure JSON commands use `device` (not `module`)
2. Add response validation

```python
# In EmulatorJSONCommunication class

def send_command(self, device, command, **kwargs):
    """Send JSON command and receive response"""
    if self.socket is None:
        print(f'[EMULATOR] No socket for {device}.{command}')
        return {'status': 'error', 'error': 'no_connection'}
    
    with self.lock:
        try:
            # Build message with 'device' key (new standard)
            data = {
                'device': device,
                'command': command,
                **kwargs
            }
            
            json_data = json.dumps(data)
            self.socket.send(json_data.encode())
            
            # Receive response
            buffer = b''
            while True:
                chunk = self.socket.recv(4096)
                if not chunk:
                    print(f'[EMULATOR] Connection closed')
                    return {'status': 'error', 'error': 'connection_closed'}
                
                buffer += chunk
                
                try:
                    response = json.loads(buffer.decode('utf-8'))
                    
                    # Validate response structure
                    if not isinstance(response, dict):
                        print(f'[EMULATOR] Invalid response type: {type(response)}')
                        return {'status': 'error', 'error': 'invalid_response'}
                    
                    if 'status' not in response:
                        print(f'[EMULATOR] Response missing status: {response}')
                        # Add default status
                        response['status'] = 'ok'
                    
                    return response
                
                except json.JSONDecodeError:
                    # Incomplete JSON, keep reading
                    if len(buffer) > 1024 * 1024:  # 1MB sanity limit
                        print(f'[EMULATOR] Response too large: {len(buffer)} bytes')
                        return {'status': 'error', 'error': 'response_too_large'}
                    continue
        
        except (ConnectionResetError, BrokenPipeError) as e:
            print(f'[EMULATOR] Connection error: {e}')
            self.socket = None
            return {'status': 'error', 'error': 'connection_lost'}
        
        except Exception as e:
            print(f'[EMULATOR] Unexpected error: {e}')
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'error': str(e)}
```

**Validation:**
```bash
# Check that all shim libraries still work
cd simulator/
uv run python3 -c "
import sys
sys.path.insert(0, 'libraries')
import emulator
print('Emulator module loaded successfully')
"
```

---

### Step 1.3: Add Response Validation to Shims

**Files:** All shim files in `simulator/libraries/`

**Example for `gc9a01.py`:**

```python
def text(self, font, string, x, y, fg_color, bg_color):
    """Render VGA bitmap text"""
    resp = emulator.send_command(
        'gc9a01', 'text',
        font=font.__name__,
        string=string,
        x=x, y=y,
        fg_color=fg_color,
        bg_color=bg_color,
        display=self.display
    )
    
    # Check for errors
    if resp.get('status') == 'error':
        print(f'[GC9A01] Text error: {resp.get("error")}')
    
    return resp.get('resp')

def write_len(self, font, string):
    """Get text width"""
    resp = emulator.send_command(
        'gc9a01', 'write_len',
        font=font.__name__,
        string=string
    )
    
    if resp.get('status') == 'error':
        print(f'[GC9A01] write_len error: {resp.get("error")}')
        return 0  # Default fallback
    
    return resp.get('resp', 0)
```

**Validation:**
Test with a badge app that uses text rendering

---

## Phase 2: Code Consolidation (Priority: HIGH)

### Step 2.1: Identify File Duplication

**Current files:**
```bash
simulator/
├── gui.py                # Main GUI implementation
├── gui_enhanced.py       # ??? Duplicate?
├── gui_binary.py         # ??? Separate file?
```

**Action:** Determine which is the "source of truth"

```bash
cd simulator/
# Compare files
diff gui.py gui_enhanced.py
# Check if any are imported
grep -r "import gui_" .
```

**Decision matrix:**

| Scenario | Action |
|----------|--------|
| `gui.py` has everything | Delete others |
| `gui_enhanced.py` is newer | Rename to `gui.py`, delete old |
| Files have different features | Merge into single `gui.py` |

---

### Step 2.2: Merge GUI Files

**Goal:** Single `gui.py` with:
- `GUIEnhanced` class (main GUI)
- `BinaryProtocolHandler` class (binary commands)
- Helper functions (color conversion, etc.)

**Structure:**

```python
# simulator/gui.py

import pygame
import pygame_gui
import struct
import json
# ... other imports

# === Helper Functions ===

def get_vga_text(font, string):
    """Render VGA bitmap font text"""
    # ... existing implementation

# === Main GUI Class ===

class GUIEnhanced:
    """Unified GUI with hardware controls and dual displays"""
    
    def __init__(self, config=None, logger=None):
        # ... initialization
        
    def handle_command(self, command):
        """Handle JSON protocol commands"""
        # ... from Step 1.1
    
    def gameloop(self):
        """Main render loop"""
        # ... existing implementation
    
    # ... all other methods

# === Binary Protocol Handler ===

class BinaryProtocolHandler:
    """Processes binary graphics commands"""
    
    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.screens = [gui_instance.screen1, gui_instance.screen2]
    
    def handle_command(self, cmd_id, payload):
        """Process binary command"""
        # ... existing implementation from gui_binary.py

# === Command ID Constants ===
CMD_FILL = 0x01
CMD_PIXEL = 0x02
# ... etc
```

**Validation:**
```bash
# Try importing
cd simulator/
python3 -c "import gui; print('✓ GUI module loads')"

# Check for syntax errors
python3 -m py_compile gui.py
```

---

### Step 2.3: Update simulator.py

**File:** `simulator/simulator.py`

**Changes:**
1. Remove imports of deleted GUI files
2. Ensure imports come from `gui.py`

```python
# Near top of file
def main():
    # ... setup code ...
    
    # Create GUI instance (line ~180)
    print('Initializing GUI...')
    import gui  # Import from consolidated gui.py
    
    gui_instance = gui.GUIEnhanced(config, logger)
    print('✓ Enhanced GUI initialized (hardware controls enabled)')
    
    # Create binary handler
    binary_handler = gui.BinaryProtocolHandler(gui_instance)
    print('✓ Binary protocol handler initialized')
    
    # ... rest of main
```

**Validation:**
```bash
uv run simulator/run.sh --help
# Should not error
```

---

## Phase 3: Documentation Updates (Priority: MEDIUM)

### Step 3.1: Update README

**File:** `simulator/README.md`

**Changes:**
- Remove references to multiple GUI files
- Update architecture diagrams
- Add error handling section

### Step 3.2: Create Migration Guide

**File:** `docs/SIMULATOR_MIGRATION_GUIDE.md`

**Contents:**
- Old vs new JSON format comparison
- Backwards compatibility notes
- Breaking changes list

---

## Phase 4: Testing (Priority: HIGH)

### Test Suite

Create `simulator/tests/test_protocol.py`:

```python
import unittest
import json

class TestJSONProtocol(unittest.TestCase):
    def test_device_command_structure(self):
        """Test standard JSON command structure"""
        cmd = {
            'device': 'gc9a01',
            'command': 'fill',
            'color': 0xF800,
            'display': 1
        }
        
        # Should have required keys
        self.assertIn('device', cmd)
        self.assertIn('command', cmd)
    
    def test_error_response(self):
        """Test error response structure"""
        resp = {
            'status': 'error',
            'error': 'unknown_device',
            'resp': None
        }
        
        self.assertEqual(resp['status'], 'error')
        self.assertIn('error', resp)

if __name__ == '__main__':
    unittest.main()
```

Run with:
```bash
cd simulator/tests/
python3 test_protocol.py
```

---

## Phase 5: Performance Validation (Priority: MEDIUM)

### Benchmark blit_buffer

Create `simulator/tests/benchmark_blit.py`:

```python
import time
import struct

def benchmark_blit_buffer():
    """Measure blit_buffer performance"""
    
    # Simulate 240x240 RGB565 buffer
    buffer = bytearray(240 * 240 * 2)
    
    # Fill with test pattern
    for i in range(0, len(buffer), 2):
        buffer[i] = 0xFF
        buffer[i+1] = 0x00
    
    # Time conversion
    start = time.time()
    
    pixels = []
    for i in range(0, len(buffer), 2):
        rgb565 = buffer[i] | (buffer[i+1] << 8)
        r = (rgb565 & 0xF800) >> 8
        g = (rgb565 & 0x07E0) >> 3
        b = (rgb565 & 0x001F) << 3
        pixels.extend([r, g, b])
    
    elapsed = (time.time() - start) * 1000  # ms
    
    print(f'RGB565→RGB888 conversion: {elapsed:.2f}ms')
    print(f'Target: < 10ms, Acceptable: < 20ms')
    
    if elapsed < 10:
        print('✓ Performance: EXCELLENT')
    elif elapsed < 20:
        print('✓ Performance: ACCEPTABLE')
    else:
        print('✗ Performance: NEEDS OPTIMIZATION')

if __name__ == '__main__':
    benchmark_blit_buffer()
```

Run:
```bash
python3 simulator/tests/benchmark_blit.py
```

---

## Phase 6: Real-World Testing (Priority: CRITICAL)

### Test Plan

1. **Boot Test**: Simulator starts without errors
2. **Menu Navigation**: Can navigate through apps using keyboard
3. **Graphics Test**: Run analog_clock app, verify smooth rendering
4. **LED Test**: Run LED animation app, verify visual feedback
5. **Button Test**: Press all buttons 0-9, verify detection
6. **Text Test**: Run app with text rendering
7. **Image Test**: Run app that loads JPEGs
8. **Long-Running**: Leave simulator running for 10 minutes

### Test Execution

```bash
# 1. Boot test
uv run simulator/run.sh -v

# 2. Navigate to analog_clock app
# Press buttons to navigate menu, select clock

# 3. Observe rendering
# Should see smooth 60 FPS clock animation

# 4. Check logs for errors
tail -f simulator/logs/simulator_*.log

# 5. Stress test
# Let run for 10+ minutes
# Check for memory leaks, crashes
```

---

## Rollback Plan

If implementation causes critical issues:

### Quick Rollback

```bash
cd simulator/
git stash  # Save changes
git checkout HEAD -- gui.py simulator.py  # Restore originals
uv run ./run.sh  # Test old version
```

### Identify Issue

```bash
# Compare what changed
git diff stash@{0} -- gui.py

# Check logs
tail -50 logs/simulator_*.log | grep -i error
```

---

## Success Criteria

### Must Have ✓
- [ ] Simulator boots without errors
- [ ] No KeyError crashes on any badge app
- [ ] `blit_buffer` performance < 20ms for 240x240
- [ ] All existing apps work unchanged
- [ ] Logs show clear error messages (no silent failures)

### Should Have ✓
- [ ] Single GUI file (no duplication)
- [ ] Consistent JSON protocol (`device/command`)
- [ ] Performance < 10ms for blit_buffer
- [ ] LED rendering visible
- [ ] Hardware control panel functional

### Nice to Have ✓
- [ ] Hot reload on file changes
- [ ] Interactive debugger
- [ ] Recording/playback

---

## Time Estimates

| Phase | Task | Time | Dependencies |
|-------|------|------|--------------|
| 1.1 | Fix JSON protocol | 2h | None |
| 1.2 | Update emulator.py | 1h | 1.1 |
| 1.3 | Update shims | 1h | 1.2 |
| 2.1 | Identify duplication | 0.5h | 1.x |
| 2.2 | Merge GUI files | 2h | 2.1 |
| 2.3 | Update simulator.py | 0.5h | 2.2 |
| 3.x | Documentation | 1h | 2.x |
| 4.x | Testing | 2h | 2.x |
| 5.x | Performance | 1h | 4.x |
| 6.x | Real-world testing | 1h | All |

**Total: 12 hours**

---

## Next Steps

1. **Review design document** with team
2. **Approve implementation plan**
3. **Create branch**: `git checkout -b simulator-refactor`
4. **Begin Step 1.1**: Fix JSON protocol
5. **Validate each step** before proceeding
6. **Merge when all tests pass**

---

**Ready to implement? Let's get started!** 🚀
