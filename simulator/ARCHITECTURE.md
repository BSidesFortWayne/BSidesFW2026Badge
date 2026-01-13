# BSides FW 2025 Badge Simulator - Architecture

**Version:** 2.0 (Unified)  
**Last Updated:** January 13, 2026

## Overview

The BSides FW 2025 Badge Simulator provides a high-performance development environment for testing badge applications without physical hardware. It uses Pygame to render dual circular displays, simulates hardware peripherals, and provides developer tools for debugging.

### Key Features

- ⚡ **Binary Protocol**: 10-20x faster rendering than JSON
- 🎮 **Hardware Simulation**: Mock accelerometer, battery, WiFi, Bluetooth
- 📺 **Dual Displays**: Two 240x240 circular GC9A01 screens
- 🎹 **Input Emulation**: Keyboard and mouse-based button controls
- 📊 **Developer Tools**: Built-in logging, screenshot capture, regression testing

---

## System Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Host System (Python 3.12)                │
│                                                             │
│  ┌─────────────────────┐         Sockets         ┌─────────┐│
│  │   MicroPython       │                         │ Pygame  ││
│  │   Process           │◄───────────────────────►│ GUI     ││
│  │                     │   Binary (port 4456)    │         ││
│  │  ┌───────────────┐  │   JSON   (port 4455)    │         ││
│  │  │ Badge Firmware│  │                         │         ││
│  │  │  (../src/)    │  │                         │         ││
│  │  └───────┬───────┘  │                         │         ││
│  │          │          │                         │         ││
│  │  ┌───────▼───────┐  │                         │         ││
│  │  │ Shim Libraries│  │                         │         ││
│  │  │ (simulator/)  │  │                         │         ││
│  │  │  - gc9a01.py  │  │   Graphics Commands     │         ││
│  │  │  - pca9535.py │  │──────────►Binary───────►│ Display ││
│  │  │  - lis3dh.py  │  │                         │  Render ││
│  │  │  - neopixel   │  │   Control/Text          │         ││
│  │  │  - network    │  │──────────►JSON─────────►│ Handle  ││
│  │  └───────────────┘  │                         │         ││
│  │  emulator.py        │   Responses             │         ││
│  │  (singleton socket) │◄────────────────────────│         ││
│  └─────────────────────┘                         └─────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communication |
|-----------|---------------|---------------|
| **simulator.py** | Entry point, process orchestration | Launches MicroPython & GUI |
| **Badge Firmware** | Runs user apps, manages state | Calls shim APIs |
| **Shim Libraries** | Translate hardware calls to socket commands | Uses emulator.py |
| **emulator.py** | Socket singleton, protocol multiplexing | Binary + JSON over sockets |
| **gui.py** | Rendering, input, hardware simulation | Receives both protocols |
| **logger.py** | Logging and debug utilities | N/A |

---

## Communication Protocols

### Design Principle: Use the Right Protocol for the Job

The simulator uses **two complementary protocols**:

1. **Binary Protocol (Port 4456)**: High-throughput graphics operations
2. **JSON Protocol (Port 4455)**: Control, configuration, text, debugging

### Binary Protocol

**Purpose**: Maximize graphics performance for smooth rendering.

**Use For:**
- Display rendering (`fill`, `pixel`, `rect`, `line`, `circle`, `blit_buffer`)
- Button state queries (fast polling)
- LED writes (7 RGB values)
- Performance-critical operations

**Packet Structure:**
```
Request:
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
CMD_FILL = 0x01           # Fill display with color
CMD_PIXEL = 0x02          # Draw single pixel
CMD_FILL_RECT = 0x03      # Draw filled rectangle
CMD_LINE = 0x04           # Draw line
CMD_CIRCLE = 0x05         # Draw circle outline
CMD_FILL_CIRCLE = 0x06    # Draw filled circle
CMD_BLIT_BUFFER = 0x10    # Framebuffer blit (MOST IMPORTANT)
CMD_GET_INPUTS = 0x20     # Query button states
CMD_PIN_VALUE = 0x21      # Read GPIO pin
CMD_POLL_INTERRUPTS = 0x22# Query pending interrupts
CMD_NEOPIXEL_WRITE = 0x30 # Write LED strip data
```

