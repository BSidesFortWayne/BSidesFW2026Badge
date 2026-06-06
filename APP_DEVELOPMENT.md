# Developing Apps for the BSidesFW 2025 Badge

This is an in-depth guide for writing apps that run on the badge. It covers the
mental model, the `BaseApp` lifecycle, every piece of hardware the controller
exposes, the configuration system, drawing patterns, async behavior, and how to
iterate using the web/desktop simulators and `mpremote`.

If you just want a "hello world" template, jump to [Minimum Viable App](#minimum-viable-app). If you want to understand what's going on under the hood
before writing anything, read [Mental Model](#mental-model) first.

---

## Table of Contents

1. [Mental Model](#mental-model)
2. [Project Layout](#project-layout)
3. [Minimum Viable App](#minimum-viable-app)
4. [The `BaseApp` Lifecycle](#the-baseapp-lifecycle)
5. [The Controller and BSP](#the-controller-and-bsp)
6. [Displays](#displays)
7. [Colors (RGB565)](#colors-rgb565)
8. [Fonts](#fonts)
9. [Reusable Menu Widget (`TextMenuWidget`)](#reusable-menu-widget-textmenuwidget)
10. [Buttons](#buttons)
11. [LEDs (NeoPixel)](#leds-neopixel)
12. [Audio / Speaker](#audio--speaker)
13. [IMU / Accelerometer](#imu--accelerometer)
14. [Bluetooth (Broadcast Mesh)](#bluetooth-broadcast-mesh)
15. [RTC and Time](#rtc-and-time)
16. [Battery](#battery)
17. [SmartConfig — App Settings](#smartconfig--app-settings)
18. [Multiple Apps per File, Hidden Apps](#multiple-apps-per-file-hidden-apps)
19. [Async and the Update Loop](#async-and-the-update-loop)
20. [Running Standalone (`single_app_runner`)](#running-standalone-single_app_runner)
21. [Iterating in the Web Simulator](#iterating-in-the-web-simulator)
22. [Iterating in the Desktop Simulator](#iterating-in-the-desktop-simulator)
23. [Deploying to Hardware (`mpremote`)](#deploying-to-hardware-mpremote)
24. [Performance Tips](#performance-tips)
25. [Common Pitfalls](#common-pitfalls)

---

## Mental Model

The badge runs MicroPython on an ESP32-WROVER-E with 8 MiB PSRAM and 8 MiB
flash. The runtime starts a single `Controller` (`src/controller.py`) which:

- Owns the **BSP** (Board Support Package) — a singleton that exposes every
  piece of hardware (`displays`, `buttons`, `leds`, `imu`, `speaker`,
  `bluetooth`, `rtc`, `i2c`).
- Maintains an **AppDirectory** — a cache of every `BaseApp` subclass found in
  `src/apps/`.
- Runs a single async loop that calls `current_view.update()` every ~10 ms and
  routes button events to the active app.

There is **one app running at a time**. Switching apps tears the previous one
down and constructs a new one. Apps don't allocate their own hardware — they
poke at properties of the controller.

The minimum contract for an app is: subclass `BaseApp`, set a `name`, and
optionally implement any of `setup` / `update` / `teardown` and the four
button hooks.

---

## Project Layout

```
src/
├── apps/                  ← every .py here is auto-discovered as an app
│   ├── app.py             ← BaseApp lives here (do not place new apps here)
│   ├── __init__.py        ← do not place new apps here
│   ├── analog_clock.py    ← reference: SmartConfig + framebuffer + RTC
│   ├── tetris.py          ← reference: gameplay, audio, framebuffer
│   ├── level.py           ← reference: IMU + MicroFont
│   ├── battery_monitor.py ← reference: battery + theme constants
│   ├── hello_world_app.py ← reference: bare minimum
│   └── ...
├── controller.py          ← Controller / async run loop / app routing
├── bsp.py                 ← BSP: aggregates all hardware drivers
├── icontroller.py         ← IController / IApp interfaces
├── app_directory.py       ← scans apps/, caches metadata to config/
├── single_app_runner.py   ← run one app from `__main__` for hardware testing
├── drivers/               ← displays, buttons, leds, audio, imu, bluetooth
├── ui/                    ← theme constants, widgets, layouts
├── lib/                   ← smart_config, microfont, battery, dns, microdot
├── fonts/                 ← .mfnt MicroFont files + vga*.py bitmap fonts
└── img/                   ← .jpg assets shipped to the badge
```

The auto-discovery rule: `AppDirectory.from_module` (`app_directory.py:25`)
imports each file in `src/apps/` and finds every class that
`issubclass(BaseApp)` and `!= BaseApp`. The class's `name` attribute is what
shows up in the menu — the filename is just a module identifier.

Files in `apps/` that aren't apps (e.g. `apps/__init__.py`, `apps/app.py`) are
listed in `AppDirectory.ignore_app_files`.

---

## Minimum Viable App

`src/apps/my_app.py`:

```python
from apps.app import BaseApp
import gc9a01

class App(BaseApp):
    name = "My App"
    version = "0.0.1"

    def __init__(self, controller):
        super().__init__(controller)
        self.controller.bsp.displays.display1.fill(gc9a01.BLUE)
        self.controller.bsp.displays.display_center_text("Hello!")
```

That's it. After dropping this file into `src/apps/`, it appears in the menu
as "My App". On next launch, `AppDirectory` detects the new file (by hashing
it), re-parses the module, and persists the result to
`config/app_directory_cache.json` so subsequent boots are fast.

> ⚠️ **`name` is the menu label, not the class name.** The controller looks up
> apps by `name`. Two apps with the same `name` will collide.

---

## The `BaseApp` Lifecycle

`BaseApp` is defined in `src/apps/app.py`. The full surface:

```python
class BaseApp:
    name = ""             # required: menu label, also used as the config filename
    version = "0.0.1"     # informational
    hidden = False        # if True, hidden from the menu (used for system apps like Menu)

    def __init__(self, controller: IController): ...
    async def setup(self): ...          # called once after construction
    async def teardown(self): ...       # called when switching away from this app
    async def update(self): ...         # called every ~10 ms by the main loop
    def button_press(self, button): ... # synchronous, runs from the button IRQ-ish path
    def button_click(self, button): ... # release without a long press
    def button_release(self, button): ...
    def button_long_press(self, button): ... # fired at ~750 ms while still held
```

### Order of operations when an app is opened

1. `Controller.switch_app(name)` calls `teardown()` on the previous app.
2. A new instance is constructed: `app.constructor(controller)` —
   `__init__` runs here.
3. `await setup()` runs.
4. The main loop starts calling `await update()` until the app is replaced.

`__init__` is synchronous; if you need to `await` anything (e.g. lazy file I/O,
network), do it in `setup`. If you do work in `__init__` that blocks for more
than a frame, you'll see a visible stutter when switching apps.

### Update loop

`Controller.run` (`controller.py:134`) does:

```python
while True:
    async with self.current_app_lock:
        if self.current_view:
            await self.current_view.update()
    for service in self.services:
        await service.update()
    await asyncio.sleep(0.01)
```

So `update()` runs as fast as it can, capped at ~100 Hz by the trailing
`asyncio.sleep(0.01)`. **The lock around `current_view.update()` is held for
the entire call**, so other tasks (e.g. button handlers that call
`switch_app`) will queue behind a slow update. Don't block in `update()`.

### Button callbacks

These are called by the buttons driver, not from `update()`. The exact path:

1. `drivers/buttons.py` polls the PCA9535 every 50 ms via `Timer(3)`.
2. On a state change, it walks `button_pressed_callbacks` /
   `button_released_callbacks` / etc.
3. The controller is registered into those lists in `controller.py:88-92`. The
   controller forwards to `self.current_view.button_press(...)`.

Button callbacks are **synchronous**. If you need to do async work in response,
do `asyncio.create_task(self.do_stuff())`. Don't `await` in a button callback —
it will silently no-op since the callback isn't a coroutine.

`button_long_press(3)` is reserved by the controller — it switches back to the
"Menu" app. Your `button_long_press` is still called first, but if you return
without consuming the event the menu will open over you. There's no consume
API; if you need to override this, you're responsible for putting yourself
back into focus.

---

## The Controller and BSP

Every app receives a `controller: IController` in `__init__`. Useful
properties:

| Path | What it is |
|------|------------|
| `controller.bsp` | BSP singleton (all hardware) |
| `controller.bsp.displays` | `Displays` driver (both 240x240 panels) |
| `controller.bsp.displays.display1` / `display2` | The two `GC9A01` panels |
| `controller.bsp.buttons` | `Buttons` driver, mostly for state inspection |
| `controller.bsp.leds` | `LEDs` driver wrapping the NeoPixel chain |
| `controller.bsp.imu` | `LIS3DH_I2C` accelerometer driver |
| `controller.bsp.speaker` | `Speaker` driver (PWM piezo) |
| `controller.bsp.bluetooth` | `Bluetooth` driver |
| `controller.bsp.rtc` | `machine.RTC()` |
| `controller.bsp.i2c` | Raw `I2C(1, ...)` if you need to talk to the bus |
| `controller.bsp.hardware_version` | Hardware rev string (V3 in production) |
| `controller.battery` | `lib.battery.Battery` instance |
| `controller.name` | Loaded contents of `name.json` |
| `controller.neopixel` | Backwards-compat alias for `bsp.leds.leds` |
| `controller.displays` | Backwards-compat alias for `bsp.displays` |

For convenience, many reference apps cache common paths in `__init__`:

```python
self.display1 = self.controller.bsp.displays.display1
self.display2 = self.controller.bsp.displays.display2
```

This is mostly a perf micro-optimization — attribute lookup in MicroPython is
not free.

---

## Displays

Two circular 240×240 SPI panels driven by the C `gc9a01` module. Both share
the SPI bus; the driver handles chip-select switching.

### Drawing directly

`display1` and `display2` are `GC9A01` instances. The most common calls:

```python
display.fill(color)
display.pixel(x, y, color)
display.line(x0, y0, x1, y1, color)
display.rect(x, y, w, h, color)
display.fill_rect(x, y, w, h, color)
display.circle(cx, cy, r, color)
display.fill_circle(cx, cy, r, color)
display.text(font, text, x, y, fg, bg)   # bitmap fonts only (vga*)
display.write(font, text, x, y, fg, bg)  # also bitmap fonts
display.jpg(path, x, y, gc9a01.FAST)     # JPEG from filesystem
display.blit_buffer(buf, x, y, w, h)     # push a RGB565 framebuffer
```

Both panels are **circular** — coordinates `(0,0)` to `(239,239)` exist but
anything within `CIRCLE_INSET=30` of the corners is clipped by the bezel. Use
the `SAFE_X`/`SAFE_Y`/`SAFE_WIDTH`/`SAFE_HEIGHT` constants from
`ui.theme` for safe content positioning.

### Direct-draw vs framebuffer

Direct calls to `display.fill_rect`, `display.line` etc. issue SPI writes
**immediately**. That's fine for static screens or small partial updates, but
for animation you'll see tearing and slow frame rates.

The fast path for animation is:

1. Allocate a `framebuf.FrameBuffer` over a `bytearray(240*240*2)` (RGB565 = 2
   bytes/pixel = 115,200 bytes per panel).
2. Draw into the framebuffer using `framebuf` methods.
3. Push the whole thing with `display.blit_buffer(mv, 0, 0, 240, 240)`.

Tetris (`apps/tetris.py:70-77`) and the analog clock
(`apps/analog_clock.py:62-68`) both do this. Hold a `memoryview` of the
buffer so the per-blit allocation is zero:

```python
self.fbuf_mem = bytearray(240 * 240 * 2)
self.fbuf_mv = memoryview(self.fbuf_mem)
self.fbuf = framebuf.FrameBuffer(
    self.fbuf_mem, 240, 240, framebuf.RGB565
)
# ... later
self.fbuf.fill(BG)
self.fbuf.line(...)
display1.blit_buffer(self.fbuf_mv, 0, 0, 240, 240)
```

A single full-screen blit at 80 MHz SPI is ~3 ms per panel — the bottleneck for
animation will almost always be your drawing code, not the bus.

For partial redraws, allocate a smaller framebuffer:

```python
self.d1_text_width = 180
self.d1_text_height = 44
self.d1_text_mem = bytearray(self.d1_text_width * self.d1_text_height * 2)
self.d1_text_fbuf = framebuf.FrameBuffer(
    self.d1_text_mem, self.d1_text_width, self.d1_text_height, framebuf.RGB565
)
# blit at a specific offset
display1.blit_buffer(self.d1_text_mv, x_off, y_off, self.d1_text_width, self.d1_text_height)
```

### Center-text helper

`Displays.display_center_text(text, fg, bg, display_index, font)` does
boilerplate text centering across either panel.
`Displays.display_text(text, x, y, fg, bg, display_index, font)` is the same
without the centering math.

---

## Colors (RGB565)

The displays speak RGB565 — 5 bits red, 6 bits green, 5 bits blue, packed
into a 16-bit big-endian word on the wire.

There are **two distinct namespaces** you'll see in the code:

1. **`gc9a01.BLACK`, `gc9a01.RED`, …** — colors as expected by the `gc9a01`
   C driver's `fill`, `line`, etc. when calling on `display.*` directly.
2. **`displays.COLOR_LOOKUP['fbuf']['red']`** — colors swapped to little-endian
   to be correct after `framebuf.RGB565` writes them (the panel sees them
   big-endian on the wire). Use these when drawing into a `FrameBuffer`.

The cheat sheet:

```python
import gc9a01
from drivers.displays import rgb  # tuple -> packed RGB565 for the C driver

# Drawing directly on the display:
display1.fill(gc9a01.BLACK)
display1.fill_rect(0, 0, 10, 10, gc9a01.color565(255, 0, 0))

# Drawing into a FrameBuffer:
from drivers.displays import Displays
fbuf.fill(Displays.COLOR_LOOKUP['fbuf']['black'])
fbuf.fill_rect(0, 0, 10, 10, rgb((255, 0, 0)))
```

For consistent styling, use the constants from `ui/theme.py`:

```python
from ui.theme import BG, FG, ACCENT, MUTED, ERROR, SUCCESS, SAFE_X, SAFE_Y
```

These are already pre-swapped to work correctly with `framebuf.RGB565`. The
`_swap()` helper in `theme.py` shows the relationship if you want to add new
named colors.

---

## Fonts

Two font systems coexist:

### `vga*` bitmap fonts (C-backed)

Fixed-width, fast, only ASCII. Used with `display.text(font, ...)` and
`display.write(font, ...)`.

```python
import vga1_bold_16x32 as font
import vga2_8x16 as font_small
display1.text(font, "Hello", 50, 100, gc9a01.WHITE, gc9a01.BLACK)
```

Each font module exposes `WIDTH`, `HEIGHT`, and a `FONT` byte string. Width
times string length gives you pixel width for centering. These are imported
from the badge's frozen modules — they ship with the firmware.

### MicroFont `.mfnt` files (variable-width)

For richer typography, use `lib/microfont.py` with the prebuilt `.mfnt` files
in `fonts/`. These render into a `FrameBuffer` (or directly to a bytearray
backing one):

```python
from lib.microfont import MicroFont
from ui.theme import FONT_BODY, FG

self.font = MicroFont(FONT_BODY, cache_index=True, cache_chars=True)

self.font.write(
    "Hello",            # text
    self.fbuf_mv,       # destination memoryview
    framebuf.RGB565,    # format
    self.fbuf_width,    # buffer width
    self.fbuf_height,   # buffer height
    x, y,               # position
    FG                  # color (already swapped if from theme)
)
```

`cache_index=True` keeps the font's glyph table in memory (faster lookups,
~few KB). `cache_chars=True` caches rendered glyphs — much faster on repeated
text at the cost of more RAM.

The theme exposes four standard sizes: `FONT_HEADING` (32px Bold), `FONT_BODY`
(24px Regular), `FONT_SMALL` (18px Regular), `FONT_TINY` (15px Regular).

> ⚠️ The MicroFont module uses `@micropython.viper` on hardware. The web
> simulator's build step patches this out for pure-Python fallback. If you're
> doing something exotic, prefer to test on hardware too.

---

## Reusable Menu Widget (`TextMenuWidget`)

If your app needs a scrolling, selectable list, don't hand-roll it — use
`ui.menu.TextMenuWidget`. It's the same widget the app launcher
(`apps/menu.py`) renders: an accent highlight bar on the selected row,
full-brightness text for the immediate neighbours, muted text further out, and
a window that scrolls to keep the selection in view.

### The pattern

Build the widget once in `__init__`, render it into a framebuffer each frame,
and route button presses to it.

```python
import framebuf
from apps.app import BaseApp
from ui.menu import TextMenuWidget
from ui.theme import BG, SAFE_X, SAFE_WIDTH

class App(BaseApp):
    name = "My Menu"
    version = "0.0.1"

    def __init__(self, controller):
        super().__init__(controller)
        self.display = self.controller.bsp.displays.display2

        # One framebuffer + its memoryview (they back the same bytes).
        self.fbuf_mem = bytearray(240 * 240 * 2)
        self.fbuf = framebuf.FrameBuffer(self.fbuf_mem, 240, 240, framebuf.RGB565)
        self.fbuf_mv = memoryview(self.fbuf_mem)

        self.menu = TextMenuWidget(
            ["Red", "Green", "Blue", "Cyan", "Magenta"],  # list OR nested dict
            width=SAFE_WIDTH,      # highlight-bar width, inside the bezel
            visible_items=5,       # rows shown at once
            center=True,           # keep the selection in the middle row
            buffer=self.fbuf_mv,   # text is written HERE (see warning below)
            on_select=self.on_select,
        )
        self._dirty = True

    def on_select(self, path, value):
        # Fired when a leaf item is chosen. `path` is the list of keys
        # descended into; `value` is the leaf value (for a list, == the label).
        print("Picked:", value, "at", path)

    async def update(self):
        if not self._dirty:
            return
        self.fbuf.fill(BG)
        # x=SAFE_X insets from the round bezel; y=30 lands the centre row at
        # the middle of the screen. Pass the FrameBuffer here (not the mv).
        self.menu.render(SAFE_X, 30, self.fbuf, 240, 240)
        self.display.blit_buffer(self.fbuf_mv, 0, 0, 240, 240)
        self._dirty = False

    def button_press(self, button):
        # V3 mapping (simulator/BUTTON_MAPPING.md): 4=down, 5=up, 6=select
        if button == 4:
            self.menu.move_down()
        elif button == 5:
            self.menu.move_up()
        elif button == 6:
            self.menu.select()      # descend a sub-menu, or fire on_select
        self._dirty = True
```

> ⚠️ **`buffer=` gets the memoryview; `render()` gets the FrameBuffer.** They
> must back the *same* bytes (`self.fbuf` and `self.fbuf_mv` both wrap
> `self.fbuf_mem`). The widget writes text into `buffer` via
> `MicroFont.write`, whose viper blit does `ptr8` item assignment — which a
> `framebuf.FrameBuffer` does **not** support on this firmware
> (`TypeError: 'FrameBuffer' object doesn't support item assignment`). It draws
> the highlight bar with the FrameBuffer's `.rect()`, which is why it needs
> both. Omit `buffer=` and text rendering crashes on hardware.

As always, gate the redraw behind a `_dirty` flag so you're not blitting
20×/sec for nothing.

### Fitting the round screen

The panels are circular, so content near the top, bottom, and left/right edges
gets clipped by the bezel. Two things keep the list readable:

- **Inset horizontally.** Render at `x=SAFE_X` with `width=SAFE_WIDTH` so the
  highlight bar and text stay inside the circle instead of running off the
  left edge.
- **Pick a vertical mode.** The widget has three, in order of precedence:

  | Constructor flag | Behaviour | Use for |
  |---|---|---|
  | `wrap=True` | Infinite carousel — selection pinned to the centre row, ends loop. | Long lists (the app launcher). |
  | `center=True` | Selection pinned to the centre row, but ends **don't** loop — blank rows above the first / below the last item. | Short menus on the round screen. |
  | *(neither)* | Window scrolls and clamps at the ends. | Lists in a rectangular region. |

  `center=True` is usually what you want for a settings-style menu: the
  selection never drifts into the clipped top/bottom, and a 2-item list shows
  2 rows (not duplicates, the way `wrap` would). Render at `y=30` with
  `visible_items=5` to land the centre row at the middle of the screen.

### Driving it

| Method | Effect |
|--------|--------|
| `menu.move_up()` / `menu.move_down()` | move the cursor (wraps if `wrap=True`) |
| `menu.select()` | descend into a sub-dict/list, or call `on_select(path, value)` on a leaf |
| `menu.back()` | return to the parent level; returns `False` if already at the root |
| `menu.on_button_press(idx)` | maps `idx` to the module constants `UP=0, DOWN=1, SELECT=2, BACK=3` |

### Finding the highlighted item

| What you want | How to get it |
|---------------|---------------|
| Highlighted **text** | `menu.selected_label` (`""` if the level is empty) |
| Its **index** in the current level | `menu.selected_index` |
| Where you are in a nested menu | `menu.path` (list of keys descended into) |

`selected_label` updates immediately after `move_up()`/`move_down()` — you
don't need to call `render()` first. This is exactly how the launcher decides
which app to open: it reads `self.menu_widget.selected_label` in
`button_press` and passes it to `switch_app`.

### Nested menus

Pass a nested `dict` and `select()` / `back()` handle drill-down automatically.
Dict keys are shown **sorted**; list order is preserved.

```python
TextMenuWidget(
    {
        "Brightness": 50,            # leaf -> on_select(["Brightness"], 50)
        "Network": {                 # sub-menu (select() descends)
            "WiFi": "on",
            "Bluetooth": "off",
        },
        "Reset": "confirm",
    },
    center=True,
    back_label="< Back",             # adds a back ROW; no back button needed
    buffer=self.fbuf_mv,
    on_select=self.on_select,
)
```

`select()` activates whatever's highlighted: it descends into a non-empty
sub-dict, or fires `on_select(path, value)` on a leaf — your handler branches on
`path[0]` to know which category a leaf belongs to.

Set **`back_label`** to put a synthetic back row at the top of every sub-menu
(it only appears once you've descended, never at the root). Selecting it calls
`back()`, so navigation is just up / down / select with no dedicated back
button. The back row isn't part of your data — `on_select` paths never include
it. To leave the app from the root, the badge's global long-press on Button 3
returns to the system Menu.

### Single vs. dual display

The example above renders the whole menu on one panel. The launcher
(`apps/menu.py`) is fancier — it puts the selected name on `display1` and the
list on `display2`, and sizes its framebuffer to `240 - x_offset` to dodge the
GC9A01 wrap bug (see the warning at `apps/menu.py:43-52`). Copy that approach
only if you want the two-display split; otherwise the single-panel pattern is
all you need.

---

## Buttons

There are 8 buttons exposed as indices 0–7:

| Index | Switch | Function |
|-------|--------|----------|
| 0 | SW5 (boot/reset, GPIO0) | Often unused in apps |
| 1 | SW1 (top) | Function button A |
| 2 | SW2 (top) | Function button B |
| 3 | SW3 (top) | Function button C / **Menu** on long press |
| 4 | SW4 (top) | Function button D / nav up |
| 5 | SW7 (game) | nav left, often "select" |
| 6 | SW8 (game) | nav right |
| 7 | SW9 (game) | game button |

(The README's "A/B/C/D/SEL/Left/Right" labels map to these indices — see
`simulator/BUTTON_MAPPING.md` for the canonical table.)

### Press / click / release / long press

- `button_press(n)` — fired when the button is first detected pressed
  (after 50 ms debounce).
- `button_long_press(n)` — fired at 750 ms while still held; **suppresses the
  click** when released.
- `button_release(n)` — fired on release.
- `button_click(n)` — fired on release **only if** a long press did not fire.

Pattern: use `button_click` for "tap to do X", `button_press` for "while held,
do Y" (e.g. holding to fast-scroll, or interactive games), and
`button_long_press` for "X is shouty, only do it on purpose".

Tetris uses all three:
- `button_press(4|5)` → move left/right (so holding repeats — well, doesn't
  here, but it could)
- `button_click(6)` → rotate (only on release)
- `button_long_press(6)` → drop instantly

### Inspecting state outside callbacks

`controller.bsp.buttons[i]` returns `"Pressed" | "Long Pressed" | "Released"`,
and you can iterate `controller.bsp.buttons` to get all of them.

---

## LEDs (NeoPixel)

Seven WS2812B LEDs chained on GPIO26. Access:

```python
self.controller.bsp.leds.leds[0] = (r, g, b)  # 0..255 each
self.controller.bsp.leds.leds.write()         # commit to the strip
```

Or via the backwards-compat alias:

```python
self.controller.neopixel.fill((10, 0, 0))
self.controller.neopixel.write()
```

The LEDs driver applies a global `max_brightness` scale
(`drivers/leds.py`), so raw `(255, 0, 0)` is already attenuated. If you need
to clean up on exit, do it in `teardown`:

```python
async def teardown(self):
    self.controller.neopixel.fill((0, 0, 0))
    self.controller.neopixel.write()
```

The boot LEDs and various background services may also touch the strip — if
you're seeing unexpected colors, check `controller.py:update_time` /
`controller.py:lights` (Bluetooth-triggered events).

---

## Audio / Speaker

A single PWM-driven piezo on GPIO15. Two ways to use it:

### Pre-built songs in `songs/*.json`

```python
self.controller.bsp.speaker.start_song('tetris', repeat=True)
# ... later
self.controller.bsp.speaker.pause_song()
self.controller.bsp.speaker.resume_song()
self.controller.bsp.speaker.stop_song()
```

Always `stop_song()` in `teardown` — otherwise the song keeps playing under
the next app. The controller already stops the speaker on `switch_app`
(`controller.py:275`), but explicit is better.

### Raw PWM tones

```python
from machine import Pin, PWM
self.pwm = PWM(Pin(15), freq=440, duty=512)
# ...
self.pwm.deinit()  # required to silence
```

See `imperial_march.py` for an example that mixes PWM tones with `await
asyncio.sleep`.

---

## IMU / Accelerometer

The LIS3DHTR is on I2C at `0x18`. The driver polls and dispatches values to
registered callbacks:

```python
self.controller.bsp.imu._imu_read_rate_s = 0.01  # 100 Hz sampling
self.controller.bsp.imu.imu_callbacks.append(self.imu_callback)

async def imu_callback(self, value):
    x, y, z = value  # acceleration in g, roughly -10..10
    # ...
```

Callbacks are **coroutines** — they're `await`ed from the driver's polling
task. Don't block.

See `apps/level.py` for a complete example (bubble level with a moving dot).

---

## Bluetooth (Broadcast Mesh)

The badge's Bluetooth driver (`drivers/bluetooth.py`) is **not** a typical
GATT/pairing setup. It's a connectionless broadcast mesh built on BLE
manufacturer-data advertisements: every badge in range scans, accepts
messages stamped with the project's sender ID, and **rebroadcasts each new
message once** to extend range across the room.

In practice that means:

- There's nothing to "connect to". Apps subscribe to a callback list and
  receive any message that flows through the mesh.
- A monotonic per-message counter is used for dedup. Old messages
  (`counter <= last_counter`) are dropped silently.
- Each badge re-advertises a new message exactly once, then suppresses
  further rebroadcasts of the same counter. So the badge that originated
  the message and every relay broadcast once — they fan out, not loop.

### Wire format

Each manufacturer-data blob is:

```
+--------+--------+--------+--------+--------+--------+----  ----+
| SENDER_ID (3)            | counter_hi | counter_lo | payload    |
| 0xA2     0x3F     0x51   |  byte 3    | byte 4     | bytes 5..n |
+--------+--------+--------+--------+--------+--------+----  ----+
```

- **Bytes 0–2**: `SENDER_ID = b"\xA2\x3F\x51"`. Anything that doesn't
  start with this prefix is ignored.
- **Bytes 3–4**: 16-bit big-endian counter. Must be strictly greater than
  `last_counter` to be accepted.
- **Bytes 5+**: payload. The driver tries to UTF-8 decode it; if that
  fails, callbacks receive raw bytes.

Total advertising space is limited (BLE advertising data is capped around
31 bytes including the framing), so the payload window is roughly **22
bytes** in practice. Keep messages short — a few keys (`time:`,
`turn_on_lights`, `chat:hi`) is the right vibe.

### Receiving messages

Append a callback to `ble_callbacks`:

```python
def __init__(self, controller):
    super().__init__(controller)
    self.controller.bsp.bluetooth.ble_callbacks.append(self.on_ble)

def on_ble(self, payload):
    # payload is str if decodable, otherwise bytes
    if isinstance(payload, str) and payload.startswith("chat:"):
        msg = payload[5:]
        # ... show on screen
```

Important details:

- Callbacks are **synchronous** and scheduled via `micropython.schedule`
  out of the BLE IRQ. They run on the main thread shortly after, but
  outside any `update()` lock. Treat them like button callbacks: kick off
  work with `asyncio.create_task(...)` if you need to `await`.
- Callbacks fire **once per new counter**, across every app — the
  controller already registers `update_time` and `lights`
  (`controller.py:80-81`). Your callback is one of N.
- **Remove your callback in `teardown()`** or it will keep firing after the
  next app loads:

  ```python
  async def teardown(self):
      try:
          self.controller.bsp.bluetooth.ble_callbacks.remove(self.on_ble)
      except ValueError:
          pass
  ```

  This is the most common bluetooth-related bug in the codebase: leaked
  callbacks from a previous instance stomp on the next app.
- The driver never resets `last_counter`, so messages older than the
  highest-seen counter are dropped. If you're testing, increment your
  counter every send.

### Sending a message

The driver doesn't expose a public `send` helper, but `make_adv` builds the
advertising blob and the BLE stack handles transmit:

```python
from drivers.bluetooth import SENDER_ID, ADV_INT_MS

def send_ble(self, payload: str | bytes):
    bt = self.controller.bsp.bluetooth
    counter = (bt.last_counter + 1) & 0xFFFF
    body = payload if isinstance(payload, bytes) else payload.encode()
    blob = SENDER_ID + bytes([counter >> 8, counter & 0xFF]) + body
    bt.last_counter = counter         # bump first so our echo is dropped
    bt.ble.gap_advertise(ADV_INT_MS, bt.make_adv(blob), connectable=False)
```

Two things to be careful about:

1. **Bump `last_counter` before/at send.** The driver dedups against it on
   the receive path, so failing to do this means your own broadcast
   triggers your own callbacks on the way back through `gap_scan`.
2. **`gap_advertise` is persistent.** Calling it again replaces the
   currently-broadcast packet, but nothing in the driver clears it. If you
   want a one-shot, either accept "this stays on the air until something
   else overwrites it", or schedule a follow-up
   `bt.ble.gap_advertise(0, b"")` after a delay.

### What the controller listens for today

For reference, the system-level callbacks set up in `controller.py`:

- `time:<unix_seconds>` → updates the RTC. This is how the badge gets the
  correct time without an internet connection — any badge that's already
  synced re-broadcasts time to its neighbors.
- `turn_on_lights` → at exactly 10:xx local time, lights up all LEDs red
  for 10 s and writes a `led_flag` sentinel so the same trigger doesn't
  fire again. (Mostly a CTF / conference-stunt feature.)

If your app uses simple `key:value` payloads, prefix your own keys to
avoid colliding with these.

### Caveats

- BLE is **disabled on the web simulator**. The driver shim returns a
  no-op. Test mesh apps on real hardware or against the desktop simulator.
- The driver uses `_IRQ_SCAN_RESULT = 5` directly. If you ever swap the
  MicroPython version, double-check the constant.
- There's no encryption or auth. Anyone in BLE range can inject messages
  that match `SENDER_ID`. For a CTF, this is a feature; for anything
  serious, layer your own integrity check into the payload.

---

## RTC and Time

```python
from machine import RTC
rtc = RTC()
year, month, day, weekday, hour, minute, second, ms = rtc.datetime()
```

The RTC is set by a Bluetooth message — when a paired companion app sends
`time:<unix>`, `controller.update_time` writes it into the RTC. If no phone
ever pairs, the time stays at the epoch (2000-01-01 for this firmware) until
power cycle.

For monotonic timing inside `update()`, prefer `time.ticks_ms()` /
`time.ticks_diff()` — they're cheap and don't depend on the RTC being set.

---

## Battery

`controller.battery` is a `lib.battery.Battery`. Two useful entry points:

```python
mv = self.controller.battery.mv_average.average()  # smoothed mV reading
pct = self.controller.battery.get_battery_percentage()
self.controller.battery.draw_battery(display, (x, y))  # draws an icon
```

See `apps/battery_monitor.py` for a complete display.

---

## SmartConfig — App Settings

Every app gets `self.config: Config` automatically, backed by
`config/apps/<App.name>.json`. Config files survive reboots and can be edited
through the web `/config` endpoint when the badge is in AP mode.

### Plain values

```python
self.config.add('lucky_range', 10000)
# ...
n = self.config['lucky_range']  # returns 10000 or the persisted value
```

`add` is a **setdefault** — it only writes if the key isn't already there. Pass
`force=True` to overwrite (used when changing the default).

### Smart values (rendered nicely on `/config`)

These all subclass `SmartConfigValue` and survive round-tripping to JSON:

```python
from lib.smart_config import (
    RangeConfig, ColorConfig, EnumConfig, BoolDropdownConfig
)

bg = self.config.add('bg_color', ColorConfig('BG Color', gc9a01.WHITE), force=True)
animate = self.config.add('animate', BoolDropdownConfig('Animate', True), force=True)
draw_mode = self.config.add('draw method', EnumConfig(
    'draw method', ['full redraw', 'partial redraw'], 'full redraw'
), force=True)
radius = self.config.add('radius', RangeConfig('Radius', 50, 120, 100))

# To read:
bg_color = bg.value()              # for SmartConfigValue, call .value()
animate_on = animate.value()       # returns True / False (BoolDropdown is enum-backed)
mode = draw_mode.value()           # returns the chosen string
r = radius.value()                 # returns int
```

`force=True` is the conventional pattern for smart values: it makes sure the
class metadata on disk matches what the app currently expects, even if a
previous version persisted a different shape.

### Reading at runtime

`self.config['key']` returns the raw stored object — a plain value, or a
`SmartConfigValue` you must `.value()` on. Cache reads in `__init__` if the
value doesn't change at runtime, since dict lookup + method call adds up
inside `update()`.

### Web `/config` endpoint

When the badge is in WiFi AP mode, browse to `/config` to see a form for the
currently running app's config. Edits POST back through `Config.update`, which
calls `parse_value` on each smart value and re-saves the JSON. This is the
intended way for end users to tweak apps without a code editor.

---

## Multiple Apps per File, Hidden Apps

A single `.py` file in `apps/` can declare multiple `BaseApp` subclasses.
`AppDirectory.from_module` enumerates all of them. Use this to group related
apps that share helper code (see the commented example in
`apps/multiple_apps.py`).

To hide an app from the menu (system apps, debug tools, sub-apps you
manually `switch_app` to):

```python
class MyHelper(BaseApp):
    name = "Helper"
    hidden = True
```

The Menu app itself uses this (`apps/menu.py:22`).

---

## Async and the Update Loop

The whole runtime is `asyncio`-based. Practical rules:

- **`update()` is `async`** — `await asyncio.sleep(small)` is fine and gives
  other tasks (services, BLE callbacks, IMU polling) a chance to run.
- **Don't `time.sleep()` in `update()`** — it blocks the entire badge.
- **Button callbacks are synchronous.** If you need to do real work, use
  `asyncio.create_task(self._handle())`.
- **You can spawn background tasks** in `setup` or `__init__`, but cancel them
  in `teardown` or they'll keep running and stomp on the next app's draws.

```python
def __init__(self, controller):
    super().__init__(controller)
    self.bg_task = asyncio.create_task(self._background())

async def teardown(self):
    if self.bg_task:
        self.bg_task.cancel()
```

- **Frame pacing**: if your `update()` does expensive work, sleep for the
  remainder of your budget at the end so you don't burn the CPU:

```python
async def update(self):
    t0 = time.ticks_ms()
    self.draw_frame()
    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    await asyncio.sleep(max(0, 0.5 - elapsed / 1000))
```

---

## Running Standalone (`single_app_runner`)

For fast iteration on a single app on hardware, wrap your file:

```python
class Level(BaseApp):
    # ...

if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(Level, perf=True)
```

`single_app_runner.run_app` constructs a Controller without starting the menu,
runs your app's `setup`, then loops on `update()` and prints FPS every 5 s
when `perf=True`. Invoke with:

```bash
uv run mpremote cp -r src/apps/level.py + run main.py
```

Or, in REPL after mounting:

```python
import apps.level
apps.level.run_app(apps.level.Level, perf=True)
```

---

## Iterating in the Web Simulator

The fastest dev loop. Builds MicroPython to WebAssembly and runs everything
in the browser.

```bash
cd web_simulator
./scripts/build_micropython.sh   # one-time (or after frozen-module changes)
python -m http.server 8080
# Open http://localhost:8080
```

Once it's up you get:

- Two 240×240 canvases mirroring `display1` / `display2`.
- A code editor (Monaco) on the right with a file picker for everything in
  `src/`.
- Keyboard buttons (see `simulator/BUTTON_MAPPING.md`).
- **Reload App**: re-execs the currently edited module and re-switches to it.
  Controller, services, LEDs, log all preserved. Best for app iteration.
- **Full Reload**: `window.location.reload()`. Use after editing
  `controller.py`, `bsp.py`, or modules held by long-lived objects.
- **Download**: saves the buffer as `apps_<name>.py` so you can sync back.

Caveats:
- The filesystem is in-memory (MEMFS), so persisted config is lost on full
  reload.
- `@micropython.viper` is patched out — see [Fonts](#fonts).
- No `_thread` (WASM is single-threaded) — `Timer` is shimmed to
  `setInterval`.
- Audio uses Web Audio API; PWM behaviour is approximate.

If your edit doesn't appear after **Reload App**, it's almost certainly held
by a parent module (controller, service, driver). Full Reload is the escape
hatch.

---

## Iterating in the Desktop Simulator

`simulator/` is a pygame-based simulator that mocks the hardware drivers
(`simulator/libraries/`). Run with:

```bash
cd simulator
./run.sh
```

Pros: full Python interpreter (no WASM constraints), faster to attach a
debugger to. Cons: a little stale relative to the web simulator. See
`simulator/README.md` and `simulator/BUTTON_MAPPING.md` for specifics.

---

## Deploying to Hardware (`mpremote`)

After `uv sync`, with the badge plugged in:

```bash
# One-shot run: push a single file and start main.py
uv run mpremote cp -r src/apps/my_app.py + run main.py

# Full sync (only changed files are written):
uv run mpremote cp -r src/* :

# Live REPL with src/ mounted from your machine
uv run mpremote mount src
```

The badge boots `boot.py` then `main.py`. `main.py` instantiates the
controller and kicks off the asyncio loop. If your app blows up at import
time, the controller logs an error to `error.txt` and the menu still works —
see `ARCHITECTURE.md` for the startup flow.

---

## Performance Tips

- **Cache attribute lookups in `__init__`.** `self.display1 = ...` once is
  faster than `self.controller.bsp.displays.display1` per frame.
- **Use a single full-screen framebuffer for animation.** Don't repeatedly
  call `display.fill_rect` for each cell — draw into the framebuffer, blit
  once.
- **Hold a `memoryview`** of the framebuffer's bytearray and blit the
  memoryview, not the bytearray — avoids reallocating views per frame.
- **`@micropython.native` / `@micropython.viper`** decorators can speed up
  hot inner loops on hardware. They're patched out in the web simulator, so
  decorated code must also work as plain Python.
- **Pre-compute everything you can.** If your background is static, draw it
  once into a buffer in `__init__`, then `blit` and overlay the moving parts.
- **Cache MicroFont glyphs** (`cache_chars=True`) when rendering the same
  small text repeatedly (HUDs, timers).
- **Avoid garbage in the inner loop.** String formatting, list
  comprehensions, and most allocations in `update()` will eventually trigger
  a GC pause that drops a frame.

---

## Common Pitfalls

- **App doesn't appear in the menu.** Either no `BaseApp` subclass in the
  file, or two apps have the same `name`. Delete
  `config/app_directory_cache.json` to force a re-scan.
- **`button_long_press(3)` opens the Menu and your handler runs first.** The
  controller's handler always fires too. You can't suppress it without
  patching `controller.py`.
- **Colors look wrong in framebuffer drawing.** You're using `gc9a01.RED`
  (big-endian) in a `framebuf.RGB565` buffer. Use `rgb((255,0,0))`,
  `COLOR_LOOKUP['fbuf']['red']`, or the theme constants.
- **Display is sheared / wrapping.** Buffer size + offset exceeds 240. The
  GC9A01 wraps writes; the web simulator does not — so it can pass in the
  browser and fail on hardware. See the warning in `apps/menu.py:48-52`.
- **Song keeps playing after exit.** Add
  `self.controller.bsp.speaker.stop_song()` to `teardown()`.
- **BLE callback fires forever after switching apps.** You appended to
  `bsp.bluetooth.ble_callbacks` but never removed it. Always pair
  `append` in `__init__` with `remove` in `teardown`.
- **LEDs stay lit after exit.** Clear and `write()` in `teardown`. The
  controller doesn't do this for you.
- **`await` in a button callback does nothing.** Callbacks aren't coroutines.
  Use `asyncio.create_task(...)`.
- **App stutters when opened.** Heavy work in `__init__` runs while the
  controller's app-switch lock is held. Defer to `setup` and yield
  periodically with `await asyncio.sleep(0)`.
- **Config changes get reverted on next boot.** Your default in
  `Config.add` doesn't match the persisted type. Use `force=True` when
  changing the default shape, or delete the per-app file in `config/apps/`.
- **`hidden = True` doesn't hide on the badge.** You may need to delete the
  app cache so the new metadata is picked up.
- **`TypeError: 'FrameBuffer' object doesn't support item assignment`.** You
  passed a `FrameBuffer` where `MicroFont.write` (or a widget like
  `TextMenuWidget`) expects the writable buffer. Pass the `memoryview` backing
  the framebuffer instead — see the warning in
  [Reusable Menu Widget](#reusable-menu-widget-textmenuwidget).

---

## Where to Go Next

- `apps/hello_world_app.py` — the bare minimum.
- `apps/lucky_number.py` — config, displays, `setup`, button handling.
- `apps/analog_clock.py` — SmartConfig with every smart type, framebuffer.
- `apps/level.py` — IMU callbacks, MicroFont, full-screen blit.
- `apps/tetris.py` — gameplay, audio, framebuffer, ghost rendering,
  `single_app_runner`, frame pacing.
- `apps/battery_monitor.py` — theme constants, MicroFont, battery API.
- `apps/menu.py` — `hidden=True`, dual-display layout, scrolling, animation;
  reference consumer of `TextMenuWidget`.
- `ui/menu.py` — the reusable `TextMenuWidget` itself (nested menus, wrap,
  selection API).

For hardware specifics not covered here, see `HARDWARE.md`. For the bigger
picture of the boot / app-cache flow, see `ARCHITECTURE.md`.
