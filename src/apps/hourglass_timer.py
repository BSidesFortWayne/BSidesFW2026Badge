"""
digital_hourglass.py - Digital Hourglass TIMER for BSides Fort Wayne 2025 Badge

Countdown timer using the hourglass sand animation.

Timer States:
  IDLE    — Set duration with A/B/C/D.  Sand fully loaded on display1.
             "PRESS SEL" shown on display2.
  RUNNING — Sand drains as countdown progresses.
             Remaining time counts down on display1.
  PAUSED  — Sand frozen. "PAUSED" shown on display2.
             A/B/C/D still adjust remaining time while paused.
  DONE    — Sand fully drained. "DONE!" shown on display2.
             Any button resets to IDLE with the same duration.

Button Map:
  0  (A)     : -1 minute  (min 1 min remaining)
  1  (B)     : +1 minute  (max 24 hr)
  2  (C)     : -1 hour    (min 1 min remaining)
  3  (D)     : +1 hour    (max 24 hr)
  4  (LEFT)  : Cycle background color
               Long press: Cycle timer color
  5  (RIGHT) : Cycle sand color
  6  (SEL)   : Start (IDLE) / Pause (RUNNING) / Resume (PAUSED)
               Long press: Reset to IDLE from any state
"""

import asyncio
import time
import gc
import gc9a01
import random
import fonts.arial32px as arial32px
import fonts.arial16px as arial16px

from apps.app import BaseApp


