# BSides FW 2025 Badge Simulator - Documentation Index

## 🎉 NEW: Unified Simulator Available!

The simulator has been unified into a single implementation with all features enabled by default!

**Quick Start:**
```bash
cd simulator/
uv run ./run.sh --setup     # First-time setup wizard
uv run ./run.sh             # Run with all features enabled
```

**Features (all included):**
- ⚡ Binary protocol (10-20x faster)
- 🎮 Hardware control panel
- 📺 Dual circular displays  
- 🎹 Full button emulation

**See:** `simulator/README.md` for complete documentation and `simulator/MIGRATION_GUIDE.md` if upgrading from old versions.

---

## Overview

This directory contains comprehensive documentation for understanding, updating, and using the BSides FW 2025 Badge simulator. The simulator provides a local development environment for testing badge applications without physical hardware.

## Documentation Files

### 1. [Simulator Architecture](./SIMULATOR_ARCHITECTURE.md)
**Purpose**: Technical documentation of the current simulator implementation

**Contents**:
- Current simulator architecture and components
- Communication protocols and data flow
- Hardware shims and their implementations
- Limitations and missing features
- Insights for future updates

**Audience**: Developers working on simulator internals

### 2. [Simulator Update Design](./SIMULATOR_UPDATE_DESIGN.md)
**Purpose**: Comprehensive design document for updating the simulator to support modern firmware

**Contents**:
- Current state analysis (firmware vs simulator)
- Framebuffer support design
- Enhanced component specifications
- Implementation plan (6 phases)
- Performance optimization strategies
- Migration path for existing code

**Audience**: Developers implementing simulator updates

### 3. [Simulator User Guide](./SIMULATOR_USER_GUIDE.md)
**Purpose**: End-user documentation for running and developing with the simulator

**Contents**:
- Installation and setup instructions
- Quick start guide
- Command-line options
- Badge app development guide
- Troubleshooting common issues
- Advanced usage and debugging tips

**Audience**: Badge app developers using the simulator

## Quick Links

| Document | Best For | Status |
|----------|----------|--------|
| [Architecture](./SIMULATOR_ARCHITECTURE.md) | Understanding current implementation | ✅ Complete |
| [Design](./SIMULATOR_UPDATE_DESIGN.md) | Planning updates | ✅ Complete |
| [User Guide](./SIMULATOR_USER_GUIDE.md) | Using the simulator | ⚠️ For updated version |

## Current Simulator Status

**Branch**: `simulator`
**Status**: ⚠️ Out of date with main firmware
**Key Missing Feature**: Framebuffer support (`blit_buffer()`)

### What Works
- ✅ Dual circular display rendering
- ✅ Button input simulation (keyboard)
- ✅ Basic drawing commands (pixel, rect, circle, line, text)
- ✅ Socket-based IPC between MicroPython and GUI
- ✅ Hardware shims for displays, buttons, machine module

### What Needs Updates
- ❌ No `blit_buffer()` support (critical for modern apps)
- ❌ No `bitmap()` method
- ❌ Display initialization incompatible with current BSP
- ❌ LED visualization missing
- ❌ Speaker visualization missing
- ❌ Some API methods don't match current driver

## Getting Started

### For Users (Running Existing Simulator)

1. Read [User Guide](./SIMULATOR_USER_GUIDE.md)
2. Install prerequisites (Python 3.8+, pygame, MicroPython)
3. Checkout simulator branch: `git checkout simulator`
4. Run: `python3 simulator/main.py -p src/`

**Note**: Some newer apps may not work due to framebuffer requirements.

### For Developers (Updating Simulator)

1. Read [Architecture](./SIMULATOR_ARCHITECTURE.md) to understand current implementation
2. Read [Design](./SIMULATOR_UPDATE_DESIGN.md) for update plan
3. Follow implementation phases outlined in design doc
4. Test with existing badge apps
5. Update [User Guide](./SIMULATOR_USER_GUIDE.md) with new features

## Implementation Roadmap

Based on [Simulator Update Design](./SIMULATOR_UPDATE_DESIGN.md):

### Phase 1: Core Framebuffer Support ⏳
**Goal**: Add `blit_buffer()` to enable framebuffer-based apps

**Tasks**:
- [ ] Implement RGB565 to RGB888 conversion in GUI
- [ ] Add `blit_buffer()` command handler to `gui.py`
- [ ] Update `gc9a01.py` shim with `blit_buffer()` method
- [ ] Test with simple framebuffer example

**Priority**: 🔴 Critical (blocks most modern apps)

### Phase 2: API Completeness ⏳
**Goal**: Match current GC9A01 driver API

**Tasks**:
- [ ] Add `bitmap()` support
- [ ] Implement `write_len()` for all font types
- [ ] Test rotation and display selection
- [ ] Verify all driver methods work

**Priority**: 🟡 High (enables full app compatibility)

### Phase 3: Hardware Emulation ⏳
**Goal**: Visualize LEDs, speaker, and other peripherals

**Tasks**:
- [ ] Render NeoPixel LEDs on GUI
- [ ] Add speaker activity indicator
- [ ] Create basic IMU simulation
- [ ] Add RTC using system time

**Priority**: 🟢 Medium (improves dev experience)

### Phase 4: Display Initialization ⏳
**Goal**: Fix BSP compatibility

