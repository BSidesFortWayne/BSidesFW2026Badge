import asyncio

import badgechal
from apps.app import BaseApp
from lib.flag_display import display_flag


BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0

CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ_"


class App(BaseApp):
    name = "CTF Challenge 5"
    version = "0.1.0"

    def __init__(self, controller):
        super().__init__(controller)
        left, right = badgechal.stereo_layers()
        self.left_hex = str(left)
        self.right_hex = str(right)
        self.answer_len = int(badgechal.stereo_answer_len())
        self.answer = ["A"] * self.answer_len
        self.cursor = 0
        self.input_mode = False

    def _hex_bits(self, hx):
        out = []
        for i in range(0, len(hx), 2):
            byte = int(hx[i:i + 2], 16)
            for bit in range(7, -1, -1):
                out.append((byte >> bit) & 1)
        return out

    def _draw_layer(self, display, hx):
        bits = self._hex_bits(hx)
        side = 12
        cell = 13
        gap = 1
        total = side * cell + (side - 1) * gap
        sx = (240 - total) // 2
        sy = (240 - total) // 2

        display.fill(WHITE)
        for y in range(side):
            for x in range(side):
                idx = y * side + x
                if idx >= len(bits):
                    continue
                if bits[idx]:
                    px = sx + x * (cell + gap)
                    py = sy + y * (cell + gap)
                    display.fill_rect(px, py, cell, cell, BLACK)

    def _render_layers(self):
        displays = self.controller.bsp.displays
        self._draw_layer(displays.display1, self.left_hex)
        self._draw_layer(displays.display2, self.right_hex)

    def _render_input(self):
        displays = self.controller.bsp.displays
        d1 = displays.display1
        d2 = displays.display2

        d1.fill(BLACK)
        d2.fill(BLACK)

        top = "".join(self.answer[:9])
        bot = "".join(self.answer[9:])
        displays.display_text(top, 18, 78, fg=WHITE, bg=BLACK, display_index=1)
        displays.display_text(bot, 18, 118, fg=WHITE, bg=BLACK, display_index=1)

        cx = 18 + (self.cursor % 9) * 16
        cy = 72 if self.cursor < 9 else 112
        d1.fill_rect(cx, cy, 16, 2, 0xFFE0)
        d1.fill_rect(cx, cy + 34, 16, 2, 0xFFE0)

        displays.display_text("XOR layers", 8, 76, fg=WHITE, bg=BLACK, display_index=2)
        displays.display_text("LR mv B- C+", 8, 108, fg=WHITE, bg=BLACK, display_index=2)
        displays.display_text("S+ D=OK A=vw", 8, 140, fg=WHITE, bg=BLACK, display_index=2)

    def _render(self):
        if self.input_mode:
            self._render_input()
        else:
            self._render_layers()

    async def _flash(self, text, color):
        displays = self.controller.bsp.displays
        displays.display1.fill(color)
        displays.display2.fill(color)
        displays.display_center_text(text, fg=WHITE, bg=color, display_index=1)
        await asyncio.sleep_ms(850)
        self._render()

    async def _submit(self):
        candidate = "".join(self.answer)
        passed = bool(badgechal.stereo_check(candidate))
        if passed:
            flag = badgechal.claim_flag(5)
            if not flag:
                await self._flash("VERIFY FAIL", RED)
                return
            await self._flash("CORRECT", GREEN)
            display_flag("C5 Stereogram", flag, self.controller.bsp.displays)
            return
        await self._flash("TRY AGAIN", RED)

    async def setup(self):
        self._render_layers()

    def button_click(self, button):
        if button == 0:
            self.input_mode = not self.input_mode
            self._render()
            return

        if not self.input_mode:
            return

        if button == 1:
            idx = CHARSET.find(self.answer[self.cursor])
            self.answer[self.cursor] = CHARSET[(idx - 1) % len(CHARSET)]
            self._render_input()
        elif button in (2, 6):
            idx = CHARSET.find(self.answer[self.cursor])
            self.answer[self.cursor] = CHARSET[(idx + 1) % len(CHARSET)]
            self._render_input()
        elif button == 5:
            self.cursor = (self.cursor - 1) % len(self.answer)
            self._render_input()
        elif button == 4:
            self.cursor = (self.cursor + 1) % len(self.answer)
            self._render_input()
        elif button == 3:
            asyncio.create_task(self._submit())
