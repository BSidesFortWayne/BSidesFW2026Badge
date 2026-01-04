# Simulator Implementation Quick Reference

## Critical Code Snippets for Implementation

This document provides ready-to-use code snippets for implementing the simulator updates.

## Phase 1: Framebuffer Support

### 1. RGB565 to RGB888 Conversion (gui.py)

```python
def rgb565_to_rgb888(self, pixel565):
    """
    Convert 16-bit RGB565 color to 24-bit RGB888.
    
    RGB565: RRRRR GGGGGG BBBBB (5-6-5 bits)
    RGB888: RRRRRRRR GGGGGGGG BBBBBBBB (8-8-8 bits)
    """
    r = ((pixel565 >> 11) & 0x1F) << 3
    g = ((pixel565 >> 5) & 0x3F) << 2
    b = (pixel565 & 0x1F) << 3
    return (r, g, b)

def blit_rgb565_buffer(self, surface, buffer_bytes, x, y, width, height):
    """
    Blit RGB565 buffer to pygame surface.
    
    Args:
        surface: pygame.Surface to draw on
        buffer_bytes: bytes object with RGB565 data
        x, y: Top-left position
        width, height: Buffer dimensions
    """
    for row in range(height):
        for col in range(width):
            # Calculate offset (2 bytes per pixel, little-endian)
            offset = ((row * width) + col) * 2
            
            # Read 16-bit color value (little-endian)
            pixel565 = buffer_bytes[offset] | (buffer_bytes[offset + 1] << 8)
            
            # Convert and draw
            rgb888 = self.rgb565_to_rgb888(pixel565)
            surface.set_at((x + col, y + row), rgb888)
```

### 2. Blit Buffer Command Handler (gui.py)

```python
def handle_command(self, command):
    screens = [self.screen1, self.screen2]
    
    if command['module'] == 'gc9a01':
        # ... existing commands ...
        
        elif command['command'] == 'blit_buffer':
            display_idx = command['parameters']['display'] - 1
            x = command['parameters']['x']
            y = command['parameters']['y']
            width = command['parameters']['width']
            height = command['parameters']['height']
            
            # Decode buffer from hex string
            buffer_hex = command['parameters']['buffer']
            buffer_bytes = bytes.fromhex(buffer_hex)
            
            # Optional: decompress if compressed flag set
            if command['parameters'].get('compressed', False):
                import zlib
                buffer_bytes = zlib.decompress(buffer_bytes)
            
            # Blit to display
            self.blit_rgb565_buffer(
                screens[display_idx],
                buffer_bytes,
                x, y,
                width, height
            )
            
            return None
```

### 3. Blit Buffer Shim Method (libraries/gc9a01.py)

```python
def blit_buffer(self, buffer, x, y, width, height):
    """
    Copy buffer to display at the given location.
    
    Args:
        buffer: bytes/bytearray/memoryview with RGB565 data
        x: Top left corner x coordinate
        y: Top left corner y coordinate
        width: Width in pixels
        height: Height in pixels
    """
    # Convert buffer to bytes if needed
    if isinstance(buffer, memoryview):
        buffer = buffer.tobytes()
    elif isinstance(buffer, bytearray):
        buffer = bytes(buffer)
    
    # Optional compression for large buffers
    buffer_size = len(buffer)
    compressed = False
    
    if buffer_size > 20000:  # ~83x240 pixels
        import zlib
        compressed_data = zlib.compress(buffer, level=1)
        if len(compressed_data) < buffer_size:
            buffer = compressed_data
            compressed = True
    
    # Convert to hex string for JSON safety
    buffer_hex = buffer.hex()
    
    # Send command
    emulator.send_command(
        'gc9a01',
        'blit_buffer',
        buffer=buffer_hex,
        x=x,
        y=y,
        width=width,
        height=height,
        compressed=compressed,
        display=self.display
    )
```

## Phase 2: Bitmap Support

### 1. Bitmap Decoder (gui.py)

