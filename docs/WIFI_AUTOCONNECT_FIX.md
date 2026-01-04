# WiFi Auto-Connect on Boot - Fix Summary

## Problem
WiFi was not connecting automatically on device boot, even when `wifi.json` credentials were configured. The WiFi only connected when manually entering the Settings app, making network-dependent apps like Remote Sign show "No Network" until Settings was visited.

## Root Cause
WiFi initialization was only happening in the Settings app's `__init__` method, not during system boot. This meant:
1. Badge boots → No WiFi connection
2. Apps start (like Remote Sign) → Show "No Network" 
3. User manually goes to Settings → WiFi finally connects
4. Remote Sign now shows network info

## Solution
Created a new **WiFi Service** (`src/services/wifi_service.py`) that:

1. **Auto-connects on boot**: Reads `wifi.json` and connects to WiFi automatically during system initialization
2. **Runs as background service**: Part of the system services, starts before apps load
3. **Configurable**: Web UI settings for auto-connect, retry behavior, retry intervals
4. **Retry logic**: Automatically retries connection if it fails
5. **Status tracking**: Apps can check WiFi status via the service

## Files Changed

### New Files
- **`src/services/wifi_service.py`** - WiFi background service for auto-connection

### Modified Files
- **`src/controller.py`** - Added WiFi service initialization before other services
- **`src/apps/remote_sign.py`** - Already fixed (larger multi-line text support)

## How It Works

### Boot Sequence (New)
```
1. boot.py → Initialize displays
2. main.py → Create Controller
3. Controller.__init__() → Initialize services
4. WiFiService.start() → Auto-connect to WiFi (if wifi.json exists)
5. Apps load → Network already available
6. Remote Sign shows proper IP address immediately
```

### WiFi Service Features

**Configuration (Web UI: `/config`)**
- `auto_connect` - Enable/disable auto-connect on boot (default: True)
- `retry_on_failure` - Retry if connection fails (default: True)
- `retry_interval_seconds` - Seconds between retries (default: 30, range: 10-120)

**Connection Process**
1. Looks for `wifi.json` in root directory
2. If found: Connects in station mode (joins WiFi network)
3. If not found: No action (Settings app can create AP mode)
4. Sets up mDNS for badge.local access
5. Retries automatically if connection fails

**Status API**
```python
# From any app or code:
wifi_status = controller.wifi_service.get_status()
# Returns:
{
    'connected': True/False,
    'mode': 'sta' or 'ap' or None,
    'ssid': 'YourNetwork',
    'ip_address': '192.168.1.100',
    'interface': 'WiFi' or 'AP' or 'None'
}
```

## Testing

### 1. Deploy Files
```bash
uv run mpremote cp src/services/wifi_service.py :services/
uv run mpremote cp src/controller.py :
```

### 2. Reset Badge
```bash
uv run mpremote reset
```

### 3. Check WiFi Connection
Watch the serial output - you should see:
```
WiFi Service: Starting
WiFi Service: Connecting to 'YourNetwork'...
WiFi Service: Connected! IP: 192.168.1.100
WiFi Service: Network config: ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')
```

### 4. Test Remote Sign
```bash
# Navigate to Remote Sign app on badge
# Should immediately show: "UDP|192.168.1.100" / "Port|8888"
# (instead of "No Network")

# Test UDP command
python remote_sign_cmd.py 192.168.1.100 "Test|Boot" "WiFi|Works"
```

## Configuration Files

### wifi.json (Root Directory)
```json
{
    "essid": "YourWiFiNetwork",
    "password": "YourPassword"
}
```

Created via command:
```bash
uv run python tools.py program-wifi YourSSID YourPassword
```

### Service Config (Auto-created)
Location: `config/services/wifi.json`

Example:
```json
{
    "auto_connect": true,
    "retry_on_failure": true,
    "retry_interval_seconds": 30
}
```

Editable via web UI at `http://<badge-ip>/config` when Settings app is running.

## Benefits

1. ✅ **Immediate Network Access**: WiFi connects before apps start
2. ✅ **Better UX**: Remote Sign shows IP immediately, not "No Network"
3. ✅ **Reliable**: Auto-retry on connection failures
4. ✅ **Configurable**: Disable auto-connect if needed via web UI
5. ✅ **Non-Breaking**: Settings app still works as before for AP mode
6. ✅ **Observable**: Service status visible in system info

## Troubleshooting

### WiFi not connecting on boot
1. Check `wifi.json` exists in root directory:
   ```bash
   uv run mpremote ls
   ```
2. Check credentials are correct in wifi.json
3. Check serial output for connection errors
4. Try manual connection via Settings app to verify credentials

### Still shows "No Network" in Remote Sign
1. Wait 10-20 seconds after boot (connection takes time)
2. Check WiFi service is enabled: Serial should show "WiFi Service: Starting"
3. Press button A in Remote Sign to manually refresh network info
4. Check WiFi service status via serial console

### Want to disable auto-connect
1. Go to Settings app → Start web server
2. Navigate to `http://<badge-ip>/config`
3. Find WiFi Service section
4. Set "Auto-connect on Boot" to False
5. Save configuration

## Future Enhancements

Possible additions to WiFi service:
- Signal strength monitoring
- Automatic AP mode fallback if STA fails
- Multiple network credential support
- WiFi status LED indicator
- Connection history/logging
- Speed test capabilities
