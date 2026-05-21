import asyncio
from apps.app import BaseApp
import gc9a01
import framebuf

from hardware_rev import HardwareRev
from lib import queue
from lib.microfont import MicroFont
from lib.smart_config import BoolDropdownConfig
from ui.theme import (
    BG, FG, ACCENT, MUTED,
    FONT_HEADING, FONT_BODY,
    PADDING, PADDING_SMALL, ITEM_HEIGHT, SAFE_Y,
)

SELECTED_INDEX = 2
DOWN = 1
UP = -1

class Menu(BaseApp):
    name = "Menu"
    hidden = True

    def __init__(self, controller):
        super().__init__(controller)

        self.title_display = self.controller.bsp.displays.display1
        self.app_selection = self.controller.bsp.displays.display2
        self.display_center_text = self.controller.bsp.displays.display_center_text
        self.display_text = self.controller.bsp.displays.display_text

        self.menu_items = sorted([str(app) for app in self.controller.app_directory if not app.hidden])
        self.selected_index = 0
        self.focus_index = 2
        item_count = len(self.menu_items)
        self.display_items = [self.menu_items[i % item_count] for i in range(self.selected_index - 2, self.selected_index + 4)]

        self.config.add("x_offset", 20)
        self.config.add("y_offset", SAFE_Y)
        self.config.add("animate", BoolDropdownConfig("Animate", default=False))

        self.title_display.fill(BG)
        self.app_selection.fill(BG)

        # Display2 framebuffer for app list. Sized to fit within the 240x240
        # panel from the live offsets — if x_offset + width or y_offset +
        # height exceeds 240, the GC9A01 wraps the write and the text comes
        # out sheared on hardware. The web simulator has no bounds check so
        # it looks fine there regardless. Derive from the live config
        # (not hardcoded) because Config.add uses setdefault, so a badge
        # with a stale Menu.json from a previous default keeps its old
        # x_offset and would still overflow.
        self.fbuf_width = 240 - self.config['x_offset']
        self.fbuf_height = 240 - self.config['y_offset']
        self.fbuf_mem = bytearray(self.fbuf_width * self.fbuf_height * 2)
        self.fbuf = framebuf.FrameBuffer(
            self.fbuf_mem,
            self.fbuf_width,
            self.fbuf_height,
            framebuf.RGB565
        )
        self.fbuf_mv = memoryview(self.fbuf_mem)
        self.font = MicroFont(FONT_BODY, cache_index=True, cache_chars=True)

        # Display1 partial framebuffer for selected app name (center region only)
        self.d1_text_width = 180
        self.d1_text_height = 44
        self.d1_text_mem = bytearray(self.d1_text_width * self.d1_text_height * 2)
        self.d1_text_fbuf = framebuf.FrameBuffer(
            self.d1_text_mem,
            self.d1_text_width,
            self.d1_text_height,
            framebuf.RGB565
        )
        self.d1_text_mv = memoryview(self.d1_text_mem)
        self.d1_font = MicroFont(FONT_HEADING, cache_index=True, cache_chars=True)

        self.queue = queue.Queue(maxsize=10)
        self.index = 0
        self.torn_down = False
        self._dirty = True
        self._last_selected_name = ""

        self._draw_d1_static()

    def _draw_d1_static(self):
        self.title_display.fill(BG)
        # "Menu" heading near top
        self.font.write(
            "Menu",
            memoryview(bytearray(self.d1_text_width * 30 * 2)),
            framebuf.RGB565,
            self.d1_text_width,
            30,
            0, 0, MUTED
        )
        self.display_center_text("Menu", fg=MUTED, bg=BG, display_index=1)

    def _update_d1_selection(self, app_name):
        if app_name == self._last_selected_name:
            return
        self._last_selected_name = app_name

        self.d1_text_fbuf.fill(BG)
        text_w, text_h = self.d1_font.measure(app_name)
        x = max(0, (self.d1_text_width - text_w) // 2)
        y = max(0, (self.d1_text_height - text_h) // 2)
        self.d1_font.write(
            app_name,
            self.d1_text_mv,
            framebuf.RGB565,
            self.d1_text_width,
            self.d1_text_height,
            x, y, FG
        )
        self.title_display.blit_buffer(
            self.d1_text_mv,
            30,  # x offset for circle inset
            98,  # vertically centered
            self.d1_text_width,
            self.d1_text_height
        )

    def put_queue_action(self, direction):
        try:
            self.queue.put_nowait(direction)
        except queue.QueueFull:
            self.queue.get_nowait()
            self.queue.put_nowait(direction)
        self._dirty = True

    async def teardown(self):
        print("[DEBUG] Menu teardown called")
        self.torn_down = True
        self.title_display.fill(BG)
        self.app_selection.fill(BG)
        self.font = None
        self.d1_font = None

    def menu_move_down(self):
        self.put_queue_action(DOWN)

    def menu_move_up(self):
        self.put_queue_action(UP)

    def button_press(self, button: int):
        print(f"Menu button press {button}")
        if self.controller.bsp.hardware_version == HardwareRev.V3:
            if button == 4:
                self.menu_move_down()
            elif button == 5:
                self.menu_move_up()
            elif button == 6:
                asyncio.create_task(self.controller.switch_app(self.display_items[SELECTED_INDEX]))
        else:
            if button == 5:
                self.menu_move_down()
            elif button == 4:
                asyncio.create_task(self.controller.switch_app(self.display_items[SELECTED_INDEX]))

    async def update(self):
        if self.torn_down:
            return

        if not self._dirty and self.queue.empty():
            await asyncio.sleep(0.05)
            return

        x_offset = self.config['x_offset']
        y_offset = self.config['y_offset']
        fbuf_width = self.fbuf_width
        fbuf_height = self.fbuf_height
        fbuf_mv = self.fbuf_mv
        fbuf = self.fbuf
        display = self.controller.bsp.displays.display2
        animate = self.config['animate'].value()

        display_items = self.display_items

        if not self.queue.empty():
            direction = await self.queue.get()
            if animate:
                for i in range(0, ITEM_HEIGHT, 5):
                    self.controller.bsp.displays.display2.blit_buffer(
                        fbuf_mv[fbuf_width*i*2:] if direction == UP else fbuf_mv[:fbuf_width*(fbuf_height - i)*2],
                        x_offset,
                        y_offset,
                        fbuf_width,
                        fbuf_height - i,
                    )
                    await asyncio.sleep(0.01)

            self.selected_index = (self.selected_index + direction) % len(self.menu_items)
            item_count = len(self.menu_items)
            display_items = [self.menu_items[i % item_count] for i in range(self.selected_index - 2, self.selected_index + 4)]

        fbuf.fill(BG)
        for i, item in enumerate(display_items):
            item_y = i * ITEM_HEIGHT
            is_selected = (i == SELECTED_INDEX)
            distance = abs(i - SELECTED_INDEX)

            if is_selected:
                fbuf.rect(0, item_y, fbuf_width, ITEM_HEIGHT, ACCENT, True)
                text_color = BG
            elif distance == 1:
                text_color = FG
            else:
                text_color = MUTED

            self.font.write(
                item,
                fbuf_mv,
                framebuf.RGB565,
                fbuf_width,
                fbuf_height,
                PADDING,
                item_y + PADDING_SMALL,
                text_color
            )

        display.blit_buffer(
            fbuf_mv,
            x_offset,
            y_offset,
            fbuf_width,
            fbuf_height
        )

        self.display_items = display_items
        self._dirty = False

        # Update display1 with selected app name
        self._update_d1_selection(display_items[SELECTED_INDEX])

        self.controller.battery.draw_battery(self.controller.displays.display1, (120-15, 240-60))
