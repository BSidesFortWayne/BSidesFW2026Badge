# BSides FW 2025 Badge Simulator

A high-performance simulator for developing and testing badge applications without physical hardware.

## Quick Start

### First Time Setup

```bash
cd simulator/
uv run ./run.sh --setup
```

The setup wizard will:
- Check and install dependencies
- Auto-detect your project directory (usually `../src`)
- Configure MicroPython path
- Save configuration to `config.json`

### Daily Use

```bash
uv run ./run.sh
```

That's it! The simulator includes all features by default:
- ✅ **Binary protocol** - 10-20x faster rendering
- ✅ **Hardware controls** - Mock sensors and peripherals
- ✅ **Dual displays** - Both 240x240 circular screens
- ✅ **Button emulation** - Keyboard keys 0-7

## Features

### High Performance Binary Protocol
- ⚡ 10-20x faster than JSON protocol
- ⚡ `blit_buffer(240x240)` in ~5ms vs ~100ms
- ⚡ Eliminates screen artifacting
- ✨ Smooth 60 FPS rendering

### Hardware Control Panel
The right panel lets you mock hardware:
- 🎮 Accelerometer (X/Y/Z axes + shake)
- 🔋 Battery voltage slider
- ⚡ Charge state control
- 📡 WiFi state simulation
- 🔵 Bluetooth state simulation

### Keyboard Controls

| Key | Hardware Button | Description |
|-----|----------------|-------------|
| `0` | SW5 | Boot/Reset |
| `1` | SW1 | Button A (top) |
| `2` | SW2 | Button B (top) |
| `3` | SW3 | Button C (top) |
| `4` | SW4 | Button D (top) |
| `7` | SW7 | Game button 1 |
| `8` | SW8 | Game button 2 |
| `9` | SW9 | Game button 3 |

## Requirements

### Install Dependencies

```bash
# Python packages (required)
pip install pygame pillow pygame-gui

# MicroPython (required)
# Option 1: System package
sudo apt install micropython

# Option 2: Via uv
uv run micropython --version

# Option 3: Build from source
# See: https://micropython.org/
```

The setup wizard can install Python packages automatically.

## Usage

### Basic Commands

```bash
# Run simulator with defaults
./run.sh

# First-time setup
./run.sh --setup

# Use custom project directory
./run.sh -p /path/to/your/project

# Verbose output for debugging
./run.sh -v

# See all options
./run.sh --help
```

### Direct Python Invocation

```bash
# Run directly
uv run python3 simulator.py

# With options
uv run python3 simulator.py -p ../src -v

# Setup wizard
uv run python3 simulator.py --setup
```

## Configuration

Settings are stored in `config.json` (created by setup wizard):

```json
{
  "project_path": "../src",
  "micropython_path": "micropython",
  "socket_port": 4455,
  "binary_port": 4456,
  "logging": {
    "enabled": true,
    "output_dir": "logs"
  },
  "gui": {
    "show_fps": true,
    "target_fps": 60
  }
}
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `project_path` | `../src` | Badge project directory |
| `micropython_path` | `micropython` | MicroPython executable |
| `socket_port` | `4455` | JSON protocol port |
| `binary_port` | `4456` | Binary protocol port |
| `logging.enabled` | `true` | Enable file logging |
| `gui.show_fps` | `true` | Show FPS counter |
| `gui.target_fps` | `60` | Target frame rate |

## How It Works

```
┌─────────────────┐           ┌──────────────────┐
│  Badge App      │           │  Pygame GUI      │
│  (MicroPython)  │◄─────────►│                  │
│                 │  Binary/  │  • Display       │
│  Fake Drivers   │   JSON    │  • Controls      │
│  (Shims)        │           │  • LEDs          │
└─────────────────┘           └──────────────────┘
   Port: N/A          127.0.0.1:4455/4456
```

1. **Setup**: Copies `src/` to `simulator/src/`
2. **Overlay**: Installs hardware shims (fake drivers)
3. **Launch**: Starts MicroPython with your badge code
4. **IPC**: Socket communication for commands
5. **Render**: Pygame displays the badge screens

## Development Workflow

### IMPORTANT: Edit Files in `src/`, Not `simulator/src/`

The simulator **copies** your project files to `simulator/src/` at startup.

- ✅ **DO**: Edit files in `src/apps/`, `src/lib/`, etc.
- ❌ **DON'T**: Edit files in `simulator/src/` (changes will be lost)
- After editing `src/`, restart the simulator to pick up changes

### Testing Your App

```bash
# 1. Create/edit your app
vim src/apps/my_app.py

