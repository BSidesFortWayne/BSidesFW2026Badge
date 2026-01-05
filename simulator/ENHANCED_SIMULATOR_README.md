# Enhanced Badge Simulator with Hardware Controls

The enhanced simulator adds a control panel to the pygame simulator, allowing you to mock hardware inputs and states during development.

## Features

### Control Panel
Located on the right side of the simulator window with the following controls:

#### Accelerometer
- **Shake Device Button**: Instantly applies random acceleration data
- **Shake Magnitude Slider**: Controls the intensity of the shake (0.5g to 8g)
- **Live Accelerometer Display**: Shows current X, Y, Z acceleration values
- **Auto-decay**: Accelerometer values gradually return to rest state (0, 0, 1g)

#### Power & Battery
- **Battery Voltage Slider**: Mock ADC readings from 2.5V to 4.5V
- **Charge State Dropdown**: Simulate different charge controller states:
  - `not_charging`: Device running on battery
  - `charging`: Device plugged in and charging
  - `charged`: Battery full
  - `error`: Charge controller error state

#### WiFi
- **WiFi State Dropdown**: Control WiFi connection state:
  - `disconnected`: No WiFi connection
  - `connecting`: Attempting to connect
  - `connected`: Successfully connected to network
  - `passthrough`: Use host system's WiFi (future feature)
  - `ap_mode`: Access point mode

#### Bluetooth
- **Bluetooth State Dropdown**: Control Bluetooth state:
  - `disabled`: Bluetooth off
  - `advertising`: Broadcasting, waiting for connection
  - `connected`: Active Bluetooth connection
  - `system_passthrough`: Use host system's Bluetooth (future feature)

## Running the Enhanced Simulator

### Prerequisites
```bash
pip install pygame pygame-gui numpy pillow
```

### From Command Line
```bash
cd simulator
python3 main_enhanced.py -p ../src
```

### Using the Run Script
```bash
cd simulator
./run_enhanced.sh
```

## Keyboard Controls

Same as the standard simulator:
- `0`: Boot/Reset button (SW5)
- `1-4`: Top buttons (SW1-SW4)
- `7-9`: Game buttons (SW7-SW9)

## Hardware Mocking API

The enhanced GUI exposes these mock values through the normal command protocol:

### Accelerometer (LIS3DH)
```python
# In your badge code, accelerometer reads will use mocked values
x, y, z = bsp.imu.acceleration
```

The GUI responds to `lis3dh` module commands and returns the current mock acceleration data.

### ADC/Battery Voltage
```python
# Mock ADC readings (for battery voltage monitoring)
voltage = adc.read()  # Returns the slider value
```

The GUI responds to `adc` module commands and returns the current voltage slider value.

### WiFi State
Accessible via `gui.wifi_state` property (can be extended to respond to network commands).

### Bluetooth State  
Accessible via `gui.bluetooth_state` property (can be extended to respond to Bluetooth commands).

### Charge State
Accessible via `gui.charge_state` property (can be extended to mock charge controller pin states).

## Architecture

The enhanced simulator is built on top of the standard simulator with these additions:

1. **gui_enhanced.py**: Extended GUI class with pygame_gui controls
2. **main_enhanced.py**: Enhanced main loop with improved JSON parsing
3. **Fixed buffer handling**: Uses 65KB receive buffer with accumulation to handle large framebuffer blits

### Key Improvements Over Standard Simulator

1. **Larger receive buffer**: 65536 bytes instead of 1024 to handle large `blit_buffer` commands
2. **Buffer accumulation**: Handles JSON messages that span multiple TCP packets
3. **JSON parsing with retry**: Accumulates incomplete JSON instead of crashing
4. **Control panel**: Visual hardware mocking without editing code

## Future Enhancements

Planned features:
- WiFi passthrough (use host system's network)
- Bluetooth passthrough (use host system's Bluetooth)
- Charge controller pin state mocking
- Temperature sensor mocking
- GPIO pin state controls
- Persist mock settings between sessions
- Record/playback sensor data sequences

## Development Notes

When adding new hardware mocking:

1. Add state variable to `GUIEnhanced.__init__()`:
   ```python
   self.my_sensor_value = 0.0
   ```

2. Add UI control in `_create_ui_controls()`:
   ```python
   self.my_slider = pygame_gui.elements.UIHorizontalSlider(...)
   ```

3. Handle UI events in `gameloop()`:
   ```python
   elif event.ui_element == self.my_slider:
       self.my_sensor_value = event.value
   ```

4. Add command handler in `handle_command()`:
   ```python
   elif command['module'] == 'my_sensor':
       return self.my_sensor_value
   ```

5. Update driver shim in `simulator/libraries/` to send commands to GUI

## Troubleshooting

### pygame-gui not found
```bash
pip install pygame-gui
```

### Window too large for screen
Edit the control panel width in `gui_enhanced.py`:
```python
self.control_panel_width = 300  # Reduce this value
```

### Controls not responding
Make sure you're clicking on the controls, not the badge image. The control panel is on the right side.

### Large framebuffer errors
The enhanced simulator uses a 65KB buffer which should handle all normal operations. If you still see JSON decode errors, increase the buffer size in `main_enhanced.py`:
```python
chunk = emulator_conn.recv(65536)  # Increase this value
```
