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

## Differences from Desktop Simulator

- No `_thread` module (WASM is single-threaded) — Timers use `setInterval`
- No `@micropython.viper` — font rendering uses pure-Python fallback
- Audio uses Web Audio API instead of native PWM
- Filesystem is in-memory (MEMFS) — config changes don't persist across reloads
