# BSides FW 2025 Badge Simulator - Design Document

**Version:** 2.0  
**Date:** January 6, 2026  
**Status:** Design Phase

---

## Executive Summary

The badge simulator provides a local development environment for testing badge applications without physical hardware. The current implementation has **structural inconsistencies** that cause crashes and confusion. This document defines a **unified architecture** to resolve these issues and establish clear patterns going forward.

### Key Problems Identified

1. **Protocol Confusion**: Code mixes "module/command" (old) with "device/command" (new) JSON structures
2. **Dual Communication**: Binary and JSON protocols overlap in functionality
3. **Inconsistent Error Handling**: Missing error checks cause KeyError crashes
4. **File Structure**: Multiple similar files (gui.py, gui_enhanced.py, gui_binary.py) create confusion
5. **Library Shimming**: Unclear which libraries are shims vs actual MicroPython code

### Design Goals

1. ✅ **Single Source of Truth**: One GUI implementation, one protocol handler
2. ✅ **Clear Separation**: Graphics (binary) vs Control (JSON)
3. ✅ **Robust Error Handling**: No crashes on malformed commands
4. ✅ **Developer Experience**: Fast iteration, clear debugging
5. ✅ **Hardware Parity**: Accurate simulation of real badge behavior

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Host System (Python 3.12)                │
│                                                              │
│  ┌─────────────────────┐         Sockets         ┌─────────┐│
│  │   MicroPython       │                          │ Pygame  ││
│  │   Process           │◄────────────────────────►│ GUI     ││
│  │                     │   Binary (port 4456)     │         ││
│  │  ┌───────────────┐  │   JSON   (port 4455)     │         ││
│  │  │ Badge Firmware│  │                          │         ││
│  │  │  (../src/)    │  │                          │         ││
│  │  └───────┬───────┘  │                          │         ││
│  │          │          │                          │         ││
│  │  ┌───────▼───────┐  │                          │         ││
│  │  │ Shim Libraries│  │                          │         ││
│  │  │ (simulator/)  │  │                          │         ││
│  │  │  - gc9a01.py  │  │   Graphics Commands      │         ││
│  │  │  - pca9535.py │  │──────────►Binary────────►│ Display ││
│  │  │  - lis3dh.py  │  │                          │  Render ││
│  │  │  - neopixel   │  │   Control/Text           │         ││
│  │  │  - network    │  │──────────►JSON──────────►│ Handle  ││
│  │  └───────────────┘  │                          │         ││
│  │  emulator.py        │   Responses              │         ││
│  │  (singleton socket) │◄─────────────────────────│         ││
│  └─────────────────────┘                          └─────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Component Roles

| Component | Responsibility | Protocol |
|-----------|---------------|----------|
| **Badge Firmware** | Runs user apps, manages hardware | Calls shim APIs |
| **Shim Libraries** | Translate hardware calls to socket commands | Uses emulator.py |
| **emulator.py** | Socket singleton, protocol encoding | Binary + JSON |
| **simulator.py** | Process orchestration, socket servers | N/A |
| **gui.py** | Rendering, input, hardware state | Receives both protocols |
| **BinaryProtocolHandler** | Decodes binary graphics commands | Binary only |

---

## Protocol Design

### Principle: **Use the Right Protocol for the Job**

- **Binary Protocol**: High-throughput graphics operations
- **JSON Protocol**: Control, configuration, text, sensors

### Binary Protocol (Port 4456)

**Use for:**
- Display rendering (fill, pixel, rect, line, circle, blit_buffer)
- Button state queries (fast polling)
- LED writes (7 RGB values)

**Packet Structure:**
```
┌──────┬────────┬────────┬──────────────────┐
│MAGIC │ CMD_ID │ LENGTH │     PAYLOAD      │
│2bytes│ 1byte  │ 4bytes │   variable       │
└──────┴────────┴────────┴──────────────────┘

Response:
┌────────┬────────┬──────────────────┐
│ STATUS │ LENGTH │       DATA       │
│ 1byte  │ 4bytes │    variable      │
└────────┴────────┴──────────────────┘
```

