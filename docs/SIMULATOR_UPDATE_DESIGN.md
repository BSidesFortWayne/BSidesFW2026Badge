# Simulator Update Design Document

## Executive Summary

This document outlines the design for updating the BSides FW 2025 Badge simulator to work with the current framebuffer-based BSP architecture. The update will preserve the existing socket-based communication architecture while extending it to support modern display driver features, particularly `blit_buffer()` for framebuffer rendering.

## Current State Analysis

### Firmware (Main Branch) - Current Architecture

#### BSP Structure
- **Constructor**: `BSP(hardware_version: str, displays, debug: bool = False)`
- **Key Change**: Displays object is now passed to BSP, not created by it
- **Hardware Components**:
  - Displays (dual GC9A01 240x240 circular LCD)
  - LEDs (NeoPixel RGB)
  - Buttons (via PCA9535 I/O expander)
  - IMU (LIS3DH accelerometer)
  - Speaker (audio output)
  - RTC (real-time clock)

#### Display Driver (GC9A01)
The firmware supports both Python and C implementations of the GC9A01 driver:

**Python Driver** (`src/drivers/gc9a01.py`):
- Full MicroPython implementation
- Key methods:
  - `fill(color)` - Fill entire display
  - `fill_rect(x, y, w, h, color)` - Draw filled rectangle
  - `pixel(x, y, color)` - Draw single pixel
  - `line(x0, y0, x1, y1, color)` - Draw line
  - `circle(x, y, r, color)` - Draw circle outline
  - `fill_circle(x, y, r, color)` - Draw filled circle
  - `text(font, string, x, y, fg, bg)` - Render text
  - `bitmap(bitmap, x, y, index)` - Draw bitmap image
  - **`blit_buffer(buffer, x, y, width, height)`** - ⭐ KEY METHOD for framebuffer support
  - `jpg(filename, x, y, mode)` - Display JPEG (C driver only)
  - `write_len(font, string)` - Calculate text width

**C Driver** (compiled into firmware):
- Faster performance via native C implementation
- Same API as Python driver
- Used by default (`USE_PY_DRIVER = False`)

#### Framebuffer Usage Pattern

Modern badge code uses MicroPython's `framebuf` module for efficient rendering:

```python
import framebuf

# Allocate buffer for 240x240 display in RGB565 format
mem_buf = bytearray(240 * 240 * 2)  # 2 bytes per pixel
fbuf = framebuf.FrameBuffer(mem_buf, 240, 240, framebuf.RGB565)

# Draw to framebuffer (all in-memory, fast)
fbuf.fill(0xF800)
fbuf.rect(10, 10, 50, 50, 0xFFFF)
fbuf.text("Hello", 100, 100, 0xFFFF)

# Send entire framebuffer to display (one SPI transaction)
display.blit_buffer(mem_buf, 0, 0, 240, 240)
```

**Benefits**:
- All drawing happens in memory (fast)
- Single SPI transfer to display (efficient)
- Complex scenes can be composed before display
- Reduces screen tearing and flicker

### Simulator (Simulator Branch) - Current Implementation