class App(BaseApp):
    """Digital Hourglass countdown timer."""

    name = "Hourglass Timer"

    # ── Animation ────────────────────────────────────────────────
    TOTAL_FRAMES = 141

    # ── Stream geometry ──────────────────────────────────────────
    STREAM_CX           = 120
    STREAM_X_HALF       = 7
    STREAM_CLEAR_MARGIN = 3
    STREAM_CLEAR_X      = STREAM_CX - STREAM_X_HALF - STREAM_CLEAR_MARGIN
    STREAM_CLEAR_W      = (STREAM_X_HALF * 2 + 1) + (STREAM_CLEAR_MARGIN * 2)

    # ── Color palette (matches colors.h from original) ───────────
    PALETTE = [
        0x0000,  # 0:  Black
        0xFFFF,  # 1:  White
        0xF800,  # 2:  Red
        0x07E0,  # 3:  Green
        0x001F,  # 4:  Blue
        0xFFE0,  # 5:  Yellow
        0x07FF,  # 6:  Cyan
        0xF81F,  # 7:  Magenta
        0xFC00,  # 8:  Orange
        0x780F,  # 9:  Purple
        0xd94f,  # 10: Pink
        0x04FF,  # 11: Turquoise
        0xbd2e,  # 12: Sand
        0x8410,  # 13: Grey
    ]
    PAL_NAMES = [
        "Black", "White", "Red", "Green", "Blue", "Yellow", "Cyan",
        "Magenta", "Orange", "Purple", "Pink", "Turquoise", "Sand", "Grey",
    ]
    PAL_COUNT = len(PALETTE)

    # ── Button IDs ───────────────────────────────────────────────
    BTN_A     = 0
    BTN_B     = 1
    BTN_C     = 2
    BTN_D     = 3
    BTN_LEFT  = 4
    BTN_RIGHT = 5
    BTN_SEL   = 6

    # ── Timer states ─────────────────────────────────────────────
    STATE_IDLE    = 'idle'
    STATE_RUNNING = 'running'
    STATE_PAUSED  = 'paused'
    STATE_DONE    = 'done'

    # ── Duration bounds ──────────────────────────────────────────
    MIN_DURATION_S = 60       # 1 minute
    MAX_DURATION_S = 86400    # 24 hours

    # ────────────────────────────────────────────────────────────
    def __init__(self, controller):
        super().__init__(controller)
        self.displays = self.controller.bsp.displays

        # Persistent config
        self.config.add('hg_bg_idx',      0)    # Black
        self.config.add('hg_sand_idx',    12)   # Sand
        self.config.add('hg_clock_idx',   6)    # Cyan for countdown text
        self.config.add('hg_timer_dur_s', 300)  # Default: 5 minutes

        # Timer state machine
        self.timer_state      = self.STATE_IDLE
        self.timer_duration_s = max(self.MIN_DURATION_S,
                                    self.config['hg_timer_dur_s'])
        self.timer_elapsed_ms = 0       # ms accumulated while paused/stopped
        self.timer_run_start  = time.ticks_ms()  # ticks when running started

        # Render state
        self.needs_full_redraw = True
        self.last_frame        = -1
        self.last_time_str     = ""
        self.stream_offset     = 0
        self.last_stream_ms    = time.ticks_ms()

        self._apply_colors()
        random.seed(time.ticks_us())

    # ── Colors ───────────────────────────────────────────────────

    def _apply_colors(self):
        pc = self.PAL_COUNT
        self.bg_color    = self.PALETTE[self.config['hg_bg_idx']    % pc]
        self.sand_color  = self.PALETTE[self.config['hg_sand_idx']  % pc]
        self.clock_color = self.PALETTE[self.config['hg_clock_idx'] % pc]

    def _next_clock_color(self):
        idx = (self.config['hg_clock_idx'] + 1) % self.PAL_COUNT
        self.config['hg_clock_idx'] = idx
        self._apply_colors()
        self.last_time_str = ""      # force time redraw in new color
        self.needs_full_redraw = True

    # ── Timer mechanics ──────────────────────────────────────────

    def _get_elapsed_ms(self):
        """Total elapsed ms including the current running segment."""
        if self.timer_state == self.STATE_RUNNING:
            return (self.timer_elapsed_ms +
                    time.ticks_diff(time.ticks_ms(), self.timer_run_start))
        return self.timer_elapsed_ms

    def _remaining_s(self):
        """Remaining seconds, clamped to 0."""
        return max(0, self.timer_duration_s - self._get_elapsed_ms() // 1000)

    def _calc_frame(self):
        """Current animation frame (0 .. TOTAL_FRAMES-1)."""
        if self.timer_state == self.STATE_IDLE:
            return 0
        if self.timer_state == self.STATE_DONE:
            return self.TOTAL_FRAMES - 1
        elapsed_ms = self._get_elapsed_ms()
        total_ms   = self.timer_duration_s * 1000
        if elapsed_ms >= total_ms:
            return self.TOTAL_FRAMES - 1
        f = elapsed_ms * self.TOTAL_FRAMES // total_ms
        return max(0, min(f, self.TOTAL_FRAMES - 1))

    # ── State transitions ────────────────────────────────────────

    def _timer_start(self):
        self.timer_elapsed_ms  = 0
        self.timer_run_start   = time.ticks_ms()
        self.timer_state       = self.STATE_RUNNING
        self.last_frame        = -1
        self.last_time_str     = ""
        self.needs_full_redraw = True

    def _timer_pause(self):
        self.timer_elapsed_ms  = self._get_elapsed_ms()
        self.timer_state       = self.STATE_PAUSED
        self.needs_full_redraw = True

    def _timer_resume(self):
        self.timer_run_start   = time.ticks_ms()
        self.timer_state       = self.STATE_RUNNING
        self.needs_full_redraw = True

    def _timer_done(self):
        self.timer_elapsed_ms  = self.timer_duration_s * 1000
        self.timer_state       = self.STATE_DONE
        self.last_time_str     = ""
        self.needs_full_redraw = True

    def _timer_reset(self):
        """Return to IDLE keeping the same duration (ready to restart)."""
        self.timer_state       = self.STATE_IDLE
        self.timer_elapsed_ms  = 0
        self.last_frame        = -1
        self.last_time_str     = ""
        self.needs_full_redraw = True

    def _adjust_duration(self, delta_s):
        """
        Adjust the timer duration by delta_s seconds.

        IDLE             : changes the set duration.
        RUNNING / PAUSED : changes remaining time; always leaves
                           at least MIN_DURATION_S seconds remaining.
        """
        if self.timer_state == self.STATE_IDLE:
            new_dur = self.timer_duration_s + delta_s
            new_dur = max(self.MIN_DURATION_S,
                          min(self.MAX_DURATION_S, new_dur))
        else:
            elapsed_s = self._get_elapsed_ms() // 1000
            new_dur   = self.timer_duration_s + delta_s
            # Guarantee at least MIN_DURATION_S seconds still remain
            min_dur   = elapsed_s + self.MIN_DURATION_S
            new_dur   = max(min_dur, min(self.MAX_DURATION_S, new_dur))

        self.timer_duration_s         = new_dur
        self.config['hg_timer_dur_s'] = new_dur
        self.last_time_str            = ""
        self.needs_full_redraw        = True

    # ── Geometry (original HourGlass.ino formulas) ───────────────

    def _upper_params(self, frame):
        """(upperY, upperTip) — funnel geometry for display1."""
        return int(frame * 0.9 + 68), int(frame * 1.2 + 90)

    def _lower_params(self, frame):
        """(n, lowerY) — pile geometry for display2."""
        n  = 250 - (frame * 175) // self.TOTAL_FRAMES
        ly = int(n * 0.55 + 105)
        return n, ly

    # ── Triangle drawing ─────────────────────────────────────────

    def _fill_tri_down(self, disp, top_y, tip_y, color):
        """
        Downward-pointing triangle (funnel).
        Full width at top_y, narrows to point at (120, tip_y).
        """
        h = tip_y - top_y
        if h <= 0:
            return
        fr = disp.fill_rect
        for y in range(max(0, top_y), min(240, tip_y + 1)):
            hw = 128 * (tip_y - y) // h
            x  = 120 - hw
            w  = hw * 2 + 1
            if x < 0:       w += x; x = 0
            if x + w > 240: w = 240 - x
            if w > 0:       fr(x, y, w, 1, color)

    def _fill_tri_up(self, disp, tip_y, base_y, color):
        """
        Upward-pointing triangle (sand pile).
        Point at (120, tip_y), full width at base_y.
        """
        h = base_y - tip_y
        if h <= 0:
            return
        fr = disp.fill_rect
        for y in range(max(0, tip_y), min(240, base_y + 1)):
            hw = 120 * (y - tip_y) // h
            x  = 120 - hw
            w  = hw * 2 + 1
            if x < 0:       w += x; x = 0
            if x + w > 240: w = 240 - x
            if w > 0:       fr(x, y, w, 1, color)

    # ── Time / label display ─────────────────────────────────────

    def _format_time(self, total_s):
        """H:MM:SS for timers >= 1 hour, MM:SS otherwise."""
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        if h > 0:
            return "{:d}:{:02d}:{:02d}".format(h, m, s)
        return "{:02d}:{:02d}".format(m, s)

    def _draw_time(self):
        """
        Draw countdown on display1 (y=0..54). Redraws only when
        the formatted string changes — no per-second flashing.

        IDLE  : shows the set duration  e.g. "05:00"
        DONE  : shows "00:00"
        Other : live remaining countdown
        """
        state = self.timer_state
        if state == self.STATE_IDLE:
            tstr = self._format_time(self.timer_duration_s)
        elif state == self.STATE_DONE:
            tstr = "00:00"
        else:
            tstr = self._format_time(self._remaining_s())

        if tstr == self.last_time_str:
            return

        d1 = self.displays.display1
        d1.fill_rect(0, 0, 240, 55, self.bg_color)
        tw = d1.write_len(arial32px, tstr)
        x  = max(0, (240 - tw) // 2)
        d1.write(arial32px, tstr, x, 20, self.clock_color, self.bg_color)
        self.last_time_str = tstr

    def _draw_state_label(self):
        """
        Draw a persistent label at the top of display2 (y=10).

        IDLE   → "PRESS SEL"
        PAUSED → "PAUSED"
        DONE   → "DONE!"
        RUNNING → nothing (cleared by the full_redraw that triggered
                  the RUNNING state transition)

        Sand on display2 never reaches y=10 so this area is always clear.
        """
        label = {
            self.STATE_IDLE:   "PRESS SEL",
            self.STATE_PAUSED: "PAUSED",
            self.STATE_DONE:   "DONE!",
        }.get(self.timer_state)

        if not label:
            return

        d2 = self.displays.display2
        tw = d2.write_len(arial16px, label)
        x  = max(0, (240 - tw) // 2)
        d2.write(arial16px, label, x, 20, self.clock_color, self.bg_color)

    # ── Sand stream ──────────────────────────────────────────────

    def _draw_stream(self, bottom_y):
        """
        Falling sand particles on display2.
        Only called when STATE_RUNNING and frame < TOTAL_FRAMES-1.
        """
        d2   = self.displays.display2
        bg   = self.bg_color
        sand = self.sand_color
        cx   = self.STREAM_CX
        cl_x = self.STREAM_CLEAR_X
        cl_w = self.STREAM_CLEAR_W
        xh   = self.STREAM_X_HALF
        fr   = d2.fill_rect

        sb = min(bottom_y - 10, 240)
        if sb <= 0:
            return

        # Clear the stream column
        fr(cl_x, 0, cl_w, sb, bg)

        # Main falling particles
        i = 0
        while i < sb:
            pos = (i + self.stream_offset) % sb
            xo  = max(-(xh - 2), min(xh - 2, random.randint(-4, 4)))
            r   = random.randint(1, 2)
            px  = cx + xo
            sz  = r * 2 + 1
            if px - r >= cl_x and px + r < cl_x + cl_w:
                fr(px - r, pos, sz, sz, sand)
            # Occasional secondary granule
            if random.randint(0, 2) == 0:
                px2 = max(cl_x + 1,
                          min(cl_x + cl_w - 2, px + random.randint(-2, 2)))
                py2 = pos + random.randint(-3, 3)
                if 0 <= py2 < sb:
                    fr(px2, py2, 2, 2, sand)
            i += 8

        # Splash near pile surface
        for _ in range(5):
            gy  = bottom_y + random.randint(-12, -3)
            gx  = cx + random.randint(-5, 5)
            gr  = random.randint(1, 2)
            gsz = gr * 2 + 1
            if 0 < gy < 240 and gx - gr >= cl_x and gx + gr < cl_x + cl_w:
                fr(gx - gr, gy - gr, gsz, gsz, sand)

        # Dust pixels
        for _ in range(3):
            dx = cx + random.randint(-5, 5)
            dy = random.randint(0, max(1, sb - 1))
            if cl_x <= dx < cl_x + cl_w:
                d2.pixel(dx, dy, sand)

    # ── Full redraw ──────────────────────────────────────────────

    def _full_redraw(self):
        """Wipe both screens and repaint everything from scratch."""
        d1 = self.displays.display1
        d2 = self.displays.display2
        d1.fill(self.bg_color)
        d2.fill(self.bg_color)

        self.last_time_str = ""
        self._draw_time()

        frame  = self._calc_frame()
        uy, ut = self._upper_params(frame)

        # Upper display sand
        if uy < 240:
            d1.fill_rect(0, uy, 240, 240 - uy, self.sand_color)
        self._fill_tri_down(d1, uy, ut, self.bg_color)

        # Lower display sand (only once sand has started accumulating)
        if frame > 0:
            n, ly = self._lower_params(frame)
            if ly < 240:
                self._fill_tri_up(d2, n, ly - 1, self.sand_color)
                d2.fill_rect(0, ly - 1, 240, 241 - ly, self.sand_color)
            if self.timer_state == self.STATE_RUNNING and frame < self.TOTAL_FRAMES - 1:
                self._draw_stream(n)

        self._draw_state_label()

        self.last_frame        = frame
        self.needs_full_redraw = False
        gc.collect()

    # ── Incremental update ───────────────────────────────────────

    def _incremental_update(self):
        """Update only the pixels that changed since the last frame."""
        frame = self._calc_frame()

        # Detect timer completion
        if (self.timer_state == self.STATE_RUNNING and
                self._get_elapsed_ms() >= self.timer_duration_s * 1000):
            self._timer_done()
            self._full_redraw()
            return

        # Backward frame (duration adjusted while running) → full redraw
        if frame < self.last_frame - 2:
            self._full_redraw()
            return

        # Advance stream offset on its own interval
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_stream_ms) >= 150:
            self.last_stream_ms = now
            self.stream_offset  = (self.stream_offset + 12) % 240

        # Same frame — just re-animate the stream
        if frame == self.last_frame:
            if (self.timer_state == self.STATE_RUNNING and
                    0 < frame < self.TOTAL_FRAMES - 1):
                n, _ = self._lower_params(frame)
                self._draw_stream(n)
            return

        # Frame advanced — update sand geometry only
        d1 = self.displays.display1
        d2 = self.displays.display2

        uy, ut = self._upper_params(frame)
        self._fill_tri_down(d1, uy, ut, self.bg_color)

        if frame > 0:
            n, ly = self._lower_params(frame)
            if ly < 240:
                self._fill_tri_up(d2, n, ly - 1, self.sand_color)
                d2.fill_rect(0, ly - 1, 240, 241 - ly, self.sand_color)
            if self.timer_state == self.STATE_RUNNING and frame < self.TOTAL_FRAMES - 1:
                self._draw_stream(n)

        self.last_frame = frame

    # ── App lifecycle ────────────────────────────────────────────

    async def setup(self):
        # Nuke any ghost pixels left by the previous app
        self.displays.display1.fill(gc9a01.BLACK)
        self.displays.display2.fill(gc9a01.BLACK)
        self._full_redraw()

    async def update(self):
        # Time string updates every second automatically (no flashing —
        # _draw_time only redraws when the string actually changes)
        self._draw_time()

        if self.needs_full_redraw:
            self._full_redraw()
        else:
            self._incremental_update()
            # Keep state label visible (no-op when RUNNING)
            self._draw_state_label()

        await asyncio.sleep(0.1)

    # ── Button actions ───────────────────────────────────────────

    def button_press(self, button):
        # In DONE state every button resets
        if self.timer_state == self.STATE_DONE:
            self._timer_reset()
            return

        if button == self.BTN_A:
            self._adjust_duration(-60)
        elif button == self.BTN_B:
            self._adjust_duration(60)
        elif button == self.BTN_C:
            self._adjust_duration(-3600)
        elif button == self.BTN_D:
            self._adjust_duration(3600)
        elif button == self.BTN_SEL:
            if self.timer_state == self.STATE_IDLE:
                self._timer_start()
            elif self.timer_state == self.STATE_RUNNING:
                self._timer_pause()
            elif self.timer_state == self.STATE_PAUSED:
                self._timer_resume()

    def button_click(self, button):
        """Short press only — not triggered during a long press."""
        if button == self.BTN_LEFT:
            idx = (self.config['hg_bg_idx'] + 1) % self.PAL_COUNT
            self.config['hg_bg_idx'] = idx
            self._apply_colors()
            self.needs_full_redraw = True
        elif button == self.BTN_RIGHT:
            idx = (self.config['hg_sand_idx'] + 1) % self.PAL_COUNT
            self.config['hg_sand_idx'] = idx
            self._apply_colors()
            self.needs_full_redraw = True

    def button_long_press(self, button):
        if button == self.BTN_SEL:
            self._timer_reset()
        elif button == self.BTN_LEFT:
            self._next_clock_color()

    def button_release(self, button):
        pass