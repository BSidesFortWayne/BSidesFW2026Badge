# Launch Caffiend. Start sleepy. Press Soda, Coffee, Energy Drink. The badge
# becomes progressively less employable. Press Water to apply a compensating
# control.

import asyncio
import time

import framebuf
import vga2_8x16 as font_small

from apps.app import BaseApp
from drivers.displays import rgb


BLACK = rgb((0, 0, 0))
WHITE = rgb((255, 255, 255))
DIM_WHITE = rgb((120, 120, 130))
GRAY = rgb((34, 34, 40))
GREEN = rgb((0, 220, 120))
BLUE = rgb((40, 120, 255))
CYAN = rgb((0, 220, 255))
YELLOW = rgb((255, 220, 40))
ORANGE = rgb((255, 120, 20))
RED = rgb((255, 30, 30))
MAGENTA = rgb((255, 40, 255))

MAX_CAFFEINE_MG = 999
FRAME_W = 240
FRAME_H = 240


STATE_SLEEPY = 0
STATE_FUNCTIONAL = 1
STATE_OVERCLOCKED = 2
STATE_UNSTABLE = 3
STATE_ASCENDED = 4

STATE_NAMES = (
    "Sleepy",
    "Functional",
    "Overclocked",
    "Unstable",
    "Ascended",
)

STATE_PHRASES = (
    ("Booting human...", "Need bean juice", "Barely operational"),
    ("Caffeine control", "Human online", "Ready-ish"),
    ("I can hear Wi-Fi", "Ideas detected", "Productivity spike"),
    ("Hydration failure", "Hands: deprecated", "Blinking optional"),
    ("Forbidden knowledge", "No longer time-bound", "I AM THE COFFEE", "Do not shake vessel"),
)

REACTION_PHRASES = {
    "COFFEE": "Bean juice acquired",
    "SODA": "Carbonation detected",
    "ENERGY": "Bad idea accepted",
    "WATER": "Compensating control applied",
}

AUDIT_FINDINGS = (
    "Finding: Coffee used as lunch.",
    "Finding: Hydration evidence missing.",
    "Finding: User claims soda is a control.",
    "Finding: Energy drink accepted without risk analysis.",
    "Finding: Badge is now supervising user.",
    "Finding: Heartbeat exceeds approved baseline.",
)

SHAKE_PHRASES = (
    "Too tired for turbulence",
    "Motion logged",
    "I AM AWAKE",
    "Hands are a blur",
    "DO NOT SHAKE VESSEL",
)


