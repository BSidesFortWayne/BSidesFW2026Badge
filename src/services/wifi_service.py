"""
WiFi Service

A background service that automatically connects to WiFi on boot if credentials are available.
This ensures WiFi is connected before apps like Remote Sign try to use the network.
"""

import asyncio
import json
import network
from lib.background_service import BackgroundService
from lib.smart_config import BoolDropdownConfig, RangeConfig
from lib.dns import MicroDNSSrv


class WiFiService(BackgroundService):
    """
    Background service for automatic WiFi connection.
    
    Reads wifi.json on boot and connects to the network if credentials exist.
    Handles both station mode (connecting to a WiFi network) and AP mode (creating an access point).
    """
    
    name = "WiFi"
    description = "Automatic WiFi connection service"
    
    def __init__(self, controller):
        super().__init__(controller)
        self.sta_if = None
        self.ap_if = None
        self.connected = False
        self.mode = None  # 'sta', 'ap', or None
        self.ssid = None
        self.ip_address = None
        
    def _setup_default_config(self):
        """Set up WiFi-specific configuration options."""
        self.config.add('auto_connect', BoolDropdownConfig("Auto-connect on Boot", True))
        self.config.add('retry_on_failure', BoolDropdownConfig("Retry on Failure", True))
        self.config.add('retry_interval_seconds', RangeConfig("Retry Interval (s)", 10, 120, 30, 5))
        
    async def start(self):
        """Start the WiFi service and attempt to connect."""
        print("WiFi Service: Starting")
        
        if not self.config['auto_connect'].value():
            print("WiFi Service: Auto-connect disabled")
            return
        
        # Try to load WiFi credentials from file
        wifi_config = self._load_wifi_config()
        
        if wifi_config:
            # Connect to existing WiFi network
            await self._connect_station_mode(wifi_config['essid'], wifi_config['password'])
        else:
            print("WiFi Service: No wifi.json found - WiFi not configured")
            # Note: AP mode is typically started by Settings app when needed
    
    async def stop(self):
        """Stop the WiFi service and disconnect."""
        print("WiFi Service: Stopping")
        
        if self.sta_if:
            self.sta_if.active(False)
            self.sta_if = None
        
        if self.ap_if:
            self.ap_if.active(False)
            self.ap_if = None
        
        self.connected = False
        self.mode = None
    
    async def update(self):
        """Periodic update to check connection status."""
        # Check if we should retry connection
        if (not self.connected and 
            self.config['retry_on_failure'].value() and 
            self.mode == 'sta'):
            
            # Reload config and try reconnecting
            wifi_config = self._load_wifi_config()
            if wifi_config:
                print("WiFi Service: Attempting to reconnect...")
                await self._connect_station_mode(wifi_config['essid'], wifi_config['password'])
                
                # Wait before next retry
                retry_interval = self.config['retry_interval_seconds'].value()
                await asyncio.sleep(retry_interval)
    
    def _load_wifi_config(self):
        """Load WiFi credentials from wifi.json file."""
        try:
            with open('wifi.json', 'r') as f:
                config = json.loads(f.read())
                return config
        except OSError:
            return None
        except Exception as e:
            print(f"WiFi Service: Error loading wifi.json: {e}")
            return None
    
    async def _connect_station_mode(self, essid, password):
        """Connect to a WiFi network in station mode."""
        try:
            print(f"WiFi Service: Connecting to '{essid}'...")
            
            # Initialize station interface
            self.sta_if = network.WLAN(network.STA_IF)
            self.sta_if.active(True)
            
            # Connect to network
            self.sta_if.connect(essid, password)
            
            # Wait for connection (with timeout)
            max_wait = 20  # 20 seconds timeout
            wait_count = 0
            
            while not self.sta_if.isconnected() and wait_count < max_wait:
                await asyncio.sleep(1)
                wait_count += 1
                if wait_count % 5 == 0:
                    print(f"WiFi Service: Still connecting... ({wait_count}s)")
            
            if self.sta_if.isconnected():
                # Successfully connected
                if_config = self.sta_if.ifconfig()
                self.ip_address = if_config[0]
                self.ssid = essid
                self.connected = True
                self.mode = 'sta'
                
                # Setup mDNS
                try:
                    MicroDNSSrv.Create({'*': self.ip_address})
                except Exception as e:
                    print(f"WiFi Service: mDNS setup failed: {e}")
                
                print(f"WiFi Service: Connected! IP: {self.ip_address}")
                print(f"WiFi Service: Network config: {if_config}")
                
                return True
            else:
                print(f"WiFi Service: Connection timeout after {max_wait}s")
                self.sta_if.active(False)
                self.connected = False
                return False
                
        except Exception as e:
            print(f"WiFi Service: Connection error: {e}")
            self.connected = False
            return False
    
    async def _create_access_point(self, essid, password):
        """Create a WiFi access point."""
        try:
            print(f"WiFi Service: Creating AP '{essid}'...")
            
            # Initialize AP interface
            self.ap_if = network.WLAN(network.AP_IF)
            self.ap_if.active(True)
            self.ap_if.config(
                essid=essid,
                authmode=network.AUTH_WPA_WPA2_PSK,
                password=password
            )
            
            # Wait for AP to become active
            max_wait = 10
            wait_count = 0
            
            while not self.ap_if.active() and wait_count < max_wait:
                await asyncio.sleep(0.5)
                wait_count += 1
            
            if self.ap_if.active():
                if_config = self.ap_if.ifconfig()
                self.ip_address = if_config[0]
                self.ssid = essid
                self.connected = True
                self.mode = 'ap'
                
                # Setup mDNS
                try:
                    MicroDNSSrv.Create({'*': self.ip_address})
                except Exception as e:
                    print(f"WiFi Service: mDNS setup failed: {e}")
                
                print(f"WiFi Service: AP created! IP: {self.ip_address}")
                return True
            else:
                print("WiFi Service: Failed to create AP")
                return False
                
        except Exception as e:
            print(f"WiFi Service: AP creation error: {e}")
            return False
    
    def get_status(self):
        """Get current WiFi status."""
        return {
            'connected': self.connected,
            'mode': self.mode,
            'ssid': self.ssid,
            'ip_address': self.ip_address,
            'interface': 'WiFi' if self.mode == 'sta' else 'AP' if self.mode == 'ap' else 'None'
        }
    
    def is_connected(self):
        """Check if WiFi is currently connected."""
        if self.mode == 'sta' and self.sta_if:
            return self.sta_if.isconnected()
        elif self.mode == 'ap' and self.ap_if:
            return self.ap_if.active()
        return False