**Limitations**:
1. Only supports direct drawing commands (pixel, line, rect, etc.)
2. No `blit_buffer()` support - **critical missing feature**
3. Hardcoded for C driver API (doesn't match Python driver exactly)
4. Display initialization in BSP not compatible with simulator shim approach
5. Missing modern API methods like `bitmap()`

## Design Goals

1. **Support Framebuffer Rendering**: Add `blit_buffer()` command to simulator
2. **Maintain Compatibility**: Work with both old direct-draw code and new framebuffer code
3. **Match Current API**: Support both Python and C driver APIs
4. **Preserve Architecture**: Keep socket-based IPC and shim pattern
5. **Improve Hardware Emulation**: Add visual representations for LEDs, speaker, etc.
6. **Developer Experience**: Make simulator easy to set up and use
7. **Performance**: Handle high-frequency blit_buffer calls efficiently

## Proposed Architecture

### Updated Component Design

#### 1. Enhanced GUI (`simulator/gui.py`)

**New Features**:

```python
class GUI:
    def handle_command(self, command):
        # ... existing commands ...
        
        elif command['command'] == 'blit_buffer':
            # Receive raw framebuffer data
            buffer_data = bytes.fromhex(command['parameters']['buffer'])
            display_idx = command['parameters']['display'] - 1
            x = command['parameters']['x']
            y = command['parameters']['y']
            width = command['parameters']['width']
            height = command['parameters']['height']
            
            # Convert RGB565 buffer to pygame surface
            self._blit_rgb565_buffer(
                screens[display_idx],
                buffer_data,
                x, y, width, height
            )
        
        elif command['command'] == 'bitmap':
            # Support bitmap rendering
            bitmap_data = command['parameters']['bitmap']
            # ... render bitmap ...
```

**RGB565 Conversion Helper**:
```python
def _blit_rgb565_buffer(self, surface, buffer, x, y, width, height):
    """
    Convert RGB565 buffer to RGB888 and blit to pygame surface.
    
    RGB565 format: RRRRR GGGGGG BBBBB (16 bits)
    Stored as little-endian shorts in buffer
    """
    for row in range(height):
        for col in range(width):
            offset = ((row * width) + col) * 2
            # Read 16-bit color (little-endian)
            pixel565 = buffer[offset] | (buffer[offset + 1] << 8)
            # Convert to RGB888
            r = ((pixel565 >> 11) & 0x1F) << 3
            g = ((pixel565 >> 5) & 0x3F) << 2
            b = (pixel565 & 0x1F) << 3
            surface.set_at((x + col, y + row), (r, g, b))
```

**Hardware Visualization**:
```python
class GUI:
    def __init__(self):
        # ... existing init ...
        
        # LED visualization (5 NeoPixels)
        self.led_states = [(0, 0, 0)] * 5
        self.led_positions = [
            (100, 950),  # LED 0 position on board
            (150, 950),  # LED 1
            (200, 950),  # LED 2
            (250, 950),  # LED 3
            (300, 950),  # LED 4
        ]
        
        # Speaker visualization
        self.speaker_active = False
        self.speaker_position = (400, 950)
    
    def render_hardware(self):
        """Render LED and speaker states on board"""
        for idx, (x, y) in enumerate(self.led_positions):
            color = self.led_states[idx]
            pygame.draw.circle(self.display, color, (x, y), 10)
        
        if self.speaker_active:
            # Draw speaker indicator
            pygame.draw.circle(
                self.display,
                (255, 255, 0),
                self.speaker_position,
                15
            )
```

#### 2. Updated GC9A01 Shim (`simulator/libraries/gc9a01.py`)

**Enhanced to match current driver API**:

```python
class GC9A01:
    def __init__(self, spi, width, height, reset, cs, dc, rotation, buffer_size=0):
        # Note: buffer_size parameter added to match Python driver
        self._width = width
        self._height = height
        self.rotation = rotation
        self.buffer_size = buffer_size
        
        # Determine display number by DC pin
        if hasattr(dc, 'pin'):
            self.display = 1 if dc.pin == 19 else 2
        else:
            self.display = 1
    
    def blit_buffer(self, buffer, x, y, width, height):
        """
        Send framebuffer data to display simulator.
        
        Args:
            buffer: bytes/bytearray/memoryview with RGB565 data
            x, y: Top-left position
            width, height: Dimensions of buffer
        """
        # Convert buffer to bytes if it's a memoryview
        if isinstance(buffer, memoryview):
            buffer = buffer.tobytes()
        elif isinstance(buffer, bytearray):
            buffer = bytes(buffer)
        
        # Send as hex string to avoid JSON encoding issues
        buffer_hex = buffer.hex()
        
        emulator.send_command(
            'gc9a01',
            'blit_buffer',
            buffer=buffer_hex,
            x=x,
            y=y,
            width=width,
            height=height,
            display=self.display
        )
    
    def bitmap(self, bitmap, x, y, index=0):
        """
        Draw bitmap from bitmap module.
        
        Args:
            bitmap: Module with BITMAP, WIDTH, HEIGHT, BPP, PALETTE
            x, y: Position
            index: Bitmap index for multi-bitmap modules
        """
        # Serialize bitmap data
        bitmap_data = {
            'width': bitmap.WIDTH,
            'height': bitmap.HEIGHT,
            'bpp': bitmap.BPP,
            'palette': list(bitmap.PALETTE),
            'bitmap': list(bitmap.BITMAP),
            'index': index
        }
        
        emulator.send_command(
            'gc9a01',
            'bitmap',
            bitmap=bitmap_data,
            x=x,
            y=y,
            display=self.display
        )
    
    def width(self):
        return self._width
    
    def height(self):
        return self._height
    
    # ... all existing methods remain ...
```

#### 3. LED Shim (`simulator/libraries/neopixel.py`)

```python
import emulator

class NeoPixel:
    def __init__(self, pin, n, bpp=3, timing=1):
        self.pin = pin
        self.n = n
        self.bpp = bpp
        self._leds = [(0, 0, 0)] * n
    
    def __setitem__(self, idx, color):
        self._leds[idx] = color
    
    def __getitem__(self, idx):
        return self._leds[idx]
    
    def write(self):
        """Send LED states to simulator"""
        emulator.send_command(
            'neopixel',
            'write',
            leds=list(self._leds)
        )
    
    def fill(self, color):
        for i in range(self.n):
            self._leds[i] = color
```

#### 4. Speaker Shim (`simulator/libraries/speaker.py`)

```python
import emulator

class Speaker:
    def __init__(self):
        self.state = 'stopped'
    
    def play_tone(self, freq, duration):
        emulator.send_command(
            'speaker',
            'play_tone',
            frequency=freq,
            duration=duration
        )
    
    def play_song(self, song):
        emulator.send_command(
            'speaker',
            'play_song',
            song=song
        )
    
    def pause_song(self):
        self.state = 'paused'
        emulator.send_command('speaker', 'pause')
    
    def resume_song(self):
        self.state = 'playing'
        emulator.send_command('speaker', 'resume')
    
    def stop_song(self):
        self.state = 'stopped'
        emulator.send_command('speaker', 'stop')
```

#### 5. Modified Main Entry Point (`simulator/main.py`)

**Key Changes**:

```python
# Allow specifying main.py or using default src/main.py
parser.add_argument('-p', '--project', type=str, 
                    help='Project directory',
                    default='src')
parser.add_argument('-m', '--micropython', type=str,
                    help='MicroPython executable',
                    default='micropython')
parser.add_argument('--no-gui', action='store_true',
                    help='Run without GUI (testing mode)')

# Better error handling
try:
    micropython_process = subprocess.Popen(
        [args.micropython, 'main.py'],
        cwd='src',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Stream MicroPython output
    def print_output(stream, prefix):
        for line in stream:
            print(f"[{prefix}] {line.rstrip()}")
    
    threading.Thread(
        target=print_output,
        args=(micropython_process.stdout, 'MP'),
        daemon=True
    ).start()
    
    threading.Thread(
        target=print_output,
        args=(micropython_process.stderr, 'MP-ERR'),
        daemon=True
    ).start()

except FileNotFoundError:
    print(f"Error: MicroPython executable '{args.micropython}' not found")
    sys.exit(1)
```

### Display Initialization Compatibility

**Challenge**: Modern BSP expects Displays object to be passed in, but simulator needs to intercept display creation.

**Solution**: Modify simulator libraries to provide a fake Displays class:

```python
# simulator/libraries/displays.py
from gc9a01 import GC9A01

class Displays:
    """Simulator version of Displays class"""
    
    def __init__(self, spi_freq=80_000_000):
        # Fake initialization - displays created via shim
        self.display1 = None
        self.display2 = None
        self.disp_en = FakePin()
    
    def __getitem__(self, index):
        if index == 0:
            return self.display1
        elif index == 1:
            return self.display2
        else:
            raise IndexError("Display index out of range")
    
    def __len__(self):
        return 2

class FakePin:
    def value(self, v=None):
        pass
```

Then modify `src/main.py` to check for simulator environment:

```python
# In src/main.py or src/controller.py
import os

if os.getenv('BADGE_SIMULATOR'):
    # Running in simulator - displays already created
    from displays import Displays
    displays = Displays()
else:
    # Running on hardware
    from drivers.displays import Displays
    displays = Displays()

controller = Controller(displays=displays)
```

Set environment variable in simulator:
```python
# simulator/main.py
os.environ['BADGE_SIMULATOR'] = '1'
```

## Implementation Plan

### Phase 1: Core Framebuffer Support
1. Add `blit_buffer()` command to GUI handler
2. Implement RGB565 to RGB888 conversion
3. Update gc9a01 shim with `blit_buffer()` method
4. Test with simple framebuffer example

### Phase 2: API Completeness
1. Add `bitmap()` support to GUI and shim
2. Add `write_len()` support for all fonts
3. Ensure all GC9A01 methods are implemented
4. Test rotation and display selection

### Phase 3: Hardware Emulation
1. Implement LED visualization
2. Add speaker indicator
3. Create IMU simulation (optional)
4. Add RTC support (system time)

### Phase 4: Display Initialization
1. Create Displays shim class
2. Add simulator detection to firmware
3. Test BSP initialization in simulator
4. Verify all apps launch correctly

### Phase 5: Developer Experience
1. Add command-line options for configuration
2. Create setup script for dependencies
3. Write comprehensive usage documentation
4. Add example launch configurations

### Phase 6: Testing & Polish
1. Test all existing badge apps
2. Verify framebuffer performance
3. Add debugging features (FPS counter, command log)
4. Handle edge cases and errors gracefully

## Performance Considerations

### Buffer Transfer Optimization

**Challenge**: Sending 240×240×2 = 115,200 bytes per frame over socket

**Solutions**:
1. **Hex Encoding**: Already planned, ~2x size but JSON-safe
2. **Compression**: Optional gzip for buffer data
3. **Delta Encoding**: Only send changed regions (complex)
4. **Binary Protocol**: Alternative to JSON for buffer data

**Recommended Approach**:
Start with hex encoding, measure performance, optimize if needed.

```python
# Optimized buffer transfer
def blit_buffer(self, buffer, x, y, width, height):
    if len(buffer) > 10000:  # Large buffer threshold
        # Use compression
        import zlib
        compressed = zlib.compress(bytes(buffer))
        buffer_data = compressed.hex()
        compressed_flag = True
    else:
        buffer_data = bytes(buffer).hex()
        compressed_flag = False
    
    emulator.send_command(
        'gc9a01',
        'blit_buffer',
        buffer=buffer_data,
        compressed=compressed_flag,
        # ... other params
    )
```

### GUI Frame Rate

- Target: 30-60 FPS for smooth animation
- Use pygame's clock for frame limiting
- Only redraw displays when commands received
- Cache board background image

```python
def gameloop(self):
    clock = pygame.Clock()
    display_dirty = [False, False]
    
    while self.running:
        # Process events
        for event in pygame.event.get():
            # ... handle events ...
        
        # Only redraw if displays changed
        if any(display_dirty):
            self.display.blit(self.board_texture, (0, 0))
            if display_dirty[0]:
                self.display.blit(
                    self.generate_circular_cutout(self.screen1),
                    (70, 558)
                )
            if display_dirty[1]:
                self.display.blit(
                    self.generate_circular_cutout(self.screen2),
                    (234, 774)
                )
            self.render_hardware()
            pygame.display.update()
            display_dirty = [False, False]
        
        clock.tick(60)  # 60 FPS max
```

## Testing Strategy

### Unit Tests
- RGB565 conversion accuracy
- Button state encoding/decoding
- Command serialization/deserialization

### Integration Tests
- Run each badge app in simulator
- Verify display output matches hardware
- Test button interactions
- Verify performance (FPS, latency)

### Test Applications
Create simple test apps:
1. Framebuffer fill test (all colors)
2. Bitmap rendering test
3. Text rendering test
4. Button response test
5. LED control test

## Dependencies

### Python Packages (Host)
```
pygame>=2.0.0
Pillow>=8.0.0  # For image handling
```

### MicroPython Unix Port
- Must have `framebuf` module compiled in
- Socket support required
- File I/O support

## Migration Path for Existing Code

Most existing badge code will work without changes:

**Direct Drawing** (existing):
```python
display.fill(gc9a01.RED)
display.text(font, "Hello", 0, 0)
```
✅ Works - commands sent to simulator

**Framebuffer Drawing** (new):
```python
import framebuf
buf = bytearray(240*240*2)
fb = framebuf.FrameBuffer(buf, 240, 240, framebuf.RGB565)
fb.fill(0xF800)
display.blit_buffer(buf, 0, 0, 240, 240)
```
✅ Works with updated simulator

**No changes needed to badge application code!**

## Future Enhancements

1. **Recording/Playback**: Record simulator sessions for debugging
2. **Network Simulation**: Test WiFi features
3. **File System Browsing**: View badge file system
4. **REPL Access**: Interactive MicroPython shell
5. **Performance Profiling**: Measure app performance
6. **Multi-Badge Simulation**: Simulate multiple badges interacting
7. **Web-Based Simulator**: Port to browser using WebAssembly

## Conclusion

This design preserves the proven architecture of the current simulator while extending it to support modern framebuffer-based rendering. The modular approach allows incremental implementation and testing. The simulator will provide a fast, convenient development environment for badge applications without requiring physical hardware.
