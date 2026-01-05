"""
Binary protocol version of GC9A01 driver for emulator.
Uses binary transport instead of JSON for much better performance.
"""

import machine
import emulator_binary as eb

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
        pass  # No init needed for binary protocol
    
    def fill(self, color):
        eb.send_fill(self.display, color)
    
    def off(self):
        pass  # Not implemented in binary protocol
    
    def on(self):
        pass  # Not implemented in binary protocol

    def pixel(self, x, y, color):
        eb.send_pixel(self.display, x, y, color)
    
    def circle(self, x, y, r, color):
        eb.send_circle(self.display, x, y, r, color, filled=False)
    
    def fill_circle(self, x, y, r, color):
        eb.send_circle(self.display, x, y, r, color, filled=True)
    
    def fill_rect(self, x, y, w, h, color):
        eb.send_fill_rect(self.display, x, y, w, h, color)
    
    def line(self, x0, y0, x1, y1, color):
        eb.send_line(self.display, x0, y0, x1, y1, color)
    
    def write(self, font, string, x, y, fg_color, bg_color):
        # Text rendering still uses JSON protocol for now
        # Could be optimized later with font rendering on simulator side
        import emulator
        emulator.send_command('gc9a01', 'write', font=font.__name__, string=string, 
                            x=x, y=y, fg_color=fg_color, bg_color=bg_color, 
                            display=self.display)
    
    def text(self, font, string, x, y, fg_color, bg_color):
        # Text rendering still uses JSON protocol for now
        import emulator
        emulator.send_command('gc9a01', 'text', font=font.__name__, string=string, 
                            x=x, y=y, fg_color=fg_color, bg_color=bg_color, 
                            display=self.display)

    def write_len(self, font, string):
        # Text metrics still use JSON protocol
        import emulator
        return emulator.send_command('gc9a01', 'write_len', 
                                    font=font.__name__, string=string)['resp']

    def jpg(self, filename, x, y, mode):
        # Image loading still uses JSON protocol
        import emulator
        if filename.startswith('/'):
            filename = filename[1:]
        emulator.send_command('gc9a01', 'jpg', filename=filename, 
                            x=x, y=y, display=self.display)
    
    def blit_buffer(self, buffer, x, y, width, height):
        """OPTIMIZED: Direct binary transfer of framebuffer"""
        eb.send_blit_buffer(self.display, buffer, x, y, width, height)
