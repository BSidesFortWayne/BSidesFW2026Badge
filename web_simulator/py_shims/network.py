"""Network module stub for WASM."""

STA_IF = 0
AP_IF = 1
STAT_IDLE = 0
STAT_CONNECTING = 1
STAT_GOT_IP = 3
STAT_NO_AP_FOUND = 2


class WLAN:
    def __init__(self, interface_id=STA_IF):
        self._active = False
        self._connected = False
        self._ssid = ''

    def active(self, state=None):
        if state is None:
            return self._active
        self._active = state

    def connect(self, ssid='', password=''):
        self._ssid = ssid
        print(f"[NETWORK] WiFi connect stub: {ssid}")

    def disconnect(self):
        self._connected = False

    def isconnected(self):
        return self._connected

    def status(self, param=None):
        if param == 'rssi':
            return -50
        return STAT_IDLE

    def ifconfig(self, config=None):
        if config is None:
            return ('0.0.0.0', '0.0.0.0', '0.0.0.0', '0.0.0.0')

    def config(self, *args, **kwargs):
        if args:
            return ''
        pass

    def scan(self):
        return []
