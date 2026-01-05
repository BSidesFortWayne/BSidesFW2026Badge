import pygame
import os
import numpy as np
from PIL import Image

pygame.init()

fonts = {
    'vga1_bold_16x32': {'image': Image.open('fonts/vga1_bold_16x32.png'), 'width': 16, 'height': 32},
    'vga2_8x16': {'image': Image.open('fonts/vga2_8x16.png'), 'width': 8, 'height': 16},
    'vga2_bold_16x32': {'image': Image.open('fonts/vga2_bold_16x32.png'), 'width': 16, 'height': 32}
}

def get_vga_text(font, string):
    width = fonts[font]['width']
    height = fonts[font]['height']
    map_image = fonts[font]['image']
    character_images = []
    for character in string:
        x = ord(character) * width
        y = 0
        character_images.append(map_image.crop((x, y, x + width, y + height)))
    total_width = width*len(string)
    image = Image.new('RGB', (total_width, height))
    x = 0
    for character_image in character_images:
        image.paste(character_image, (x, 0))
        x += width
    return image

class GUI:
    def __init__(self, config=None, logger=None):
        # Store config and logger
        self.config = config or {}
        self.logger = logger
        
        # Get GUI config
        gui_config = self.config.get('gui', {})
        window_title = gui_config.get('window_title', 'BSides FW 2025 Badge Simulator')
        self.show_fps = gui_config.get('show_fps', False)
        self.target_fps = gui_config.get('target_fps', 60)
        
        # Initialize pygame display
        self.display = pygame.display.set_mode((560, 1060))
        pygame.display.set_caption(window_title)
        
        self.board_texture = pygame.image.load('board_render.png')
        self.running = True
        self.screen1 = pygame.Surface((240, 240))
        self.screen2 = pygame.Surface((240, 240))
        # Track button states: 0 = not pressed, >0 = timestamp when pressed
        # Button mapping for V3 hardware:
        # 0: GPIO pin 0 (boot/SW5 - can be mapped to reset)
        # 1: SW1 (top button 1)
        # 2: SW2 (top button 2) 
        # 3: SW3 (top button 3)
        # 4: SW4 (top button 4)
        # 5: SW7 (game button 1)
        # 6: SW8 (game button 2)
        # 7: SW9 (game button 3)
        self.button_states = [0, 0, 0, 0, 0, 0, 0, 0]
        # Map keyboard keys to button indices
        # 0=boot, 1-4=SW1-4 (top), 5-7=SW7-9 (game buttons)
        self.key_to_button = {
            pygame.K_0: 0,  # Boot/Reset button (SW5)
            pygame.K_1: 1,  # SW1 (top)
            pygame.K_2: 2,  # SW2 (top)
            pygame.K_3: 3,  # SW3 (top)
            pygame.K_4: 4,  # SW4 (top)
            pygame.K_7: 5,  # SW7 (game button 1)
            pygame.K_8: 6,  # SW8 (game button 2)
            pygame.K_9: 7,  # SW9 (game button 3)
        }
        # V3 hardware PCA9535 button mapping (matches buttons.py v3_init)
        # Index 0 is GPIO button, indices 1-7 are PCA9535 buttons
        self.iox_button_map = [
            1 << 10, # Button 1: SW1 (0000 0100 0000 0000)
            1 << 9,  # Button 2: SW2 (0000 0010 0000 0000)
            1 << 8,  # Button 3: SW3 (0000 0001 0000 0000)
            1 << 0,  # Button 4: SW4 (0000 0000 0000 0001)
            1 << 1,  # Button 5: SW7 (0000 0000 0000 0010)
            1 << 2,  # Button 6: SW8 (0000 0000 0000 0100)
            1 << 3,  # Button 7: SW9 (0000 0000 0000 1000)
        ]
        
        # LED state (7 RGB LEDs on badge)
        self.leds = [(0, 0, 0)] * 7
        self.show_leds = gui_config.get('show_led_positions', True)
        
        # FPS tracking
        self.clock = pygame.time.Clock()
        self.frame_count = 0
        self.fps_display_font = pygame.font.Font(None, 24)
        
        # Queue for pending interrupts (pin_num, edge_type)
        self.interrupt_queue = []
    
    def rgb565_to_rgb(self, color):
        r = (color & 0xF800) >> 8
        g = (color & 0x07E0) >> 3
        b = (color & 0x001F) << 3
        return (r, g, b)

    def handle_command(self, command):
        screens = [self.screen1, self.screen2]
        if command['module'] == 'gc9a01':
            if command['command'] == 'fill':
                print(f"[GUI] fill command received: color={command['parameters']['color']}, display={command['parameters']['display']}")
                screens[command['parameters']['display']-1].fill(self.rgb565_to_rgb(command['parameters']['color']))
            elif command['command'] == 'pixel':
                screens[command['parameters']['display']-1].set_at(
                    (
                        (command['parameters']['x']),
                        (command['parameters']['y'])
                    ),
                    self.rgb565_to_rgb(command['parameters']['color'])
                )
            elif command['command'] == 'circle':
                pygame.draw.circle(
                    screens[command['parameters']['display']-1],
                    self.rgb565_to_rgb(command['parameters']['color']),
                    (command['parameters']['x'], command['parameters']['y']),
                    command['parameters']['r'],
                    draw_top_left=True,
                    width=1
                )
            elif command['command'] == 'fill_circle':
                pygame.draw.circle(
                    screens[command['parameters']['display']-1],
                    self.rgb565_to_rgb(command['parameters']['color']),
                    (command['parameters']['x'], command['parameters']['y']),
                    command['parameters']['r'],
                    draw_top_left=True
                )
            elif command['command'] == 'fill_rect':
                pygame.draw.rect(
                    screens[command['parameters']['display']-1],
                    self.rgb565_to_rgb(command['parameters']['color']),
                    pygame.Rect(
                        command['parameters']['x'],
                        command['parameters']['y'],
                        command['parameters']['w'],
                        command['parameters']['h']
                    )
                )
            elif command['command'] == 'line':
                pygame.draw.line(
                    screens[command['parameters']['display']-1],
                    self.rgb565_to_rgb(command['parameters']['color']),
                    (
                        command['parameters']['x0'],
                        command['parameters']['y0'],
                    ),
                    (
                        command['parameters']['x1'],
                        command['parameters']['y1'],
                    )
                )
            elif command['command'] == 'write':
                if command['parameters']['font'] == 'fonts.arial32px':
                    font = pygame.font.Font('arial.ttf', 32)
                elif command['parameters']['font'] == 'fonts.arial16px':
                    font = pygame.font.Font('arial.ttf', 16)

                # Render the text into an image
                text_surface = font.render(
                    command['parameters']['string'],
                    True,
                    self.rgb565_to_rgb(command['parameters']['fg_color']),
                    self.rgb565_to_rgb(command['parameters']['bg_color'])
                )
                screens[command['parameters']['display']-1].blit(
                    text_surface,
                    (
                        command['parameters']['x'],
                        command['parameters']['y']
                    )
                )
            elif command['command'] == 'text':
                print(f"[GUI] text command received: font={command['parameters']['font']}, string={command['parameters']['string']}, display={command['parameters']['display']}")
                try:
                    text_image = get_vga_text(command['parameters']['font'], command['parameters']['string'])
                    raw_str = text_image.tobytes("raw", 'RGBA')
                    text = pygame.image.fromstring(raw_str, text_image.size, 'RGBA')
                    screens[command['parameters']['display']-1].blit(
                        text,
                        (
                            command['parameters']['x'],
                            command['parameters']['y']
                        )
                    )
                    print(f"[GUI] text rendered successfully")
                except Exception as e:
                    print(f"[GUI] ERROR rendering text: {e}")
                    import traceback
                    traceback.print_exc()
            elif command['command'] == 'write_len':
                if command['parameters']['font'] == 'fonts.arial32px':
                    font = pygame.font.Font('arial.ttf', 32)
                elif command['parameters']['font'] == 'fonts.arial16px':
                    font = pygame.font.Font('arial.ttf', 16)
                
                text_surface = font.render(
                    command['parameters']['string'],
                    True,
                    (255, 255, 255)
                )

                return text_surface.get_width()
            elif command['command'] == 'jpg':
                img = pygame.image.load(
                    os.path.join('src', command['parameters']['filename'])
                )
                screens[command['parameters']['display']-1].blit(
                    img,
                    (
                        command['parameters']['x'],
                        command['parameters']['y']
                    )
                )
            elif command['command'] == 'blit_buffer':
                # Handle framebuffer blit - buffer is in RGB565 format
                params = command['parameters']
                buffer_data = bytes(params['buffer'])
                width = params['width']
                height = params['height']
                x = params['x']
                y = params['y']
                
                # Convert RGB565 buffer to RGB888 for pygame
                # RGB565: 16 bits per pixel (2 bytes)
                pixels = []
                for i in range(0, len(buffer_data), 2):
                    # Read 16-bit RGB565 value (little endian)
                    rgb565 = buffer_data[i] | (buffer_data[i+1] << 8)
                    rgb888 = self.rgb565_to_rgb(rgb565)
                    pixels.extend(rgb888)
                
                # Create surface from pixel data
                if len(pixels) == width * height * 3:
                    try:
                        img_surface = pygame.image.frombuffer(
                            bytes(pixels), 
                            (width, height), 
                            'RGB'
                        )
                        screens[params['display']-1].blit(img_surface, (x, y))
                    except Exception as e:
                        if self.logger:
                            self.logger.log_error(f'Failed to blit buffer: {e}')
        elif command['module'] == 'pca9535':
            if command['command'] == 'get_inputs':
                #print(self.button_states)
                #print(self.get_inputs(self.button_states))
                return self.get_inputs(self.button_states)
        elif command['module'] == 'pin':
            if command['command'] == 'value':
                # Handle GPIO pin reads (button 0 is GPIO pin 0)
                pin_num = command['parameters']['pin']
                if pin_num == 0:
                    # Return 1 if button 0 is NOT pressed (pull-up), 0 if pressed
                    return 0 if self.button_states[0] > 0 else 1
                return 1  # Default high for other pins
            elif command['command'] == 'poll_interrupts':
                # Return and clear all pending interrupts
                interrupts = self.interrupt_queue.copy()
                self.interrupt_queue.clear()
                if interrupts and self.logger:
                    self.logger.log_info(f'Returning {len(interrupts)} pending interrupt(s)')
                return interrupts
        elif command['module'] == 'neopixel':
            if command['command'] == 'write':
                # Update LED state from badge
                # NeoPixels use GRB format, but we need RGB for rendering
                # Convert from GRB to RGB: (G, R, B) -> (R, G, B)
                leds_grb = command['parameters']['leds'][:7]  # Ensure max 7 LEDs
                self.leds = [(r, b, g) for g, r, b in leds_grb]
                # if self.logger:
                #     self.logger.log_info(f'LEDs updated: {self.leds}')

    def get_inputs(self, input_list):
        """Calculate PCA9535 input register value based on button states.
        
        Returns a 16-bit value where buttons pressed = bit cleared (active low).
        Base value has all button bits set (no buttons pressed).
        Button 0 is GPIO (not in PCA9535), buttons 1-7 are PCA9535.
        """
        # Start with all bits set (no buttons pressed)
        # Bits used: 0,1,2,3,8,9,10 for buttons 1-7
        input_number = 0xFFFF
        
        # Skip button 0 (GPIO button), process buttons 1-7 (PCA9535)
        for button_index in range(1, len(input_list)):
            button_time = input_list[button_index]
            # Button is pressed if button_time > 0 (stores press timestamp)
            if button_time > 0:
                # Clear the bit for this button (active low)
                iox_index = button_index - 1  # Offset by 1 since button 0 is GPIO
                if iox_index < len(self.iox_button_map):
                    input_number &= ~self.iox_button_map[iox_index]
        
        return input_number

    def render_leds(self):
        """Render LED strip with glow effects"""
        if not self.show_leds:
            return
        
        # LED positions on the badge board (aligned with white spots on right edge)
        # These are positioned along the right edge of the badge
        led_x = 499
        led_y_start = 187
        led_y_delta = 108.7
        radius = 12
        led_positions = []
        for i in range(7):
            led_positions.append((led_x, led_y_start + i * led_y_delta))
        
        for i, (x, y) in enumerate(led_positions):
            if i < len(self.leds):
                r, g, b = self.leds[i]
                
                # Skip completely off LEDs
                if r == 0 and g == 0 and b == 0:
                    # Draw dim outline to show LED position
                    pygame.draw.circle(self.display, (255, 255, 255), (x, y), radius, width=1)
                    continue
                
                # Outer glow (larger, dimmer)
                glow_surface = pygame.Surface((40, 40), pygame.SRCALPHA)
                pygame.draw.circle(glow_surface, (r//4, g//4, b//4, 80), (20, 20), 20)
                self.display.blit(glow_surface, (x-20, y-20), special_flags=pygame.BLEND_RGBA_ADD)
                
                # Middle glow
                glow_surface2 = pygame.Surface((24, 24), pygame.SRCALPHA)
                pygame.draw.circle(glow_surface2, (r//2, g//2, b//2, 120), (12, 12), radius)
                self.display.blit(glow_surface2, (x-12, y-12), special_flags=pygame.BLEND_RGBA_ADD)
                
                # Core LED (bright)
                pygame.draw.circle(self.display, (r, g, b), (x, y), radius)
                
                # Highlight (makes it look shiny)
                pygame.draw.circle(self.display, 
                                 (min(255, r+100), min(255, g+100), min(255, b+100)), 
                                 (x-2, y-2), 3)
    
    def generate_circular_cutout(self, surface):
        circle_mask = pygame.Surface((240, 240), pygame.SRCALPHA)
        circle_mask.fill((0, 0, 0, 0))
        pygame.draw.circle(
            circle_mask, 
            (255, 255, 255, 255),
            (240 // 2, 240 // 2),
            240 // 2
        )

        circular_cutout = pygame.Surface((240, 240), pygame.SRCALPHA)
        circular_cutout.fill((0, 0, 0, 0))
        circular_cutout.blit(
            surface, 
            (0, 0), 
            area=pygame.Rect(0, 0, 240, 240)
        )

        circular_cutout.blit(circle_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

        return circular_cutout

    def gameloop(self):
        while self.running:
            # Handle events
            current_time = pygame.time.get_ticks()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    # Store timestamp when button pressed (allows long press detection)
                    button_idx = self.key_to_button.get(event.key)
                    if button_idx is not None and self.button_states[button_idx] == 0:
                        self.button_states[button_idx] = current_time
                        if self.logger:
                            self.logger.log_info(f'Button {button_idx} pressed (key {event.key})')
                elif event.type == pygame.KEYUP:
                    # Clear button state when released
                    button_idx = self.key_to_button.get(event.key)
                    if button_idx is not None and self.button_states[button_idx] > 0:
                        held_duration = current_time - self.button_states[button_idx]
                        self.button_states[button_idx] = 0
                        if self.logger:
                            self.logger.log_info(f'Button {button_idx} released after {held_duration}ms')
            
            # Render displays
            self.display.blit(self.board_texture, (0, 0))
            self.render_leds()  # Render LEDs before displays
            self.display.blit(self.generate_circular_cutout(self.screen1), (70, 558))
            self.display.blit(self.generate_circular_cutout(self.screen2), (234, 774))
            
            # Show FPS if enabled
            if self.show_fps:
                fps = self.clock.get_fps()
                fps_text = self.fps_display_font.render(f'FPS: {fps:.1f}', True, (255, 255, 0))
                self.display.blit(fps_text, (10, 10))
            
            pygame.display.update()
            
            # Limit frame rate
            self.clock.tick(self.target_fps)
            self.frame_count += 1
