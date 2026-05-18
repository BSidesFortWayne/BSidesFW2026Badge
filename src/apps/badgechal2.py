import asyncio
import gc9a01

import badgechal
from apps.app import BaseApp
from lib.flag_display import display_flag


BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0

CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class App(BaseApp):
    name = "CTF Challenge 2"
    version = "0.1.0"

    def __init__(self, controller):
        super().__init__(controller)
        self.bits = str(badgechal.pixel_cipher_bits()).split("|")
        self.length = len(self.bits)
        self.answer = ["A"] * self.length
        self.cursor = 0
        self.show_input = False
        self.status = ""

    def _render_bits(self):
        displays = self.controller.bsp.displays
        d1 = displays.display1
        d2 = displays.display2

        d1.fill(WHITE)

        cols = self.bits
        col_count = len(cols)
        gap = 2
        cell = min(14, max(6, (220 - (col_count - 1) * gap) // col_count))
        width = col_count * cell + (col_count - 1) * gap
        height = 7 * cell + 6 * gap
        sx = (240 - width) // 2
        sy = (240 - height) // 2

        for x, col in enumerate(cols):
            for y, bit in enumerate(col):
                if bit == "1":
                    px = sx + x * (cell + gap)
                    py = sy + y * (cell + gap)
                    d1.fill_rect(px, py, cell, cell, BLACK)

        d2.fill(BLACK)
        displays.display_center_text("A:Edit", fg=WHITE, bg=BLACK, display_index=2)
        displays.display_text("SEL:Enter", 48, 128, fg=WHITE, bg=BLACK, display_index=2)

    def _render_input(self):
        displays = self.controller.bsp.displays
        d1 = displays.display1
        d2 = displays.display2

        d1.fill(BLACK)

        top = "".join(self.answer[:8])
        bot = "".join(self.answer[8:])
        displays.display_text(top, 40, 78, fg=WHITE, bg=BLACK, display_index=1)
        displays.display_text(bot, 40, 118, fg=WHITE, bg=BLACK, display_index=1)

        cx = 40 + (self.cursor % 8) * 16
        cy = 72 if self.cursor < 8 else 112
        d1.fill_rect(cx, cy, 16, 2, gc9a01.YELLOW)
        d1.fill_rect(cx, cy + 34, 16, 2, gc9a01.YELLOW)

        d2.fill(BLACK)
        displays.display_text("L/R mv B- C+", 24, 84, fg=WHITE, bg=BLACK, display_index=2)
        displays.display_text("SEL/C+ D=OK", 32, 116, fg=WHITE, bg=BLACK, display_index=2)

    def _render(self):
        if self.show_input:
            self._render_input()
        else:
            self._render_bits()

    async def _flash_status(self, text, color):
        displays = self.controller.bsp.displays
        displays.display1.fill(color)
        displays.display2.fill(color)
        displays.display_center_text(text, fg=WHITE, bg=color, display_index=1)
        await asyncio.sleep_ms(900)
        self._render()

    async def _submit(self):
        candidate = "".join(self.answer)
        passed, flag = badgechal.pixel_cipher_check(candidate)
        if passed and flag:
            await self._flash_status("CORRECT", GREEN)
            display_flag("A3 Pixel Cipher", flag, self.controller.bsp.displays)
            return
        await self._flash_status("TRY AGAIN", RED)

    async def setup(self):
        self._render()

    def button_click(self, button):
        if not self.show_input:
            if button == 0:
                self.show_input = True
                self._render()
            return

        if button == 0:
            self.show_input = False
        elif button == 5:
            self.cursor = (self.cursor - 1) % self.length
        elif button == 4:
            self.cursor = (self.cursor + 1) % self.length
        elif button == 1:
            idx = CHARSET.find(self.answer[self.cursor])
            self.answer[self.cursor] = CHARSET[(idx - 1) % len(CHARSET)]
        elif button in (2, 6):
            idx = CHARSET.find(self.answer[self.cursor])
            self.answer[self.cursor] = CHARSET[(idx + 1) % len(CHARSET)]
        elif button == 3:
            asyncio.create_task(self._submit())
            return

        self._render()
