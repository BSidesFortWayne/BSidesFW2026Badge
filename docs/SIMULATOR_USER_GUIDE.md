# BSides FW 2025 Badge Simulator - User Guide

## Overview

The badge simulator allows you to develop and test badge applications on your computer without physical hardware. It provides a graphical representation of the badge's dual displays, buttons, LEDs, and other components.

## Prerequisites

### Required Software

1. **Python 3.8+** (host system)
   ```bash
   python3 --version  # Should be 3.8 or higher
   ```

2. **MicroPython Unix Port**
   
   **Option A: Build from source**
   ```bash
   git clone https://github.com/micropython/micropython.git
   cd micropython/ports/unix
   make submodules
   make
   # Binary will be at build-standard/micropython
   ```
   
   **Option B: Use pre-built binary** (if available)
   - Download from MicroPython releases
   - Or use system package manager (may be outdated)

3. **Python Packages** (for simulator GUI)
   ```bash
   pip install pygame pillow
   ```

### Verify Installation

```bash
# Test MicroPython
micropython --version
# Should output: MicroPython v1.x.x

# Test pygame
python3 -c "import pygame; print(pygame.version.ver)"
# Should output pygame version
```

## Quick Start

### 1. Clone Repository and Switch to Simulator Branch

```bash
cd /path/to/BSidesFW2025Badge
git checkout simulator
```

### 2. Run the Simulator

**Basic usage** (simulates firmware in `src/` directory):
```bash
cd simulator
python3 main.py -p ../src
```

**With custom MicroPython path**:
```bash
python3 main.py -p ../src -m /path/to/micropython
```

### 3. Interact with Badge

- **Keyboard Controls**:
  - Press `1` - Button 0 (top button on badge)
  - Press `2` - Button 1
  - Press `3` - Button 2
  - Press `4` - Button 3
  - Press `5` - Button 4 (bottom button on badge)
  
- **Close Simulator**: Click the window close button or press `Ctrl+C` in terminal

## Directory Structure

```
BSidesFW2025Badge/
├── simulator/              # Simulator code (simulator branch)
│   ├── main.py            # Entry point
│   ├── gui.py             # Pygame GUI
│   ├── board_render.png   # Badge background image
│   ├── arial.ttf          # Font file
│   ├── fonts/             # Bitmap fonts
│   └── libraries/         # Hardware shims
│       ├── emulator.py    # Socket communication
│       ├── gc9a01.py      # Display driver shim
│       ├── pca9535.py     # Button I/O shim
│       ├── machine.py     # Machine module stubs
│       ├── neopixel.py    # LED shim
│       └── ...
├── src/                   # Badge firmware (main branch)
│   ├── main.py           # Firmware entry point
│   ├── bsp.py            # Board support package
│   ├── controller.py     # Main controller
│   ├── apps/             # Badge applications
│   ├── drivers/          # Hardware drivers
│   └── ...
```

## Command-Line Options

```bash
python3 main.py [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-p`, `--project` | Path to firmware source directory | Required |
| `-m`, `--micropython` | Path to MicroPython executable | `micropython` (from PATH) |
| `--no-gui` | Run without GUI (testing mode) | GUI enabled |

### Examples

**Use custom project directory**:
```bash
python3 main.py -p /path/to/my/badge/code
```

**Specify MicroPython binary**:
```bash
python3 main.py -p ../src -m ~/micropython/ports/unix/build-standard/micropython
```

**Run without GUI** (for automated testing):
```bash
python3 main.py -p ../src --no-gui
```

## Simulator Window Layout

```
┌─────────────────────────────────────────┐
│         Badge Simulator Window           │
│                                          │
│         [Badge PCB Background]           │
│                                          │
│              ┌────────┐                  │
│              │Display1│  ← Upper Display │
│              │ (240x  │                  │
│              │  240)  │                  │
│              └────────┘                  │
│                                          │
│                ┌────────┐                │
│                │Display2│ ← Lower Display│
│                │ (240x  │                │
│                │  240)  │                │
│                └────────┘                │
│                                          │
│   ●  ●  ●  ●  ●    ←  LEDs (NeoPixels)  │
│                                          │
│         🔊  ←  Speaker Indicator         │
│                                          │
└─────────────────────────────────────────┘

Keyboard: 1 2 3 4 5  →  Buttons 0-4
```