```python
def decode_bitmap(self, bitmap_data, index=0):
    """
    Decode bitmap data from badge format to RGB565 buffer.
    
    Args:
        bitmap_data: Dict with WIDTH, HEIGHT, BPP, PALETTE, BITMAP
        index: Bitmap index for multi-bitmap modules
    
    Returns:
        bytearray with RGB565 data
    """
    width = bitmap_data['width']
    height = bitmap_data['height']
    bpp = bitmap_data['bpp']
    palette = bitmap_data['palette']
    bitmap_bits = bitmap_data['bitmap']
    
    bitmap_size = width * height
    buffer = bytearray(bitmap_size * 2)  # RGB565 = 2 bytes/pixel
    
    # Starting bit offset for this index
    bs_bit = bpp * bitmap_size * index
    
    for i in range(0, bitmap_size * 2, 2):
        # Extract color index from bitmap
        color_index = 0
        for bit in range(bpp):
            color_index <<= 1
            byte_idx = (bs_bit + bit) // 8
            bit_idx = 7 - ((bs_bit + bit) % 8)
            color_index |= (bitmap_bits[byte_idx] >> bit_idx) & 1
        
        bs_bit += bpp
        
        # Get color from palette
        color565 = palette[color_index]
        
        # Store as little-endian
        buffer[i] = color565 & 0xFF
        buffer[i + 1] = (color565 >> 8) & 0xFF
    
    return buffer

def handle_command(self, command):
    # ... in gc9a01 section ...
    
    elif command['command'] == 'bitmap':
        display_idx = command['parameters']['display'] - 1
        x = command['parameters']['x']
        y = command['parameters']['y']
        bitmap_data = command['parameters']['bitmap']
        index = command['parameters'].get('index', 0)
        
        # Decode bitmap to RGB565 buffer
        buffer = self.decode_bitmap(bitmap_data, index)
        
        # Blit to display
        width = bitmap_data['width']
        height = bitmap_data['height']
        self.blit_rgb565_buffer(
            screens[display_idx],
            buffer,
            x, y,
            width, height
        )
```

### 2. Bitmap Shim Method (libraries/gc9a01.py)

```python
def bitmap(self, bitmap, x, y, index=0):
    """
    Draw a bitmap on display at the specified column and row.
    
    Args:
        bitmap: Module containing bitmap data (BITMAP, WIDTH, HEIGHT, etc.)
        x: Column to start drawing at
        y: Row to start drawing at
        index: Optional index of bitmap to draw from multiple bitmap module
    """
    # Serialize bitmap data for transmission
    bitmap_data = {
        'width': bitmap.WIDTH,
        'height': bitmap.HEIGHT,
        'bpp': bitmap.BPP,
        'palette': list(bitmap.PALETTE),
        'bitmap': list(bitmap.BITMAP),
    }
    
    emulator.send_command(
        'gc9a01',
        'bitmap',
        bitmap=bitmap_data,
        x=x,
        y=y,
        index=index,
        display=self.display
    )
```

## Phase 3: LED Visualization

### 1. LED Rendering (gui.py)

```python
class GUI:
    def __init__(self):
        # ... existing init ...
        
        # LED state (5 NeoPixels, RGB tuples)
        self.led_states = [(0, 0, 0)] * 5
        
        # LED positions on board image (adjust based on board_render.png)
        self.led_positions = [
            (100, 950),  # LED 0
            (150, 950),  # LED 1
            (200, 950),  # LED 2
            (250, 950),  # LED 3
            (300, 950),  # LED 4
        ]
        
        self.led_radius = 8
    
    def render_leds(self):
        """Draw LED states on display"""
        for idx, (x, y) in enumerate(self.led_positions):
            color = self.led_states[idx]
            
            # Draw LED circle with glow effect
            for r in range(self.led_radius, 0, -2):
                alpha = int(255 * (r / self.led_radius))
                glow_color = tuple(
                    min(255, int(c * 1.5)) for c in color
                )
                pygame.draw.circle(
                    self.display,
                    glow_color,
                    (x, y),
                    r
                )
            
            # Draw LED center
            pygame.draw.circle(
                self.display,
                color,
                (x, y),
                self.led_radius // 2
            )
    
    def handle_command(self, command):
        # ... existing commands ...
        
        elif command['module'] == 'neopixel':
            if command['command'] == 'write':
                # Update LED states
                self.led_states = [
                    tuple(led) for led in command['parameters']['leds']
                ]
    
    def gameloop(self):
        while self.running:
            # ... existing gameloop ...
            
            # Render board background
            self.display.blit(self.board_texture, (0, 0))
            
            # Render displays
            self.display.blit(
                self.generate_circular_cutout(self.screen1),
                (70, 558)
            )
            self.display.blit(
                self.generate_circular_cutout(self.screen2),
                (234, 774)
            )
            
            # Render LEDs on top
            self.render_leds()
            
            pygame.display.update()
```

### 2. NeoPixel Shim (libraries/neopixel.py)

