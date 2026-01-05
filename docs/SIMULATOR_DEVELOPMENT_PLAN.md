# Simulator Development Plan

## 1. Development Workflow

### Current State
The simulator currently **copies the entire src/ folder** every time it runs:
```bash
# In main_improved.py
shutil.copytree(args.project, 'src')  # Full copy
shutil.copytree('libraries', 'src', dirs_exist_ok=True)  # Overlay shims
```

### Recommended Workflow Options

#### Option A: Symlink Approach (Recommended)
**Best for**: Rapid development with live code changes

```python
# Modify main_improved.py setup_project_directory()
def setup_project_directory(project_path: str, logger):
    logger.log_info('Setting up project directory...')
    
    # Clean old src directory
    if os.path.exists('src'):
        if os.path.islink('src'):
            os.unlink('src')
        else:
            shutil.rmtree('src')
    
    # Create symlink to parent src/ directory
    os.symlink(os.path.abspath(project_path), 'src')
    logger.log_info(f'Created symlink: src -> {project_path}')
    
    # Copy ONLY simulator libraries over (don't use dirs_exist_ok)
    # This overlays shims without copying everything
    for lib_file in os.listdir('libraries'):
        src_file = os.path.join('libraries', lib_file)
        dst_file = os.path.join('src', lib_file)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)
    
    logger.log_info('Overlayed simulator library shims')
```

**Pros:**
- Instant changes - edit files in `../src/` and see results immediately
- No copy overhead on startup
- Single source of truth

**Cons:**
- Shim files must be copied over real files (potential confusion)
- Need to be careful not to commit simulator shims to main src/

#### Option B: Watch & Copy on Change
**Best for**: Avoiding symlink confusion with explicit copies

```python
# Add file watcher to detect changes and copy only modified files
import watchdog
# Implementation would watch ../src/ and copy changed files to simulator/src/
```

**Pros:**
- Clear separation between original and simulator versions
- Can see exactly what's being run

**Cons:**
- More complex implementation
- Additional dependency (watchdog)

#### Option C: Current Approach (Copy All)
**Best for**: Safety and isolation

**Pros:**
- Complete isolation - simulator can't affect source
- Simple to understand

**Cons:**
- ~2-3 second startup delay on every run
- Must restart simulator for every code change
- Disk space usage

### Recommended Solution: **Option A with safeguards**

1. Use symlink for quick development
2. Add `--copy-mode` flag for isolated testing
3. Add `.simulatorignore` file to prevent copying back shims
4. Update config.json:

```json
{
  "development": {
    "use_symlink": true,
    "watch_changes": false,
    "copy_on_change": false
  }
}
```

---

## 2. Peripheral Simulation Plan

### Architecture Overview

```
MicroPython (src/main.py)
    ↓ (via emulator.py shims)
Socket Communication (port 4455)
    ↓ (JSON commands)
Python Simulator (main_improved.py)
    ↓
GUI (gui.py) + Peripheral Handlers
```

### Current State
✅ **Already Working:**
- Display rendering (gc9a01.py shim → gui.py)
- Button input (keyboard 1-5 → PCA9535 shim)
- Basic LED support (neopixel.py shim exists)

❌ **Not Yet Working:**
- LED visual feedback in GUI
- Mouse/clickable buttons on GUI
- Network/Bluetooth
- Accelerometer shake simulation

---

## 3. Feature Implementation Plan

### Phase 1: LED Visual Feedback (Priority: HIGH)

**Current State:** 
- `neopixel.py` shim sends commands via emulator
- GUI receives commands but doesn't render

**Implementation:**

1. **Update gui.py to handle LED commands:**

