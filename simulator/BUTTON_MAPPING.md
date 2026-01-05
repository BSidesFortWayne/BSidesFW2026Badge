# Badge Simulator Button Mapping

The BSides FW 2025 Badge has 7 buttons that are mapped to keyboard keys in the simulator.

## Hardware Button Layout

```
                SW1  SW2  SW3  SW4
                [1]  [2]  [3]  [4]    <- Top buttons (small)
                

                     [7] [8] [9]       <- Game buttons (large, center)


                        [0]            <- Reset/Boot button (SW5, near MCU)
```

## Keyboard Mapping

| Keyboard Key | Button | Hardware Name | Description |
|-------------|--------|---------------|-------------|
| `0` | Button 0 | SW5 | Boot/Reset button (GPIO pin 0) |
| `1` | Button 1 | SW1 | Top button 1 (PCA9535 bit 10) |
| `2` | Button 2 | SW2 | Top button 2 (PCA9535 bit 9) |
| `3` | Button 3 | SW3 | Top button 3 (PCA9535 bit 8) |
| `4` | Button 4 | SW4 | Top button 4 (PCA9535 bit 0) |
| `7` | Button 5 | SW7 | Game button 1 (PCA9535 bit 1) |
| `8` | Button 6 | SW8 | Game button 2 (PCA9535 bit 2) |
| `9` | Button 7 | SW9 | Game button 3 (PCA9535 bit 3) |

## Button Types

### GPIO Button (Button 0)
- Hardware: Connected directly to ESP32 GPIO pin 0
- Function: Boot button, can be used for reset functionality
- Behavior: Active low (pressed = 0, released = 1)

### PCA9535 Buttons (Buttons 1-7)
- Hardware: Connected via PCA9535 I2C GPIO expander at address 0x20
- Function: User interface buttons for app navigation and game controls
- Behavior: Active low (pressed = bit cleared, released = bit set)

## Usage in Apps

In your app code, buttons are numbered 0-7:

```python
def button_press(self, button: int):
    if button == 0:
        # Boot/reset button
        pass
    elif button in [1, 2, 3, 4]:
        # Top navigation buttons (SW1-SW4)
        pass
    elif button in [5, 6, 7]:
        # Game buttons (SW7-SW9)
        pass
```

## Common Button Patterns

- **Button 3**: Often used as "Menu" button (long press returns to main menu)
- **Buttons 4-5**: Navigation (up/down in V3 hardware)
- **Button 6**: Select/confirm
- **Buttons 5-7**: Game controls in game apps

## Long Press Detection

The button system supports long press detection (750ms threshold). Long press on button 3 (menu button) typically returns to the main menu in most apps.
