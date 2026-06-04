from apps.app import BaseApp
import framebuf
from lib.microfont import MicroFont
import gc9a01
from ui.theme import BG, FG, FONT_BODY, SAFE_X

class BatteryMonitor(BaseApp):
    name = "Battery Monitor"
    version = "0.0.4"
    def __init__(self, controller):
        super().__init__(controller)
        self.display1 = self.controller.bsp.displays.display1

        self.font = MicroFont(FONT_BODY, cache_index=True, cache_chars=True)

        self.controller.bsp.displays.display_center_text("Battery", fg=FG, bg=BG)

        self.display2_mem_buf = bytearray(240*240*2)
        self.display2_fbuf_mv = memoryview(self.display2_mem_buf)
        self.display2_fbuf = framebuf.FrameBuffer(
            self.display2_mem_buf,
            240,
            240,
            framebuf.RGB565
        )

        self.center = self.display1.width() // 2
        self._last_voltage = -1
        self._last_pct = -1

    def draw_voltage_meter(self, voltage_mv, battery_pct):
        self.display2_fbuf.fill(BG)

        off_x, off_y = self.font.write(
            f'Voltage: {voltage_mv:.1f}mv',
            self.display2_fbuf_mv,
            framebuf.RGB565,
            240,
            240,
            SAFE_X,
            120,
            FG
        )

        off_x, off_y = self.font.write(
            f'Battery: {battery_pct:.1f}%',
            self.display2_fbuf_mv,
            framebuf.RGB565,
            240,
            240,
            SAFE_X,
            120 - off_y - 5,
            FG
        )

    async def update(self):
        voltage_mv = self.controller.battery.mv_average.average()
        battery_pct = self.controller.battery.get_battery_percentage()

        if voltage_mv == self._last_voltage and battery_pct == self._last_pct:
            return

        self._last_voltage = voltage_mv
        self._last_pct = battery_pct

        self.draw_voltage_meter(voltage_mv, battery_pct)
        self.controller.battery.draw_battery(self.controller.bsp.displays.display1, (120-15, 240-60))
        self.controller.bsp.displays.display2.blit_buffer(self.display2_fbuf_mv, 0, 0, 240, 240)

if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(BatteryMonitor, perf=True)