```python
class GUI:
    def __init__(self, config=None, logger=None):
        # ... existing code ...
        self.leds = [(0, 0, 0)] * 7  # 7 RGB LEDs
        
    def handle_command(self, command):
        # ... existing gc9a01 handling ...
        
        elif command['module'] == 'neopixel':
            if command['command'] == 'write':
                self.leds = command['parameters']['leds']
                # Will be rendered in gameloop
                
    def render_leds(self):
        """Render LED strip on GUI"""
        # LED positions on board_render.png (approximate)
        led_positions = [
            (280, 400), (280, 430), (280, 460),  # Left side
            (280, 490), (280, 520), (280, 550),  # Right side
            (280, 580)  # Bottom
        ]
        
        for i, (x, y) in enumerate(led_positions):
            if i < len(self.leds):
                color = self.leds[i]
                # Draw glowing circle
                pygame.draw.circle(self.display, color, (x, y), 10)
                # Add glow effect
                pygame.draw.circle(self.display, 
                                 tuple(c//2 for c in color), 
                                 (x, y), 15, width=2)
    
    def gameloop(self):
        while self.running:
            # ... existing event handling ...
            
            # Render displays
            self.display.blit(self.board_texture, (0, 0))
            self.render_leds()  # ADD THIS
            self.display.blit(self.generate_circular_cutout(self.screen1), (70, 558))
            self.display.blit(self.generate_circular_cutout(self.screen2), (234, 774))
```

2. **Enhance board_render.png (optional):**
   - Add LED outlines/labels to show where they should appear
   - Or overlay transparent PNG with LED positions

**Effort:** 2-3 hours  
**Dependencies:** None

---

### Phase 2: Interactive GUI Buttons (Priority: HIGH)

**Goal:** Click buttons on GUI with mouse instead of only keyboard

**Implementation:**

1. **Define button hitboxes in gui.py:**

```python
class GUI:
    def __init__(self, config=None, logger=None):
        # ... existing code ...
        
        # Button hitboxes (x, y, width, height) - adjust based on board_render.png
        self.button_hitboxes = {
            0: pygame.Rect(100, 650, 50, 50),   # Button A
            1: pygame.Rect(180, 650, 50, 50),   # Button B  
            2: pygame.Rect(260, 650, 50, 50),   # Button C
            3: pygame.Rect(100, 900, 50, 50),   # Down/Nav
            4: pygame.Rect(180, 900, 50, 50),   # Up/Nav
        }
        
    def gameloop(self):
        while self.running:
            for event in pygame.event.get():
                # ... existing QUIT and KEYDOWN handlers ...
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_press(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.handle_mouse_release(event.pos)
    
    def handle_mouse_press(self, pos):
        """Handle mouse button press"""
        for button_id, rect in self.button_hitboxes.items():
            if rect.collidepoint(pos):
                self.button_states[button_id] = 1
                if self.logger:
                    self.logger.log_info(f'Button {button_id} pressed (mouse)')
                break
    
    def handle_mouse_release(self, pos):
        """Handle mouse button release"""
        for button_id, rect in self.button_hitboxes.items():
            if rect.collidepoint(pos):
                self.button_states[button_id] = 0
                break
    
    def render_button_overlays(self):
        """Draw semi-transparent overlays showing button hitboxes"""
        for button_id, rect in self.button_hitboxes.items():
            color = (0, 255, 0, 100) if self.button_states[button_id] else (255, 255, 255, 50)
            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill(color)
            self.display.blit(s, (rect.x, rect.y))
```

2. **Add keyboard shortcuts config:**

```python
# In config.json
{
  "gui": {
    "keyboard_shortcuts": {
      "button_0": ["1", "a"],
      "button_1": ["2", "b"],
      "button_2": ["3", "c"],
      "button_3": ["4", "DOWN"],
      "button_4": ["5", "UP"],
      "menu": ["ESCAPE", "m"]
    },
    "show_button_overlays": true
  }
}
```

**Effort:** 3-4 hours  
**Dependencies:** Need accurate button positions on board_render.png

---

### Phase 3: Network Support (Priority: MEDIUM)

**Goal:** Real network connectivity through host OS

**Implementation:**

1. **Update network.py shim:**