**Performance Targets:**
- `blit_buffer(240x240)`: < 10ms (target), < 20ms (acceptable)
- Simple graphics: < 1ms
- Overall: 60 FPS with complex animations

**Example: `blit_buffer` Command**
```python
# Payload format
display_id (1 byte)
x (2 bytes, little-endian)
y (2 bytes, little-endian)
width (2 bytes, little-endian)
height (2 bytes, little-endian)
pixel_data (width * height * 2 bytes, RGB565)
```

### JSON Protocol

**Purpose**: Human-readable commands for control and debugging.

**Use For:**
- Text rendering (VGA fonts, TrueType)
- Image loading (JPEG, PNG)
- Sensor queries (accelerometer)
- Network/Bluetooth state
- Configuration queries
- Screenshots and external tools

**Message Structure:**
```json
{
  "device": "gc9a01",
  "command": "text",
  "display": 1,
  "parameters": {
    "font": "vga2_8x16",
    "string": "Hello World",
    "x": 10,
    "y": 20,
    "fg_color": 65535,
    "bg_color": 0
  }
}
```

**Response:**
```json
{
  "status": "ok",
  "resp": <optional_return_value>
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Description of error"
}
```

---

## File Structure

### Simulator Directory Layout

```
simulator/
├── simulator.py          # Main entry point
├── run.sh               # Launcher script (uv wrapper)
├── setup_wizard.py      # Interactive first-time setup
├── gui.py               # Unified GUI (rendering, controls, logging)
├── logger.py            # Logging utilities
├── config.json          # User configuration (created by setup)
│
├── libraries/           # Hardware shim modules
│   ├── emulator.py      # Socket communication singleton
│   ├── gc9a01.py        # Display driver shim
│   ├── pca9535.py       # Button controller shim
│   ├── lis3dh.py        # Accelerometer shim
│   ├── neopixel.py      # LED strip shim
│   ├── machine.py       # MicroPython machine module shim
│   ├── network.py       # WiFi/network shim
│   ├── bluetooth.py     # Bluetooth shim
│   └── vga*.py          # VGA bitmap fonts
│
├── fonts/               # TrueType fonts for GUI
├── logs/                # Runtime logs (created at runtime)
├── screenshots/         # Screenshot output (created at runtime)
├── src/                 # Copy of ../src/ (created at runtime)
│
├── take_screenshot.py   # CLI screenshot tool
├── regression_test.py   # Automated regression testing
└── demo_regression_test.py  # Example regression test

Documentation:
├── README.md            # User guide (Quick start, usage, troubleshooting)
├── ARCHITECTURE.md      # This file (Architecture, design decisions)
├── BUTTON_MAPPING.md    # Hardware button reference
├── REGRESSION_TEST_GUIDE.md  # Regression testing documentation
└── SCREENSHOT_GUIDE.md  # Screenshot tool documentation
```

### Important Files

- **`simulator.py`**: Entry point, orchestrates MicroPython and GUI processes
- **`gui.py`**: Unified GUI implementation (previously split across multiple files)
- **`emulator.py`**: Singleton socket connection manager
- **`libraries/`**: Hardware shim layer that translates hardware API calls to socket commands
- **`src/`**: **Auto-generated** - copied from `../src/` at startup, overlaid with shims

---

## Startup Sequence

### What Happens When You Run `./run.sh`

1. **Parse Arguments**: Read command line options and `config.json`
2. **Validate Paths**: Check that project directory and MicroPython exist
3. **Setup Project Directory**:
   - Delete old `simulator/src/` if it exists
   - Copy `../src/` → `simulator/src/`
   - Overlay `simulator/libraries/` → `simulator/src/` (shims replace real drivers)
4. **Create Socket Servers**:
   - Bind JSON protocol socket (port 4455)
   - Bind Binary protocol socket (port 4456)
5. **Launch MicroPython Process**:
   - Set `BADGE_SIMULATOR=1` environment variable
   - Execute `_boot_then_main.py` (auto-generated)
   - This runs `boot.py` then `main.py` in the same global namespace
6. **Start GUI**:
   - Initialize Pygame window
   - Start render loop (60 FPS target)
   - Start hardware control panel
