import machine
import json
import emulator

FAST = 0
SLOW = 1
RED = 63488
GREEN = 2016
BLUE = 31
CYAN = 2047
BLACK = 0
MAGENTA = 63519
WHITE = 65535
YELLOW = 65504

def color565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

class GC9A01:
    def __init__(self, spi, width, height, reset, cs, dc, rotation, options=0, buffer_size=0):
        self._width = width
        self._height = height
        self.width = lambda: self._width
        self.height = lambda: self._height
        self.rotation = rotation
        if dc.pin == 19:
            self.display = 1
        else:
            self.display = 2
 
    def init(self):
        emulator.send_command('gc9a01', 'init', display=self.display)
    
    def fill(self, color):
        emulator.send_command('gc9a01', 'fill', color=color, display=self.display)
    
    def off(self):
        emulator.send_command('gc9a01', 'off', display=self.display)
    
    def on(self):
        emulator.send_command('gc9a01', 'on', display=self.display)

    def pixel(self, x, y, color):
        emulator.send_command('gc9a01', 'pixel', x=x, y=y, color=color, display=self.display)
    
    def circle(self, x, y, r, color):
        emulator.send_command('gc9a01', 'circle', x=x, y=y, r=r, color=color, display=self.display)
    
    def fill_circle(self, x, y, r, color):
        emulator.send_command('gc9a01', 'fill_circle', x=x, y=y, r=r, color=color, display=self.display)
    
    def fill_rect(self, x, y, w, h, color):
        emulator.send_command('gc9a01', 'fill_rect', x=x, y=y, w=w, h=h, color=color, display=self.display)
    
    def line(self, x0, y0, x1, y1, color):
        emulator.send_command('gc9a01', 'line', x0=x0, y0=y0, x1=x1, y1=y1, color=color, display=self.display)
    
    def write(self, font, string, x, y, fg_color, bg_color):
        emulator.send_command('gc9a01', 'write', font=font.__name__, string=string, x=x, y=y, fg_color=fg_color, bg_color=bg_color, display=self.display)
    
    def text(self, font, string, x, y, fg_color, bg_color):
        emulator.send_command('gc9a01', 'text', font=font.__name__, string=string, x=x, y=y, fg_color=fg_color, bg_color=bg_color, display=self.display)

    def write_len(self, font, string):
        return emulator.send_command('gc9a01', 'write_len', font=font.__name__, string=string)['resp']

    def jpg(self, filename, x, y, mode):
        # Strip leading slash for simulator compatibility
        if filename.startswith('/'):
            filename = filename[1:]
        emulator.send_command('gc9a01', 'jpg', filename=filename, x=x, y=y, display=self.display)
    
    def blit_buffer(self, buffer, x, y, width, height):
        # Convert memoryview/buffer to list for JSON serialization
        # Buffer is in RGB565 format (16-bit per pixel)
        if hasattr(buffer, 'tobytes'):
            buffer_bytes = buffer.tobytes()
        elif isinstance(buffer, (bytes, bytearray)):
            buffer_bytes = bytes(buffer)
        else:
            buffer_bytes = bytes(buffer)
        
        # Convert to list of integers for JSON transmission
        buffer_list = list(buffer_bytes)
        emulator.send_command('gc9a01', 'blit_buffer', 
                            buffer=buffer_list, 
                            x=x, y=y, 
                            width=width, height=height, 
                            display=self.display)
