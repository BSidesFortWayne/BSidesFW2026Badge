# BSides FW 2025 Badge - Web Simulator

Browser-based badge simulator using MicroPython compiled to WebAssembly. Runs entirely client-side — no server required after build.

## Quick Start (Demo Mode)

The web simulator works immediately in demo mode without building the WASM binary:

```bash
cd web_simulator
python -m http.server 8080
# Open http://localhost:8080
```

Demo mode shows test patterns on both displays and animates the LEDs to verify the rendering layer works.

## Building with MicroPython WASM

To run the actual badge firmware in the browser, you need to compile MicroPython to WebAssembly:

### Prerequisites

- Linux or WSL (Emscripten requires a Unix-like environment)
- Git, Make, Python 3
- ~2GB disk space for Emscripten SDK + MicroPython source

### Build

```bash
chmod +x scripts/build_micropython.sh
./scripts/build_micropython.sh
```

This will:
1. Install the Emscripten SDK (if not present)
2. Clone MicroPython (if not present)
3. Build `mpy-cross` (cross-compiler)
4. Freeze badge firmware + web shims into the WASM binary
5. Patch `microfont.py` to replace Viper-specific code with pure Python
6. Build `micropython.wasm` + `micropython.mjs`
7. Package font/image/config assets into `build/fs/`

### Serve

```bash
python -m http.server 8080
# Open http://localhost:8080
```

## Architecture

```
Browser
├── index.html + style.css     — Badge layout + control panel
├── js/
│   ├── main.js                — Boot sequence, MicroPython WASM init
│   ├── display.js             — 2x 240x240 Canvas (RGB565→RGBA32)
│   ├── leds.js                — 7 NeoPixel LEDs (CSS glow)
│   ├── buttons.js             — Keyboard + click input
│   ├── controls.js            — Accelerometer, battery, state controls
│   ├── audio.js               — Web Audio API (PWM tones)
│   └── bridge.js              — JS↔MicroPython bridge functions
├── py_shims/                  — Hardware mock modules (frozen into WASM)
│   ├── emulator.py            — JS bridge calls (replaces TCP sockets)
│   ├── gc9a01.py              — Display driver
│   ├── machine.py             — Pin, I2C, Timer, RTC, PWM, ADC
│   ├── neopixel.py            — LED control
│   └── ...                    — Other hardware stubs
└── build/                     — Compiled WASM + packaged assets
```

## Controls

| Key | Button |
|-----|--------|
| 0 | Boot/Reset (SW5) |
| 1-4 | SW1-SW4 (top buttons) |
| 7-9 | SW7-SW9 (game buttons) |

Buttons can also be clicked directly on the badge image. Touch is supported on mobile.

## Editing code in the simulator

The right-side **Code Editor** panel (Monaco) lets you live-edit any file in
`src/` and re-run it without rebuilding the WASM binary.

- **File picker** lists every `.py` under `src/` (grouped by top-level dir).
- **Reload App** hot-swaps the module: the running app is torn down, the
  edited module is re-`exec()`'d into a fresh module object, and the app is
  restarted via `Controller.switch_app`. Controller state, services, logs,
  and LED state are preserved.
- **Full Reload** is just `window.location.reload()` — use it when you've
  edited `controller.py`, `bsp.py`, a service, or anything held by a
  long-lived object. The page reloads against the same (frozen) WASM, so
  for *permanent* changes you still need to re-run `build_micropython.sh`.
- **Download** saves the currently active file (with your edits) to disk.
  Filename mirrors the source path: `apps/menu.py` → `apps_menu.py`.
- **Revert** drops your edits for the active file and re-loads it from disk.
- All edits live in `localStorage` (`badge_sim_edit:<path>` keys). They
  persist across page reloads. Nothing is written back to your real `src/`
  files — use **Download** to export changes.

**Trade-offs of hot-swap:**

Hot-swap re-executes the edited module, but already-imported callers still
hold references to the *old* classes. For app files that's fine —
`switch_app` constructs a fresh instance from the new class. For `ui/`,
`lib/`, or `drivers/` modules, the running app re-imports them at
construction time, so most shallow changes pick up after Reload App. For
anything deeper (a class held by a service, a module imported only by
`controller.py`), use **Full Reload**.

`__init__.py` files cannot be hot-swapped — they'd need to re-execute the
whole package body. Use Full Reload for those.

## Differences from Desktop Simulator

- No `_thread` module (WASM is single-threaded) — Timers use `setInterval`
- No `@micropython.viper` — font rendering uses pure-Python fallback
- Audio uses Web Audio API instead of native PWM
- Filesystem is in-memory (MEMFS) — config changes don't persist across reloads
