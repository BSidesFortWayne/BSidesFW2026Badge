# Simulator Architecture Diagrams

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Development Environment                       │
│                                                                  │
│  ┌──────────────────┐                    ┌──────────────────┐  │
│  │   ../src/        │                    │  simulator/      │  │
│  │  (Original Code) │                    │                  │  │
│  │                  │                    │  ┌────────────┐  │  │
│  │  • main.py       │   COPY AT         │  │    src/    │  │  │
│  │  • apps/         │   STARTUP         │  │  (Runtime) │  │  │
│  │  • drivers/      │ ─────────────────►│  │            │  │  │
│  │  • lib/          │                    │  │  + shims   │  │  │
│  │  • ...           │                    │  └─────┬──────┘  │  │
│  └──────────────────┘                    │        │         │  │
│                                           │  ┌─────▼──────┐  │  │
│  ┌──────────────────┐                    │  │ MicroPython│  │  │
│  │ simulator/       │                    │  │  Process   │  │  │
│  │  libraries/      │   OVERLAY         │  └─────┬──────┘  │  │
│  │                  │   SHIMS           │        │         │  │
│  │  • emulator.py   │ ─────────────────►│        │         │  │
│  │  • gc9a01.py     │                    │  ┌─────▼──────┐  │  │
│  │  • pca9535.py    │                    │  │  Sockets   │  │  │
│  │  • machine.py    │                    │  │            │  │  │
│  │  • ...           │                    │  │  4455 JSON │  │  │
│  └──────────────────┘                    │  │  4456 Bin  │  │  │
│                                           │  └─────┬──────┘  │  │
│                                           │        │         │  │
│                                           │  ┌─────▼──────┐  │  │
│                                           │  │  gui.py    │  │  │
│                                           │  │            │  │  │
│                                           │  │  • Pygame  │  │  │
│                                           │  │  • Render  │  │  │
│                                           │  │  • Input   │  │  │
│                                           │  └────────────┘  │  │
│                                           └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Protocol Flow

### Binary Protocol (Graphics)

```
Badge App                  Shim Library              Emulator Socket           GUI
─────────                  ────────────              ───────────────           ───

display.fill(RED)  ──────►  gc9a01.py
                            fill(color)  ─────────►  emulator.py
                                                     send_fill()   ─────────►
                                                     
                                                     PACKET:
                                                     ┌──────┬───┬────┬──────┐
                                                     │ 0xEB │ 1 │ 3  │0xF800│
                                                     │ 0x01 │   │    │      │
                                                     └──────┴───┴────┴──────┘
                                                       ^     ^   ^      ^
                                                       │     │   │      │
                                                     Magic  CMD Len  Payload
                                                     
                                                                    gui.py
                                                                    BinaryProtocolHandler
                                                                    handle_command(1, ...)
                                                                    screen1.fill(rgb)
                                                     
                                                     RESPONSE:
                                                     ┌───┬────┐
                                                     │ 0 │ 0  │
                                                     └───┴────┘
                                                       ^   ^
                                                       │   │
                                                     Status Len
                                                     
                            return      ◄─────────  return (0, None)
return                ◄────

Time: ~1ms for simple graphics, ~5-10ms for 240x240 blit_buffer
```

### JSON Protocol (Text, Sensors)

```
Badge App                  Shim Library              Emulator Socket           GUI
─────────                  ────────────              ───────────────           ───

display.text(            ──────────────►  gc9a01.py
  font, "Hello", ...)                     text(...)  ───────────►  emulator.py
                                                                   send_command()  ────►
                                                     
                                                     JSON:
                                                     {
                                                       "device": "gc9a01",
                                                       "command": "text",
                                                       "font": "vga2_8x16",
                                                       "string": "Hello",
                                                       "x": 10,
                                                       "y": 20,
                                                       "fg_color": 65535,
                                                       "bg_color": 0,
                                                       "display": 1
                                                     }
                                                     
                                                                              gui.py
                                                                              handle_command()
                                                                              _handle_gc9a01()
                                                                              render_text()
                                                     
                                                     RESPONSE:
                                                     {
                                                       "status": "ok",
                                                       "resp": null
                                                     }
                                                     
                            return      ◄──────────  return response
return                ◄────

Time: ~5-15ms depending on text complexity
```

