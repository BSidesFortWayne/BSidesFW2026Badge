# BSides FW 2025 Badge Simulator - Current Architecture

## Overview

The badge simulator (in the `simulator` branch) provides a local development environment for testing badge applications without physical hardware. It uses pygame to render the dual circular displays and simulate button inputs.

**Current Status**: The simulator is out of date with the current firmware implementation and needs updating to work with the new framebuffer-based BSP architecture.

## Current Simulator Architecture

### Components

#### 1. Main Entry Point (`simulator/main.py`)
- **Purpose**: Orchestrates the simulator by launching MicroPython and the GUI
- **Flow**:
  1. Parses command-line arguments for project directory and MicroPython executable path
  2. Creates a TCP socket server on `127.0.0.1:4455` for emulator communication
  3. Copies the project source files to a `src/` directory
  4. Overlays simulator-specific library shims from `simulator/libraries/` 
  5. Launches MicroPython as a subprocess running the badge firmware
  6. Starts the pygame GUI in a separate thread
  7. Handles bidirectional communication between MicroPython and GUI

#### 2. GUI Renderer (`simulator/gui.py`)
- **Purpose**: Renders the badge displays and handles user input
- **Key Features**:
  - Creates a 560x1060 pygame window with a background board image
  - Manages two 240x240 circular displays (pygame Surfaces)
  - Handles keyboard input (keys 1-5) mapped to the 5 badge buttons
  - Processes drawing commands from the emulator communication layer
  
- **Display Rendering**:
  - Maintains two separate 240x240 pixel surfaces for each display
  - Applies circular masking to create round display appearance
  - Blits masked displays onto board background at appropriate positions
  - Position 1: (70, 558) - Upper display
  - Position 2: (234, 774) - Lower display

- **Supported Drawing Commands**:
  - `fill` - Fill display with solid color
  - `pixel` - Draw single pixel
  - `circle` / `fill_circle` - Draw circle outlines/filled
  - `fill_rect` - Draw filled rectangle
  - `line` - Draw line between two points
  - `write` - Render text using Arial font (32px or 16px)
  - `text` - Render text using VGA bitmap fonts
  - `jpg` - Load and display JPEG images

- **Button Simulation**:
  - Maps keyboard keys 1-5 to badge buttons 0-4
  - Tracks button press/release states
  - Converts button states to PCA9535 I/O expander format (bitfield)
  - Button mapping mimics hardware IOX pin assignments

#### 3. Emulator Communication (`simulator/libraries/emulator.py`)
- **Purpose**: Provides socket-based IPC between MicroPython and pygame GUI
- **Pattern**: Singleton socket connection with thread-safe locking
- **Protocol**:
  - Commands sent as JSON: `{'module': 'gc9a01', 'command': 'fill', 'parameters': {...}}`
  - Responses: `{'status': 'ok', 'resp': <optional_return_value>}`
  - Synchronous request-response pattern (blocks until GUI responds)

#### 4. Hardware Shims (`simulator/libraries/`)
Provide fake implementations of hardware modules that communicate with the GUI:

- **`gc9a01.py`**: Display driver shim
  - Translates display method calls into emulator commands
  - Determines which display (1 or 2) based on DC pin number
  - Supports: init, fill, pixel, circle, fill_circle, fill_rect, line, write, text, jpg
  - `write_len()` returns text width from GUI

- **`pca9535.py`**: I/O expander shim (buttons)
  - Returns button states from GUI
  - Converts GUI button array to hardware bitfield format

- **`machine.py`**: Machine module stubs
  - Provides Pin, SPI, I2C classes that don't do anything
  - Allows firmware code to instantiate hardware objects without errors