**Tasks**:
- [ ] Create `Displays` shim class
- [ ] Add simulator detection to firmware
- [ ] Test BSP initialization
- [ ] Verify all apps launch

**Priority**: 🟡 High (required for current firmware)

### Phase 5: Developer Experience ⏳
**Goal**: Make simulator easy to use

**Tasks**:
- [ ] Add more command-line options
- [ ] Create setup/install script
- [ ] Add example launch configs
- [ ] Improve error messages

**Priority**: 🟢 Medium (quality of life)

### Phase 6: Testing & Polish ⏳
**Goal**: Ensure reliability and performance

**Tasks**:
- [ ] Test all badge apps
- [ ] Measure and optimize performance
- [ ] Add debugging features (FPS, logging)
- [ ] Handle edge cases

**Priority**: 🟢 Medium (stability)

## Key Technical Concepts

### Framebuffer Architecture

The modern firmware uses MicroPython's `framebuf` module for efficient rendering:

```python
import framebuf

# Allocate memory buffer (240x240 pixels, 2 bytes per pixel)
buffer = bytearray(240 * 240 * 2)

# Create framebuffer object
fb = framebuf.FrameBuffer(buffer, 240, 240, framebuf.RGB565)

# Draw to framebuffer (in-memory, fast)
fb.fill(0xF800)  # Red
fb.rect(10, 10, 100, 100, 0xFFFF)  # White rectangle
fb.text("Hello", 50, 50, 0xFFFF)  # White text

# Send entire buffer to display (one transfer)
display.blit_buffer(buffer, 0, 0, 240, 240)
```

**Benefits**:
- All drawing operations happen in RAM (very fast)
- Single SPI transfer to display (efficient)
- Reduces screen flicker and tearing
- Enables double-buffering for smooth animation

**Simulator Challenge**: Must receive and render large buffers (115KB) efficiently over socket.

### Socket-Based IPC

The simulator uses TCP sockets for communication between MicroPython and pygame:

```
MicroPython Process          Socket (TCP)           Pygame GUI
┌─────────────────┐                              ┌──────────────┐
│  Badge Firmware │──── JSON Commands ────────► │              │
│                 │                              │   Display    │
│  Hardware Shims │◄─── JSON Responses ────────│   Rendering  │
└─────────────────┘                              └──────────────┘
     Port: N/A          127.0.0.1:4455              Window
```

**Command Example**:
```json
{
  "module": "gc9a01",
  "command": "fill_rect",
  "parameters": {
    "x": 10, "y": 10,
    "w": 50, "h": 50,
    "color": 63488,
    "display": 1
  }
}
```

**Response**:
```json
{
  "status": "ok",
  "resp": null
}
```

### Hardware Shims

Shims are fake implementations of hardware modules that forward operations to the GUI:

```python
# simulator/libraries/gc9a01.py
class GC9A01:
    def fill(self, color):
        # Instead of talking to SPI, send command to GUI
        emulator.send_command(
            'gc9a01',
            'fill',
            color=color,
            display=self.display
        )
```

This allows badge firmware to run unmodified - it thinks it's talking to real hardware!

## Contributing

### Adding New Features

1. **Update Design Doc**: Document your changes in [Design](./SIMULATOR_UPDATE_DESIGN.md)
2. **Implement**: Follow the architecture patterns
3. **Test**: Verify with multiple badge apps
4. **Document**: Update [User Guide](./SIMULATOR_USER_GUIDE.md)
5. **Submit PR**: Include tests and documentation updates

### Code Style

- Follow existing code patterns
- Add comments for complex logic
- Use type hints where appropriate
- Keep functions focused and modular

### Testing

Create test apps to verify functionality:
```python
# test_framebuffer.py
import framebuf

def test_framebuffer():
    buf = bytearray(240 * 240 * 2)
    fb = framebuf.FrameBuffer(buf, 240, 240, framebuf.RGB565)
    fb.fill(0xF800)
    display.blit_buffer(buf, 0, 0, 240, 240)
    # Verify display shows red
```

## Additional Resources

- **Main Firmware**: `src/` directory (main branch)
- **Hardware Docs**: [HARDWARE.md](../HARDWARE.md)
- **Architecture**: [ARCHITECTURE.md](../ARCHITECTURE.md)
- **Programming Guide**: [PROGRAMMING.md](../PROGRAMMING.md)

## FAQ

**Q: Why is the simulator on a separate branch?**
A: The simulator has diverged from main firmware and needs updates. Keeping it separate prevents breaking the main branch.

**Q: Can I use the simulator for WiFi features?**
A: Not currently. Network simulation is not implemented.

**Q: Is the simulator accurate?**
A: It's close but not perfect. Always test critical features on real hardware.

**Q: Can I contribute?**
A: Yes! See Contributing section above. Help with Phase 1-6 implementation is especially welcome.

**Q: When will the updated simulator be ready?**
A: It depends on contributor availability. The design is complete - implementation is needed.

## Contact

- **Issues**: GitHub issue tracker
- **Discussion**: BSides FW Discord/Slack
- **Documentation**: This directory

---

**Document Status**: ✅ Complete and current as of January 3, 2026

**Next Actions**:
1. Begin Phase 1 implementation (framebuffer support)
2. Test with existing badge apps
3. Iterate based on feedback
