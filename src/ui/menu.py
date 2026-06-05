import framebuf

from lib.microfont import MicroFont
from ui.widget import Widget
from ui.theme import (
    BG, FG, ACCENT, MUTED,
    FONT_BODY,
    PADDING, PADDING_SMALL, ITEM_HEIGHT, SAFE_WIDTH,
)

# Button actions for on_button_press(). Apps map their physical buttons to
# these; the widget itself is hardware-agnostic.
UP = 0
DOWN = 1
SELECT = 2
BACK = 3


class TextMenuWidget(Widget):
    """Scrolling selection menu styled like the app launcher.

    Renders a vertical window of items with the launcher's look (see
    apps/menu.py): an accent highlight bar behind the selected row,
    full-brightness text for the immediately adjacent rows, and muted text
    further away. The window scrolls to keep the selection centred, clamping
    at the ends of the list.

    Backed by a possibly-nested ``dict`` (or ``list``): selecting a key that
    maps to another dict/list descends into a sub-menu, and selecting a leaf
    value invokes the ``on_select(path, value)`` callback. ``back()`` returns
    to the parent level.
    """

    def __init__(
            self,
            items,
            title: str = "",
            path: list | None = None,
            on_select=None,
            width: int = SAFE_WIDTH,
            visible_items: int = 5,
            wrap: bool = False,
            center: bool = False,
            buffer=None,
            back_label: str = "",
            name: str = "",
        ):
        super().__init__(name)
        if not isinstance(items, (dict, list)):
            raise ValueError("TextMenuWidget requires a dict or list of items")

        self.items = items
        self.title = title
        self.on_select = on_select
        self.width = width
        self.visible_items = visible_items
        # When set, a synthetic row with this label is shown at the top of any
        # sub-menu (i.e. whenever path is non-empty). Selecting it calls back(),
        # so a menu needs no dedicated back button. The row is not part of the
        # backing data — selected indices are mapped past it internally.
        self.back_label = back_label
        self._has_back = False
        # Text is drawn via MicroFont.write(), whose viper blit assigns into
        # the target with ptr8 item assignment. A framebuf.FrameBuffer does
        # NOT support that on this firmware, so callers that want text must
        # pass the writable buffer (the memoryview/bytearray backing the
        # FrameBuffer they render into). The FrameBuffer passed to render() is
        # still used for the highlight rect via .rect(). When buffer is None we
        # fall back to the FrameBuffer, matching the rest of the ui/ library.
        self.buffer = buffer
        # Vertical behaviour, in order of precedence:
        #  - wrap:   infinite carousel; selection fixed in the centre row, ends
        #            join up (the app launcher's look). Best for long lists.
        #  - center: selection fixed in the centre row but the ends DON'T wrap —
        #            blank rows appear above the first / below the last item.
        #            Best for short menus on the round display (nothing clips at
        #            the top/bottom and short lists don't show duplicates).
        #  - neither: the window scrolls and clamps at the ends.
        self.wrap = wrap
        self.center = center

        # One body font shared between the title header and the rows.
        self.font = MicroFont(FONT_BODY, cache_index=True, cache_chars=True)

        self.highlight_color = ACCENT
        self.selected_text_color = BG
        self.near_color = FG
        self.far_color = MUTED
        self.title_color = MUTED

        # Navigation state. ``path`` is the chain of keys descended into;
        # ``selected_index`` is the cursor within the current level; the index
        # stack remembers the cursor at each parent level so back() restores
        # it. Invariant: len(self._index_stack) == len(self.path).
        self.path = list(path) if path else []
        self.selected_index = 0
        self._index_stack = [0] * len(self.path)

        self._labels = []
        self._refresh()

    # --- data helpers ---------------------------------------------------

    def _node_at_path(self):
        node = self.items
        for key in self.path:
            if isinstance(node, dict):
                if key not in node:
                    raise ValueError("Key {} not found in items".format(key))
                node = node[key]
            elif isinstance(node, list):
                node = node[key]
            else:
                raise ValueError("Path descends into a non-container value")
        return node

    def _refresh(self):
        """Recompute the selectable labels for the current level and clamp
        the cursor into range. Dict keys are sorted (matching the launcher's
        sorted app list); list order is preserved so indices stay valid. When
        back_label is set and we're inside a sub-menu, a synthetic back row is
        prepended as index 0."""
        node = self._node_at_path()
        if isinstance(node, dict):
            labels = sorted(node.keys())
        elif isinstance(node, list):
            labels = [str(v) for v in node]
        else:
            # Leaf reached directly via the initial path: show it read-only.
            labels = [str(node)]

        self._has_back = bool(self.back_label) and len(self.path) > 0
        self._labels = [self.back_label] + labels if self._has_back else labels

        if self.selected_index >= len(self._labels):
            self.selected_index = max(0, len(self._labels) - 1)

    def _on_back_row(self) -> bool:
        return self._has_back and self.selected_index == 0

    def _data_index(self) -> int:
        """Cursor position within the backing node, skipping the back row."""
        return self.selected_index - (1 if self._has_back else 0)

    def _selected_entry(self):
        """Return (key, value) for the current selection, or (None, None) for
        the back row / an empty level. ``key`` is a dict key or a list index."""
        if not self._labels or self._on_back_row():
            return None, None
        node = self._node_at_path()
        di = self._data_index()
        if isinstance(node, dict):
            key = sorted(node.keys())[di]
            return key, node[key]
        if isinstance(node, list):
            return di, node[di]
        return None, node

    @property
    def selected_label(self) -> str:
        if not self._labels:
            return ""
        return self._labels[self.selected_index]

    # --- navigation -----------------------------------------------------

    def move_up(self):
        n = len(self._labels)
        if not n:
            return
        if self.wrap:
            self.selected_index = (self.selected_index - 1) % n
        elif self.selected_index > 0:
            self.selected_index -= 1

    def move_down(self):
        n = len(self._labels)
        if not n:
            return
        if self.wrap:
            self.selected_index = (self.selected_index + 1) % n
        elif self.selected_index < n - 1:
            self.selected_index += 1

    def select(self):
        """Activate the current row: the back row returns to the parent, a
        non-empty container descends into a sub-menu, and a leaf fires
        on_select with its value."""
        if self._on_back_row():
            self.back()
            return
        key, value = self._selected_entry()
        if key is None:
            return
        if isinstance(value, (dict, list)) and value:
            self._index_stack.append(self.selected_index)
            self.path.append(key)
            self.selected_index = 0
            self._refresh()
            # Land on the first real item rather than the back row.
            if self._has_back:
                self.selected_index = 1
        elif self.on_select:
            self.on_select(self.path + [key], value)

    def back(self):
        """Return to the parent level, restoring its cursor position. Returns
        True if it moved up a level, False if already at the root."""
        if not self.path:
            return False
        self.path.pop()
        self.selected_index = self._index_stack.pop() if self._index_stack else 0
        self._refresh()
        return True

    def on_button_press(self, button_index):
        if button_index == UP:
            self.move_up()
        elif button_index == DOWN:
            self.move_down()
        elif button_index == SELECT:
            self.select()
        elif button_index == BACK:
            self.back()

    # --- rendering ------------------------------------------------------

    def _window_start(self):
        """First visible row index, centred on the selection but clamped so
        the window never runs past either end of the list."""
        n = len(self._labels)
        if n <= self.visible_items:
            return 0
        start = self.selected_index - self.visible_items // 2
        if start < 0:
            return 0
        if start > n - self.visible_items:
            return n - self.visible_items
        return start

    def _draw_row(self, label, x, row_y, distance, fbuf, text_target, fbuf_width, fbuf_height):
        """Render one row: an accent highlight bar with inverted text when
        selected (distance 0), bright text for the immediate neighbours, and
        muted text further out. The bar is drawn into the FrameBuffer (fbuf);
        the text into text_target (see __init__ on why they differ)."""
        if distance == 0:
            fbuf.rect(x, row_y, self.width, ITEM_HEIGHT, self.highlight_color, True)
            color = self.selected_text_color
        elif distance == 1:
            color = self.near_color
        else:
            color = self.far_color

        self.font.write(
            label,
            text_target,
            framebuf.RGB565,
            fbuf_width,
            fbuf_height,
            x + PADDING,
            row_y + PADDING_SMALL,
            color,
        )

    def render(
            self,
            x: int,
            y: int,
            fbuf: framebuf.FrameBuffer,
            fbuf_width: int = 240,
            fbuf_height: int = 240,
        ):
        self._refresh()
        start_y = y
        text_target = self.buffer if self.buffer is not None else fbuf

        if self.title:
            tw, _ = self.font.measure(self.title)
            self.font.write(
                self.title,
                text_target,
                framebuf.RGB565,
                fbuf_width,
                fbuf_height,
                x + max(0, (self.width - tw) // 2),
                y + PADDING_SMALL,
                self.title_color,
            )
            y += ITEM_HEIGHT

        n = len(self._labels)
        if n == 0:
            return self.width, y - start_y

        if self.wrap:
            # Carousel: selection fixed in the centre slot, ends joined up.
            above = (self.visible_items - 1) // 2
            for slot in range(self.visible_items):
                i = (self.selected_index - above + slot) % n
                self._draw_row(
                    self._labels[i], x, y + slot * ITEM_HEIGHT,
                    abs(slot - above), fbuf, text_target, fbuf_width, fbuf_height,
                )
            y += self.visible_items * ITEM_HEIGHT
        elif self.center:
            # Selection fixed in the centre slot, but no wrap: rows that fall
            # outside the list are left blank instead of looping.
            above = (self.visible_items - 1) // 2
            for slot in range(self.visible_items):
                i = self.selected_index - above + slot
                if 0 <= i < n:
                    self._draw_row(
                        self._labels[i], x, y + slot * ITEM_HEIGHT,
                        abs(slot - above), fbuf, text_target, fbuf_width, fbuf_height,
                    )
            y += self.visible_items * ITEM_HEIGHT
        else:
            start = self._window_start()
            end = min(n, start + self.visible_items)
            for i in range(start, end):
                self._draw_row(
                    self._labels[i], x, y + (i - start) * ITEM_HEIGHT,
                    abs(i - self.selected_index), fbuf, text_target, fbuf_width, fbuf_height,
                )
            y += (end - start) * ITEM_HEIGHT

        return self.width, y - start_y
