"""
Digital Hourglass app for dual-screen devices.

Animation:
  Display1 (upper):
    - Solid sand fills the lower portion
    - A background-colored triangle (funnel) expands downward,
      "draining" the sand.  Sand visible at the sides of the funnel
      is the remaining sand in the upper bulb — this is expected.
  Display2 (lower):
    - A sand-colored triangle (pile) grows upward from the bottom
    - Solid sand fills below the pile triangle
    - Random particle stream trickles down from the top

Button Map:
  0  (A)     : Toggle minute / hour mode
  1  (B)     : Timezone -1 hour
  2  (C)     : Timezone +1 hour
  3  (D)     : Toggle 12-hour / 24-hour (short press)
  4  (LEFT)  : Cycle background color
  5  (RIGHT) : Cycle sand color
  6  (SEL)   : Force NTP re-sync
"""

import asyncio
import time
import gc
import gc9a01
import random
import fonts.arial32px as arial32px

from apps.app import BaseApp

class App(BaseApp):
    """Digital Hourglass — sand drains from display1 into display2."""

    name = "Hourglass"

    # ── Animation ────────────────────────────────────────────────
    TOTAL_FRAMES = 141

    # ── Stream geometry (from original drawSandStream) ───────────
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

    # ── Button numbers ───────────────────────────────────────────
    BTN_A     = 0
    BTN_B     = 1
    BTN_C     = 2
    BTN_D     = 3
    BTN_LEFT  = 4
    BTN_RIGHT = 5
    BTN_SEL   = 6

    # ────────────────────────────────────────────────────────────
    def __init__(self, controller):
        super().__init__(controller)
        self.displays = self.controller.bsp.displays

        # Persistent configuration
        self.config.add('hg_mode',      'minute')  # 'minute' or 'hour'
        self.config.add('hg_bg_idx',    0)         # Black
        self.config.add('hg_sand_idx',  12)        # Sand
        self.config.add('hg_clock_idx', 6)         # Cyan
        self.config.add('hg_tz_offset', -5)        # US-Eastern
        self.config.add('hg_is_24hr',   0)         # 0=12hr, 1=24hr

        # Runtime state
        self.needs_full_redraw   = True
        self.last_frame          = -1
        self.last_minute_tracked = -1
        self.last_time_str       = ""
        self.stream_offset       = 0
        self.last_stream_ms      = time.ticks_ms()
        self.status_msg          = ""
        self.status_expire       = 0

        self._apply_colors()
        random.seed(time.ticks_us())

    # ── Color management ─────────────────────────────────────────

    def _apply_colors(self):
        pc = self.PAL_COUNT
        self.bg_color    = self.PALETTE[self.config['hg_bg_idx']    % pc]
        self.sand_color  = self.PALETTE[self.config['hg_sand_idx']  % pc]
        self.clock_color = self.PALETTE[self.config['hg_clock_idx'] % pc]

    # ── RTC / Time ───────────────────────────────────────────────

    def _rtc(self):
        return self.controller.bsp.rtc.datetime()

    def _local_hr(self, utc_hr):
        return (utc_hr + self.config['hg_tz_offset']) % 24

    def _calc_frame(self):
        """Compute current animation frame (0..TOTAL_FRAMES-1)."""
        t   = self._rtc()
        sec = t[6]
        mn  = t[5]
        if self.config['hg_mode'] == 'minute':
            elapsed = sec * 1000
            total   = 60000
        else:
            elapsed = (mn * 60 + sec) * 1000
            total   = 3600000
        f = elapsed * self.TOTAL_FRAMES // total
        return max(0, min(f, self.TOTAL_FRAMES - 1))

    # ── Geometry (from original drawFrame math) ──────────────────

    def _upper_params(self, frame):
        """(upperY, upperTip) for the draining funnel on display1."""
        return int(frame * 0.9 + 68), int(frame * 1.2 + 90)

    def _lower_params(self, frame):
        """(n, lowerY) for the growing pile on display2."""
        n  = 250 - (frame * 175) // self.TOTAL_FRAMES
        ly = int(n * 0.55 + 105)
        return n, ly

    # ── Triangle drawing ─────────────────────────────────────────

    def _fill_tri_down(self, disp, top_y, tip_y, color):
        """
        Downward-pointing triangle (the funnel).
        Full width at top_y, narrows to point at (120, tip_y).
        Matches: fillTriangle(0, upperY, 240, upperY, 120, upperTip, bg)
        Uses hw*2+1 width for pixel-perfect symmetry around x=120.
        """
        h = tip_y - top_y
        if h <= 0:
            return
        fr = disp.fill_rect
        y0 = max(0, top_y)
        y1 = min(240, tip_y + 1)
        for y in range(y0, y1):
            hw = 128 * (tip_y - y) // h
            x = 120 - hw
            w = hw * 2 + 1
            if x < 0:
                w += x
                x = 0
            if x + w > 240:
                w = 240 - x
            if w > 0:
                fr(x, y, w, 1, color)

    def _fill_tri_up(self, disp, tip_y, base_y, color):
        """
        Upward-pointing triangle (the sand pile).
        Point at (120, tip_y), full width at base_y.
        Matches: fillTriangle(0, lowerY-1, 240, lowerY-1, 120, n, sand)
        """
        h = base_y - tip_y
        if h <= 0:
            return
        fr = disp.fill_rect
        y0 = max(0, tip_y)
        y1 = min(240, base_y + 1)
        for y in range(y0, y1):
            hw = 120 * (y - tip_y) // h
            x = 120 - hw
            w = hw * 2 + 1
            if x < 0:
                w += x
                x = 0
            if x + w > 240:
                w = 240 - x
            if w > 0:
                fr(x, y, w, 1, color)

    # ── Time display (display1 only) ─────────────────────────────

    def _draw_time(self):
        """
        Draw HH:MM [AM/PM] centered at top of display1.
        Only redraws when the formatted string actually changes,
        which prevents the per-second flashing.
        """
        if arial32px is None:
            return
        t  = self._rtc()
        hr = self._local_hr(t[4])
        mn = t[5]
        if self.config['hg_is_24hr']:
            tstr = "{:02d}:{:02d}".format(hr, mn)
        else:
            h12 = hr % 12 or 12
            ap  = "AM" if hr < 12 else "PM"
            tstr = "{:d}:{:02d} {}".format(h12, mn, ap)
        if tstr == self.last_time_str:
            return
        d1 = self.displays.display1
        d1.fill_rect(0, 0, 240, 55, self.bg_color)
        tw = d1.write_len(arial32px, tstr)
        x  = max(0, (240 - tw) // 2)
        d1.write(arial32px, tstr, x, 20, self.clock_color, self.bg_color)
        self.last_time_str = tstr

    # ── Status overlay (display2, temporary) ─────────────────────

    def _set_status(self, msg, ms=2500):
        self.status_msg    = msg
        self.status_expire = time.ticks_ms() + ms

    def _draw_status(self):
        """Draw centered status banner on display2 if active."""
        if not self.status_msg or arial32px is None:
            return
        if time.ticks_diff(self.status_expire, time.ticks_ms()) <= 0:
            self.status_msg = ""
            return
        d2 = self.displays.display2
        tw = d2.write_len(arial32px, self.status_msg)
        x  = max(0, (240 - tw) // 2)
        d2.write(arial32px, self.status_msg, x, 104,
                 gc9a01.WHITE, gc9a01.BLACK)

    # ── Sand stream (display2) ───────────────────────────────────

    def _draw_stream(self, bottom_y):
        """
        Falling sand granules on display2, from y=0 down to the
        pile apex.  Closely matches original drawSandStream().
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

        # Main falling particles (every 8 pixels)
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

        # Splash granules near the pile surface
        for _ in range(5):
            gy  = bottom_y + random.randint(-12, -3)
            gx  = cx + random.randint(-5, 5)
            gr  = random.randint(1, 2)
            gsz = gr * 2 + 1
            if (0 < gy < 240
                    and gx - gr >= cl_x
                    and gx + gr < cl_x + cl_w):
                fr(gx - gr, gy - gr, gsz, gsz, sand)

        # Dust pixels
        for _ in range(3):
            dx = cx + random.randint(-5, 5)
            dy = random.randint(0, max(1, sb - 1))
            if cl_x <= dx < cl_x + cl_w:
                d2.pixel(dx, dy, sand)

    # ── Full redraw ──────────────────────────────────────────────

    def _full_redraw(self):
        """Wipe both screens and paint everything from scratch."""
        d1   = self.displays.display1
        d2   = self.displays.display2
        bg   = self.bg_color
        sand = self.sand_color

        # Clear both displays completely
        d1.fill(bg)
        d2.fill(bg)

        # Force fresh time draw
        self.last_time_str = ""
        self._draw_time()

        frame = self._calc_frame()

        if frame > 0:
            uy, ut = self._upper_params(frame)

            # Solid sand on the lower portion of display1
            if uy < 240:
                d1.fill_rect(0, uy, 240, 240 - uy, sand)
            # Carve out the funnel (bg triangle expanding downward)
            self._fill_tri_down(d1, uy, ut, bg)

            # Sand pile on display2 (triangle growing upward)
            n, ly = self._lower_params(frame)
            if ly < 240:
                self._fill_tri_up(d2, n, ly - 1, sand)
                d2.fill_rect(0, ly - 1, 240, 241 - ly, sand)

            # Particle stream
            if frame < self.TOTAL_FRAMES - 1:
                self._draw_stream(n)
        else:
            # Frame 0: upper display full of sand, no funnel yet
            d1.fill_rect(0, 100, 240, 140, sand)

        self._draw_status()

        self.last_frame        = frame
        self.needs_full_redraw = False
        gc.collect()

    # ── Incremental update ───────────────────────────────────────

    def _incremental_update(self):
        """Update only what changed since the last frame."""
        frame = self._calc_frame()

        # Period wrapped (e.g. second 59 -> 0) — full redraw
        if frame < self.last_frame:
            self._full_redraw()
            return

        # Advance stream animation offset
        now      = time.ticks_ms()
        interval = 400 if self.config['hg_mode'] == 'hour' else 150
        if time.ticks_diff(now, self.last_stream_ms) >= interval:
            self.last_stream_ms = now
            self.stream_offset  = (self.stream_offset + 12) % 240

        # Same frame — just re-animate the stream
        if frame == self.last_frame:
            if 0 < frame < self.TOTAL_FRAMES - 1:
                n, _ = self._lower_params(frame)
                self._draw_stream(n)
                self._draw_status()
            return

        # ── Frame advanced — update sand geometry ──
        d1 = self.displays.display1
        d2 = self.displays.display2

        # Expand funnel on display1
        uy, ut = self._upper_params(frame)
        self._fill_tri_down(d1, uy, ut, self.bg_color)

        # Grow pile on display2
        n, ly = self._lower_params(frame)
        if ly < 240:
            self._fill_tri_up(d2, n, ly - 1, self.sand_color)
            d2.fill_rect(0, ly - 1, 240, 241 - ly, self.sand_color)

        # Stream
        if frame < self.TOTAL_FRAMES - 1:
            self._draw_stream(n)

        self._draw_status()
        self.last_frame = frame

    # ── App lifecycle ────────────────────────────────────────────

    async def setup(self):
        # Nuclear clear to remove ghosts from any previous app
        self.displays.display1.fill(gc9a01.BLACK)
        self.displays.display2.fill(gc9a01.BLACK)
        self._full_redraw()

    async def update(self):
        t  = self._rtc()
        mn = t[5]

        # Detect minute change
        if mn != self.last_minute_tracked:
            self.last_minute_tracked = mn
            if self.config['hg_mode'] == 'minute':
                self.needs_full_redraw = True

        # Expire status message
        if self.status_msg:
            if time.ticks_diff(self.status_expire, time.ticks_ms()) <= 0:
                self.status_msg = ""
                self.needs_full_redraw = True

        # Render
        if self.needs_full_redraw:
            self._full_redraw()
        else:
            self._draw_time()
            self._incremental_update()

        await asyncio.sleep_ms(100)

    # ── Button actions ───────────────────────────────────────────

    def _toggle_mode(self):
        if self.config['hg_mode'] == 'minute':
            self.config['hg_mode'] = 'hour'
            self._set_status("HOUR MODE")
        else:
            self.config['hg_mode'] = 'minute'
            self._set_status("MIN MODE")
        self.needs_full_redraw = True

    def _tz_down(self):
        tz = self.config['hg_tz_offset'] - 1
        if tz < -12:
            tz = 14
        self.config['hg_tz_offset'] = tz
        self.last_time_str = ""
        self._set_status("TZ {:+d}".format(tz))
        self.needs_full_redraw = True

    def _tz_up(self):
        tz = self.config['hg_tz_offset'] + 1
        if tz > 14:
            tz = -12
        self.config['hg_tz_offset'] = tz
        self.last_time_str = ""
        self._set_status("TZ {:+d}".format(tz))
        self.needs_full_redraw = True

    def _next_bg_color(self):
        idx = (self.config['hg_bg_idx'] + 1) % self.PAL_COUNT
        self.config['hg_bg_idx'] = idx
        self._apply_colors()
        self._set_status(self.PAL_NAMES[idx])
        self.needs_full_redraw = True

    def _next_sand_color(self):
        idx = (self.config['hg_sand_idx'] + 1) % self.PAL_COUNT
        self.config['hg_sand_idx'] = idx
        self._apply_colors()
        self._set_status(self.PAL_NAMES[idx])
        self.needs_full_redraw = True

    def _toggle_24hr(self):
        if self.config['hg_is_24hr']:
            self.config['hg_is_24hr'] = 0
            self._set_status("12-HOUR")
        else:
            self.config['hg_is_24hr'] = 1
            self._set_status("24-HOUR")
        self.last_time_str = ""
        self.needs_full_redraw = True

    def _ntp_sync(self):
        try:
            import ntptime
            import network
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                self._set_status("NO WIFI")
                self.needs_full_redraw = True
                return
            self._set_status("SYNCING...")
            ntptime.settime()
            self._set_status("SYNCED!")
        except Exception as e:
            self._set_status("NTP FAIL")
            print("[hourglass] NTP error:", e)
        self.needs_full_redraw = True

    # ── Button dispatch ──────────────────────────────────────────

    def button_press(self, button):
        if button == self.BTN_A:
            self._toggle_mode()
        elif button == self.BTN_B:
            self._tz_down()
        elif button == self.BTN_C:
            self._tz_up()
        elif button == self.BTN_LEFT:
            self._next_bg_color()
        elif button == self.BTN_RIGHT:
            self._next_sand_color()
        elif button == self.BTN_SEL:
            self._ntp_sync()

    def button_click(self, button):
        """Short press D toggles 12/24hr format."""
        if button == self.BTN_D:
            self._toggle_24hr()

    def button_release(self, button):
        pass

    def button_long_press(self, button):
        pass