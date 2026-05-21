import emulator

FAST = 0
SLOW = 1
RED = 63488
GREEN = 2016
BLUE = 31
CYAN = 2047
BLACK = 0
MAGENTA = 63519
WHITE = 65535
YELLOW = 65504


def color565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


class GC9A01:
    def __init__(self, spi, width, height, reset, cs, dc, rotation, options=0, buffer_size=0):
        self._width = width
        self._height = height
        self.width = lambda: self._width
        self.height = lambda: self._height
        self.rotation = rotation
        if dc.pin == 19:
            self.display = 1
        else:
            self.display = 2

    def init(self):
        pass

    def fill(self, color):
        emulator.send_fill(self.display, color)

    def off(self):
        pass

    def on(self):
        pass

    def pixel(self, x, y, color):
        emulator.send_pixel(self.display, x, y, color)

    def circle(self, x, y, r, color):
        emulator.send_circle(self.display, x, y, r, color, filled=False)

    def fill_circle(self, x, y, r, color):
        emulator.send_circle(self.display, x, y, r, color, filled=True)

    def fill_rect(self, x, y, w, h, color):
        emulator.send_fill_rect(self.display, x, y, w, h, color)

    def line(self, x0, y0, x1, y1, color):
        emulator.send_line(self.display, x0, y0, x1, y1, color)

    def _char_metrics(self, font):
        ch = getattr(font, 'HEIGHT', 32)
        if hasattr(font, 'WIDTH'):
            cw = font.WIDTH
        else:
            cw = int(ch * 0.55)
        return cw, ch

    def _font_short_name(self, font):
        # The JS atlas table is keyed by the bare module name (e.g. 'vga1_bold_16x32').
        name = getattr(font, '__name__', '') or ''
        return name.rsplit('.', 1)[-1]

    def _draw_text(self, font, string, x, y, fg_color, bg_color):
        if not string:
            return
        # Variable-width Arial-style fonts: render in Python from the embedded
        # bitmap data, then blit via the framebuf path (which has the correct
        # byte order). The JS atlas path can't handle variable widths.
        if hasattr(font, '_BITMAPS'):
            self._render_glyphmap(font, string, x, y, fg_color, bg_color)
            return

        # Fixed-width VGA-style fonts: pass the module name to JS so it can
        # blit glyphs from the PNG atlas. The JS side falls back to canvas
        # text if the atlas isn't registered.
        cw, ch = self._char_metrics(font)
        emulator.send_text(
            self.display, string, x, y, fg_color, bg_color,
            cw, ch, self._font_short_name(font)
        )

    def write(self, font, string, x, y, fg_color, bg_color):
        self._draw_text(font, string, x, y, fg_color, bg_color)

    def text(self, font, string, x, y, fg_color, bg_color):
        self._draw_text(font, string, x, y, fg_color, bg_color)

    def write_len(self, font, string):
        if hasattr(font, '_WIDTHS') and hasattr(font, 'MAP'):
            total = 0
            widths = font._WIDTHS
            mp = font.MAP
            for ch in string:
                idx = mp.find(ch)
                if idx >= 0 and idx < len(widths):
                    total += widths[idx]
                else:
                    total += getattr(font, 'MAX_WIDTH', 0)
            return total
        cw, _ = self._char_metrics(font)
        return len(string) * cw

    def _render_glyphmap(self, font, string, x, y, fg_color, bg_color):
        # Russ-Hughes-style variable-width font: MAP, _BITMAPS, _WIDTHS, _OFFSETS, BPP, HEIGHT.
        # _BITMAPS is a continuous 1bpp bitstream (MSB-first). _OFFSETS gives the
        # starting *bit* position of each glyph (big-endian, OFFSET_WIDTH bytes per entry).
        # Each glyph occupies WIDTH bits per row * HEIGHT rows of consecutive bits.
        height = font.HEIGHT
        bpp = getattr(font, 'BPP', 1)
        if bpp != 1:
            cw, ch = self._char_metrics(font)
            emulator.send_text(
                self.display, string, x, y, fg_color, bg_color,
                cw, ch, self._font_short_name(font)
            )
            return

        mp = font.MAP
        widths = font._WIDTHS
        offsets = font._OFFSETS
        bitmaps = font._BITMAPS
        ow = getattr(font, 'OFFSET_WIDTH', 2)

        glyph_widths = []
        glyph_bit_offsets = []
        for ch in string:
            idx = mp.find(ch)
            if idx < 0:
                glyph_widths.append(0)
                glyph_bit_offsets.append(0)
                continue
            glyph_widths.append(widths[idx])
            o = 0
            for b in range(ow):
                o = (o << 8) | offsets[idx * ow + b]
            glyph_bit_offsets.append(o)
        total_w = sum(glyph_widths)
        if total_w <= 0:
            return

        # framebuf.RGB565 stores uint16 little-endian (lo byte first). displayBlitBuffer
        # reads bytes big-endian — matches the badge's wire format.
        # Write each pixel as big-endian RGB565 ([HI, LO]) so the byte-swap in
        # displayBlitBuffer recovers the intended color (matches the badge's
        # display.text path which writes BE color bytes to the panel).
        fg_lo = fg_color & 0xFF
        fg_hi = (fg_color >> 8) & 0xFF
        bg_lo = bg_color & 0xFF
        bg_hi = (bg_color >> 8) & 0xFF

        buf = bytearray(total_w * height * 2)
        for i in range(0, len(buf), 2):
            buf[i] = bg_hi
            buf[i + 1] = bg_lo

        dst_col = 0
        for gi in range(len(string)):
            gw = glyph_widths[gi]
            if gw == 0:
                continue
            bit_off = glyph_bit_offsets[gi]
            for row in range(height):
                row_bit = bit_off + row * gw
                for col in range(gw):
                    bp = row_bit + col
                    if (bitmaps[bp >> 3] >> (7 - (bp & 7))) & 1:
                        px = ((dst_col + col) + row * total_w) * 2
                        buf[px] = fg_hi
                        buf[px + 1] = fg_lo
            dst_col += gw

        emulator.send_blit_buffer(self.display, buf, x, y, total_w, height)

    def jpg(self, filename, x, y, mode):
        pass

    def blit_buffer(self, buffer, x, y, width, height):
        emulator.send_blit_buffer(self.display, buffer, x, y, width, height)