class Caffiend(BaseApp):
    name = "Caffiend"
    version = "0.0.1"

    def __init__(self, controller):
        super().__init__(controller)

        self.displays = self.controller.bsp.displays
        self.display1 = self.displays.display1
        self.display2 = self.displays.display2

        self.fbuf_mem = bytearray(FRAME_W * FRAME_H * 2)
        self.fbuf_mv = memoryview(self.fbuf_mem)
        self.fbuf = framebuf.FrameBuffer(self.fbuf_mv, FRAME_W, FRAME_H, framebuf.RGB565)

        self.caffeine_mg = self._clamp_mg(self.config.add("caffeine_mg", 0))
        self.config.add("high_score_mg", self.caffeine_mg)

        self.tick = 0
        self.event_count = 0
        self.last_action = "SYSTEM"
        self.last_delta = 0
        self.status_override = None
        self.status_until_ms = 0
        self.surge_ticks = 0
        self.water_ticks = 0
        self.ascension_ticks = 0
        self.ascension_triggered = self.caffeine_mg >= 450
        self.help_until_ms = self._deadline_ms(2500)
        self.last_audit_ms = self._ticks_ms()
        self.audit_index = 0
        self.needs_redraw = True
        self.imu_callback_registered = False
        self.imu_callback_ref = self.imu_callback
        self.last_accel = None
        self.sound_task = None

        # Badge driver button IDs are zero-based. The on-screen legend shows
        # human labels 1-4. Button ID 3 long-press is reserved by the controller
        # for returning to Menu, so Caffiend only uses clicks for water/reset.
        self.button_actions = {
            0: ("COFFEE", 95),
            1: ("SODA", 40),
            2: ("ENERGY", 160),
            3: ("WATER", -40),
        }

    async def setup(self):
        self._register_imu()
        self._draw_scene()
        self._update_leds(force=True)

    async def teardown(self):
        self._unregister_imu()
        if self.sound_task:
            self.sound_task.cancel()
            self.sound_task = None
        self._speaker_off()
        self._leds_off()

    async def update(self):
        self.tick += 1
        now = self._ticks_ms()

        if self.status_override and self._ticks_diff(self.status_until_ms, now) <= 0:
            self.status_override = None
            self.status_until_ms = 0
            self.needs_redraw = True

        if self.help_until_ms and self._ticks_diff(self.help_until_ms, now) <= 0:
            self.help_until_ms = 0
            self.needs_redraw = True

        if self.surge_ticks > 0:
            self.surge_ticks -= 1
            self.needs_redraw = True

        if self.water_ticks > 0:
            self.water_ticks -= 1
            self.needs_redraw = True

        if self.ascension_ticks > 0:
            self.ascension_ticks -= 1
            self.needs_redraw = True

        state = self._state_for_mg(self.caffeine_mg)
        animate = False
        if state == STATE_SLEEPY:
            animate = self.tick % 12 == 0
        elif state == STATE_FUNCTIONAL:
            animate = self.tick % 10 == 0
        elif state == STATE_OVERCLOCKED:
            animate = self.tick % 5 == 0
        elif state == STATE_UNSTABLE:
            animate = self.tick % 3 == 0
        elif state == STATE_ASCENDED:
            animate = self.tick % 2 == 0

        if (
            state >= STATE_UNSTABLE
            and not self.status_override
            and not self._help_active()
            and self._ticks_diff(now, self.last_audit_ms) > 7000
        ):
            self.last_audit_ms = now
            self._show_status(AUDIT_FINDINGS[self.audit_index % len(AUDIT_FINDINGS)], 1800)
            self.audit_index += 1

        if self.needs_redraw or animate:
            self._draw_scene()

        if self.ascension_ticks > 0 or self.tick % 4 == 0:
            self._update_leds()

    def button_click(self, button):
        action = self.button_actions.get(button)
        if not action:
            return

        drink_name, delta = action
        old_mg = self.caffeine_mg
        old_state = self._state_for_mg(self.caffeine_mg)
        self.caffeine_mg = self._clamp_mg(self.caffeine_mg + delta)
        new_state = self._state_for_mg(self.caffeine_mg)

        self.event_count += 1
        self.last_action = drink_name
        self.last_delta = delta

        self._show_status(REACTION_PHRASES.get(drink_name, drink_name), 1600)
        self.surge_ticks = 14 if delta > 0 else 0
        self.water_ticks = 24 if delta < 0 else 0

        self._persist_caffeine()
        if not self.ascension_triggered and old_mg < 450 <= self.caffeine_mg:
            self._trigger_ascension(old_state, new_state)
        else:
            self._chirp(old_state, new_state, delta)
        self.needs_redraw = True

    def button_long_press(self, button):
        # Intentionally no reset on long press: button ID 3 is the global menu
        # escape in controller.py. Water click is the safe calm-down path.
        pass

    async def imu_callback(self, value):
        if self.last_accel is None:
            self.last_accel = value
            return

        dx = abs(value[0] - self.last_accel[0])
        dy = abs(value[1] - self.last_accel[1])
        dz = abs(value[2] - self.last_accel[2])
        self.last_accel = value

        if dx + dy + dz > 18:
            state = self._state_for_mg(self.caffeine_mg)
            self._show_status(SHAKE_PHRASES[state], 1700)
            self.needs_redraw = True
            if state >= STATE_UNSTABLE:
                self._chirp(state, state, 1)

    def _state_for_mg(self, mg):
        if mg <= 0:
            return STATE_SLEEPY
        if mg < 150:
            return STATE_FUNCTIONAL
        if mg < 300:
            return STATE_OVERCLOCKED
        if mg < 450:
            return STATE_UNSTABLE
        return STATE_ASCENDED

    def _clamp_mg(self, mg):
        try:
            mg = int(mg)
        except Exception:
            mg = 0
        if mg < 0:
            return 0
        if mg > MAX_CAFFEINE_MG:
            return MAX_CAFFEINE_MG
        return mg

    def _persist_caffeine(self):
        # BaseApp Config is the repo's obvious persistence hook. If storage is
        # unavailable, keep running RAM-only instead of ruining the demo.
        try:
            self.config["caffeine_mg"] = self.caffeine_mg
            if self.caffeine_mg > self.config.get("high_score_mg", 0):
                self.config["high_score_mg"] = self.caffeine_mg
        except Exception:
            pass

    def _pick(self, phrases):
        return phrases[self.event_count % len(phrases)]

    def _show_status(self, text, duration_ms):
        self.status_override = text
        self.status_until_ms = self._deadline_ms(duration_ms)
        self.needs_redraw = True

    def _trigger_ascension(self, old_state, new_state):
        self.ascension_triggered = True
        self.ascension_ticks = 46
        self.surge_ticks = 46
        self.water_ticks = 0
        self._show_status("ASCENSION EVENT", 1800)
        self._chirp(old_state, new_state, 160)

    def _current_phrase(self):
        if self.status_override:
            return self.status_override
        state = self._state_for_mg(self.caffeine_mg)
        return STATE_PHRASES[state][(self.event_count + state) % len(STATE_PHRASES[state])]

    def _risk_label(self):
        state = self._state_for_mg(self.caffeine_mg)
        if state == STATE_SLEEPY:
            return "Risk: asleep"
        if state == STATE_FUNCTIONAL:
            return "Risk: acceptable"
        if state == STATE_OVERCLOCKED:
            return "Risk: productive"
        if state == STATE_UNSTABLE:
            return "Risk: twitchy"
        return "Risk: legally coffee"

    def _draw_scene(self):
        state = self._state_for_mg(self.caffeine_mg)
        jitter = self._jitter_amount(state)
        calm = self.water_ticks > 0
        pulse = self._pulse_amount()
        blink = self._blink_amount(state)
        dart_x, dart_y = self._dart_offset(state)

        self._draw_eye(
            self.display1,
            state,
            is_left=True,
            jitter=jitter,
            calm=calm,
            pulse=pulse,
            blink=blink,
            dart_x=dart_x,
            dart_y=dart_y,
        )
        self._draw_eye(
            self.display2,
            state,
            is_left=False,
            jitter=-jitter,
            calm=calm,
            pulse=pulse,
            blink=blink,
            dart_x=-dart_x,
            dart_y=dart_y,
        )
        self.needs_redraw = False

    def _draw_eye(self, display, state, is_left, jitter, calm, pulse, blink, dart_x, dart_y):
        fbuf = self.fbuf
        fbuf.fill(BLACK)

        accent = self._accent_color(state)
        if calm:
            accent = BLUE

        if state == STATE_SLEEPY:
            self._draw_sleepy_eye(fbuf, is_left, accent, blink)
        elif state == STATE_FUNCTIONAL:
            self._draw_functional_eye(fbuf, is_left, accent, calm, pulse, blink, dart_x, dart_y)
        elif state == STATE_OVERCLOCKED:
            self._draw_overclocked_eye(fbuf, is_left, accent, calm, pulse, dart_x, dart_y)
        elif state == STATE_UNSTABLE:
            self._draw_unstable_eye(fbuf, is_left, accent, jitter, calm, pulse)
        else:
            self._draw_ascended_eye(fbuf, is_left, accent, jitter, calm, pulse)

        self._draw_action_effect(fbuf, accent, is_left, calm, pulse)

        if is_left:
            self._draw_left_overlay(fbuf, accent)
        else:
            self._draw_right_overlay(fbuf, accent)

        display.blit_buffer(self.fbuf_mv, 0, 0, FRAME_W, FRAME_H)

    def _draw_sleepy_eye(self, fbuf, is_left, accent, blink):
        y = 128 if is_left else 124
        fbuf.ellipse(120, y, 80, 30, DIM_WHITE, True)
        fbuf.fill_rect(34, y - 48, 172, 42, BLACK)
        if blink:
            fbuf.fill_rect(34, y - 10, 172, min(38, blink), BLACK)
        fbuf.line(48, y - 5, 192, y - 13, accent)
        fbuf.line(49, y - 4, 193, y - 12, accent)
        pupil_x = 116 if is_left else 124
        fbuf.ellipse(pupil_x, y + 9, 10, 6, GRAY, True)
        fbuf.ellipse(pupil_x - 3, y + 7, 2, 2, DIM_WHITE, True)

    def _draw_functional_eye(self, fbuf, is_left, accent, calm, pulse, blink, dart_x, dart_y):
        px = (116 if is_left else 124) + ((pulse // 2) if is_left else -(pulse // 2)) + dart_x
        py = (116 if not calm else 124) + dart_y
        fbuf.ellipse(120, 118, 82 + pulse, 54 + pulse, WHITE, True)
        fbuf.ellipse(120, 118, 84 + pulse, 56 + pulse, accent, False)
        fbuf.ellipse(px, py, max(14, 24 - pulse), max(16, 26 - pulse), accent, False)
        fbuf.ellipse(px, py, max(10, 18 - pulse), max(12, 20 - pulse), BLACK, True)
        fbuf.ellipse(px - 6, py - 8, 4, 4, WHITE, True)
        if calm:
            fbuf.ellipse(px + 8, py + 10, 5, 3, CYAN, True)
        if blink:
            fbuf.fill_rect(34, 78, 172, min(48, blink), BLACK)
            fbuf.fill_rect(34, 158 - min(48, blink), 172, min(48, blink), BLACK)

    def _draw_overclocked_eye(self, fbuf, is_left, accent, calm, pulse, dart_x, dart_y):
        px = 120 + (-10 if is_left else 10) + (pulse if is_left else -pulse) + dart_x
        py = (112 if not calm else 124) + dart_y
        fbuf.ellipse(120, 116, 92 + pulse, 72 + pulse, WHITE, True)
        fbuf.ellipse(120, 116, 94 + pulse, 74 + pulse, accent, False)
        self._draw_bloodshot(fbuf, px, py, 1, pulse)
        fbuf.ellipse(px, py, 24 + pulse, 28 + pulse, accent, False)
        fbuf.ellipse(px, py, max(5, 10 - pulse // 2), max(6, 12 - pulse // 2), BLACK, True)
        fbuf.ellipse(px - 4, py - 8, 3, 3, WHITE, True)
        if calm:
            fbuf.ellipse(px, py, 30, 32, BLUE, False)

    def _draw_unstable_eye(self, fbuf, is_left, accent, jitter, calm, pulse):
        roll = (self.tick // 3) % 4
        if roll == 0:
            roll_x, roll_y = (-36 if is_left else 34), -26
        elif roll == 1:
            roll_x, roll_y = (28 if is_left else -30), 30
        elif roll == 2:
            roll_x, roll_y = (-44 if is_left else -26), 8
        else:
            roll_x, roll_y = (20 if is_left else 46), -6
        px = 120 + jitter + roll_x + (pulse if is_left else -pulse)
        py = 116 - jitter + roll_y + (12 if calm else 0)
        pupil_rx = (18 if is_left else 30) + (0 if calm else pulse // 2)
        pupil_ry = (34 if is_left else 16) + (0 if calm else pulse // 2)
        fbuf.ellipse(120 + jitter, 116 - jitter, 92, 70, WHITE, True)
        fbuf.ellipse(120 + jitter, 116 - jitter, 96, 74, accent, False)
        self._draw_bloodshot(fbuf, px, py, 2, jitter + pulse)
        fbuf.ellipse(px, py, pupil_rx + 8, pupil_ry + 8, accent, False)
        fbuf.ellipse(px, py, pupil_rx, pupil_ry, BLACK, True)
        fbuf.ellipse(px - 8, py - 10, 4, 4, WHITE, True)
        fbuf.ellipse(px + 9, py + 8, 3, 3, WHITE, True)

    def _draw_ascended_eye(self, fbuf, is_left, accent, jitter, calm, pulse):
        cx = 120 + jitter
        cy = 118 - jitter
        fbuf.ellipse(cx, cy, 96, 76, WHITE, True)
        fbuf.ellipse(cx, cy, 98, 78, accent, False)
        self._draw_bloodshot(fbuf, cx, cy, 3, jitter + pulse)
        fbuf.ellipse(cx, cy, 58 + pulse, 46 + pulse, BLACK, True)
        self._draw_spiral(fbuf, cx, cy, accent if not calm else BLUE)
        fbuf.ellipse(cx - 28, cy - 24, 7, 7, WHITE, True)
        fbuf.ellipse(cx + 25, cy + 19, 4, 4, WHITE, True)
        if self.ascension_ticks > 0:
            fbuf.text("!!!", 108, 48, RED)
            fbuf.ellipse(cx, cy, 68 + pulse, 56 + pulse, RED, False)
            fbuf.ellipse(cx, cy, 72 + pulse, 60 + pulse, accent, False)
        if is_left:
            fbuf.ellipse(cx - 36, cy + 24, 10, 16, RED, False)
        else:
            fbuf.ellipse(cx + 36, cy - 24, 10, 16, RED, False)

    def _draw_spiral(self, fbuf, cx, cy, color):
        points = (
            (0, 0), (14, 0), (14, 14), (-14, 14), (-14, -14),
            (28, -14), (28, 28), (-28, 28), (-28, -28),
            (42, -28), (42, 42), (-42, 42), (-42, -42),
        )
        last = points[0]
        for point in points[1:]:
            fbuf.line(cx + last[0], cy + last[1], cx + point[0], cy + point[1], color)
            last = point
        fbuf.ellipse(cx, cy, 5, 5, color, True)

    def _draw_bloodshot(self, fbuf, cx, cy, level, jitter):
        veins = (
            (44, 100, -46, -8), (56, 142, -38, 16),
            (196, 96, 46, -12), (188, 148, 40, 18),
            (72, 76, -28, -28), (168, 76, 30, -26),
            (70, 168, -28, 28), (170, 166, 30, 26),
            (34, 120, -52, 0), (206, 118, 52, 0),
            (112, 48, -8, -42), (130, 184, 8, 38),
        )
        count = min(len(veins), 4 + level * 4)
        for i in range(0, count):
            sx, sy, tx, ty = veins[i]
            wobble = 0
            if level > 1:
                wobble = ((self.tick + i * 3 + jitter) % 7) - 3
            ex = cx + tx + wobble
            ey = cy + ty - wobble
            fbuf.line(sx, sy, ex, ey, RED)
            if level >= 2:
                fbuf.line(ex, ey, ex + (6 if tx < 0 else -6), ey + (5 if ty <= 0 else -5), RED)

    def _draw_action_effect(self, fbuf, accent, is_left, calm, pulse):
        if calm:
            fbuf.ellipse(120, 118, 100, 78, BLUE, False)
            fbuf.ellipse(120, 118, 102, 80, CYAN if self.water_ticks % 2 else BLUE, False)
            return

        if pulse <= 0:
            return

        color = accent if is_left else RED
        fbuf.ellipse(120, 118, 98 + pulse * 2, 76 + pulse * 2, color, False)
        fbuf.ellipse(120, 118, 101 + pulse * 2, 79 + pulse * 2, color, False)

    def _draw_left_overlay(self, fbuf, accent):
        state = self._state_for_mg(self.caffeine_mg)
        fbuf.fill_rect(58, 12, 124, 18, BLACK)
        self._center_text(fbuf, "{}mg".format(self.caffeine_mg), 14, accent)
        self._center_text(fbuf, self._risk_label(), 34, DIM_WHITE)
        if self._help_active():
            self._draw_help_overlay(fbuf, True, accent)
            return
        self._center_text(fbuf, STATE_NAMES[state], 194, accent)
        fbuf.text("1 Coffee", 42, 214, DIM_WHITE)
        fbuf.text("2 Soda", 122, 214, DIM_WHITE)

    def _draw_right_overlay(self, fbuf, accent):
        phrase = self._short(self._current_phrase(), 28)
        fbuf.fill_rect(20, 12, 200, 18, BLACK)
        self._center_text(fbuf, phrase, 14, accent)
        if self._help_active():
            self._draw_help_overlay(fbuf, False, accent)
            return
        fbuf.text("3 Energy", 36, 214, DIM_WHITE)
        fbuf.text("4 Water", 124, 214, BLUE if self.water_ticks else DIM_WHITE)
        if self.last_delta:
            label = "+{}".format(self.last_delta) if self.last_delta > 0 else str(self.last_delta)
            self._center_text(fbuf, label + " " + self.last_action, 194, accent)

    def _draw_help_overlay(self, fbuf, is_left, accent):
        if is_left:
            self._center_text(fbuf, "1 Coffee +95", 194, accent)
            self._center_text(fbuf, "2 Soda +40", 214, DIM_WHITE)
        else:
            self._center_text(fbuf, "3 Energy +160", 186, accent)
            self._center_text(fbuf, "4 Water -40", 204, BLUE)
            self._center_text(fbuf, "Long press menu", 222, DIM_WHITE)

    def _center_text(self, fbuf, text, y, color):
        x = int((FRAME_W - (font_small.WIDTH * len(text))) / 2)
        if x < 0:
            x = 0
        fbuf.text(text, x, y, color)

    def _short(self, text, limit):
        if len(text) <= limit:
            return text
        if limit <= 3:
            return text[:limit]
        return text[:limit - 3] + "..."

    def _ticks_ms(self):
        try:
            return time.ticks_ms()
        except AttributeError:
            return int(time.time() * 1000)

    def _ticks_diff(self, left, right):
        try:
            return time.ticks_diff(left, right)
        except AttributeError:
            return left - right

    def _deadline_ms(self, duration_ms):
        now = self._ticks_ms()
        try:
            return time.ticks_add(now, duration_ms)
        except AttributeError:
            return now + duration_ms

    def _help_active(self):
        return bool(self.help_until_ms and self._ticks_diff(self.help_until_ms, self._ticks_ms()) > 0)

    def _jitter_amount(self, state):
        if self.ascension_ticks > 0:
            return ((self.tick * 17) % 41) - 20
        if self.water_ticks > 0:
            return 0
        if state < STATE_UNSTABLE:
            return 0
        if state == STATE_UNSTABLE:
            return ((self.tick * 7) % 17) - 8
        return ((self.tick * 11) % 27) - 13

    def _pulse_amount(self):
        if self.ascension_ticks > 0:
            return 8 + (self.ascension_ticks % 8)
        if self.surge_ticks <= 0:
            return 0
        return 2 + (self.surge_ticks % 6)

    def _blink_amount(self, state):
        if state == STATE_SLEEPY:
            phase = self.tick % 90
            if phase < 10:
                return phase * 3
            if phase < 20:
                return (20 - phase) * 3
        elif state == STATE_FUNCTIONAL:
            phase = self.tick % 130
            if phase < 4:
                return phase * 12
            if phase < 8:
                return (8 - phase) * 12
        return 0

    def _dart_offset(self, state):
        if self.water_ticks > 0:
            return (0, 2)
        if state == STATE_OVERCLOCKED:
            return ((((self.tick // 4) % 5) - 2) * 2, (((self.tick // 7) % 3) - 1) * 2)
        if state == STATE_ASCENDED:
            return ((((self.tick // 2) % 7) - 3) * 2, (((self.tick // 3) % 5) - 2) * 2)
        return (0, 0)

    def _accent_color(self, state):
        if self.ascension_ticks > 0:
            colors = (RED, MAGENTA, YELLOW, CYAN)
            return colors[self.tick % len(colors)]
        if state == STATE_SLEEPY:
            return BLUE
        if state == STATE_FUNCTIONAL:
            return GREEN
        if state == STATE_OVERCLOCKED:
            return YELLOW
        if state == STATE_UNSTABLE:
            return ORANGE
        return MAGENTA if self.tick % 2 else RED

    def _register_imu(self):
        try:
            callbacks = self.controller.bsp.imu.imu_callbacks
            if self.imu_callback_ref not in callbacks:
                callbacks.append(self.imu_callback_ref)
                self.imu_callback_registered = True
        except Exception:
            # IMU is optional polish; the tracker still works without it.
            self.imu_callback_registered = False

    def _unregister_imu(self):
        if not self.imu_callback_registered:
            return
        try:
            callbacks = self.controller.bsp.imu.imu_callbacks
            if self.imu_callback_ref in callbacks:
                callbacks.remove(self.imu_callback_ref)
        except Exception:
            pass
        self.imu_callback_registered = False

    def _update_leds(self, force=False):
        state = self._state_for_mg(self.caffeine_mg)
        try:
            leds = self.controller.bsp.leds.leds
        except Exception:
            return

        base = self._led_color(state)
        for i in range(0, len(leds)):
            scale = self._led_scale(state, i)
            leds[i] = (
                int(base[0] * scale),
                int(base[1] * scale),
                int(base[2] * scale),
            )
        try:
            leds.write()
        except Exception:
            pass

    def _led_color(self, state):
        if self.ascension_ticks > 0:
            colors = ((50, 0, 0), (40, 0, 40), (0, 36, 48), (50, 32, 0))
            return colors[self.tick % len(colors)]
        if self.water_ticks > 0:
            return (0, 10, 32)
        if state == STATE_SLEEPY:
            return (0, 0, 18)
        if state == STATE_FUNCTIONAL:
            return (0, 24, 8)
        if state == STATE_OVERCLOCKED:
            return (34, 20, 0)
        if state == STATE_UNSTABLE:
            return (42, 6, 0)
        colors = ((40, 0, 0), (30, 0, 30), (0, 28, 36), (36, 24, 0))
        return colors[(self.tick // 2) % len(colors)]

    def _led_scale(self, state, index):
        if self.ascension_ticks > 0:
            return 0.15 + (((self.tick * 3) + index * 5) % 9) / 9
        if self.water_ticks > 0:
            return 0.18 + ((index + self.tick // 6) % 3) * 0.08
        if state == STATE_SLEEPY:
            return 0.20 + (((self.tick // 8) + index) % 3) * 0.08
        if state == STATE_FUNCTIONAL:
            return 0.45
        if state == STATE_OVERCLOCKED:
            return 0.35 + (((self.tick // 3) + index) % 4) * 0.13
        if state == STATE_UNSTABLE:
            return 0.05 if ((self.tick + index * 3) % 5) else 1.0
        return 0.2 + (((self.tick + index * 5) % 7) / 7)

    def _leds_off(self):
        try:
            self.controller.bsp.leds.turn_off_all()
            return
        except Exception:
            pass
        try:
            self.controller.neopixel.fill((0, 0, 0))
            self.controller.neopixel.write()
        except Exception:
            pass

    def _chirp(self, old_state, new_state, delta):
        if self.sound_task:
            self.sound_task.cancel()
        try:
            self.sound_task = asyncio.create_task(self._play_chirp(old_state, new_state, delta))
        except Exception:
            self.sound_task = None

    async def _play_chirp(self, old_state, new_state, delta):
        try:
            speaker = self.controller.bsp.speaker
            notes = (620, 820)
            if delta < 0:
                notes = (420, 260)
            elif new_state > old_state:
                notes = (740, 980, 1240)
            if new_state == STATE_ASCENDED and old_state != STATE_ASCENDED:
                notes = (880, 1175, 1568, 1175)

            for note in notes:
                speaker.pwm.freq(note)
                self._pwm_duty(speaker, 24 if new_state < STATE_ASCENDED else 36)
                await asyncio.sleep(0.045)
                self._pwm_duty(speaker, 0)
                await asyncio.sleep(0.025)
        except Exception:
            pass
        finally:
            self._speaker_off()
            self.sound_task = None

    def _pwm_duty(self, speaker, value):
        try:
            speaker.pwm.duty(value)
        except Exception:
            try:
                speaker.pwm.duty_u16(value * 128)
            except Exception:
                pass

    def _speaker_off(self):
        try:
            self.controller.bsp.speaker.stop_song()
            self._pwm_duty(self.controller.bsp.speaker, 0)
        except Exception:
            pass


if __name__ == "__main__":
    from single_app_runner import run_app

    run_app(Caffiend, perf=True)
