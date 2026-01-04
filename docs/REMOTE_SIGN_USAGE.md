# Remote Sign UDP Control

## Overview

The Remote Sign app now supports multi-line text display on both screens, fixing the truncation issue where text like "UDP Enabl" and "No Networ" was cut off.

## What Changed

### 1. Text Display Fix (`src/apps/remote_sign.py`)

- **Multi-line Support**: Messages can now use the `|` pipe character to split text into top and bottom lines
- **Better Layout**: Text is split vertically for better readability on circular displays
- **Network Status**: Network info now displays properly with "UDP|Enabled" and "No|Network" format

Examples:
- `"UDP|Enabled"` → displays "UDP" on top, "Enabled" on bottom
- `"UDP|192.168.1.100"` → displays "UDP" on top, IP on bottom
- `"Port|8888"` → displays "Port" on top, "8888" on bottom

### 2. Command Tools

Three ways to control the badge:

#### A. Simple Python Script (Recommended for Quick Commands)

**File**: `remote_sign_cmd.py`

```bash
# Send message to badge
python remote_sign_cmd.py 192.168.1.100 "Alert" "System Down"

# Multi-line format
python remote_sign_cmd.py 192.168.1.100 "UDP|Active" "Port|8888"

# Control LEDs (all LEDs red at 75% brightness)
python remote_sign_cmd.py 192.168.1.100 led -1 255 0 0 75

# Control single LED (LED 0 green at 50% brightness)
python remote_sign_cmd.py 192.168.1.100 led 0 0 255 0 50
```

#### B. Typer CLI Commands

**Added to**: `tools.py`

```bash
# Send message
uv run python tools.py remote-sign 192.168.1.100 "Alert" "System Down"

# Multi-line format
uv run python tools.py remote-sign 192.168.1.100 "UDP|Active" "Ready|Go"

# Control LEDs
uv run python tools.py remote-sign-led 192.168.1.100 -1 255 0 0 75
uv run python tools.py remote-sign-led 192.168.1.100 0 0 255 0 50
```

#### C. Comprehensive Test Client (Already Existed)

**File**: `test_udp_client.py`

```bash
# Interactive mode
python test_udp_client.py 192.168.1.100 interactive

# Demo sequence
python test_udp_client.py 192.168.1.100 demo

# Quick test
python test_udp_client.py 192.168.1.100 test

# Send emergency alert
python test_udp_client.py 192.168.1.100 emergency
```

## Usage Examples

### Display Messages with Multi-line Format

```bash
# Show network status properly
python remote_sign_cmd.py 192.168.1.100 "UDP|Enabled" "Port|8888"

# Show connection info
python remote_sign_cmd.py 192.168.1.100 "WiFi|192.168.1.100" "Port|8888"

# Alert format
python remote_sign_cmd.py 192.168.1.100 "ALERT|Fire Drill" "Exit|Now"

# Status message
python remote_sign_cmd.py 192.168.1.100 "System|OK" "All|Clear"
```

### LED Control

```bash
# All LEDs red (alert)
python remote_sign_cmd.py 192.168.1.100 led -1 255 0 0 75

# All LEDs green (OK)
python remote_sign_cmd.py 192.168.1.100 led -1 0 255 0 50

# All LEDs blue (info)
python remote_sign_cmd.py 192.168.1.100 led -1 0 0 255 60

# Turn off all LEDs
python remote_sign_cmd.py 192.168.1.100 led -1 0 0 0 0

# Individual LED control (LED 0 yellow)
python remote_sign_cmd.py 192.168.1.100 led 0 255 255 0 50
```

### Combined Commands

```bash
# Emergency alert with red LEDs
python remote_sign_cmd.py 192.168.1.100 "EMERGENCY|Fire Drill" "Exit|Now"
python remote_sign_cmd.py 192.168.1.100 led -1 255 0 0 80

# Status OK with green LEDs
python remote_sign_cmd.py 192.168.1.100 "Status|OK" "All|Clear"
python remote_sign_cmd.py 192.168.1.100 led -1 0 255 0 50
```

## Technical Details

### Text Format Parsing

The `_refresh_displays()` method now:
1. Checks for `|` separator in message text
2. If found, splits text into top (y=80) and bottom (y=140) portions
3. Uses small font for multi-line, large font for single-line
4. Centers each line independently

### Display Positions

- **Single-line text**: Centered at y=104 (120 - 16)
- **Multi-line top**: y=80
- **Multi-line bottom**: y=140

### Network Status Display

The `_show_network_status()` method now formats messages as:
- Connected: `"UDP|192.168.1.100"` / `"Port|8888"` (green)
- No network: `"UDP|Enabled"` / `"No|Network"` (yellow)
- Disabled: `"Remote|Sign"` / `"UDP|Disabled"` (white/red)

## Testing

1. **Deploy updated code to badge**:
   ```bash
   uv run mpremote cp src/apps/remote_sign.py :apps/
   ```

2. **Start Remote Sign app on badge**:
   - Navigate to Menu → Remote Sign
   - Press A button to show network info
   - Verify IP address displays properly

3. **Test from computer**:
   ```bash
   # Test connection
   python remote_sign_cmd.py <badge_ip> "Test|Connection" "From|Computer"
   
   # Test LEDs
   python remote_sign_cmd.py <badge_ip> led -1 255 0 0 50
   ```

## Troubleshooting

### Text Still Truncated
- Use the `|` separator: `"Long Text|Message"` instead of `"Long Text Message"`
- Keep each line under ~12 characters for best fit
- Try small font: Set "Default Font Size" to "Small" in app config

### UDP Not Working
- Check badge WiFi: Press A button in Remote Sign app to see network info
- Verify "UDP Server Enabled" is True in app config (web UI)
- Check firewall on computer
- Verify badge IP with network scan or router

### LEDs Not Changing
- Check brightness value (0-100)
- LED index: 0-6 for individual, -1 for all
- RGB values: 0-255 each

## API Reference

### Message Command
```json
{
    "action": "set_message",
    "display1": "Text for top display",
    "display2": "Text for bottom display"
}
```

### LED Command
```json
{
    "action": "set_led",
    "led": -1,
    "color": [255, 0, 0],
    "brightness": 50
}
```

### Timeout Command
```json
{
    "action": "set_timeout",
    "timeout": 30,
    "timeout_action": "green"
}
```