**Command IDs:**
```python
CMD_FILL = 0x01           # Fill display
CMD_PIXEL = 0x02          # Single pixel
CMD_FILL_RECT = 0x03      # Filled rectangle
CMD_LINE = 0x04           # Line
CMD_CIRCLE = 0x05         # Circle outline
CMD_FILL_CIRCLE = 0x06    # Filled circle
CMD_BLIT_BUFFER = 0x10    # Framebuffer blit (CRITICAL)
CMD_GET_INPUTS = 0x20     # Button state
CMD_PIN_VALUE = 0x21      # GPIO read
CMD_POLL_INTERRUPTS = 0x22# Pending IRQs
CMD_NEOPIXEL_WRITE = 0x30 # LED strip
```

**Performance Target:**
- `blit_buffer(240x240)`: < 10ms
- Simple graphics: < 1ms
- 60 FPS with complex animations

### JSON Protocol (Port 4455)

**Use for:**
- Text rendering (VGA fonts, TrueType)
- Image loading (JPEG, PNG)
- Sensor queries (accelerometer, etc.)
- Network/Bluetooth control
- Configuration queries

**Message Structure:**
```json
{
  "device": "gc9a01",
  "command": "text",
  "display": 1,
  "font": "vga2_8x16",
  "string": "Hello World",
  "x": 10,
  "y": 20,
  "fg_color": 65535,
  "bg_color": 0
}
```

**Response:**
```json
{
  "status": "ok",
  "resp": <optional_return_value>
}
```

**Error Handling:**
```json
{
  "status": "error",
  "error": "Unknown command: foo",
  "resp": null
}
```

### Protocol Migration Strategy

**Current Problem:** Inconsistent JSON keys (`module` vs `device`, `parameters` vs flat)

**Solution:** Standardize on **flat structure with device/command**

```python
# OLD (broken)
{'module': 'gc9a01', 'command': 'fill', 'parameters': {'color': 0xF800, 'display': 1}}

# NEW (standard)
{'device': 'gc9a01', 'command': 'fill', 'color': 0xF800, 'display': 1}
```

---

## File Organization

### Current State (Problematic)
```
simulator/
├── simulator.py               # Main entry (GOOD)
├── gui.py                     # Enhanced GUI (GOOD)
├── gui_enhanced.py            # ??? duplicate?
├── gui_binary.py              # ??? separate file?
├── emulator.py                # In wrong place?
└── libraries/
    ├── emulator.py            # ✓ Correct location
    ├── gc9a01.py              # ✓ Shim
    └── ...
```

### Proposed Structure (Clean)
```
simulator/
├── simulator.py               # Entry point, orchestration
├── gui.py                     # Unified GUI + BinaryProtocolHandler
├── logger.py                  # Logging utilities
├── setup_wizard.py            # First-time setup
├── config.json                # Runtime configuration
├── board_render.png           # Background image
├── run.sh                     # Launcher script
├── fonts/                     # GUI bitmap fonts
├── libraries/                 # MicroPython shims
│   ├── emulator.py            # Socket singleton (STAYS HERE)
│   ├── gc9a01.py              # Display driver shim
│   ├── pca9535.py             # Button controller shim
│   ├── machine.py             # Machine module shim
│   ├── lis3dh.py              # Accelerometer shim
│   ├── neopixel.py            # LED shim
│   ├── network.py             # WiFi shim
│   ├── bluetooth.py           # Bluetooth shim
│   ├── esp32.py               # ESP32-specific shim
│   └── vga*.py                # Font modules
├── logs/                      # Runtime logs (created)
└── src/                       # Project copy (created)
```

**Deletion Candidates:**
- `gui_enhanced.py` (merge into `gui.py`)
- `gui_binary.py` (merge into `gui.py` as class)
- Any `emulator.py` outside of `libraries/`

---

## GUI Architecture

### Single GUI Class: `GUIEnhanced`