7. **Accept Connections**:
   - MicroPython connects to both sockets
   - External tools (screenshot, regression) can connect to JSON socket
8. **Run Badge Firmware**: User's badge code executes normally

### Boot Sequence Behavior

The simulator replicates hardware boot behavior:

```python
# simulator generates _boot_then_main.py:
exec(compile(open('boot.py').read(), 'boot.py', 'exec'), globals())
exec(compile(open('main.py').read(), 'main.py', 'exec'), globals())
```

This ensures:
- `boot.py` runs first (sets up displays, hardware)
- `main.py` can access variables defined in `boot.py`
- Matches real hardware behavior exactly

---

## Hardware Shimming

### How Shims Work

Badge firmware imports hardware modules like normal:
```python
import gc9a01
display = gc9a01.GC9A01(...)
display.fill(0xFFFF)  # White
```

But in the simulator, these imports resolve to **shim modules** in `simulator/libraries/`:

```python
# simulator/libraries/gc9a01.py (shim)
from emulator import send_command

class GC9A01:
    def fill(self, color):
        send_command('gc9a01', 'fill', {
            'display': self.display_id,
            'color': color
        })
```

The shim:
1. Receives the hardware API call
2. Translates it to a socket command (binary or JSON)
3. Sends via `emulator.py` singleton
4. Returns response to badge firmware

### Key Shim Modules

**`gc9a01.py`** - Display Driver
- Translates display method calls to binary protocol
- Determines display ID (1 or 2) from DC pin
- Supports: `fill`, `pixel`, `rect`, `line`, `circle`, `blit_buffer`, `text`, `jpg`

**`pca9535.py`** - I/O Expander (Buttons)
- Queries button states from GUI
- Converts to hardware bitfield format
- Maps keyboard/mouse input to button indices

**`lis3dh.py`** - Accelerometer
- Returns mock accelerometer data from GUI sliders
- Supports shake detection
- Can be controlled via GUI control panel

**`machine.py`** - MicroPython Machine Module
- Provides Pin, SPI, I2C, PWM, Timer classes
- Most operations are no-ops or return mock data
- Enough to satisfy badge firmware initialization

**`neopixel.py`** - RGB LED Strip
- Translates `write()` calls to GUI LED rendering
- Supports 7 RGB LEDs
- Uses binary protocol for performance

**`network.py` / `bluetooth.py`** - Connectivity
- Mock WiFi and Bluetooth state
- Controllable via GUI control panel
- No actual network functionality

**`emulator.py`** - Communication Singleton
- Thread-safe socket connection manager
- Handles protocol multiplexing (binary vs JSON)
- Error handling and reconnection logic

---

## GUI Architecture

### Main Components

**Display Rendering:**
- Two 240x240 pixel Pygame surfaces (RGB565 color space)
- Circular masking applied for authentic round display look
- Positioned on badge hardware background image
- Updates at 60 FPS target

**Hardware Control Panel:**
- Right side of window
- Sliders for accelerometer axes (X, Y, Z)
- Shake button (triggers shake interrupt)
- Battery voltage slider
- Charge state button
- WiFi/Bluetooth state toggles

**Log Panel:**
- Bottom of window (toggleable)
- Displays last 100 log messages
- Color-coded: INFO (blue), WARNING (orange), ERROR (red)
- Timestamps on all entries
- Synchronized with console output

**Button Emulation:**
- Keyboard keys: 0-9 (see BUTTON_MAPPING.md)
- Mouse click: Clickable overlays on badge image
- Visual feedback: Buttons highlight green when pressed

### Render Loop

```python
while running:
    # Handle events (keyboard, mouse, close)
    handle_events()
    
    # Process socket commands (non-blocking)
    process_binary_commands()
    process_json_commands()
    
    # Render frame
    screen.fill(background_color)
    draw_board_image()
    draw_displays_with_circular_mask()
    draw_led_strip()
    draw_hardware_controls()
    draw_button_overlays()
    draw_log_panel()
    draw_fps()
    
    pygame.display.flip()
    clock.tick(60)  # 60 FPS target
```

### Thread Architecture

The simulator uses multiple threads:

