import pygame
import pygame_gui
import os
import numpy as np
from PIL import Image
import random

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

class GUIEnhanced:
    def __init__(self, config=None, logger=None):
        # Store config and logger
        self.config = config or {}
        self.logger = logger
        
        # Get GUI config
        gui_config = self.config.get('gui', {})
        window_title = gui_config.get('window_title', 'BSides FW 2025 Badge Simulator')
        self.show_fps = gui_config.get('show_fps', False)
        self.target_fps = gui_config.get('target_fps', 60)
        
        # Initialize pygame display with extra space for controls
        self.control_panel_width = 300
        self.display = pygame.display.set_mode((560 + self.control_panel_width, 1060))
        pygame.display.set_caption(window_title)
        
        # Initialize pygame_gui manager
        self.ui_manager = pygame_gui.UIManager((560 + self.control_panel_width, 1060))
        
        self.board_texture = pygame.image.load('board_render.png')
        self.running = True
        self.screen1 = pygame.Surface((240, 240))
        self.screen2 = pygame.Surface((240, 240))
        
        # Track button states: 0 = not pressed, >0 = timestamp when pressed
        self.button_states = [0, 0, 0, 0, 0, 0, 0, 0]
        
        # Map keyboard keys to button indices
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
        
        # V3 hardware PCA9535 button mapping
        self.iox_button_map = [
            1 << 10, # Button 1: SW1
            1 << 9,  # Button 2: SW2
            1 << 8,  # Button 3: SW3
            1 << 0,  # Button 4: SW4
            1 << 1,  # Button 5: SW7
            1 << 2,  # Button 6: SW8
            1 << 3,  # Button 7: SW9
        ]
        
        # LED state (7 RGB LEDs on badge)
        self.leds = [(0, 0, 0)] * 7
        self.show_leds = gui_config.get('show_led_positions', True)
        
        # FPS tracking
        self.clock = pygame.time.Clock()
        self.frame_count = 0
        self.fps_display_font = pygame.font.Font(None, 24)
        
        # Hardware mock state
        self.accel_data = [0.0, 0.0, 1.0]  # Default: 1g on Z-axis
        self.shake_magnitude = 2.0  # Default shake intensity
        self.adc_voltage = 4.2  # Default battery voltage (fully charged)
        self.resistor_r1 = 100.0  # Top resistor in divider (kΩ)
        self.resistor_r2 = 47.0   # Bottom resistor in divider (kΩ)
        self.wifi_state = 'disconnected'
        self.bluetooth_state = 'disabled'
        self.charge_state = 'not_charging'
        
        # Queue for pending interrupts (pin_num, edge_type)
        self.interrupt_queue = []
        
        # Create UI controls
        self._create_ui_controls()
    
    def _create_ui_controls(self):
        """Create the control panel UI elements"""
        panel_x = 570  # Right side of badge display
        y_offset = 20
        spacing = 10
        
        # Title
        self.title_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 30),
            text='Hardware Controls',
            manager=self.ui_manager
        )
        y_offset += 40
        
        # === Accelerometer Section ===
        self.accel_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            text='Accelerometer',
            manager=self.ui_manager
        )
        y_offset += 30
        
        # Shake button
        self.shake_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 35),
            text='Shake Device',
            manager=self.ui_manager
        )
        y_offset += 40
        
        # Shake magnitude slider
        self.shake_mag_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 200, 25),
            text=f'Shake Magnitude: {self.shake_magnitude:.1f}g',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.shake_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            start_value=self.shake_magnitude,
            value_range=(0.5, 8.0),
            manager=self.ui_manager
        )
        y_offset += 35
        
        # Accel X/Y/Z display
        self.accel_display_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 20),
            text=f'X: {self.accel_data[0]:.2f}g Y: {self.accel_data[1]:.2f}g Z: {self.accel_data[2]:.2f}g',
            manager=self.ui_manager
        )
        y_offset += 30
        
        # === Power/ADC Section ===
        self.power_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            text='Power & Battery',
            manager=self.ui_manager
        )
        y_offset += 30
        
        # ADC voltage slider
        self.adc_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 200, 25),
            text=f'Battery Voltage: {self.adc_voltage:.2f}V',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.adc_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            start_value=self.adc_voltage,
            value_range=(2.9, 4.5),
            manager=self.ui_manager
        )
        y_offset += 35
        
        # Resistor divider R1 (top resistor)
        self.r1_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 200, 25),
            text=f'R1 (top): {self.resistor_r1:.1f}kΩ',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.r1_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            start_value=self.resistor_r1,
            value_range=(10.0, 200.0),
            manager=self.ui_manager
        )
        y_offset += 35
        
        # Resistor divider R2 (bottom resistor)
        self.r2_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 200, 25),
            text=f'R2 (bottom): {self.resistor_r2:.1f}kΩ',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.r2_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            start_value=self.resistor_r2,
            value_range=(10.0, 200.0),
            manager=self.ui_manager
        )
        y_offset += 35
        
        # Divided voltage display (what ADC actually sees)
        self.divided_voltage_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 20),
            text=f'ADC sees: {self._calculate_divided_voltage():.0f}mV',
            manager=self.ui_manager
        )
        y_offset += 30
        
        # Charge state dropdown
        self.charge_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 200, 25),
            text='Charge State:',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.charge_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=['not_charging', 'charging', 'charged', 'error'],
            starting_option='not_charging',
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 35),
            manager=self.ui_manager
        )
        y_offset += 45
        
        # === WiFi Section ===
        self.wifi_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            text='WiFi',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.wifi_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=['disconnected', 'connecting', 'connected', 'passthrough', 'ap_mode'],
            starting_option='disconnected',
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 35),
            manager=self.ui_manager
        )
        y_offset += 45
        
        # === Bluetooth Section ===
        self.bluetooth_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 25),
            text='Bluetooth',
            manager=self.ui_manager
        )
        y_offset += 30
        
        self.bluetooth_dropdown = pygame_gui.elements.UIDropDownMenu(
            options_list=['disabled', 'advertising', 'connected', 'system_passthrough'],
            starting_option='disabled',
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 35),
            manager=self.ui_manager
        )
        y_offset += 45
        
        # === Info Section ===
        self.info_label = pygame_gui.elements.UITextBox(
            html_text='<font size=2>Press 0-4, 7-9 for buttons<br>Adjust sliders to mock hardware values</font>',
            relative_rect=pygame.Rect(panel_x, y_offset, 280, 80),
            manager=self.ui_manager
        )
    
    def _calculate_divided_voltage(self):
        """Calculate the voltage after resistor divider (what ADC actually sees)"""
        # Voltage divider formula: Vout = Vin * R2 / (R1 + R2)
        battery_voltage_mV = self.adc_voltage * 1000  # Convert V to mV
        divided_voltage_mV = battery_voltage_mV * self.resistor_r2 / (self.resistor_r1 + self.resistor_r2)
        return divided_voltage_mV
    
    def _apply_shake(self):
        """Apply shake effect to accelerometer"""
        # Generate random acceleration values with specified magnitude
        self.accel_data = [
            random.uniform(-self.shake_magnitude, self.shake_magnitude),
            random.uniform(-self.shake_magnitude, self.shake_magnitude),
            random.uniform(-self.shake_magnitude, self.shake_magnitude)
        ]
        if self.logger:
            self.logger.log_info(f'Shake applied: X={self.accel_data[0]:.2f}g Y={self.accel_data[1]:.2f}g Z={self.accel_data[2]:.2f}g')
        
        # Queue motion interrupt on pin 34 (LIS3DH INT2 pin)
        self.interrupt_queue.append({'pin': 34, 'edge': 'rising'})
        if self.logger:
            self.logger.log_info('Motion interrupt queued for pin 34')
    
    def _decay_shake(self):
        """Gradually return accelerometer to rest state (0, 0, 1g)"""
        decay_rate = 0.1
        self.accel_data[0] *= (1 - decay_rate)
        self.accel_data[1] *= (1 - decay_rate)
        self.accel_data[2] = self.accel_data[2] * (1 - decay_rate) + 1.0 * decay_rate
    
    def rgb565_to_rgb(self, color):
        r = (color & 0xF800) >> 8
        g = (color & 0x07E0) >> 3
        b = (color & 0x001F) << 3
        return (r, g, b)

    def handle_command(self, command):
        screens = [self.screen1, self.screen2]
        if command['module'] == 'gc9a01':
            if command['command'] == 'fill':
                screens[command['parameters']['display']-1].fill(self.rgb565_to_rgb(command['parameters']['color']))
            elif command['command'] == 'pixel':
                screens[command['parameters']['display']-1].set_at(
                    (command['parameters']['x'], command['parameters']['y']),
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
                    (command['parameters']['x0'], command['parameters']['y0']),
                    (command['parameters']['x1'], command['parameters']['y1'])
                )
            elif command['command'] == 'write':
                if command['parameters']['font'] == 'fonts.arial32px':
                    font = pygame.font.Font('arial.ttf', 32)
                elif command['parameters']['font'] == 'fonts.arial16px':
                    font = pygame.font.Font('arial.ttf', 16)

                text_surface = font.render(
                    command['parameters']['string'],
                    True,
                    self.rgb565_to_rgb(command['parameters']['fg_color']),
                    self.rgb565_to_rgb(command['parameters']['bg_color'])
                )
                screens[command['parameters']['display']-1].blit(
                    text_surface,
                    (command['parameters']['x'], command['parameters']['y'])
                )
            elif command['command'] == 'text':
                try:
                    text_image = get_vga_text(command['parameters']['font'], command['parameters']['string'])
                    raw_str = text_image.tobytes("raw", 'RGBA')
                    text = pygame.image.fromstring(raw_str, text_image.size, 'RGBA')
                    screens[command['parameters']['display']-1].blit(
                        text,
                        (command['parameters']['x'], command['parameters']['y'])
                    )
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(f'Error rendering text: {e}')
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
                    (command['parameters']['x'], command['parameters']['y'])
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
                pixels = []
                for i in range(0, len(buffer_data), 2):
                    rgb565 = buffer_data[i] | (buffer_data[i+1] << 8)
                    rgb888 = self.rgb565_to_rgb(rgb565)
                    pixels.extend(rgb888)
                
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
                return self.get_inputs(self.button_states)
        elif command['module'] == 'pin':
            if command['command'] == 'value':
                pin_num = command['parameters']['pin']
                if pin_num == 0:
                    return 0 if self.button_states[0] > 0 else 1
                return 1
            elif command['command'] == 'poll_interrupts':
                # Return and clear all pending interrupts
                interrupts = self.interrupt_queue.copy()
                self.interrupt_queue.clear()
                if interrupts and self.logger:
                    self.logger.log_info(f'Returning {len(interrupts)} pending interrupt(s)')
                return interrupts
        elif command['module'] == 'neopixel':
            if command['command'] == 'write':
                leds_grb = command['parameters']['leds'][:7]
                self.leds = [(r, b, g) for g, r, b in leds_grb]
        elif command['module'] == 'lis3dh':
            # Mock accelerometer data
            if command['command'] == 'acceleration' or command['command'] == 'get_acceleration':
                # Return current accel data
                return {
                    'x': self.accel_data[0],
                    'y': self.accel_data[1],
                    'z': self.accel_data[2]
                }
        elif command['module'] == 'adc':
            # Mock ADC readings (battery voltage, etc)
            if command['command'] == 'read' or command['command'] == 'get_voltage':
                divided_voltage = self._calculate_divided_voltage()
                return divided_voltage  # Return in mV

    def get_inputs(self, input_list):
        """Calculate PCA9535 input register value based on button states"""
        input_number = 0xFFFF
        
        for button_index in range(1, len(input_list)):
            button_time = input_list[button_index]
            if button_time > 0:
                iox_index = button_index - 1
                if iox_index < len(self.iox_button_map):
                    input_number &= ~self.iox_button_map[iox_index]
        
        return input_number

    def render_leds(self):
        """Render LED strip with glow effects"""
        if not self.show_leds:
            return
        
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
                
                if r == 0 and g == 0 and b == 0:
                    pygame.draw.circle(self.display, (255, 255, 255), (x, y), radius, width=1)
                    continue
                
                glow_surface = pygame.Surface((40, 40), pygame.SRCALPHA)
                pygame.draw.circle(glow_surface, (r//4, g//4, b//4, 80), (20, 20), 20)
                self.display.blit(glow_surface, (x-20, y-20), special_flags=pygame.BLEND_RGBA_ADD)
                
                glow_surface2 = pygame.Surface((24, 24), pygame.SRCALPHA)
                pygame.draw.circle(glow_surface2, (r//2, g//2, b//2, 120), (12, 12), radius)
                self.display.blit(glow_surface2, (x-12, y-12), special_flags=pygame.BLEND_RGBA_ADD)
                
                pygame.draw.circle(self.display, (r, g, b), (x, y), radius)
                
                pygame.draw.circle(self.display, 
                                 (min(255, r+100), min(255, g+100), min(255, b+100)), 
                                 (x-2, y-2), 3)
    
    def generate_circular_cutout(self, surface):
        circle_mask = pygame.Surface((240, 240), pygame.SRCALPHA)
        circle_mask.fill((0, 0, 0, 0))
        pygame.draw.circle(
            circle_mask, 
            (255, 255, 255, 255),
            (120, 120),
            120
        )

        circular_cutout = pygame.Surface((240, 240), pygame.SRCALPHA)
        circular_cutout.fill((0, 0, 0, 0))
        circular_cutout.blit(surface, (0, 0), area=pygame.Rect(0, 0, 240, 240))
        circular_cutout.blit(circle_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

        return circular_cutout

    def gameloop(self):
        while self.running:
            time_delta = self.clock.tick(self.target_fps) / 1000.0
            current_time = pygame.time.get_ticks()
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    button_idx = self.key_to_button.get(event.key)
                    if button_idx is not None and self.button_states[button_idx] == 0:
                        self.button_states[button_idx] = current_time
                        if self.logger:
                            self.logger.log_info(f'Button {button_idx} pressed (key {event.key})')
                elif event.type == pygame.KEYUP:
                    button_idx = self.key_to_button.get(event.key)
                    if button_idx is not None and self.button_states[button_idx] > 0:
                        held_duration = current_time - self.button_states[button_idx]
                        self.button_states[button_idx] = 0
                        if self.logger:
                            self.logger.log_info(f'Button {button_idx} released after {held_duration}ms')
                elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == self.shake_button:
                        self._apply_shake()
                elif event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                    if event.ui_element == self.shake_slider:
                        self.shake_magnitude = event.value
                        self.shake_mag_label.set_text(f'Shake Magnitude: {self.shake_magnitude:.1f}g')
                    elif event.ui_element == self.adc_slider:
                        self.adc_voltage = event.value
                        self.adc_label.set_text(f'Battery Voltage: {self.adc_voltage:.2f}V')
                        self.divided_voltage_label.set_text(f'ADC sees: {self._calculate_divided_voltage():.0f}mV')
                    elif event.ui_element == self.r1_slider:
                        self.resistor_r1 = event.value
                        self.r1_label.set_text(f'R1 (top): {self.resistor_r1:.1f}kΩ')
                        self.divided_voltage_label.set_text(f'ADC sees: {self._calculate_divided_voltage():.0f}mV')
                    elif event.ui_element == self.r2_slider:
                        self.resistor_r2 = event.value
                        self.r2_label.set_text(f'R2 (bottom): {self.resistor_r2:.1f}kΩ')
                        self.divided_voltage_label.set_text(f'ADC sees: {self._calculate_divided_voltage():.0f}mV')
                elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                    if event.ui_element == self.charge_dropdown:
                        self.charge_state = event.text
                        if self.logger:
                            self.logger.log_info(f'Charge state changed to: {self.charge_state}')
                    elif event.ui_element == self.wifi_dropdown:
                        self.wifi_state = event.text
                        if self.logger:
                            self.logger.log_info(f'WiFi state changed to: {self.wifi_state}')
                    elif event.ui_element == self.bluetooth_dropdown:
                        self.bluetooth_state = event.text
                        if self.logger:
                            self.logger.log_info(f'Bluetooth state changed to: {self.bluetooth_state}')
                
                self.ui_manager.process_events(event)
            
            # Update accelerometer decay
            self._decay_shake()
            
            # Update accel display
            self.accel_display_label.set_text(
                f'X: {self.accel_data[0]:.2f}g Y: {self.accel_data[1]:.2f}g Z: {self.accel_data[2]:.2f}g'
            )
            
            # Update UI
            self.ui_manager.update(time_delta)
            
            # Render
            self.display.fill((30, 30, 30))  # Dark background
            self.display.blit(self.board_texture, (0, 0))
            self.render_leds()
            self.display.blit(self.generate_circular_cutout(self.screen1), (70, 558))
            self.display.blit(self.generate_circular_cutout(self.screen2), (234, 774))
            
            # Draw UI
            self.ui_manager.draw_ui(self.display)
            
            # Show FPS if enabled
            if self.show_fps:
                fps = self.clock.get_fps()
                fps_text = self.fps_display_font.render(f'FPS: {fps:.1f}', True, (255, 255, 0))
                self.display.blit(fps_text, (10, 10))
            
            pygame.display.update()
            self.frame_count += 1