## GUI Internal Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         gui.py                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              GUIEnhanced Class                          │    │
│  │                                                          │    │
│  │  State:                                                  │    │
│  │  • screen1, screen2 (pygame.Surface 240x240)           │    │
│  │  • button_states[8]                                     │    │
│  │  • leds[7] (RGB tuples)                                 │    │
│  │  • accel_data[3] (X,Y,Z)                               │    │
│  │  • adc_voltage, wifi_state, bluetooth_state            │    │
│  │  • interrupt_queue                                      │    │
│  │                                                          │    │
│  │  Methods:                                                │    │
│  │  • handle_command(dict) → dict      [JSON protocol]    │    │
│  │    ├─ _handle_gc9a01()                                  │    │
│  │    ├─ _handle_pca9535()                                 │    │
│  │    ├─ _handle_accelerometer()                           │    │
│  │    └─ _handle_neopixel()                                │    │
│  │                                                          │    │
│  │  • gameloop()                        [Main render loop] │    │
│  │    ├─ Process pygame events                             │    │
│  │    ├─ Update UI controls                                │    │
│  │    ├─ Render displays                                   │    │
│  │    ├─ Render LEDs                                       │    │
│  │    └─ Update screen                                     │    │
│  │                                                          │    │
│  │  • _create_ui_controls()            [Hardware panel]    │    │
│  │  • render_leds()                                        │    │
│  │  • _apply_shake()                                       │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         BinaryProtocolHandler Class                     │    │
│  │                                                          │    │
│  │  State:                                                  │    │
│  │  • gui (reference to GUIEnhanced)                       │    │
│  │  • screens[2] (references to gui.screen1/2)            │    │
│  │                                                          │    │
│  │  Methods:                                                │    │
│  │  • handle_command(cmd_id, payload) → (status, data)    │    │
│  │    ├─ _handle_fill()           CMD_FILL = 0x01         │    │
│  │    ├─ _handle_pixel()          CMD_PIXEL = 0x02        │    │
│  │    ├─ _handle_fill_rect()      CMD_FILL_RECT = 0x03    │    │
│  │    ├─ _handle_line()           CMD_LINE = 0x04         │    │
│  │    ├─ _handle_circle()         CMD_CIRCLE = 0x05       │    │
│  │    ├─ _handle_blit_buffer() ⚡ CMD_BLIT_BUFFER = 0x10  │    │
│  │    ├─ _handle_get_inputs()     CMD_GET_INPUTS = 0x20   │    │
│  │    └─ _handle_neopixel_write() CMD_NEOPIXEL = 0x30     │    │
│  │                                                          │    │
│  │  • rgb565_to_rgb(color) → (r,g,b)                      │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Thread Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Simulator Process                          │
│                                                               │
│  Main Thread                                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  1. Parse arguments                                  │    │
│  │  2. Setup project directory (copy + overlay)        │    │
│  │  3. Create socket servers (4455, 4456)              │    │
│  │  4. Launch MicroPython subprocess                   │    │
│  │  5. Accept connections (wait for connect)           │    │
│  │  6. Create GUI instance                              │    │
│  │  7. Start communication threads                      │    │
│  │  8. Run GUI gameloop (BLOCKS HERE)                   │    │
│  │  9. Cleanup on exit                                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  JSON Thread (daemon)                                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  while gui.running:                                  │    │
│  │    recv JSON from socket                             │    │
│  │    gui.handle_command(json_obj)                      │    │
│  │    send response                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  Binary Thread (daemon)                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  while gui.running:                                  │    │
│  │    recv binary packet                                │    │
│  │    binary_handler.handle_command(cmd_id, payload)   │    │
│  │    send response                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  MicroPython Process (separate)                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Runs badge firmware code                            │    │
│  │  Connects to localhost:4455 (JSON)                   │    │
│  │  Connects to localhost:4456 (Binary)                 │    │
│  │  stdout/stderr captured by simulator                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘

Note: GUI gameloop runs at 60 FPS target
      Communication threads are non-blocking
      All pygame operations are NOT thread-safe
      → Only gameloop thread touches pygame surfaces
```

## Error Handling Flow

```
                        ┌─────────────┐
                        │  Command    │
                        │   Arrives   │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │  Validate   │
                        │  Structure  │
                        └──────┬──────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
              ┌─────▼─────┐         ┌────▼────┐
              │   Valid   │         │ Invalid │
              └─────┬─────┘         └────┬────┘
                    │                    │
              ┌─────▼─────┐         ┌────▼────────────┐
              │   Route   │         │ Return Error    │
              │  to Device│         │ {               │
              │  Handler  │         │   status: error │
              └─────┬─────┘         │   error: msg    │
                    │               │ }               │
         ┌──────────┼──────────┐    └─────────────────┘
         │          │          │
    ┌────▼───┐ ┌───▼───┐ ┌───▼────┐
    │ gc9a01 │ │pca9535│ │ lis3dh │
    │handler │ │handler│ │ handler│
    └────┬───┘ └───┬───┘ └───┬────┘
         │         │          │
    ┌────▼─────────▼──────────▼────┐
    │      Execute Command          │
    └────┬──────────────────────────┘
         │
         ├─────── Success ─────────┐
         │                          │
    ┌────▼────┐              ┌─────▼──────┐
    │ Return  │              │  Exception │
    │ Result  │              │   Caught   │
    │ {       │              └─────┬──────┘
    │  status:│                    │
    │    ok   │              ┌─────▼──────┐
    │  resp:  │              │    Log     │
    │   ...   │              │   Error    │
    │ }       │              └─────┬──────┘
    └────┬────┘                    │
         │                   ┌─────▼──────┐
         │                   │Return Error│
         │                   │ Response   │
         │                   └─────┬──────┘
         │                         │
         └─────────┬───────────────┘
                   │
            ┌──────▼──────┐
            │   Logged    │
            │   (if logger│
            │   enabled)  │
            └─────────────┘
