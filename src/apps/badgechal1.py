import asyncio
import gc9a01

import badgechal
from apps.app import BaseApp
from lib.flag_display import display_flag


RED_BG = 0xF800
GREEN_BG = 0x07E0
BLACK_BG = 0x0000
WHITE_FG = 0xFFFF

F1_FAIL_TIMEOUT = -1
F1_FAIL_JUMP_START = -2


def _fill_both(displays, color):
    displays.display1.fill(color)
    displays.display2.fill(color)


class App(BaseApp):
    name = "CTF Challenge 1"
    version = "0.0.7"

    async def setup(self):
        displays = self.controller.bsp.displays
        leds = self.controller.bsp.leds

        _fill_both(displays, BLACK_BG)
        displays.display_center_text("F1 Start", fg=WHITE_FG, bg=BLACK_BG, display_index=1)
        displays.display_center_text("Press SEL", fg=WHITE_FG, bg=BLACK_BG, display_index=2)
        await asyncio.sleep_ms(1200)

        while True:
            _fill_both(displays, BLACK_BG)
            displays.display_center_text("Watch LEDs", fg=WHITE_FG, bg=BLACK_BG, display_index=1)
            displays.display_center_text("Press at GO", fg=WHITE_FG, bg=BLACK_BG, display_index=2)
            await asyncio.sleep_ms(400)

            passed, elapsed_us = badgechal.f1_start(leds, displays)
            elapsed_ms = elapsed_us // 1000 if elapsed_us >= 0 else elapsed_us

            if passed:
                flag = badgechal.claim_flag(1)
                if flag is None:
                    reason = "VERIFY FAIL"
                    shown_ms = elapsed_ms
                    _fill_both(displays, RED_BG)
                    displays.display_center_text(reason, fg=WHITE_FG, bg=RED_BG, display_index=1)
                    displays.display_center_text("{} ms".format(shown_ms), fg=WHITE_FG, bg=RED_BG, display_index=2)
                    await asyncio.sleep_ms(1800)
                    continue
                _fill_both(displays, GREEN_BG)
                displays.display_center_text("WIN!", fg=WHITE_FG, bg=GREEN_BG, display_index=1)
                displays.display_center_text("{} ms".format(elapsed_ms), fg=WHITE_FG, bg=GREEN_BG, display_index=2)
                await asyncio.sleep_ms(2500)
                display_flag("F1 Start Light", flag, displays)
                return

            if elapsed_us == F1_FAIL_TIMEOUT:
                reason = "TIMEOUT"
                shown_ms = 0
            elif elapsed_us == F1_FAIL_JUMP_START:
                reason = "JUMP START"
                shown_ms = 0
            elif elapsed_us < 100_000:
                reason = "JUMP START"
                shown_ms = elapsed_ms
            else:
                reason = "TOO SLOW"
                shown_ms = elapsed_ms

            _fill_both(displays, RED_BG)
            displays.display_center_text(reason, fg=WHITE_FG, bg=RED_BG, display_index=1)
            if shown_ms > 0:
                displays.display_center_text("{} ms".format(shown_ms), fg=WHITE_FG, bg=RED_BG, display_index=2)
            else:
                displays.display_center_text("Restarting", fg=WHITE_FG, bg=RED_BG, display_index=2)
            await asyncio.sleep_ms(1800)
