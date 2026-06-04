from apps.app import BaseApp
import random
import gc9a01
import vga1_bold_16x32
import asyncio

class App(BaseApp):
    name = "Lucky Number"
    def __init__(self, controller):
        super().__init__(controller)
        self.config.add("lucky_range", 10000)

    async def setup(self):
        print("[LuckyNumber] Setup called")
        await self.generate_lucky_number()

    async def generate_lucky_number(self):
        print("[LuckyNumber] Generating lucky number")
        displays = self.controller.bsp.displays
        
        lucky_range: int = self.config['lucky_range']
        lucky_num = random.randint(0, lucky_range)
        lucky_str = str(lucky_num)
        print(f"[LuckyNumber] Lucky number: {lucky_str}")
        
        print("[LuckyNumber] About to fill displays with black")
        displays.display1.fill(gc9a01.BLACK)
        print("[LuckyNumber] Display1 filled")
        await asyncio.sleep(0)  # Yield control
        
        displays.display2.fill(gc9a01.BLACK)
        print("[LuckyNumber] Display2 filled")
        await asyncio.sleep(0)  # Yield control
        
        # Try direct text call with explicit parameters
        print("[LuckyNumber] About to call display1.text")
        displays.display1.text(vga1_bold_16x32, lucky_str, 50, 100, gc9a01.WHITE, gc9a01.BLACK)
        
        print("[LuckyNumber] Done displaying")

    def button_press(self, button: int):
        print(f"[LuckyNumber] Button {button} pressed")
        import asyncio
        asyncio.create_task(self.generate_lucky_number())