```

## File Organization (Proposed)

```
simulator/
│
├── simulator.py              # Main entry point (orchestration)
│   ├─ parse_args()
│   ├─ setup_project_directory()
│   ├─ create_socket_servers()
│   ├─ start_micropython()
│   ├─ handle_json_protocol()   [thread function]
│   ├─ handle_binary_protocol() [thread function]
│   └─ main()
│
├── gui.py                     # SINGLE GUI FILE (consolidated)
│   ├─ class GUIEnhanced
│   │   ├─ __init__()
│   │   ├─ handle_command()     [JSON protocol]
│   │   ├─ gameloop()           [render loop]
│   │   ├─ _create_ui_controls()
│   │   └─ render_leds()
│   │
│   ├─ class BinaryProtocolHandler
│   │   ├─ __init__()
│   │   ├─ handle_command()     [binary protocol]
│   │   └─ rgb565_to_rgb()
│   │
│   └─ helper functions
│       └─ get_vga_text()
│
├── logger.py                  # Logging utilities
├── setup_wizard.py            # First-time setup
├── run.sh                     # Launcher script
├── config.json                # Runtime configuration
│
├── board_render.png           # Badge background image
├── arial.ttf                  # TrueType font
│
├── fonts/                     # VGA bitmap fonts
│   ├── vga1_bold_16x32.png
│   ├── vga2_8x16.png
│   └── vga2_bold_16x32.png
│
├── libraries/                 # MicroPython shims (copied to src/)
│   ├── emulator.py           # Socket singleton (STAYS HERE)
│   ├── gc9a01.py             # Display driver shim
│   ├── pca9535.py            # Button controller shim
│   ├── machine.py            # Machine module stubs
│   ├── lis3dh.py             # Accelerometer shim
│   ├── neopixel.py           # LED strip shim
│   ├── network.py            # WiFi shim
│   ├── bluetooth.py          # Bluetooth shim
│   ├── esp32.py              # ESP32-specific shim
│   └── vga*.py               # Font module shims
│
├── logs/                      # Runtime logs (created)
│   └── simulator_*.log
│
└── src/                       # Project copy (created at runtime)
    ├── [copied from ../src/]
    └── [+ shims from libraries/]

Files to DELETE:
├── gui_enhanced.py            # Merge into gui.py
├── gui_binary.py              # Merge into gui.py
└── any emulator.py outside libraries/
```

## Configuration Flow

```
Command Line Args
       │
       ▼
┌──────────────┐
│ config.json  │
│  (file)      │
└──────┬───────┘
       │
       ▼
┌──────────────┐     Passed to:
│ config dict  │ ────────────────┐
└──────────────┘                 │
                                 │
       ┌─────────────────────────┼─────────────────┐
       │                         │                 │
       ▼                         ▼                 ▼
┌─────────────┐         ┌──────────────┐   ┌──────────────┐
│ simulator.py│         │  gui.py      │   │  logger.py   │
│             │         │              │   │              │
│ • proj_path │         │ • window_    │   │ • log_dir    │
│ • mp_path   │         │   title      │   │ • verbose    │
│ • ports     │         │ • show_fps   │   │ • enabled    │
│             │         │ • target_fps │   │              │
└─────────────┘         └──────────────┘   └──────────────┘
```

---

## Legend

```
┌────┐
│Box │  = Component / Module
└────┘

────►  = Data flow / Function call

◄────  = Return value

┌────┐
│ ⚡ │  = Performance-critical operation
└────┘

[Text] = Description / Note

├──    = List item / Tree structure
```

---

## Notes

1. **Thread Safety**: Only the GUI gameloop thread touches pygame surfaces
2. **Performance**: Binary protocol for all graphics (10-20x faster than JSON)
3. **Error Handling**: Every command has validation and exception handling
4. **Backwards Compat**: Support both old and new JSON formats during transition
5. **Single Source**: One gui.py file, no duplicates

---

These diagrams complement the written documentation and provide visual reference for understanding the simulator architecture.
