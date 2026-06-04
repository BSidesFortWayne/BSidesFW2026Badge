# Screenshot Guide for Badge Simulator

The pygame-based badge simulator now supports screenshot capture, similar to browser MCP tools. This allows you to capture the visual state of the simulator for debugging, documentation, or automated testing.

## Features

- **Keyboard Shortcut**: Press `F12` to instantly capture a screenshot
- **Programmatic API**: Send commands via JSON protocol socket
- **Auto-naming**: Automatically generates timestamped filenames
- **Custom paths**: Specify custom output locations
- **Full window capture**: Captures entire simulator including hardware controls

## Usage Methods

### 1. Keyboard Shortcut (Simplest)

While the simulator is running, simply press **F12** to capture a screenshot.

- Screenshots are automatically saved to `simulator/screenshots/`
- Filenames use format: `screenshot_YYYYMMDD_HHMMSS_####.png`
- Console/log shows the saved filepath

### 2. Command-Line Utility

Use the included `take_screenshot.py` utility:

```bash
# From simulator directory
cd simulator/

# Basic usage - auto-generated filename
./take_screenshot.py

# Custom output file
./take_screenshot.py -o my_badge_screenshot.png

# Wait for app to load, then capture
./take_screenshot.py --wait 2.0 -o startup_screen.png

# Different simulator instance
./take_screenshot.py --host localhost --port 4455
```

**Arguments:**
- `-o, --output PATH` - Custom output filepath
- `--wait SECONDS` - Wait before capturing (useful for timing)
- `--host HOST` - Simulator host (default: 127.0.0.1)
- `--port PORT` - JSON protocol port (default: 4455)
- `--timeout SECONDS` - Connection timeout (default: 5.0)

### 3. Python API

Integrate screenshot capture into your own scripts:

```python
import socket
import json

def take_screenshot(filepath=None, host='127.0.0.1', port=4455):
    """Capture simulator screenshot via JSON protocol"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    command = {
        'module': 'screenshot',
        'command': 'take',
        'parameters': {'filepath': filepath} if filepath else {}
    }
    
    sock.sendall(json.dumps(command).encode('utf-8'))
    response = json.loads(sock.recv(4096).decode('utf-8'))
    sock.close()
    
    return response['resp']  # Returns saved filepath

# Example usage
saved_path = take_screenshot('test_output.png')
print(f"Screenshot saved to: {saved_path}")
```

### 4. MCP-Style Integration

For AI assistants or automated testing tools using MCP-like patterns:

```python
# Example integration similar to browser MCP
class SimulatorMCP:
    def __init__(self, host='127.0.0.1', port=4455):
        self.host = host
        self.port = port
    
    def take_screenshot(self, filepath=None):
        """Capture screenshot from simulator"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        
        command = {
            'module': 'screenshot',
            'command': 'take',
            'parameters': {}
        }
        if filepath:
            command['parameters']['filepath'] = filepath
        
        sock.sendall(json.dumps(command).encode('utf-8'))
        response = json.loads(sock.recv(4096).decode('utf-8'))
        sock.close()
        
        if response['status'] == 'ok':
            return response['resp']
        raise RuntimeError(f"Screenshot failed: {response}")
    
    def wait_and_screenshot(self, wait_seconds, filepath=None):
        """Wait for state change, then capture"""
        import time
        time.sleep(wait_seconds)
        return self.take_screenshot(filepath)

# Usage
mcp = SimulatorMCP()
screenshot_path = mcp.take_screenshot('badge_state.png')
```

## Use Cases

### Debugging
```bash
# Capture current state when bug occurs
./take_screenshot.py -o bug_state_$(date +%s).png
```

### Documentation
```bash
# Capture each app screen
./take_screenshot.py -o docs/analog_clock_app.png
# (Switch to different app in simulator)
./take_screenshot.py -o docs/tetris_app.png
```

### Automated Testing
```python
import subprocess
import time

def test_app_rendering():
    # Start simulator (in background)
    sim_proc = subprocess.Popen(['./simulator.py'])
    time.sleep(3)  # Wait for startup
    
    # Capture initial state
    subprocess.run(['./take_screenshot.py', '-o', 'test_initial.png'])
    
    # ... interact with simulator via buttons/commands ...
    
    # Capture final state
    subprocess.run(['./take_screenshot.py', '-o', 'test_final.png'])
    
    # Compare images, assert expected state, etc.
    sim_proc.terminate()
```

### CI/CD Integration
```yaml
# Example GitHub Actions workflow
- name: Run simulator and capture screenshots
  run: |
    cd simulator
    ./simulator.py &
    SIM_PID=$!
    sleep 5
    ./take_screenshot.py -o artifacts/badge_render.png
    kill $SIM_PID
    
- name: Upload screenshots
  uses: actions/upload-artifact@v3
  with:
    name: simulator-screenshots
    path: simulator/artifacts/*.png
```

## File Formats

Screenshots are saved as **PNG** files with:
- Full color RGB (24-bit)
- Alpha channel preserved
- No compression loss
- Resolution: 870x1060 pixels (full simulator window)

## Screenshot Directory

Default location: `simulator/screenshots/`

The directory is automatically created if it doesn't exist. You can:
- Change location by specifying full path: `./take_screenshot.py -o ~/my_screenshots/badge.png`
- Use relative paths from simulator directory
- Use absolute paths for system-wide locations

## Troubleshooting

### "Connection refused" error
- Ensure simulator is running (`./simulator.py`)
- Check correct port (default: 4455 for JSON protocol)
- Verify no firewall blocking localhost connections

### Screenshot is black/empty
- Simulator needs to be fully initialized
- Try adding `--wait 1.0` to allow rendering to complete
- Check that display updates are not frozen

### Permission denied
- Ensure write permissions in output directory
- Use `sudo` if writing to system directories
- Default `screenshots/` directory is always writable

## Comparison to Browser MCP

Like browser MCP screenshot tools, the simulator screenshot feature provides:

✅ **Programmatic capture** - Call from scripts/code  
✅ **Visual feedback** - Capture exact rendered state  
✅ **Automated testing** - Integrate into test suites  
✅ **AI/LLM integration** - Feed visual state to AI assistants  
✅ **Custom paths** - Control output location  
✅ **Timestamped names** - Auto-organize captures  

**Advantages over browser MCP:**
- No browser overhead
- Captures hardware mock state (LEDs, controls)
- Faster (direct pygame surface capture)
- No network latency
- Full control panel visible

## Advanced: Binary Protocol Support

For maximum performance, you could also add screenshot support to the binary protocol. However, the JSON protocol is sufficient for screenshot capture since it's not a high-frequency operation.

## Keyboard Shortcuts Summary

| Key | Action |
|-----|--------|
| F12 | Take screenshot (auto-named) |
| 0-4 | Hardware buttons (SW1-SW5) |
| 7-9 | Game buttons |

## Future Enhancements

Potential additions:
- Video recording (capture sequence)
- Region-specific screenshots (display1 only, display2 only)
- Format options (JPEG, BMP)
- Clipboard integration
- Screenshot history/gallery viewer
- Diff mode (compare screenshots)