```python
class GUIEnhanced:
    """Unified GUI with hardware controls and dual displays"""
    
    def __init__(self, config=None, logger=None):
        # Core state
        self.config = config or {}
        self.logger = logger
        self.running = True
        
        # Display surfaces (240x240 circular)
        self.screen1 = pygame.Surface((240, 240))
        self.screen2 = pygame.Surface((240, 240))
        
        # Hardware state
        self.button_states = [0] * 8       # 8 buttons (0=boot, 1-7=IOX)
        self.leds = [(0,0,0)] * 7          # 7 RGB LEDs
        self.accel_data = [0.0, 0.0, 1.0]  # X, Y, Z (m/s²)
        self.adc_voltage = 4.2             # Battery voltage
        self.wifi_state = 'disconnected'
        self.bluetooth_state = 'disabled'
        self.interrupt_queue = []          # Pending IRQs
        
        # UI components
        self.ui_manager = pygame_gui.UIManager(...)
        self._create_ui_controls()
    
    def handle_command(self, command_dict):
        """Handle JSON protocol commands (text, images, sensors)"""
        # Validate structure
        if 'device' not in command_dict or 'command' not in command_dict:
            self.logger.log_error(f'Malformed command: {command_dict}')
            return {'error': 'Missing device or command'}
        
        device = command_dict['device']
        command = command_dict['command']
        
        # Route to handlers
        if device == 'gc9a01':
            return self._handle_gc9a01(command, command_dict)
        elif device == 'pca9535':
            return self._handle_pca9535(command, command_dict)
        elif device == 'lis3dh':
            return self._handle_lis3dh(command, command_dict)
        elif device == 'pin':
            return self._handle_pin(command, command_dict)
        elif device == 'neopixel':
            return self._handle_neopixel(command, command_dict)
        elif device == 'adc':
            return self._handle_adc(command, command_dict)
        else:
            return {'error': f'Unknown device: {device}'}
    
    def _handle_gc9a01(self, command, params):
        """Handle display commands (text, images)"""
        if command == 'text':
            # Render VGA text via pygame
            ...
        elif command == 'jpg':
            # Load and blit image
            ...
        elif command == 'write_len':
            # Return text width measurement
            return text_surface.get_width()
        else:
            return {'error': f'Unknown gc9a01 command: {command}'}
    
    def gameloop(self):
        """Main render loop"""
        while self.running:
            time_delta = self.clock.tick(60) / 1000.0
            
            # Process events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keypress(event)
                elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                    self._handle_ui_event(event)
                
                self.ui_manager.process_events(event)
            
            # Update physics
            self._decay_shake()
            self._update_ui_labels()
            
            # Render
            self.display.fill((30, 30, 30))
            self.display.blit(self.board_texture, (0, 0))
            self.render_leds()
            self.display.blit(self.generate_circular_cutout(self.screen1), (70, 558))
            self.display.blit(self.generate_circular_cutout(self.screen2), (234, 774))
            self.ui_manager.draw_ui(self.display)
            
            pygame.display.update()
```

### Binary Protocol Handler

```python
class BinaryProtocolHandler:
    """Processes binary graphics commands"""
    
    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.screens = [self.gui.screen1, self.gui.screen2]
    
    def handle_command(self, cmd_id, payload):
        """
        Process binary command.
        Returns: (status_byte, response_bytes)
          status: 0=success, 1=error
        """
        try:
            if cmd_id == CMD_FILL:
                return self._handle_fill(payload)
            elif cmd_id == CMD_BLIT_BUFFER:
                return self._handle_blit_buffer(payload)
            # ... etc
            else:
                self.gui.logger.log_error(f'Unknown binary command: {cmd_id}')
                return (1, None)
        except struct.error as e:
            self.gui.logger.log_error(f'Binary decode error: {e}')
            return (1, None)
        except Exception as e:
            self.gui.logger.log_error(f'Binary handler error: {e}')
            return (1, None)
    
    def _handle_blit_buffer(self, payload):
        """CRITICAL: Fast framebuffer blit (must be < 10ms)"""
        # Parse: display(1) + x(2) + y(2) + width(2) + height(2) + buffer
        display, x, y, w, h = struct.unpack('<BhhHH', payload[:9])
        buffer_data = payload[9:]
        
        # Validate
        expected_size = w * h * 2  # RGB565
        if len(buffer_data) != expected_size:
            return (1, None)
        
        # Convert RGB565 → RGB888 (vectorized for speed)
        pixels = []
        for i in range(0, len(buffer_data), 2):
            rgb565 = buffer_data[i] | (buffer_data[i+1] << 8)
            pixels.extend(self.rgb565_to_rgb(rgb565))
        
        # Blit to pygame surface
        img = pygame.image.frombuffer(bytes(pixels), (w, h), 'RGB')
        self.screens[display - 1].blit(img, (x, y))
        
        return (0, None)
```

---

## Emulator Library (Shim Layer)

### Location: `simulator/libraries/emulator.py`

**This file is copied into `simulator/src/` and imported by badge firmware**