```python
import emulator

class NeoPixel:
    """Simulated NeoPixel LED strip"""
    
    def __init__(self, pin, n, bpp=3, timing=1):
        """
        Args:
            pin: GPIO pin (ignored in simulator)
            n: Number of LEDs
            bpp: Bytes per pixel (3 for RGB, 4 for RGBW)
            timing: Timing parameter (ignored)
        """
        self.pin = pin
        self.n = n
        self.bpp = bpp
        self._leds = [(0, 0, 0)] * n
    
    def __setitem__(self, idx, color):
        """Set LED color: neopixel[0] = (255, 0, 0)"""
        if isinstance(idx, slice):
            # Handle slice assignment
            start, stop, step = idx.indices(self.n)
            for i in range(start, stop, step or 1):
                self._leds[i] = tuple(color)
        else:
            self._leds[idx] = tuple(color)
    
    def __getitem__(self, idx):
        """Get LED color: r, g, b = neopixel[0]"""
        return self._leds[idx]
    
    def fill(self, color):
        """Set all LEDs to the same color"""
        for i in range(self.n):
            self._leds[i] = tuple(color)
    
    def write(self):
        """Send LED states to simulator for display"""
        emulator.send_command(
            'neopixel',
            'write',
            leds=[list(led) for led in self._leds]
        )
```

## Phase 4: Display Initialization Fix

### 1. Displays Shim (libraries/displays.py)

```python
from machine import Pin, SPI
from gc9a01 import GC9A01
import machine

class Displays:
    """Simulated Displays class matching hardware API"""
    
    SCK = 18
    MOSI = 23
    DC1 = 19
    RST1 = 14
    CS1 = 33
    DC2 = 25
    RST2 = 27
    CS2 = 13
    DISP_EN = 32
    
    def __init__(self, spi_freq=80_000_000):
        """Initialize display objects (simulator version)"""
        # Create fake pin for display enable
        self.disp_en = Pin(self.DISP_EN, Pin.OUT)
        self.disp_en.value(1)
        
        # Create fake SPI
        spi = SPI(1, baudrate=spi_freq, sck=Pin(self.SCK), mosi=Pin(self.MOSI))
        
        # Create display objects using simulator shims
        self.display1 = GC9A01(
            spi,
            240, 240,
            reset=Pin(self.RST1, Pin.OUT),
            cs=Pin(self.CS1, Pin.OUT),
            dc=Pin(self.DC1, Pin.OUT),
            rotation=3
        )
        
        self.display2 = GC9A01(
            spi,
            240, 240,
            reset=Pin(self.RST2, Pin.OUT),
            cs=Pin(self.CS2, Pin.OUT),
            dc=Pin(self.DC2, Pin.OUT),
            rotation=3
        )
        
        # Initialize displays
        self.display1.init()
        self.display2.init()
    
    def __getitem__(self, index):
        """Access displays by index: displays[0] or displays[1]"""
        if index == 0:
            return self.display1
        elif index == 1:
            return self.display2
        else:
            raise IndexError("Display index out of range")
    
    def __len__(self):
        return 2
    
    @staticmethod
    def rgb_to_565(r, g, b):
        """Convert RGB888 to RGB565"""
        return (r & 0xF8) | ((g & 0xE0) >> 5) | ((g & 0x1C) << 11) | ((b & 0xF8) << 5)
```

### 2. Simulator Detection (Add to firmware)

```python
# In src/main.py or src/controller.py
import os
import sys

# Check if running in simulator
SIMULATOR_MODE = os.getenv('BADGE_SIMULATOR') == '1'

if SIMULATOR_MODE:
    print("Running in simulator mode")
    # Simulator-specific setup if needed
else:
    print("Running on hardware")

# Displays initialization works the same way now
# because simulator provides compatible Displays class
```

### 3. Environment Variable Setup (simulator/main.py)

```python
# In simulator/main.py, before launching MicroPython
import os

# Set environment variable for simulator detection
os.environ['BADGE_SIMULATOR'] = '1'

# Copy project files
shutil.copytree(args.project, 'src')

# Overlay simulator libraries
shutil.copytree('libraries', 'src', dirs_exist_ok=True)

# Launch MicroPython in src directory
micropython_process = subprocess.Popen(
    [args.micropython, 'main.py'],
    cwd='src',
    env=os.environ.copy()  # Pass environment to subprocess
)
```

## Performance Optimization

### Efficient Buffer Transfer