## How It Works

### Architecture Overview

```
┌──────────────────────────────────────────────────┐
│                Host Computer                      │
│                                                   │
│  ┌──────────────┐         ┌─────────────────┐   │
│  │ MicroPython  │◄────────┤ Pygame Window   │   │
│  │   Process    │  Socket │                 │   │
│  │              │─────────►│  - Displays     │   │
│  │ Badge        │   IPC   │  - LEDs         │   │
│  │ Firmware     │         │  - Buttons      │   │
│  │ (src/)       │         │  - Speaker      │   │
│  └──────────────┘         └─────────────────┘   │
│        │                           │             │
│        │ Uses                      │ Renders     │
│        ▼                           ▼             │
│  ┌──────────────┐         ┌─────────────────┐   │
│  │ Simulator    │         │ Hardware        │   │
│  │ Shims        │         │ Visualization   │   │
│  │ (libraries/) │         │                 │   │
│  └──────────────┘         └─────────────────┘   │
└──────────────────────────────────────────────────┘
```

### Communication Flow

1. **Firmware boots**: MicroPython loads badge firmware from `src/`
2. **Shims intercept**: Hardware calls go to simulator libraries instead of real hardware
3. **Commands sent**: Shims send JSON commands over TCP socket to GUI
4. **GUI renders**: Pygame receives commands and updates display/LEDs/etc.
5. **Input received**: GUI captures keyboard input as button presses
6. **State returned**: GUI responds with button states when firmware polls

### Example: Drawing to Display

```python
# Badge firmware code (src/apps/my_app.py)
display.fill_rect(10, 10, 50, 50, 0xF800)  # Draw red rectangle

# ↓ Shim intercepts (libraries/gc9a01.py)
emulator.send_command('gc9a01', 'fill_rect', 
                     x=10, y=10, w=50, h=50, 
                     color=0xF800, display=1)

# ↓ Socket communication
{"module": "gc9a01", "command": "fill_rect", 
 "parameters": {"x": 10, "y": 10, "w": 50, "h": 50,
               "color": 63488, "display": 1}}

# ↓ GUI handles (gui.py)
pygame.draw.rect(self.screen1, (248, 0, 0), 
                pygame.Rect(10, 10, 50, 50))

# ↓ Response
{"status": "ok", "resp": null}
```

## Developing Badge Applications

### Creating a New App

1. Create your app file:
   ```bash
   cd src/apps
   vim my_new_app.py
   ```

2. Write your app (inherits from `BaseApp`):
   ```python
   from apps.app import BaseApp
   import gc9a01
   
   class MyNewApp(BaseApp):
       name = "My New App"
       
       async def setup(self):
           self.controller.bsp.displays.display1.fill(gc9a01.BLACK)
           self.controller.bsp.displays.display1.text(
               vga1_bold_16x32,
               "Hello!",
               50, 100,
               gc9a01.WHITE,
               gc9a01.BLACK
           )
       
       def button_click(self, button):
           print(f"Button {button} clicked!")
   ```

3. Run simulator with your new app:
   ```bash
   cd simulator
   python3 main.py -p ../src
   ```

4. Select your app from the badge menu (use button navigation)

### Using Framebuffers (Recommended for Complex Graphics)

