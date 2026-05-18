import asyncio
import math
import time

import badgechal
from apps.app import BaseApp
from lib.flag_display import display_flag


BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0

GESTURE_TEXT = {
    "U": "^",
    "D": "v",
    "L": "<",
    "R": ">",
    "S": "*",
}


class App(BaseApp):
    name = "CTF Challenge 3"
    version = "0.1.0"

    def __init__(self, controller):
        super().__init__(controller)
        self.sequence = str(badgechal.combo_expected())
        self.progress = 0
        self.await_release = False
        self.running = True
        self.prev_accel = None
        self.last_shake_ms = 0

    def _render(self):
        displays = self.controller.bsp.displays
        d1 = displays.display1
        d2 = displays.display2

        d1.fill(BLACK)
        d2.fill(BLACK)

        pretty = "".join(GESTURE_TEXT.get(ch, "?") for ch in self.sequence)
        displays.display_center_text(pretty, fg=WHITE, bg=BLACK, display_index=1)
        displays.display_text("Do pattern in order", 16, 84, fg=WHITE, bg=BLACK, display_index=2)
        displays.display_text("A:{} of {}".format(self.progress, len(self.sequence)), 48, 116, fg=WHITE, bg=BLACK, display_index=2)

    def _show_led_progress(self):
        leds = self.controller.bsp.leds
        leds.turn_off_all()
        for i in range(self.progress):
            leds.set_led_color(i, (0, 20, 0))

    def _detect_gesture(self):
        imu = self.controller.bsp.imu
        accel = imu.acceleration
        ax, ay, az = accel[0], accel[1], accel[2]

        mag = math.sqrt((ax * ax) + (ay * ay) + (az * az))
        delta = 0.0
        if self.prev_accel is not None:
            px, py, pz = self.prev_accel
            delta = abs(ax - px) + abs(ay - py) + abs(az - pz)
        self.prev_accel = (ax, ay, az)

        now = time.ticks_ms()
        if (
            time.ticks_diff(now, self.last_shake_ms) > 400
            and delta > 10.0
            and abs(mag - 9.8) > 2.5
        ):
            self.last_shake_ms = now
            return "S"

        if ax < -7:
            return "U"
        if ax > 7:
            return "D"
        if ay < -7:
            return "L"
        if ay > 7:
            return "R"
        return None

    def _is_neutral(self):
        accel = self.controller.bsp.imu.acceleration
        ax, ay, az = accel[0], accel[1], accel[2]
        return abs(ax) < 3 and abs(ay) < 3 and abs(az - 9.8) < 4

    async def _wrong(self):
        leds = self.controller.bsp.leds
        for i in range(7):
            leds.set_led_color(i, (25, 0, 0))
        self.controller.bsp.displays.display1.fill(RED)
        self.controller.bsp.displays.display_center_text("RESET", fg=WHITE, bg=RED, display_index=1)
        await asyncio.sleep_ms(550)
        self.progress = 0
        self._show_led_progress()
        self._render()

    async def setup(self):
        self._render()
        self._show_led_progress()

        while self.running:
            gesture = self._detect_gesture()

            if self.await_release:
                if self._is_neutral():
                    self.await_release = False
                await asyncio.sleep_ms(60)
                continue

            if gesture is None:
                await asyncio.sleep_ms(60)
                continue

            self.await_release = True
            expected = self.sequence[self.progress]
            if gesture == expected:
                self.progress += 1
                self._show_led_progress()
                self._render()
            else:
                await self._wrong()
                await asyncio.sleep_ms(60)
                continue

            if self.progress >= len(self.sequence):
                passed, flag = badgechal.combo_check(self.sequence)
                if passed and flag:
                    self.controller.bsp.displays.display1.fill(GREEN)
                    self.controller.bsp.displays.display2.fill(GREEN)
                    self.controller.bsp.displays.display_center_text("UNLOCKED", fg=WHITE, bg=GREEN, display_index=1)
                    await asyncio.sleep_ms(800)
                    display_flag("C3 Combo Lock", flag, self.controller.bsp.displays)
                    self.controller.bsp.leds.turn_off_all()
                    return
                await self._wrong()

            await asyncio.sleep_ms(60)

    async def teardown(self):
        self.running = False
        self.controller.bsp.leds.turn_off_all()