```python
# simulator/libraries/network.py
import socket as real_socket
import emulator

class WLAN:
    STA_IF = 0
    AP_IF = 1
    
    def __init__(self, interface):
        self.interface = interface
        self.active_state = False
        self._connected = False
    
    def active(self, state=None):
        if state is None:
            return self.active_state
        self.active_state = state
        emulator.send_command('network', 'active', state=state)
        return self.active_state
    
    def connect(self, ssid, password):
        """In simulator, use host OS network - always succeeds"""
        self._connected = True
        emulator.send_command('network', 'connect', ssid=ssid, connected=True)
    
    def isconnected(self):
        return self._connected
    
    def ifconfig(self):
        """Return host machine's network config"""
        # Get actual local IP
        s = real_socket.socket(real_socket.AF_INET, real_socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        except:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        
        return (local_ip, '255.255.255.0', '192.168.1.1', '8.8.8.8')
    
    def status(self, param=None):
        if param == 'rssi':
            return -50  # Simulated good signal
        return 3 if self._connected else 0  # STAT_GOT_IP or STAT_IDLE

# Socket should work natively - just use Python's socket module
# MicroPython socket API is compatible enough
```

2. **Update GUI to show network status:**

```python
def render_network_status(self):
    """Show WiFi icon when connected"""
    if self.network_connected:
        font = pygame.font.Font(None, 24)
        text = font.render('📶 WiFi', True, (0, 255, 0))
        self.display.blit(text, (450, 10))
```

