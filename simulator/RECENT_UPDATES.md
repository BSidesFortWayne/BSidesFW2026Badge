# Simulator Updates - January 2026

## Summary of Changes

Three major improvements have been made to the simulator:

### 1. Screenshot Filename & Controls Parameter Support ✓

**Problem**: The `take_screenshot.py` script accepted a filename parameter but didn't pass it to the simulator properly.

**Solution**:
- Updated the screenshot command protocol to accept both `filepath` and `include_controls` parameters
- Modified `take_screenshot.py` to support `--include-controls` flag
- Updated GUI's `take_screenshot()` method to accept these parameters
- Screenshots now properly save to custom paths and can include/exclude the control panel

**Usage**:
```bash
# Basic screenshot (badge only)
python simulator/take_screenshot.py --output my_badge.png

# Include control panel in screenshot
python simulator/take_screenshot.py --output full_sim.png --include-controls
```

### 2. Expandable/Collapsible Log Window ✓

**Feature**: Added a log panel at the bottom of the simulator window that shows real-time logs.

**Details**:
- Log panel displays the same output as console (stdout/stderr from MicroPython)
- Shows last 100 log messages with color coding:
  - **Blue**: INFO messages
  - **Orange**: WARNING messages  
  - **Red**: ERROR messages
- Timestamps on all log entries
- Toggle button in control panel: "▼ Hide Log Panel" / "▶ Show Log Panel"
- Window dynamically resizes when log panel is toggled
- Logs are also integrated with button presses, hardware events, and shake actions

**Implementation**:
- Added `log_buffer` to GUI class for storing messages
- New `add_log_message()` method for adding timestamped log entries
- New `render_log_panel()` method for drawing the log UI
- Integrated with MicroPython stdout/stderr streams
- Log panel height: 250px (configurable via `self.log_panel_height`)

### 3. Clickable Button Areas on Simulator ✓

**Feature**: Mouse clicks on the badge hardware image now trigger button presses.

**Details**:
- Added visual overlays showing clickable button areas (semi-transparent circles)
- Buttons highlight in **green** when pressed
- Button labels (1-7) displayed in circle centers
- Works alongside existing keyboard controls (0-4, 7-9 keys)
- Proper press/release timing tracked
- All button events logged to console and log panel

**Button Positions** (approximate):
- SW1-SW4: Top row of badge (buttons 1-4)
- SW7-SW9: Left side game buttons (buttons 5-7)

**Implementation**:
- `button_click_areas` list defines clickable regions: `(x, y, radius, button_index)`
- New `render_button_click_areas()` method draws overlay circles
- Mouse event handlers in gameloop detect clicks within button radius
- Uses Pythagorean distance calculation for hit detection

## Technical Details

### Modified Files

1. **simulator/take_screenshot.py**
   - Added `include_controls` parameter to `send_screenshot_command()`
   - Added `--include-controls` CLI argument
   - Properly passes parameters to simulator via JSON protocol

2. **simulator/gui.py**
   - Added log panel UI system (240+ lines of new code)
   - Added clickable button overlay system
   - Enhanced event handling for mouse clicks
   - Integrated logging throughout hardware mock actions
   - Dynamic window resizing for log panel toggle

3. **simulator/simulator.py**
   - Updated stdout/stderr streaming to feed GUI log window
   - Handles case with and without logger instance

### API Changes

**Screenshot Command** (JSON Protocol):
```json
{
  "module": "screenshot",
  "command": "take",
  "parameters": {
    "filepath": "/path/to/screenshot.png",  // Optional
    "include_controls": false                // Optional, default: false
  }
}
```

**New GUI Methods**:
- `add_log_message(message: str, level: str = 'INFO')` - Add entry to log buffer
- `render_log_panel()` - Draw log panel on screen
- `render_button_click_areas()` - Draw clickable button overlays

## Testing

To test the new features:

1. **Screenshot with custom filename**:
   ```bash
   uv run simulator/run.sh &
   sleep 5
   python simulator/take_screenshot.py --output test.png
   python simulator/take_screenshot.py --output test_full.png --include-controls
   ```

2. **Log Panel**:
   - Run simulator
   - Look for log panel at bottom
   - Click "▼ Hide Log Panel" button to toggle
   - Perform actions (shake, button press) and watch logs appear

3. **Clickable Buttons**:
   - Run simulator
   - Look for semi-transparent circles over badge buttons
   - Click on circles to trigger button presses
   - Verify button highlights green when pressed
   - Check log panel for press/release messages

## Notes

- Button click areas can be adjusted by modifying `self.button_click_areas` in `gui.py`
- Log panel height configurable via `self.log_panel_height` (default: 250px)
- Maximum log buffer size: 100 messages (configurable via `self.max_log_lines`)
- All features maintain backward compatibility with existing simulator API
