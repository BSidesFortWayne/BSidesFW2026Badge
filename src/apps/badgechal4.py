import asyncio
import time

import badgechal
from apps.app import BaseApp
from lib.flag_display import display_flag


BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0

DIGITS = "0123456789"
MORSE_DIGITS = {
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
}

# Morse timing (in ms)
MORSE_UNIT_MS = 90
MORSE_DOT_MS = MORSE_UNIT_MS
MORSE_DASH_MS = MORSE_UNIT_MS * 3
MORSE_PART_GAP_MS = MORSE_UNIT_MS
MORSE_CHAR_GAP_MS = MORSE_UNIT_MS * 6
MORSE_WORD_GAP_MS = MORSE_UNIT_MS * 7
MORSE_FREQ = 720
MORSE_DUTY = 26


class App(BaseApp):
    name = "CTF Challenge 4"
    version = "0.1.0"

    def __init__(self, controller):
        super().__init__(controller)
        self.sequence = str(badgechal.dtmf_sequence())  # digits players must decode
        self.answer = ["0"] * len(self.sequence)
        self.cursor = 0
        self.playing = False
        self.replay_task = None
        self.input_dirty = False
        self.accept_input_at_ms = 0

    def _tone(self, duration_ms, led_idx=None):
        pwm = self.controller.bsp.speaker.pwm
        leds = self.controller.bsp.leds
        if led_idx is not None:
            leds.turn_off_all()
            leds.set_led_color(led_idx, (0, 0, 28))
        pwm.freq(MORSE_FREQ)
        pwm.duty(MORSE_DUTY)
        time.sleep_ms(duration_ms)
        pwm.duty(0)
        if led_idx is not None:
            leds.turn_off_all()

    def _play_morse_char(self, ch, led_idx):
        if ch == " ":
            time.sleep_ms(MORSE_WORD_GAP_MS)
            return

        pattern = MORSE_DIGITS.get(ch)
        if pattern is None:
            return

        for i, mark in enumerate(pattern):
            if mark == ".":
                self._tone(MORSE_DOT_MS, led_idx)
            else:
                self._tone(MORSE_DASH_MS, led_idx)
            if i < len(pattern) - 1:
                time.sleep_ms(MORSE_PART_GAP_MS)
        time.sleep_ms(MORSE_CHAR_GAP_MS)

    async def _play_sequence(self):
        displays = self.controller.bsp.displays
        displays.display1.fill(BLACK)
        displays.display2.fill(BLACK)
        displays.display_center_text("LISTEN", fg=WHITE, bg=BLACK, display_index=1)
        displays.display_center_text("Decode Morse", fg=WHITE, bg=BLACK, display_index=2)

        leds = self.controller.bsp.leds
        self.playing = True
        try:
            leds.turn_off_all()
            for idx, ch in enumerate(self.sequence):
                self._play_morse_char(ch, idx % 7)
                leds.turn_off_all()
        finally:
            self.playing = False
            self.controller.bsp.speaker.pwm.duty(0)
            leds.turn_off_all()

    def _render_input(self):
        displays = self.controller.bsp.displays
        d1 = displays.display1
        d2 = displays.display2

        d1.fill(BLACK)
        d2.fill(BLACK)

        top = "".join(self.answer[:4])
        bot = "".join(self.answer[4:])
        displays.display_text(top, 88, 78, fg=WHITE, bg=BLACK, display_index=1)
        displays.display_text(bot, 88, 118, fg=WHITE, bg=BLACK, display_index=1)

        cx = 88 + (self.cursor % 4) * 16
        cy = 72 if self.cursor < 4 else 112
        d1.fill_rect(cx, cy, 16, 2, 0xFFE0)
        d1.fill_rect(cx, cy + 34, 16, 2, 0xFFE0)

        displays.display_text("L/R mv B- C+", 24, 84, fg=WHITE, bg=BLACK, display_index=2)
        displays.display_text("SEL+ D=OK A=Rp", 8, 116, fg=WHITE, bg=BLACK, display_index=2)

    async def _flash(self, text, color):
        displays = self.controller.bsp.displays
        displays.display1.fill(color)
        displays.display2.fill(color)
        displays.display_center_text(text, fg=WHITE, bg=color, display_index=1)
        await asyncio.sleep_ms(900)
        self._render_input()

    async def _submit(self):
        candidate = "".join(self.answer)
        passed, flag = badgechal.dtmf_check(candidate)
        if passed and flag:
            await self._flash("CORRECT", GREEN)
            display_flag("C4 Morse Codec", flag, self.controller.bsp.displays)
            return
        await self._flash("NOPE", RED)

    async def _replay(self):
        if self.playing:
            return
        self.input_dirty = False
        await self._play_sequence()
        self.accept_input_at_ms = time.ticks_add(time.ticks_ms(), 350)
        self._render_input()

    def _start_replay(self):
        if self.playing:
            return
        if self.replay_task is not None and not self.replay_task.done():
            return
        self.replay_task = asyncio.create_task(self._replay())

    async def setup(self):
        self.input_dirty = False
        await self._play_sequence()
        self.accept_input_at_ms = time.ticks_add(time.ticks_ms(), 350)
        self._render_input()

    async def teardown(self):
        if self.replay_task is not None and not self.replay_task.done():
            self.replay_task.cancel()
        self.playing = False
        self.controller.bsp.speaker.pwm.duty(0)
        self.controller.bsp.leds.turn_off_all()

    def button_click(self, button):
        if time.ticks_diff(time.ticks_ms(), self.accept_input_at_ms) < 0:
            return
        if self.playing:
            return
        if button == 0:
            self._start_replay()
        elif button == 5:
            self.cursor = (self.cursor - 1) % len(self.answer)
            self.input_dirty = True
            self._render_input()
        elif button == 4:
            self.cursor = (self.cursor + 1) % len(self.answer)
            self.input_dirty = True
            self._render_input()
        elif button == 1:
            idx = DIGITS.find(self.answer[self.cursor])
            self.answer[self.cursor] = DIGITS[(idx - 1) % len(DIGITS)]
            self.input_dirty = True
            self._render_input()
        elif button in (2, 6):
            idx = DIGITS.find(self.answer[self.cursor])
            self.answer[self.cursor] = DIGITS[(idx + 1) % len(DIGITS)]
            self.input_dirty = True
            self._render_input()
        elif button == 3:
            if not self.input_dirty:
                return
            asyncio.create_task(self._submit())
