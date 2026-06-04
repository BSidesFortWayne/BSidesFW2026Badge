"""Network module simulator for badge simulator"""

# Network interface types
STA_IF = 0
AP_IF = 1

# WiFi modes
MODE_11B = 1
MODE_11G = 2
MODE_11N = 4

# Auth modes
AUTH_OPEN = 0
AUTH_WEP = 1
AUTH_WPA_PSK = 2
AUTH_WPA2_PSK = 3
AUTH_WPA_WPA2_PSK = 4

class WLAN:
    """Simulated WLAN interface"""
    
    def __init__(self, interface_id):
        self._interface_id = interface_id
        self._active = False
        self._connected = False
        self._ssid = None
        self._config = {}
    
    def active(self, is_active=None):
        """Get or set the active state"""
        if is_active is None:
            return self._active
        self._active = is_active
        return self._active
    
    def connect(self, ssid=None, password=None):
        """Connect to a WiFi network (simulated)"""
        self._ssid = ssid
        # In simulator, pretend we're always connected
        self._connected = True
    
    def disconnect(self):
        """Disconnect from WiFi"""
        self._connected = False
        self._ssid = None
    
    def isconnected(self):
        """Check if connected to WiFi"""
        return self._connected
    
    def status(self):
        """Get connection status"""
        if self._connected:
            return 3  # STAT_GOT_IP
        return 0  # STAT_IDLE
    
    def ifconfig(self, config=None):
        """Get or set network interface configuration"""
        if config is None:
            # Return (ip, subnet, gateway, dns)
            return ('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')
        # Set config (no-op in simulator)
        pass
    
    def config(self, param=None, **kwargs):
        """Get or set network configuration"""
        if param is None and not kwargs:
            return self._config
        if param:
            return self._config.get(param)
        self._config.update(kwargs)
    
    def scan(self):
        """Scan for available networks (returns empty list in simulator)"""
        return []