### Design Principles

1. **Singleton Sockets**: One connection per protocol
2. **Thread-Safe**: Use locks for concurrent access
3. **Automatic Reconnect**: Handle socket errors gracefully
4. **Protocol Selection**: Binary for graphics, JSON for control

### API

```python
# Binary protocol (high-performance graphics)
def send_fill(display, color): ...
def send_pixel(display, x, y, color): ...
def send_blit_buffer(display, buffer, x, y, width, height): ...
def send_get_inputs(): ...
def send_neopixel_write(leds): ...

# JSON protocol (control and text)
def send_command(device, command, **kwargs): ...
def poll_interrupts(): ...
```

### Error Handling

```python
def send_command(device, command, **kwargs):
    """Send JSON command with robust error handling"""
    socket = get_json_socket()
    
    if socket.socket is None:
        print(f'[EMULATOR] No connection for {device}.{command}')
        return {'status': 'error', 'error': 'no_connection'}
    
    try:
        # Build message
        msg = {'device': device, 'command': command, **kwargs}
        
        with socket.lock:
            socket.socket.send(json.dumps(msg).encode())
            response = socket._receive_json()
            
        return response
    
    except (ConnectionResetError, BrokenPipeError):
        print(f'[EMULATOR] Connection lost')
        socket.socket = None
        return {'status': 'error', 'error': 'connection_lost'}
    
    except Exception as e:
        print(f'[EMULATOR] Error: {e}')
        return {'status': 'error', 'error': str(e)}
```

---

## Hardware Shim Pattern

All shim libraries follow this pattern:

### Example: `gc9a01.py`

```python
"""
Display driver shim for simulator.
Routes graphics commands to emulator binary/JSON protocols.
"""

import machine
import emulator

# Color constants (RGB565)
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
# ... etc

class GC9A01:
    def __init__(self, spi, width, height, reset, cs, dc, rotation, options=0, buffer_size=0):
        """Initialize display (matches real driver API)"""
        self._width = width
        self._height = height
        self.rotation = rotation
        
        # Determine which display based on DC pin
        # Hardware V4 uses pins 19 (display1) and 21 (display2)
        if dc.pin == 19:
            self.display = 1
        else:
            self.display = 2
    
    def width(self):
        return self._width
    
    def height(self):
        return self._height
    
    # === Binary Protocol (Fast Graphics) ===
    
    def fill(self, color):
        """Fill entire display with color"""
        emulator.send_fill(self.display, color)
    
    def pixel(self, x, y, color):
        """Set single pixel"""
        emulator.send_pixel(self.display, x, y, color)
    
    def fill_rect(self, x, y, w, h, color):
        """Fill rectangle"""
        emulator.send_fill_rect(self.display, x, y, w, h, color)
    
    def blit_buffer(self, buffer, x, y, width, height):
        """CRITICAL: Blit framebuffer (RGB565) to display"""
        emulator.send_blit_buffer(self.display, buffer, x, y, width, height)
    
    # === JSON Protocol (Text, Images) ===
    
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
        return resp.get('resp')
    
    def jpg(self, filename, x, y, mode):
        """Load and display JPEG image"""
        # Strip leading slash for simulator paths
        if filename.startswith('/'):
            filename = filename[1:]
        
        emulator.send_command(
            'gc9a01', 'jpg',
            filename=filename,
            x=x, y=y,
            display=self.display
        )
```

### Example: `pca9535.py`

```python
"""
PCA9535 I/O expander shim (buttons).
"""

import emulator

class PCA9535:
    def __init__(self, i2c, address=0x20):
        self.i2c = i2c
        self.address = address
    
    def get_inputs(self):
        """Read button states as 16-bit value"""
        # Binary protocol for fast polling
        return emulator.send_get_inputs()
    
    def set_outputs(self, value):
        """Set output pins (not used for buttons)"""
        pass
```

---

## Development Workflow

### Directory Setup

**Important:** The simulator **copies** `../src/` to `simulator/src/` at startup, then **overlays** shim libraries.

```bash
# Original source
../src/
  ├── main.py
  ├── apps/
  ├── drivers/
  └── ...

# Runtime copy (created by simulator)
simulator/src/
  ├── main.py          # Copied from ../src/
  ├── apps/            # Copied from ../src/
  ├── emulator.py      # Overlaid from simulator/libraries/
  ├── gc9a01.py        # Overlaid from simulator/libraries/
  └── ...              # Other shims overlaid
```

