from apps.app import BaseApp
import framebuf
from lib.microfont import MicroFont
import gc9a01

class BatteryMonitor(BaseApp):
    name = "Battery Monitor"
    version = "0.0.3"
    def __init__(self, controller):
        super().__init__(controller)
        self.display1 = self.controller.bsp.displays.display1

        self.bg_color = gc9a01.WHITE
        self.fg_color = gc9a01.BLACK
        
        self.font = MicroFont("fonts/victor_R_24.mfnt", cache_index=True, cache_chars=True)

        self.controller.bsp.displays.display_center_text("Battery")

        self.display2_mem_buf = bytearray(240*240*2)
        self.display2_fbuf_mv = memoryview(self.display2_mem_buf)
        self.display2_fbuf = framebuf.FrameBuffer(
            self.display2_mem_buf, 
            240, 
            240, 
            framebuf.RGB565
        )

        self.center = self.display1.width() // 2

    def draw_voltage_meter(self):
        # Clear the framebuffer
        self.display2_fbuf.fill(gc9a01.BLACK)

        # Get battery values
        voltage_mv = self.controller.battery.mv_average.average()
        battery_pct = self.controller.battery.get_battery_percentage()
        
        print(f"Battery values: {voltage_mv}mV, {battery_pct}%")

        # Draw voltage text
        off_x, off_y = self.font.write(
            f'Voltage: {voltage_mv:.1f}mv',
            self.display2_fbuf_mv,
            framebuf.RGB565,
            240,
            240,
            5,
            120,
            gc9a01.WHITE
        )

        # Draw battery percentage text
        off_x, off_y = self.font.write(
            f'Battery: {battery_pct:.1f}%',
            self.display2_fbuf_mv,
            framebuf.RGB565,
            240,
            240,
            5,
            120 - off_y - 5,
            gc9a01.WHITE
        )

    async def update(self):
        self.draw_voltage_meter()
        # Draw battery icon on display1
        self.controller.battery.draw_battery(self.controller.bsp.displays.display1, (120-15, 240-60))
        # Blit the voltage meter to display2
        self.controller.bsp.displays.display2.blit_buffer(self.display2_fbuf_mv, 0, 0, 240, 240)

if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(BatteryMonitor, perf=True)