```python
# In libraries/gc9a01.py

def blit_buffer(self, buffer, x, y, width, height):
    """Optimized buffer transfer with compression"""
    
    # Convert buffer
    if isinstance(buffer, memoryview):
        buffer = buffer.tobytes()
    elif isinstance(buffer, bytearray):
        buffer = bytes(buffer)
    
    buffer_size = len(buffer)
    
    # Adaptive compression strategy
    if buffer_size > 50000:
        # Large buffer: try compression
        import zlib
        compressed = zlib.compress(buffer, level=1)
        if len(compressed) < buffer_size * 0.8:  # Only if 20%+ savings
            buffer = compressed
            compressed_flag = True
        else:
            compressed_flag = False
    elif buffer_size > 10000:
        # Medium buffer: fast compression
        import zlib
        compressed = zlib.compress(buffer, level=1)
        if len(compressed) < buffer_size * 0.9:  # Only if 10%+ savings
            buffer = compressed
            compressed_flag = True
        else:
            compressed_flag = False
    else:
        # Small buffer: no compression overhead
        compressed_flag = False
    
    # Send
    emulator.send_command(
        'gc9a01',
        'blit_buffer',
        buffer=buffer.hex(),
        x=x, y=y,
        width=width, height=height,
        compressed=compressed_flag,
        display=self.display
    )
```

### Frame Rate Limited Game Loop

```python
# In gui.py

def gameloop(self):
    clock = pygame.Clock()
    target_fps = 60
    
    # Track which displays need redraw
    display_dirty = [False, False]
    
    while self.running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            # ... other event handling ...
        
        # Only redraw if needed
        if any(display_dirty):
            # Clear and draw base
            self.display.blit(self.board_texture, (0, 0))
            
            # Draw displays
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
            
            # Draw hardware
            self.render_leds()
            
            # Update display
            pygame.display.update()
            
            # Reset dirty flags
            display_dirty = [False, False]
        
        # Limit frame rate
        clock.tick(target_fps)
```

## Testing

### Simple Framebuffer Test

```python
# test_framebuffer.py (place in src/test/)
import framebuf
from controller import Controller

def test_basic_framebuffer():
    """Test basic framebuffer functionality"""
    c = Controller(displays=None, start_app_on_launch=False)
    
    # Create framebuffer
    buf = bytearray(240 * 240 * 2)
    fb = framebuf.FrameBuffer(buf, 240, 240, framebuf.RGB565)
    
    # Test 1: Fill
    fb.fill(0xF800)  # Red
    c.bsp.displays.display1.blit_buffer(buf, 0, 0, 240, 240)
    print("Test 1: Red fill - Check display 1")
    input("Press Enter to continue...")
    
    # Test 2: Rectangle
    fb.fill(0x0000)  # Black
    fb.rect(10, 10, 220, 220, 0xFFFF)  # White rect
    c.bsp.displays.display1.blit_buffer(buf, 0, 0, 240, 240)
    print("Test 2: White rectangle - Check display 1")
    input("Press Enter to continue...")
    
    # Test 3: Text
    fb.fill(0x001F)  # Blue
    fb.text("Hello!", 80, 110, 0xFFFF)  # White text
    c.bsp.displays.display1.blit_buffer(buf, 0, 0, 240, 240)
    print("Test 3: 'Hello!' text - Check display 1")
    input("Press Enter to continue...")
    
    print("All tests complete!")

if __name__ == '__main__':
    test_basic_framebuffer()
```

### Run Test

```bash
cd simulator
python3 main.py -p ../src

# In another terminal (once simulator is running)
# MicroPython will execute the test
```

## Common Pitfalls

1. **Buffer Endianness**: RGB565 is little-endian on ESP32
   ```python
   # Correct:
   pixel = buffer[i] | (buffer[i+1] << 8)
   
   # Wrong:
   pixel = (buffer[i] << 8) | buffer[i+1]
   ```

2. **Memoryview vs Bytes**: Must convert before hex encoding
   ```python
   # Correct:
   if isinstance(buffer, memoryview):
       buffer = buffer.tobytes()
   buffer_hex = buffer.hex()
   
   # Wrong:
   buffer_hex = buffer.hex()  # memoryview has no hex() method
   ```

3. **Display Index**: Displays are 1-indexed in commands, 0-indexed in arrays
   ```python
   # Correct:
   screens[command['parameters']['display'] - 1]
   
   # Wrong:
   screens[command['parameters']['display']]
   ```

4. **JSON Encoding**: Binary data must be hex-encoded
   ```python
   # Correct:
   {'buffer': buffer.hex()}
   
   # Wrong:
   {'buffer': buffer}  # Not JSON serializable
   ```

## Next Steps

1. Copy relevant snippets into simulator code
2. Test each phase incrementally
3. Verify with existing badge apps
4. Profile and optimize performance
5. Update user documentation

Happy implementing! 🚀