```
┌─────────────────────────────────────────────────┐
│ Main Thread (Pygame GUI)                        │
│  - Event loop                                   │
│  - Rendering                                    │
│  - Command processing                           │
└─────────────────────────────────────────────────┘
         ▲
         │ Socket Communication
         │
┌─────────────────────────────────────────────────┐
│ MicroPython Process (subprocess)                │
│  - Badge firmware execution                     │
│  - App lifecycle management                     │
└─────────────────────────────────────────────────┘
         ▲
         │ stdout/stderr pipes
         │
┌─────────────────────────────────────────────────┐
│ External Tool Threads (daemon)                  │
│  - Screenshot requests                          │
│  - Regression test commands                     │
└─────────────────────────────────────────────────┘
```

**Thread Safety:**
- Socket sends use thread-safe locking
- GUI state is only modified in main thread
- External commands queued for main thread processing

---

## Error Handling

### Design Principles

1. **Never crash on malformed input**
2. **Log errors clearly with context**
3. **Return error responses, don't throw exceptions**
4. **Provide actionable error messages**

### Error Response Format

**Binary Protocol:**
```
Status Byte: 0x01 (error)
Length: 4 bytes
Data: Error code (32-bit integer)
```

**JSON Protocol:**
```json
{
  "status": "error",
  "message": "Descriptive error message",
  "details": {
    "command": "fill",
    "missing_param": "color"
  }
}
```

### Common Error Cases

1. **Missing Required Parameter**
   - Check for required keys before processing
   - Return error with missing parameter name

2. **Invalid Value**
   - Validate ranges (e.g., display ID 1-2)
   - Return error with expected range

3. **Unknown Command**
   - Log command for debugging
   - Return error with list of valid commands

4. **Socket Disconnect**
   - Attempt reconnection
   - Fall back to dummy responses if persistent failure

5. **MicroPython Crash**
   - Log stdout/stderr
   - Display error in GUI log panel
   - Don't crash simulator

---

## Performance Optimization

### Binary Protocol Benefits

**Before (JSON):**
- `blit_buffer(240x240)`: ~100ms
- JSON encoding: ~50ms
- Socket transmission: ~30ms
- JSON decoding: ~20ms

**After (Binary):**
- `blit_buffer(240x240)`: ~5ms
- Binary encoding: ~1ms
- Socket transmission: ~3ms
- Binary decoding: ~1ms

**Result: 20x speedup** for full-screen operations

### Performance Best Practices

**For Badge Apps:**
1. Use `blit_buffer()` for complex graphics (always use binary)
2. Batch small operations when possible
3. Avoid `time.sleep()` in update loops (use `await asyncio.sleep()`)
4. Cache framebuffers instead of recreating

**For Simulator Development:**
1. Keep GUI render loop fast (<16ms per frame for 60 FPS)
2. Use non-blocking socket operations
3. Minimize data copying
4. Profile before optimizing

---

## Configuration

### config.json Schema

```json
{
  "project_path": "../src",
  "micropython_path": "micropython",
  "socket_port": 4455,
  "binary_port": 4456,
  "logging": {
    "enabled": true,
    "output_dir": "logs",
    "level": "INFO"
  },
  "gui": {
    "show_fps": true,
    "target_fps": 60,
    "log_panel_visible": true
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `project_path` | string | `"../src"` | Badge project directory |
| `micropython_path` | string | `"micropython"` | MicroPython executable |
| `socket_port` | int | `4455` | JSON protocol port |
| `binary_port` | int | `4456` | Binary protocol port |
| `logging.enabled` | bool | `true` | Enable file logging |
| `logging.output_dir` | string | `"logs"` | Log output directory |
| `gui.show_fps` | bool | `true` | Display FPS counter |
| `gui.target_fps` | int | `60` | Target frame rate |
| `gui.log_panel_visible` | bool | `true` | Show log panel on startup |

---

## Developer Workflow

### CRITICAL: Edit Files in `src/`, Not `simulator/src/`

The simulator **copies** `src/` to `simulator/src/` at startup and overlays shim libraries.

✅ **DO:**
- Edit files in `src/apps/`, `src/lib/`, `src/drivers/`
- Test by restarting simulator
- Commit changes to `src/` directory

❌ **DON'T:**
- Edit files in `simulator/src/` (changes will be **lost** on next run)
- Commit `simulator/src/` to version control

### Typical Development Cycle

```bash
# 1. Edit your badge app
vim src/apps/my_app.py

