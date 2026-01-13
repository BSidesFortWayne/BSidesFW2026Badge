# Simulator Long Press Test Guide

## Changes Made

The simulator now properly supports long press detection by:

1. **Tracking button press timestamps** instead of binary states
2. **Maintaining pressed state** while keys are held down
3. **Letting firmware detect duration** - the firmware's `poll_buttons()` polls at 50ms intervals and detects when 750ms threshold is exceeded

## How It Works

### GUI Layer (`simulator/gui.py`)
- `button_states` now stores timestamps (milliseconds) when pressed, or 0 when released
- `KEYDOWN` event: Records `pygame.time.get_ticks()` as press time
- `KEYUP` event: Clears state to 0 and logs duration
- `get_inputs()`: Returns PCA9535 register value with bits cleared for pressed buttons

### PCA9535 Shim (`simulator/libraries/pca9535.py`)
- Unchanged - just queries GUI via `emulator.send_command('pca9535', 'get_inputs')`

### Firmware (`src/drivers/buttons.py`)
- Unchanged - polls PCA9535 every 50ms
- Tracks `last_press_times` for each button
- Fires `button_long_press_callbacks` after 750ms
- Fires `button_clicked_callbacks` on release if no long press occurred

## Testing

### Button Mapping
- Key `1` → Button 0
- Key `2` → Button 1  
- Key `3` → Button 2 (long press opens Menu)
- Key `4` → Button 3
- Key `5` → Button 4

### Expected Behavior

**Short Press (< 750ms)**:
1. Press key → firmware calls `button_pressed_callbacks`
2. Release key → firmware calls `button_clicked_callbacks`
3. App receives `button_click()` event

**Long Press (≥ 750ms)**:
1. Press key → firmware calls `button_pressed_callbacks`
2. Hold 750ms → firmware calls `button_long_press_callbacks`
3. Release key → firmware calls `button_released_callbacks` (no click fired)
4. App receives `button_long_press()` event

### Special Behavior
- **Key 3 long press** → Opens Menu app (controller.py line 211)
- **Keys 4+5 long press together** → Clears LED flag (controller.py line 202-226)

## Verification

Run the simulator and:
1. **Tap key 1** quickly - should see "Button click" in MicroPython output
2. **Hold key 1** for 1 second - should see "Long click detected" in MicroPython output
3. **Hold key 3** for 1 second - should open the Menu app

## Architecture Benefits

This implementation requires **zero firmware changes** because:
- The PCA9535 interface is unchanged (returns same register format)
- The firmware's polling and timing logic works identically
- Button press duration is detected by firmware, not GUI
- Easy to test firmware button handling without hardware