```python
import framebuf

class MyFramebufferApp(BaseApp):
    name = "Framebuffer Demo"
    
    async def setup(self):
        # Allocate framebuffer (240x240 RGB565 = 115,200 bytes)
        self.buffer = bytearray(240 * 240 * 2)
        self.fb = framebuf.FrameBuffer(
            self.buffer, 
            240, 
            240, 
            framebuf.RGB565
        )
        
        # Draw to framebuffer (in-memory, fast)
        self.fb.fill(0x0000)  # Black
        self.fb.rect(10, 10, 220, 220, 0xFFFF)  # White border
        self.fb.text("Framebuffer!", 50, 100, 0xF800)  # Red text
        
        # Send to display (one SPI transaction)
        self.controller.bsp.displays.display1.blit_buffer(
            self.buffer,
            0, 0,
            240, 240
        )
```

**Benefits**:
- Much faster for complex scenes
- Reduces flicker
- Allows double-buffering

### Testing Different Scenarios

**Button Interactions**:
```python
def button_click(self, button):
    # Test all 5 buttons
    messages = [
        "Button 0: Menu",
        "Button 1: Up", 
        "Button 2: Select",
        "Button 3: Down",
        "Button 4: Back"
    ]
    
    display = self.controller.bsp.displays.display1
    display.fill(gc9a01.BLACK)
    display.text(vga1_bold_16x32, messages[button], 10, 100)
```

**LED Control**:
```python
async def setup(self):
    leds = self.controller.bsp.leds
    
    # Rainbow effect
    colors = [
        (255, 0, 0),    # Red
        (255, 127, 0),  # Orange
        (255, 255, 0),  # Yellow
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
    ]
    
    for i, color in enumerate(colors):
        leds.leds[i] = color
    leds.leds.write()
```

**Dual Display**:
```python
async def setup(self):
    # Display 1 (upper)
    self.controller.bsp.displays.display1.fill(gc9a01.BLUE)
    self.controller.bsp.displays.display1.text(
        vga1_bold_16x32, "Display 1", 50, 100
    )
    
    # Display 2 (lower)
    self.controller.bsp.displays.display2.fill(gc9a01.GREEN)
    self.controller.bsp.displays.display2.text(
        vga1_bold_16x32, "Display 2", 50, 100
    )
```

## Troubleshooting

### Simulator Won't Start

**Error**: `ModuleNotFoundError: No module named 'pygame'`
```bash
# Install pygame
pip install pygame
```

**Error**: `micropython: command not found`
```bash
# Specify full path to micropython
python3 main.py -p ../src -m /path/to/micropython
```

**Error**: `No project found`
```bash
# Make sure path to src directory is correct
ls ../src/main.py  # Should exist
python3 main.py -p ../src
```

### Display Not Updating

**Symptom**: Displays remain blank or show old content

**Possible Causes**:
1. **Firmware error**: Check MicroPython output in terminal for exceptions
2. **Display init failed**: Make sure display objects are created properly
3. **Buffer issue**: If using framebuffer, ensure buffer is sent via `blit_buffer()`

**Debug Steps**:
```bash
# Run with verbose output
python3 main.py -p ../src 2>&1 | tee simulator.log

# Check for errors in output
grep -i error simulator.log
grep -i exception simulator.log
```

### Buttons Not Working

**Symptom**: Keyboard presses don't trigger button events

**Solutions**:
1. Make sure pygame window has focus (click on it)
2. Try pressing keys 1-5 (not numpad, regular number keys)
3. Check button mapping in `gui.py`:
   ```python
   if event.key == pygame.K_1:  # Uses K_1, not KP_1
       self.button_states[0] = 1
   ```

### Slow Performance

**Symptom**: Simulator runs slowly, animations stutter

**Causes & Solutions**:

1. **Large buffer transfers**:
   - Use direct drawing for simple graphics instead of blit_buffer
   - Reduce update frequency
   
2. **Pygame rendering**:
   - Close other applications
   - Reduce window size (edit `gui.py` to scale down)
   
3. **MicroPython overhead**:
   - Normal for interpreted Python
   - Consider optimizing hot loops in firmware

### Socket Connection Issues

**Error**: `Connection refused` or `Address already in use`

**Solutions**:
```bash
# Check if port 4455 is in use
lsof -i :4455

# Kill process using port
kill <PID>

# Or wait a moment and try again (TIME_WAIT state)
```

