# Shared design constants for badge UI — clean/minimal style.
# All colors are pre-computed RGB565 integers. No classes, no allocations.

# Colors. These are stored in pre-swapped RGB565 form: framebuf.RGB565 saves
# them little-endian, the gc9a01 driver sends those bytes to the panel, and
# the panel reads them as big-endian. So the constant is the byte-swap of the
# *standard* RGB565 value the panel actually displays. Use `_swap()` if you
# want to express a new color in normal RGB565 notation.
def _swap(c):
    return ((c & 0xFF) << 8) | ((c >> 8) & 0xFF)

BG = 0x0000                    # black — primary background
FG = 0xFFFF                    # white — primary text
ACCENT = _swap(0x04FF)         # teal/cyan — selection highlights, active indicators (= 0xFF04)
ACCENT_DIM = _swap(0x0293)     # darker teal — subtle borders, separators (= 0x9302)
MUTED = _swap(0x7BEF)          # gray — non-selected items, secondary text (= 0xEF7B)
ERROR = _swap(0xF800)          # red — battery low, errors (= 0x00F8)
SUCCESS = _swap(0x07E0)        # green — battery full (= 0xE007)

# Font paths (MicroFont .mfnt files)
FONT_HEADING = "fonts/victor_B_32.mfnt"
FONT_BODY = "fonts/victor_R_24.mfnt"
FONT_SMALL = "fonts/victor_R_18.mfnt"
FONT_TINY = "fonts/victor_R_15.mfnt"

# Spacing
PADDING = 8
PADDING_SMALL = 4
MARGIN = 10
ITEM_HEIGHT = 36
SEPARATOR_HEIGHT = 1

# Circle-safe area — content inset from 240x240 edges to avoid circular bezel clipping
CIRCLE_INSET = 30
SAFE_X = CIRCLE_INSET
SAFE_Y = CIRCLE_INSET
SAFE_WIDTH = 240 - 2 * CIRCLE_INSET   # 180
SAFE_HEIGHT = 240 - 2 * CIRCLE_INSET  # 180