### Edit Workflow

1. **Edit files in `../src/`** (not `simulator/src/`)
2. Restart simulator to pick up changes
3. Simulator copies `../src/` → `simulator/src/` with shims

**Alternative (Advanced):**
- Use symlinks: `simulator/src` → `../src` (experimental)
- File watcher: Auto-restart on changes (not implemented)

### Testing

```bash
# Run simulator
cd simulator/
uv run ./run.sh

# Run with debugging
uv run ./run.sh -v

# Check logs
tail -f logs/simulator_*.log
```

---

## Hardware Control Panel

### UI Layout

```
┌──────────────────────────────────────┐
│        Hardware Controls             │
├──────────────────────────────────────┤
│  Accelerometer                       │
│    [Shake Device]      Magnitude: 2.0│
│    X: 0.00g Y: 0.00g Z: 1.00g       │
├──────────────────────────────────────┤
│  Power & Battery                     │
│    Battery Voltage: 4.20V            │
│    R1 (top): 100.0kΩ                 │
│    R2 (bottom): 47.0kΩ               │
│    ADC sees: 1330mV                  │
│    Charge State: [not_charging ▾]    │
├──────────────────────────────────────┤
│  WiFi                                │
│    State: [disconnected ▾]           │
├──────────────────────────────────────┤
│  Bluetooth                           │
│    State: [disabled ▾]               │
├──────────────────────────────────────┤
│  Press 0-4, 7-9 for buttons         │
│  Adjust sliders to mock hardware    │
└──────────────────────────────────────┘
```

### Features

- **Accelerometer Shake**: Button triggers random acceleration spike
- **Battery Voltage**: Slider simulates voltage divider ADC readings
- **Charge State**: Dropdown for charging/charged/error states
- **WiFi/BT State**: Dropdowns for connection states
- **Visual Feedback**: LED rendering with glow effects

---

## Error Handling Strategy

### Levels

1. **Validation**: Check message structure before processing
2. **Device Routing**: Unknown devices return error response
3. **Command Execution**: Catch exceptions, return error status
4. **Logging**: All errors logged to file + console

### JSON Error Response

```json
{
  "status": "error",
  "error": "Unknown device: xyz",
  "resp": null
}
```

### Binary Error Response

```
STATUS: 0x01 (error)
LENGTH: 0
DATA: (none)
```

### Crash Prevention

```python
def handle_command(self, command_dict):
    """Robust command handler"""
    # Validate structure
    if not isinstance(command_dict, dict):
        self.logger.log_error(f'Invalid command type: {type(command_dict)}')
        return {'status': 'error', 'error': 'invalid_type'}
    
    if 'device' not in command_dict:
        self.logger.log_error(f'Missing device in command: {command_dict}')
        return {'status': 'error', 'error': 'missing_device'}
    
    if 'command' not in command_dict:
        self.logger.log_error(f'Missing command: {command_dict}')
        return {'status': 'error', 'error': 'missing_command'}
    
    # ... rest of handler
```

---

## Performance Targets

| Operation | Target | Acceptable | Unacceptable |
|-----------|--------|------------|--------------|
| `blit_buffer(240x240)` | < 5ms | < 10ms | > 20ms |
| Simple graphics | < 1ms | < 2ms | > 5ms |
| Text rendering | < 5ms | < 10ms | > 20ms |
| Button poll | < 0.5ms | < 1ms | > 2ms |
| Overall FPS | 60 | 30 | < 20 |

### Optimization Strategies

1. **Binary Protocol**: Use for all graphics operations
2. **Vectorized Conversion**: RGB565 → RGB888 in tight loops
3. **Minimal Logging**: Debug logs only in verbose mode
4. **Buffer Reuse**: Avoid allocations in hot paths
5. **Pygame Hardware Acceleration**: Use HWSURFACE where supported

---

## Configuration Schema

### config.json

```json
{
  "project_path": "../src",
  "micropython_path": "micropython",
  "socket_host": "127.0.0.1",
  "socket_port": 4455,
  "binary_port": 4456,
  
  "logging": {
    "enabled": true,
    "output_dir": "logs",
    "verbose": false
  },
  
  "gui": {
    "window_title": "BSides FW 2025 Badge Simulator",
    "show_fps": true,
    "target_fps": 60,
    "show_led_positions": true
  },
  
  "hardware": {
    "accelerometer": {
      "default_gravity": 1.0,
      "shake_magnitude": 2.0
    },
    "battery": {
      "default_voltage": 4.2,
      "r1_kohm": 100.0,
      "r2_kohm": 47.0
    }
  }
}
```