# 2. Run simulator
cd simulator/
uv run ./run.sh

# 3. Navigate to your app using buttons
# 4. Check logs/ for errors
```

### Performance Testing

For apps using `blit_buffer()` and framebuffers:

```python
# Your app (src/apps/my_app.py)
import framebuf
import gc9a01

# Create framebuffer
buf = bytearray(240 * 240 * 2)
fb = framebuf.FrameBuffer(buf, 240, 240, framebuf.RGB565)

# Draw to framebuffer
fb.fill(0xF800)  # Red
fb.rect(10, 10, 100, 100, 0xFFFF)

# Blit to display (FAST with binary protocol)
display.blit_buffer(buf, 0, 0, 240, 240)
```

The binary protocol makes this 10-20x faster than the old JSON protocol.

## Troubleshooting

### "No MicroPython found"

```bash
# Install system package
sudo apt install micropython

# Or check PATH
which micropython
```

### "pygame not found"

```bash
pip install pygame pillow pygame-gui
```

### Port already in use

```bash
# Change ports
uv run ./run.sh --port 4460 --binary-port 4461

# Or kill existing process
pkill -f simulator.py
```

### MicroPython crashes on startup

```bash
# Check logs
cat logs/simulator_*.log

# Run verbose
uv run ./run.sh -v

# Verify your code works
cd ../src
uv run micropython main.py
```

### Black screens / No display

- Check that your app draws to displays
- Verify MicroPython output for errors
- Ensure `blit_buffer()` or drawing commands are being called

### Low FPS

The binary protocol should give you 60 FPS. If not:
- Check CPU usage
- Look for Python exceptions in logs
- Verify your app isn't blocking with `time.sleep()`

## File Structure

```
simulator/
├── simulator.py          # Main entry point
├── run.sh               # Launcher script
├── setup_wizard.py      # Interactive setup
├── gui_enhanced.py      # Enhanced GUI (hardware controls)
├── gui_binary.py        # Binary protocol handler
├── logger.py            # Logging utilities
├── config.json          # Configuration (created by setup)
├── libraries/           # Hardware shims (fake drivers)
│   ├── gc9a01.py        # Display driver shim
│   ├── gc9a01_binary.py # Binary protocol display driver
│   ├── pca9535.py       # Button controller shim
│   ├── machine.py       # machine module shim
│   └── ...              # Other hardware shims
├── fonts/               # Bitmap fonts for GUI
├── logs/                # Log output (created at runtime)
└── src/                 # Project copy (created at runtime)
```

## Performance Comparison

| Operation | Old (JSON) | New (Binary) | Speedup |
|-----------|-----------|--------------|---------|
| Full screen blit | ~100ms | ~5ms | **20x** |
| Rectangle fill | ~2ms | ~0.3ms | **6x** |
| Single pixel | ~0.5ms | ~0.1ms | **5x** |

**The binary protocol is essential for smooth animations.**

## Additional Documentation

- `BUTTON_MAPPING.md` - Hardware button reference
- `../docs/SIMULATOR_*.md` - Architecture docs
- `logs/` - Runtime logs and debug output

## FAQ

**Q: Do I need to run setup every time?**  
A: No, only once. After setup, just use `./run.sh`.

**Q: Can I use this for WiFi/Bluetooth features?**  
A: WiFi and Bluetooth state can be mocked, but actual network functionality is not simulated.

**Q: Is this 100% accurate to real hardware?**  
A: Very close, but not perfect. Always test critical features on real hardware before deployment.

**Q: Can I run multiple simulators at once?**  
A: Yes, but use different ports for each:
```bash
./run.sh --port 4460 --binary-port 4461
```

**Q: What if I don't have a config.json?**  
A: The simulator will prompt you to run setup, or you can skip and use defaults.

## Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: See `../docs/` directory
- **Logs**: Check `logs/` for detailed error information

---

**Made with ❤️ for BSides FW 2025**