**Effort:** 4-6 hours  
**Dependencies:** None (Python's socket module is sufficient)

---

### Phase 4: Bluetooth Support (Priority: LOW)

**Goal:** Real Bluetooth connectivity through host OS

**Challenges:**
- MicroPython BLE API is ESP32-specific
- Host OS Bluetooth APIs vary (BlueZ on Linux, CoreBluetooth on macOS, etc.)
- Complex state machine

**Implementation Options:**

**Option A: Mock Bluetooth (Recommended for Phase 1)**
```python
# simulator/libraries/bluetooth.py
import emulator

class BLE:
    def __init__(self):
        self.active_state = False
        
    def active(self, state=None):
        if state is None:
            return self.active_state
        self.active_state = state
        emulator.send_command('bluetooth', 'active', state=state)
        return state
    
    def gap_advertise(self, interval_us, adv_data=None):
        # Mock - just log
        emulator.send_command('bluetooth', 'advertise', interval=interval_us)
```

**Option B: Real Bluetooth via PyBluez**
```python
# Requires: pip install pybluez
import bluetooth as host_bt

class BLE:
    def __init__(self):
        self.socket = None
        
    # Implement actual Bluetooth using host OS
    # Map MicroPython BLE API to PyBluez calls
```

**Effort:** 
- Option A (mock): 2-3 hours
- Option B (real): 15-20 hours

**Recommendation:** Start with Option A, upgrade to Option B only if needed

---

### Phase 5: Accelerometer Simulation (Priority: HIGH)

**Goal:** Simulate shake/tilt events via GUI buttons

**Implementation:**

1. **Update lis3dh.py shim:**

```python
# simulator/libraries/lis3dh.py
import emulator

class LIS3DH:
    def __init__(self, i2c):
        self.i2c = i2c
        self._shake_active = False
        self._tilt_x = 0
        self._tilt_y = 0
        self._tilt_z = 0
        
    def shake_detected(self):
        """Check if shake was triggered from GUI"""
        result = emulator.send_command('accelerometer', 'get_shake')
        return result.get('resp', False)
    
    def read_accel(self):
        """Get current acceleration values"""
        result = emulator.send_command('accelerometer', 'get_accel')
        accel = result.get('resp', {'x': 0, 'y': 0, 'z': 9.8})
        return (accel['x'], accel['y'], accel['z'])
    
    def enable_shake_detection(self):
        emulator.send_command('accelerometer', 'enable_shake', enabled=True)
```

2. **Update gui.py:**

```python
class GUI:
    def __init__(self, config=None, logger=None):
        # ... existing code ...
        self.shake_triggered = False
        self.accel_x = 0.0
        self.accel_y = 0.0
        self.accel_z = 9.8
        
        # Add accelerometer control buttons
        self.accel_buttons = {
            'shake': pygame.Rect(450, 50, 80, 30),
            'tilt_left': pygame.Rect(420, 90, 40, 30),
            'tilt_right': pygame.Rect(510, 90, 40, 30),
        }
    
    def handle_command(self, command):
        # ... existing handlers ...
        
        elif command['module'] == 'accelerometer':
            if command['command'] == 'get_shake':
                result = self.shake_triggered
                self.shake_triggered = False  # Reset after read
                return result
            elif command['command'] == 'get_accel':
                return {
                    'x': self.accel_x,
                    'y': self.accel_y,
                    'z': self.accel_z
                }
    
    def gameloop(self):
        while self.running:
            for event in pygame.event.get():
                # ... existing handlers ...
                
                elif event.type == pygame.KEYDOWN:
                    # ... existing button keys ...
                    if event.key == pygame.K_s:
                        self.shake_triggered = True
                        if self.logger:
                            self.logger.log_info('Shake triggered!')
    
    def render_accel_controls(self):
        """Render accelerometer control UI"""
        font = pygame.font.Font(None, 20)
        
        # Shake button
        color = (255, 100, 100) if self.shake_triggered else (100, 100, 100)
        pygame.draw.rect(self.display, color, self.accel_buttons['shake'])
        text = font.render('SHAKE (S)', True, (255, 255, 255))
        self.display.blit(text, (self.accel_buttons['shake'].x + 5, 
                                  self.accel_buttons['shake'].y + 5))
        
        # Show current accel values
        accel_text = font.render(f'X:{self.accel_x:.1f} Y:{self.accel_y:.1f} Z:{self.accel_z:.1f}',
                                 True, (255, 255, 255))
        self.display.blit(accel_text, (420, 130))
```

3. **Keyboard shortcuts for accelerometer:**
```
S - Trigger shake
Arrow keys - Tilt simulation
R - Reset to flat
```

**Effort:** 4-5 hours  
**Dependencies:** None

---

## 4. Implementation Priority

### Sprint 1 (Essential): 
1. ✅ Fix development workflow (symlink approach)
2. ✅ LED visual feedback
3. ✅ Mouse-clickable buttons

### Sprint 2 (Important):
4. ✅ Accelerometer shake simulation
5. ✅ Network support (basic)

### Sprint 3 (Nice-to-have):
6. ⚠️ Bluetooth support (mock)
7. ⚠️ Advanced accelerometer (tilt angles)
8. ⚠️ Audio simulation (speaker PWM)

---

## 5. Configuration Updates

**Recommended config.json additions:**

```json
{
  "development": {
    "use_symlink": true,
    "auto_reload_on_change": false
  },
  "gui": {
    "window_title": "BSides FW 2025 Badge Simulator",
    "show_fps": true,
    "target_fps": 60,
    "show_button_overlays": true,
    "show_led_positions": true,
    "show_accel_controls": true,
    "keyboard_shortcuts": {
      "button_0": ["1", "a"],
      "button_1": ["2", "b"],
      "button_2": ["3", "c"],
      "button_3": ["4", "DOWN"],
      "button_4": ["5", "UP"],
      "menu": ["ESCAPE", "m"],
      "shake": ["s"],
      "reset_accel": ["r"]
    }
  },
  "peripherals": {
    "network": {
      "enabled": true,
      "auto_connect": false,
      "mock_mode": false
    },
    "bluetooth": {
      "enabled": false,
      "mock_mode": true
    },
    "accelerometer": {
      "enabled": true,
      "default_gravity": 9.8
    }
  }
}
```

---

## 6. Testing Strategy

1. **Unit Tests:** Test each shim module independently
2. **Integration Tests:** Run actual badge apps in simulator
3. **Visual Tests:** Compare simulator output to real hardware
4. **Performance Tests:** Ensure GUI maintains 60 FPS

---

## 7. Documentation Needed

- [ ] Update SIMULATOR_USER_GUIDE.md with new features
- [ ] Document keyboard shortcuts
- [ ] Add troubleshooting section
- [ ] Create video demo of simulator features

---

## 8. Future Enhancements

- Hot reload (detect file changes and restart MicroPython)
- Recording/playback of interactions
- Multiple simulator instances
- Remote debugging (step through code)
- Performance profiling
- Network traffic inspection
- Bluetooth packet analyzer

---

## Questions for Discussion

1. Should we commit simulator shim files to git, or gitignore them?
2. Do we want to support multiple "board profiles" (different LED counts, button layouts)?
3. Should accelerometer return real physics-based values or simplified digital states?
4. Do we want to simulate battery level/voltage?