### Import Errors in Firmware

**Error**: `ImportError: no module named 'gc9a01'`

**Cause**: Firmware trying to import C extension

**Solution**: Modify firmware to use Python driver in simulator:
```python
# src/drivers/displays.py
import os

if os.getenv('BADGE_SIMULATOR'):
    USE_PY_DRIVER = True  # Force Python driver
else:
    USE_PY_DRIVER = False  # Use C driver on hardware
```

Simulator sets `BADGE_SIMULATOR` environment variable automatically.

## Advanced Usage

### Running Multiple Simulators

Each simulator needs a unique port:

```python
# Edit simulator/main.py
PORT = 4455  # Change to 4456, 4457, etc.
emulator_socket.bind(('127.0.0.1', PORT))
```

Then run:
```bash
# Terminal 1
python3 main.py -p ../src  # Uses port 4455

# Terminal 2
# Edit main.py to use port 4456 first
python3 main.py -p ../src2  # Uses port 4456
```

### Automated Testing

Run simulator in headless mode for testing:

```python
# test_badge_app.py
import subprocess
import socket
import json
import time

# Start simulator in no-GUI mode
sim = subprocess.Popen(
    ['python3', 'main.py', '-p', '../src', '--no-gui'],
    cwd='simulator'
)

time.sleep(2)  # Wait for startup

# Connect to simulator
sock = socket.socket()
sock.connect(('127.0.0.1', 4455))

# Send test commands
test_cmd = {
    'module': 'pca9535',
    'command': 'get_inputs'
}
sock.send(json.dumps(test_cmd).encode() + b'\n')
response = sock.recv(1024)
print(f"Response: {response}")

# Cleanup
sock.close()
sim.terminate()
```

### Debugging Tips

**Enable command logging**:
```python
# Edit simulator/gui.py
def handle_command(self, command):
    # Add at start of function
    if command['module'] != 'pca9535':  # Skip button polling spam
        print(f"[GUI] Command: {command['module']}.{command['command']}")
    
    # ... rest of function
```

**Monitor socket traffic**:
```bash
# In one terminal
sudo tcpdump -i lo -A port 4455

# In another terminal
python3 main.py -p ../src
```

**Profile performance**:
```python
# Add to gui.py gameloop
import time

def gameloop(self):
    frame_times = []
    
    while self.running:
        t_start = time.time()
        
        # ... existing gameloop code ...
        
        t_end = time.time()
        frame_time = (t_end - t_start) * 1000
        frame_times.append(frame_time)
        
        if len(frame_times) >= 60:
            avg = sum(frame_times) / len(frame_times)
            print(f"Avg frame time: {avg:.2f}ms ({1000/avg:.1f} FPS)")
            frame_times = []
```

## Tips for Best Results

1. **Start Simple**: Test basic apps before complex ones
2. **Use Framebuffers**: Much better performance for complex graphics
3. **Check Terminal Output**: MicroPython prints errors and debug info
4. **Keep Window Focused**: Pygame only receives input when focused
5. **Save Often**: Simulator doesn't save badge state between runs
6. **Test on Hardware**: Simulator is not 100% accurate - always verify on real badge

## Known Limitations

- **No WiFi simulation**: Network features won't work
- **Timing differences**: Simulator may run faster/slower than hardware
- **Limited hardware emulation**: Some peripherals are stubs only
- **No persistence**: Files written to filesystem are temporary
- **Audio playback**: Only visual indicator, no actual sound
- **IMU simulation**: Accelerometer events are not simulated

## Getting Help

- **Documentation**: Check `docs/` folder for more information
- **Issues**: Report bugs on GitHub issue tracker
- **Logs**: Save terminal output when reporting issues
- **Community**: Ask on BSides FW Discord/Slack

## Next Steps

Now that you know how to run the simulator:
1. Try running existing badge apps
2. Create a simple test app
3. Experiment with framebuffer rendering
4. Test button interactions
5. Contribute improvements to the simulator!

Happy developing! 🎮