---

## Testing Plan

### Unit Tests

- `test_emulator.py`: Socket communication
- `test_binary_protocol.py`: Command encoding/decoding
- `test_gui_commands.py`: Command handlers

### Integration Tests

- Run actual badge apps in simulator
- Compare output to screenshots from real hardware

### Performance Tests

- Benchmark `blit_buffer` with various sizes
- Stress test: 1000 graphics commands/second
- Memory leak detection: Run for 1 hour

---

## Implementation Checklist

### Phase 1: Stabilization (This Sprint)

- [ ] Merge `gui.py`, `gui_enhanced.py`, `gui_binary.py` → single `gui.py`
- [ ] Standardize JSON protocol on `device/command` (remove `module/parameters`)
- [ ] Add validation to all JSON command handlers
- [ ] Fix KeyError crashes with proper error handling
- [ ] Update all shim libraries to use consistent protocol
- [ ] Test with existing badge apps

### Phase 2: Feature Completion

- [ ] LED rendering with glow effects
- [ ] Hardware control panel improvements
- [ ] Accelerometer interrupt simulation
- [ ] Network shim (passthrough to host OS)
- [ ] Bluetooth shim (mock mode)

### Phase 3: Developer Experience

- [ ] Hot reload (detect file changes)
- [ ] Interactive debugger
- [ ] Recording/playback of interactions
- [ ] Performance profiler

---

## Migration Guide

### For Badge App Developers

**No changes needed** - apps run unmodified in simulator

### For Simulator Maintainers

1. **Update JSON Commands:**
   ```python
   # OLD
   {'module': 'gc9a01', 'command': 'fill', 'parameters': {'color': 0xF800}}
   
   # NEW
   {'device': 'gc9a01', 'command': 'fill', 'color': 0xF800}
   ```

2. **Merge GUI Files:**
   - Delete `gui_enhanced.py`, `gui_binary.py`
   - Keep only `gui.py` with both classes

3. **Fix emulator.py Location:**
   - Keep in `simulator/libraries/` only
   - Remove any copies outside libraries/

---

## Appendix A: Button Mapping

### Hardware V4 Buttons

| Button | IOX Bit | Keyboard Key | Description |
|--------|---------|--------------|-------------|
| SW5 (Boot) | GPIO0 | `0` | Boot/Reset |
| SW1 | Bit 10 | `1` | Button A |
| SW2 | Bit 9 | `2` | Button B |
| SW3 | Bit 8 | `3` | Button C |
| SW4 | Bit 0 | `4` | Button D |
| SW7 | Bit 1 | `7` | Game button 1 |
| SW8 | Bit 2 | `8` | Game button 2 |
| SW9 | Bit 3 | `9` | Game button 3 |

---

## Appendix B: Display Positions

### GUI Layout

- **Window Size**: 560 + 300 = 860 wide, 1060 tall
- **Board Image**: `board_render.png` at (0, 0)
- **Display 1** (upper): 240x240 circular at (70, 558)
- **Display 2** (lower): 240x240 circular at (234, 774)
- **Control Panel**: 300px wide on right side
- **LED Strip**: 7 LEDs at (499, 187) with 108.7px spacing

---

## Appendix C: Color Conversion

### RGB565 ↔ RGB888

```python
def rgb565_to_rgb(color565):
    """Convert RGB565 (16-bit) to RGB888 (24-bit)"""
    r = (color565 & 0xF800) >> 8   # 5 bits → 8 bits
    g = (color565 & 0x07E0) >> 3   # 6 bits → 8 bits
    b = (color565 & 0x001F) << 3   # 5 bits → 8 bits
    return (r, g, b)

def rgb_to_rgb565(r, g, b):
    """Convert RGB888 to RGB565"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
```

---

**End of Design Document**

---

## Next Steps

1. **Review this design** with team
2. **Create implementation tickets** from Phase 1 checklist
3. **Begin code consolidation** (merge GUI files)
4. **Update tests** to match new architecture
5. **Update user documentation** (README, guides)

