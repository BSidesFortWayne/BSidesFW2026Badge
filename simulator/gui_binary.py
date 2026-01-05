"""
Binary protocol handler for high-performance display rendering.
Receives binary commands from emulator and updates pygame surfaces.
"""

import struct
import pygame
from gui import GUI

# Command IDs (keep in sync with emulator_binary.py)
CMD_FILL = 0x01
CMD_PIXEL = 0x02
CMD_FILL_RECT = 0x03
CMD_LINE = 0x04
CMD_CIRCLE = 0x05
CMD_FILL_CIRCLE = 0x06
CMD_BLIT_BUFFER = 0x10
CMD_GET_INPUTS = 0x20
CMD_PIN_VALUE = 0x21
CMD_POLL_INTERRUPTS = 0x22
CMD_NEOPIXEL_WRITE = 0x30

class BinaryProtocolHandler:
    """Handles binary protocol commands for the GUI"""
    
    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.screens = [self.gui.screen1, self.gui.screen2]
    
    def rgb565_to_rgb(self, color):
        """Convert RGB565 to RGB888"""
        r = (color & 0xF800) >> 8
        g = (color & 0x07E0) >> 3
        b = (color & 0x001F) << 3
        return (r, g, b)
    
    def handle_command(self, cmd_id, payload):
        """Process binary command and return response (status, data)"""
        try:
            if cmd_id == CMD_FILL:
                return self._handle_fill(payload)
            elif cmd_id == CMD_PIXEL:
                return self._handle_pixel(payload)
            elif cmd_id == CMD_FILL_RECT:
                return self._handle_fill_rect(payload)
            elif cmd_id == CMD_LINE:
                return self._handle_line(payload)
            elif cmd_id == CMD_CIRCLE:
                return self._handle_circle(payload, filled=False)
            elif cmd_id == CMD_FILL_CIRCLE:
                return self._handle_circle(payload, filled=True)
            elif cmd_id == CMD_BLIT_BUFFER:
                return self._handle_blit_buffer(payload)
            elif cmd_id == CMD_GET_INPUTS:
                return self._handle_get_inputs()
            elif cmd_id == CMD_PIN_VALUE:
                return self._handle_pin_value(payload)
            elif cmd_id == CMD_POLL_INTERRUPTS:
                return self._handle_poll_interrupts()
            elif cmd_id == CMD_NEOPIXEL_WRITE:
                return self._handle_neopixel_write(payload)
            else:
                return (1, None)  # Unknown command
        except Exception as e:
            if self.gui.logger:
                self.gui.logger.log_error(f'Binary command error: {e}')
            return (1, None)
    
    def _handle_fill(self, payload):
        """Fill display with color"""
        display, color = struct.unpack('<BH', payload)
        self.screens[display - 1].fill(self.rgb565_to_rgb(color))
        return (0, None)
    
    def _handle_pixel(self, payload):
        """Set individual pixel"""
        display, x, y, color = struct.unpack('<BhhH', payload)
        self.screens[display - 1].set_at((x, y), self.rgb565_to_rgb(color))
        return (0, None)
    
    def _handle_fill_rect(self, payload):
        """Fill rectangle"""
        display, x, y, w, h, color = struct.unpack('<BhhhhH', payload)
        pygame.draw.rect(
            self.screens[display - 1],
            self.rgb565_to_rgb(color),
            pygame.Rect(x, y, w, h)
        )
        return (0, None)
    
    def _handle_line(self, payload):
        """Draw line"""
        display, x0, y0, x1, y1, color = struct.unpack('<BhhhhH', payload)
        pygame.draw.line(
            self.screens[display - 1],
            self.rgb565_to_rgb(color),
            (x0, y0),
            (x1, y1)
        )
        return (0, None)
    
    def _handle_circle(self, payload, filled=False):
        """Draw circle (filled or outline)"""
        display, x, y, r, color = struct.unpack('<BhhhH', payload)
        pygame.draw.circle(
            self.screens[display - 1],
            self.rgb565_to_rgb(color),
            (x, y),
            r,
            draw_top_left=True,
            width=0 if filled else 1
        )
        return (0, None)
    
    def _handle_blit_buffer(self, payload):
        """Blit RGB565 buffer to display - OPTIMIZED"""
        # Parse header
        header_size = struct.calcsize('<BhhHH')
        display, x, y, width, height = struct.unpack('<BhhHH', payload[:header_size])
        buffer_data = payload[header_size:]
        
        # Expected buffer size
        expected_size = width * height * 2  # RGB565 = 2 bytes per pixel
        if len(buffer_data) != expected_size:
            if self.gui.logger:
                self.gui.logger.log_error(
                    f'Buffer size mismatch: got {len(buffer_data)}, expected {expected_size}'
                )
            return (1, None)
        
        # Convert RGB565 buffer to RGB888 - optimized with list comprehension
        pixels = []
        for i in range(0, len(buffer_data), 2):
            rgb565 = buffer_data[i] | (buffer_data[i+1] << 8)
            rgb888 = self.rgb565_to_rgb(rgb565)
            pixels.extend(rgb888)
        
        # Create surface and blit
        try:
            img_surface = pygame.image.frombuffer(
                bytes(pixels),
                (width, height),
                'RGB'
            )
            self.screens[display - 1].blit(img_surface, (x, y))
        except Exception as e:
            if self.gui.logger:
                self.gui.logger.log_error(f'Failed to blit buffer: {e}')
            return (1, None)
        
        return (0, None)
    
    def _handle_get_inputs(self):
        """Get button input state"""
        inputs = self.gui.get_inputs(self.gui.button_states)
        return (0, struct.pack('<H', inputs))
    
    def _handle_pin_value(self, payload):
        """Read GPIO pin value"""
        pin_num = struct.unpack('<B', payload)[0]
        if pin_num == 0:
    
    def _handle_poll_interrupts(self):
        """Poll for pending interrupts"""
        import json
        interrupts = self.gui.interrupt_queue.copy()
        self.gui.interrupt_queue.clear()
        if interrupts and self.gui.logger:
            self.gui.logger.log_info(f'Returning {len(interrupts)} pending interrupt(s)')
        # Return as JSON encoded bytes
        return (0, json.dumps(interrupts).encode('utf-8'))
    
    def _handle_neopixel_write(self, payload):
        """Handle neopixel LED writes"""
        # Payload is 7 LEDs * 3 bytes (GRB) = 21 bytes
        leds_grb = []
        for i in range(0, min(len(payload), 21), 3):
            if i + 2 < len(payload):
                g, r, b = struct.unpack('BBB', payload[i:i+3])
                leds_grb.append((g, r, b))
        # Convert from GRB to RGB for rendering
        self.gui.leds = [(r, b, g) for g, r, b in leds_grb]
        return (0, None)
            value = 0 if self.gui.button_states[0] > 0 else 1
        else:
            value = 1
        return (0, struct.pack('<B', value))