- **`lis3dh.py`**: IMU sensor stub (placeholder)
- **`neopixel.py`**: RGB LED stub (placeholder)
- **VGA font modules**: Bitmap font definitions

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Host System (Python 3)                    │
│                                                              │
│  ┌───────────────┐         TCP Socket          ┌──────────┐ │
│  │  MicroPython  │◄────── 127.0.0.1:4455 ─────►│  Pygame  │ │
│  │   Process     │                              │   GUI    │ │
│  │               │                              │          │ │
│  │  ┌─────────┐  │    JSON Commands            │  Render  │ │
│  │  │ Badge   │  │──────────────────────────►  │  Displays│ │
│  │  │Firmware │  │                              │  Handle  │ │
│  │  │  Code   │  │    JSON Responses           │  Input   │ │
│  │  │         │  │◄──────────────────────────  │          │ │
│  │  └─────────┘  │                              └──────────┘ │
│  │       │       │                                           │
│  │  ┌────▼────┐  │                                           │
│  │  │ Emulator│  │                                           │
│  │  │ Library │  │                                           │
│  │  │  Shims  │  │                                           │
│  │  └─────────┘  │                                           │
│  └───────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

### Command Flow Example

1. Badge firmware calls: `display.fill(gc9a01.RED)`
2. Shimmed `gc9a01.py` calls: `emulator.send_command('gc9a01', 'fill', color=0xF800, display=1)`
3. Emulator library sends JSON over socket: `{"module": "gc9a01", "command": "fill", "parameters": {"color": 63488, "display": 1}}`
4. GUI thread receives command in `handle_command()`
5. GUI executes: `self.screen1.fill(self.rgb565_to_rgb(0xF800))`
6. GUI responds: `{"status": "ok", "resp": null}`
7. Emulator library receives response and returns to caller

### Button Input Flow

1. User presses keyboard key '1'
2. Pygame receives `KEYDOWN` event
3. GUI sets: `self.button_states[0] = 1`
4. Badge firmware polls: `buttons.get_inputs()` (via IOX)
5. Shimmed `pca9535.py` calls: `emulator.send_command('pca9535', 'get_inputs')`
6. GUI returns bitfield with button 0 bit cleared
7. Firmware processes button press

## Limitations of Current Simulator

1. **Out of Date**: Not compatible with current BSP/display driver architecture
2. **No Framebuffer Support**: Only supports direct drawing commands, no blit_buffer
3. **Incomplete Hardware Emulation**:
   - LEDs not rendered
   - Speaker/audio not simulated
   - IMU not functional
   - No RTC emulation
4. **Limited Font Support**: Only supports Arial and basic VGA fonts
5. **Performance**: Drawing is synchronous and may be slow for complex scenes
6. **No Python Driver Support**: Assumes C extension for gc9a01, but shims the old API
7. **Missing Features**:
   - No bitmap() method support
   - No rotation handling
   - No color mode switching (RGB565 only)
   - No write_len() for VGA fonts

## Files and Directory Structure

```
simulator/
├── main.py              # Entry point and orchestration
├── gui.py               # Pygame rendering and input handling
├── board_render.png     # Background image of badge PCB
├── arial.ttf            # Font file for text rendering
├── fonts/               # VGA bitmap fonts
│   ├── vga1_bold_16x32.png
│   ├── vga2_8x16.png
│   └── vga2_bold_16x32.png
└── libraries/           # Hardware shims
    ├── emulator.py      # Socket communication
    ├── gc9a01.py        # Display driver shim
    ├── pca9535.py       # I/O expander shim
    ├── machine.py       # Machine module stubs
    ├── lis3dh.py        # IMU stub
    ├── neopixel.py      # LED stub
    └── vga*.py          # VGA font modules
```

## Key Insights for Updating

1. **Communication Layer is Sound**: The socket-based IPC works well and can be reused
2. **Shim Pattern Works**: Replacing hardware modules with emulator versions is effective
3. **Need Framebuffer Support**: Must add `blit_buffer()` command to handle modern code
4. **Display Driver Mismatch**: Current shims don't match the actual driver API (Python vs C)
5. **BSP Injection**: Modern firmware passes displays to BSP constructor - simulator must handle this
6. **Missing Hardware**: LEDs, speaker, and other peripherals need basic visualization
