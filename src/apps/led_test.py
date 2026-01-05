"""LED Test App - Demonstrates LED visualization in simulator"""
from apps.app import BaseApp
from machine import Pin
import neopixel
import asyncio
import fonts.arial16px as arial16px


class LEDTest(BaseApp):
    """Test app to visualize LEDs in the simulator"""
    name = "LED Test"
    
    def setup(self):
        self.leds = neopixel.NeoPixel(Pin(26), 7)
        self.mode = 0  # 0=rainbow, 1=pulse, 2=chase, 3=random
        self.frame = 0
        
        # Draw instructions
        display = self.controller.bsp.displays.display1
        display.fill(0x0000)  # Black
        display.write(arial16px, "LED Test", 70, 100, 0xFFFF, 0x0000)
        display.write(arial16px, "1: Rainbow", 70, 130, 0xFFFF, 0x0000)
        display.write(arial16px, "2: Pulse", 70, 150, 0xFFFF, 0x0000)
        display.write(arial16px, "3: Chase", 70, 170, 0xFFFF, 0x0000)
        display.write(arial16px, "4: Random", 70, 190, 0xFFFF, 0x0000)
        
        # Initial pattern
        self.rainbow_pattern()
    
    def rainbow_pattern(self):
        """Display a rainbow across all LEDs"""
        colors = [
            (255, 0, 0),     # Red
            (255, 127, 0),   # Orange
            (255, 255, 0),   # Yellow
            (0, 255, 0),     # Green
            (0, 0, 255),     # Blue
            (75, 0, 130),    # Indigo
            (148, 0, 211),   # Violet
        ]
        for i in range(7):
            self.leds[i] = colors[i]
        self.leds.write()
    
    def pulse_pattern(self):
        """Pulse all LEDs in sync"""
        import math
        brightness = int((math.sin(self.frame / 10) + 1) * 127.5)
        color = (brightness, 0, brightness)  # Purple
        for i in range(7):
            self.leds[i] = color
        self.leds.write()
    
    def chase_pattern(self):
        """Chase pattern - one LED at a time"""
        for i in range(7):
            if i == (self.frame // 5) % 7:
                self.leds[i] = (0, 255, 0)  # Green
            else:
                self.leds[i] = (0, 0, 0)    # Off
        self.leds.write()
    
    def random_pattern(self):
        """Random colors every few frames"""
        if self.frame % 20 == 0:
            import random
            for i in range(7):
                self.leds[i] = (
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255)
                )
            self.leds.write()
    
    async def update(self):
        self.frame += 1
        
        if self.mode == 0:
            # Rainbow is static, only update on mode change
            pass
        elif self.mode == 1:
            self.pulse_pattern()
        elif self.mode == 2:
            self.chase_pattern()
        elif self.mode == 3:
            self.random_pattern()
        
        await asyncio.sleep(0.05)
    
    def button_press(self, button: int):
        if button == 0:  # Button 1 - Rainbow
            self.mode = 0
            self.rainbow_pattern()
        elif button == 1:  # Button 2 - Pulse
            self.mode = 1
        elif button == 2:  # Button 3 - Chase
            self.mode = 2
        elif button == 3:  # Button 4 - Random
            self.mode = 3
    
    def teardown(self):
        # Turn off all LEDs
        for i in range(7):
            self.leds[i] = (0, 0, 0)
        self.leds.write()
