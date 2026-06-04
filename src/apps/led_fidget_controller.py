import time
import asyncio
from apps.app import BaseApp
from drivers.leds import wheel

class LEDFidgetController(BaseApp):
    name = "LED Fidget"

    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.leds = self.controller.bsp.leds
        self.buttons = self.controller.bsp.buttons
        self.mode = 0  # Start with the first mode
        self.mode_names = [
            "Strip Color Set",
            "Single LED Color Set",
            "Rainbow Cycle",
            "Bounce LEDs",
            "Random LEDs Lighting Up"
        ]

        self.controller.bsp.displays.display_center_text(
            f"Mode: {self.mode_names[self.mode]}",
        )

    def button_press(self, button: int):
        print(f"Button {button} pressed in LEDFidgetController")
        if button == 4:  # Button to change mode forward
            self.mode = (self.mode + 1) % len(self.mode_names)
            print(f"Mode changed to: {self.mode_names[self.mode]}")
        elif button == 5:  # Button to change mode backward
            self.mode = (self.mode - 1) % len(self.mode_names)
            print(f"Mode changed to: {self.mode_names[self.mode]}")
        elif button == 3: #Customize something?
            pass


        self.controller.bsp.displays.display_center_text(
            f"Mode: {self.mode_names[self.mode]}",
        )

    async def update(self):
        # Execute the current mode
        if self.mode == 0:
            self._strip_color_set()
        elif self.mode == 1:
            self._single_led_color_set()
        elif self.mode == 2:
            self._rainbow_cycle()
        elif self.mode == 3:
            self._bounce_leds()
        elif self.mode == 4:
            self._random_leds()

    def _strip_color_set(self):
        # Set all LEDs to a specific color
        color = (255, 0, 0)  # Red color
        for i in range(7):
            self.leds.set_led_color(i, color)

    def _single_led_color_set(self):
        # Set a single LED to a specific color, cycling through each LED
        color = (0, 255, 0)  # Green color
        for i in range(7):
            self.leds.turn_off_all()
            self.leds.set_led_color(i, color)
            time.sleep(0.5)

    def _rainbow_cycle(self):
        # Cycle through rainbow colors on all LEDs
        for j in range(255):
            for i in range(7):
                index_offset = (255 // 7) * i
                color = wheel((j + index_offset) & 255)
                self.leds.set_led_color(i, color)
            time.sleep(0.05)

    def _bounce_leds(self):
        # Bounce a color back and forth along the LED strip
        color = (0, 0, 255)  # Blue color
        direction = 1
        index = 0
        while True:
            self.leds.turn_off_all()
            self.leds.set_led_color(index, color)
            time.sleep(0.2)
            index += direction
            if index == 6 or index == 0:
                direction *= -1

    def _random_leds(self):
        # Randomly light up LEDs with random colors
        import random
        for _ in range(10):
            led_index = random.randint(0, 6)
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            self.leds.set_led_color(led_index, color)
            time.sleep(0.1)

    async def teardown(self):
        self.leds.turn_off_all()

if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(LEDFidgetController)
