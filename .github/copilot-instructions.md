# BSides FW 2025 Badge Development Guide

## Project Overview
This is a **MicroPython firmware project** for an ESP32-based conference badge with dual GC9A01 circular displays, 7 RGB LEDs, buttons, accelerometer, and speaker. The badge runs interactive apps through a dynamic app loading system.

## Architecture Patterns

### App System (`src/apps/`)
- **Apps inherit from `BaseApp`** in `apps/app.py` with lifecycle methods: `setup()`, `teardown()`, `update()`, `button_*`
- **Auto-discovery**: Apps in `apps/` folder are automatically detected by `AppDirectory` using file hash caching
- **App registration**: Classes must have a `name` class attribute and inherit `BaseApp`
- **Multiple apps per module**: One file can contain multiple app classes
- **Hidden apps**: Set `hidden = True` to exclude from menu (e.g., system apps like Menu)

### Configuration System (`lib/smart_config.py`)
- **Smart Config pattern**: Apps use `Config` objects with typed config values (ColorConfig, RangeConfig, EnumConfig, BoolDropdownConfig)  
- **Web UI auto-generation**: Config objects render as HTML forms accessible via HTTP server
- **File-based persistence**: Configs saved to `config/apps/{app_name}.json`, `config/services/{service_name}.json`, `config/system.json`
- **Force updates**: Use `self.config.add('key', ConfigType(...), force=True)` to override existing values
- **System Config**: `SystemConfig` in `lib/system_config.py` manages system-wide settings (sleep, display, LEDs, debug)

### Hardware Abstraction (`bsp.py`)
- **BSP (Board Support Package)** centralizes all hardware drivers: displays, buttons, LEDs, IMU, speaker, bluetooth
- **Access via controller**: `self.controller.bsp.displays.display1`, `self.controller.bsp.leds`, etc.
- **Async-safe**: All hardware operations designed for asyncio context

### Display System
- **Dual displays**: `display1` (top), `display2` (bottom) - both 240x240 circular GC9A01
- **Framebuffer pattern**: Use `framebuf.FrameBuffer` with `blit_buffer()` for performance (see `analog_clock.py`)
- **Color format**: RGB565 format, use `gc9a01.WHITE`, `gc9a01.BLACK`, etc.

## Development Workflows

### Simulator Development
- **IMPORTANT**: When editing apps/drivers/lib files, **ONLY edit files in `src/`**, not `simulator/src/`
- The simulator automatically copies `src/` to `simulator/src/` at startup
- Changes to `simulator/src/` will be overwritten on next simulator run
- After editing `src/`, restart the simulator to pick up changes

**Running the Simulator:**
```bash
# First time setup
cd simulator/
uv run ./run.sh --setup

# Daily use
uv run ./run.sh

# With options
uv run ./run.sh -p ../src -v
```

**Features (always enabled):**
- Binary protocol (10-20x faster rendering)
- Hardware control panel (mock sensors)
- Dual circular displays
- Full button emulation

### On-device Development (Recommended)
```bash
# Setup environment
uv sync
sudo chmod a+x /dev/ttyUSB0  # Linux only

# Deploy and run specific file
uv run mpremote cp src/apps/my_app.py : + run main.py

# Mount source directory for live editing
uv run mpremote mount src

# Deploy all source files
uv run mpremote cp -r src/* :
```

### Testing
- **Unit tests**: `uv run pytest tests/` (hardware-independent)
- **On-device tests**: Files in `src/test/` run with `uv run mpremote run src/test/test_file.py`
- **Hardware validation**: Use test files for driver verification

### Flashing Custom Firmware
```bash
cd firmware/
uv run esptool.py erase_flash
uv run esptool.py --baud 460800 write_flash 0x1000 BSFWCustom_firmware_SPIRAM_with_GC9A01.bin
```

### Background Services (`lib/background_service.py`)
- **Service Pattern**: Background services inherit from `BackgroundService` for system-level functionality
- **Lifecycle Management**: Services have `start()`, `stop()`, `update()` methods called by controller
- **Config Integration**: Services get own config namespace and web UI exposure
- **Examples**: `SleepService` for power management, expandable for monitoring, connectivity, etc.

### Remote Sign Pattern (`apps/remote_sign.py`)
- **External Control**: Apps can be designed for remote control via command queues
- **State Management**: Use dedicated state classes for complex app state
- **Timeout Functionality**: Built-in timeout system for automatic state changes
- **Public API**: Clean API methods for external control (UDP, HTTP, etc.)
- **Example Usage**: `RemoteSignController` shows programmatic control patterns

## Key Development Patterns

### Button Handling
```python
def button_press(self, button: int):
    # Hardware V3 mapping: 4=down, 5=up, 6=select, 3=long-press for menu
    if button == 6:  # Select button
        # Handle selection
```

### Async App Updates
```python
async def update(self):
    # Called every ~50ms, use for animations/state updates
    # Keep processing light to maintain 20Hz target framerate
```

### Config Integration
```python
def __init__(self, controller):
    super().__init__(controller)
    self.config.add('my_setting', EnumConfig('Label', ['option1', 'option2'], 'default'))
    # Config automatically available at /config endpoint when app is active
```

### Performance Considerations
- **Framebuffer use**: For complex graphics, draw to framebuffer then `blit_buffer()` to display
- **Async sleep**: Use `await asyncio.sleep(0.01)` in update loops for cooperative multitasking  
- **Memory management**: Call `gc.collect()` periodically in long-running operations

## File Organization
- `src/apps/` - User applications (auto-discovered)
- `src/drivers/` - Hardware abstraction layers
- `src/lib/` - Utility modules (smart_config, file_hash, etc.)
- `src/config/` - Runtime configuration files
- `tests/` - Off-device unit tests
- `src/test/` - On-device hardware tests

## Hardware Specifics (V4)
- **Buttons**: 0-6 (0=boot, 1-3=A/B/C, 4-5=nav, 6=select via PCA9535 I2C expander)
- **I2C Bus**: Address 0x20 (PCA9535), 0x18 (LIS3DH accelerometer)  
- **Power Management**: `DISP_EN` pin controls display power, accelerometer interrupt for sleep/wake
- **LED Strip**: 7x WS2812B on GPIO26
- **Speaker**: PWM buzzer on GPIO15

## Common Gotchas
- **Module reloading**: App directory caches modules by file hash; change file to trigger reload
- **Display coordination**: Both displays share SPI bus; use different CS/DC/RST pins
- **Async context**: Always use async/await in update loops; never block the main thread
- **Config timing**: Add configs in `__init__` before using values in setup/update