"""Patch microfont.py to replace @micropython.viper draw_ch_blit with pure-Python version.

The Viper version uses ptr8/ptr16 types not available in WASM. This script rewrites
the draw_ch_blit method with a functionally equivalent pure-Python implementation.
"""

import sys
import re

PURE_PYTHON_DRAW_CH_BLIT = '''
    def draw_ch_blit(
        self,
        fb,
        fb_width,
        fb_len,
        ch_buf,
        ch_width,
        ch_height,
        dst_x,
        dst_y,
        off_x,
        off_y,
        color,
        sin_a,
        cos_a,
        colormode
    ):
        color_lo = color & 0xFF
        color_hi = (color >> 8) & 0xFF
        for y in range(ch_height):
            for x in range(ch_width):
                ch_byte = (ch_width >> 3) * y + (x >> 3)
                ch_pixel = (ch_buf[ch_byte] >> (7 - (x & 7))) & 1
                if ch_pixel == 0:
                    continue
                for step in range(2):
                    s = (step << 4) + (step << 3)
                    dx = dst_x + ((((x + off_x) * 64 + s) * cos_a - ((y + off_y) * 64 + s) * sin_a + 2048) >> 12)
                    dy = dst_y + ((((x + off_x) * 64 + s) * sin_a + ((y + off_y) * 64 + s) * cos_a + 2048) >> 12)
                    if colormode == 0:  # MONO_HLSB
                        fb_byte = (dy * fb_width + dx) >> 3
                        if fb_byte < 0 or fb_byte >= fb_len or dx >= fb_width or dx < 0:
                            continue
                        fb_bit_shift = 7 - (dx & 7)
                        fb_bit_mask = 0xFF ^ (1 << fb_bit_shift)
                        fb[fb_byte] = (fb[fb_byte] & fb_bit_mask) | (color << fb_bit_shift)
                    elif colormode == 1:  # RGB_565
                        fb_word = dy * fb_width + dx
                        if fb_word < 0 or fb_word >= (fb_len >> 1) or dx >= fb_width or dx < 0:
                            continue
                        byte_off = fb_word * 2
                        fb[byte_off] = color_lo
                        fb[byte_off + 1] = color_hi
'''


def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Remove the @micropython.viper decorator
    content = content.replace('@micropython.viper\n', '')

    # Replace the draw_ch_blit method
    # Match from "    def draw_ch_blit(" to the next method at the same indentation
    pattern = r'(    def draw_ch_blit\(.*?\n)(.*?)(?=\n    def |\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        before = content[:match.start()]
        after = content[match.end():]
        content = before + PURE_PYTHON_DRAW_CH_BLIT + after
        print(f"  Patched draw_ch_blit in {filepath}")
    else:
        print(f"  Warning: Could not find draw_ch_blit in {filepath}")

    # Remove @micropython.native decorators too
    content = content.replace('@micropython.native\n', '')

    with open(filepath, 'w') as f:
        f.write(content)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <microfont.py path>")
        sys.exit(1)
    patch_file(sys.argv[1])