# 2. Run simulator
cd simulator/
uv run ./run.sh

# 3. Test your app
# Navigate to app using buttons, verify behavior

# 4. Check logs if needed
tail -f logs/simulator_*.log

# 5. Make changes and repeat
# Restart simulator to pick up changes
```

---

## Testing and Debugging

### Built-in Tools

**Screenshot Capture:**
```bash
python simulator/take_screenshot.py --output my_screenshot.png
python simulator/take_screenshot.py --output full_sim.png --include-controls
```

**Regression Testing:**
```bash
python simulator/regression_test.py demo_regression_test.py
```

**Verbose Logging:**
```bash
./run.sh -v
```

### Debugging Tips

**Problem: Display not updating**
- Check MicroPython output for errors
- Verify app is calling display methods
- Check logs for socket communication errors

**Problem: Buttons not working**
- Check keyboard focus (click simulator window)
- Verify button mapping in BUTTON_MAPPING.md
- Check log panel for button press events

**Problem: Low FPS**
- Check CPU usage
- Look for exceptions in logs
- Profile badge app for blocking operations

**Problem: MicroPython crashes**
- Check `logs/simulator_*.log` for stack traces
- Run MicroPython directly: `micropython simulator/src/main.py`
- Test on real hardware to isolate simulator issues

---

## Extension Points

### Adding New Hardware

To add a new peripheral (e.g., GPS):

1. **Create shim module** `simulator/libraries/gps.py`:
```python
from emulator import send_command

class GPS:
    def get_position(self):
        return send_command('gps', 'get_position', {})
```

2. **Add GUI control** in `gui.py`:
```python
# In __init__:
self.gps_lat = 30.0
self.gps_lon = -95.0

# In render_controls:
# Add sliders for lat/lon

# In handle_command:
if data.get('device') == 'gps':
    if data.get('command') == 'get_position':
        return {'lat': self.gps_lat, 'lon': self.gps_lon}
```

3. **Document in README.md**

### Adding New Commands

To add a new binary command:

1. **Define command ID** in both `emulator.py` and `gui.py`:
```python
CMD_NEW_THING = 0x40
```

2. **Implement in shim** (e.g., `gc9a01.py`):
```python
def new_thing(self, param):
    payload = struct.pack('<BI', self.display_id, param)
    return self.emulator.send_binary(CMD_NEW_THING, payload)
```

3. **Handle in GUI** (`gui.py`):
```python
elif cmd_id == CMD_NEW_THING:
    display_id, param = struct.unpack('<BI', payload)
    # Do something with param
    return self.pack_response(STATUS_OK, b'')
```

---

## Troubleshooting

See [README.md](README.md) for common issues and solutions.

---

## Future Enhancements

### Potential Features

- **Network Simulation**: Real UDP/TCP sockets with local server
- **Bluetooth Simulation**: BLE peripheral emulation
- **Audio Playback**: WAV/MP3 support for speaker
- **Recording/Playback**: Record button sequences for automation
- **Remote Control**: Web interface for controlling simulator
- **Multi-badge**: Run multiple simulators for badge-to-badge communication

### Performance Improvements

- **GPU Acceleration**: Use OpenGL for rendering (via pygame)
- **Parallel Rendering**: Multi-threaded display updates
- **Protocol Optimization**: Further reduce binary protocol overhead
- **Caching**: Cache font rendering and common graphics

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial JSON-only simulator |
| 2.0 | Jan 6, 2026 | Binary protocol, unified GUI, boot sequence |

---

## References

- [README.md](README.md) - User guide
- [BUTTON_MAPPING.md](BUTTON_MAPPING.md) - Hardware button reference
- [REGRESSION_TEST_GUIDE.md](REGRESSION_TEST_GUIDE.md) - Automated testing
- [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md) - Screenshot tool usage

---

**Maintained by the BSides FW 2025 Badge Team**
