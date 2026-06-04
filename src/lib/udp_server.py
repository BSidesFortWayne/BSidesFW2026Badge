"""
UDP Remote Sign Server

A MicroPython-compatible UDP server for controlling the Remote Sign app over WiFi.
This server listens for JSON commands and forwards them to the Remote Sign app.
"""

import socket
import json
import asyncio
import time
from apps.remote_sign_controller import create_command_from_network_message


class UDPRemoteSignServer:
    """
    UDP server for remote control of the Remote Sign app.
    
    Listens for JSON commands over UDP and forwards them to the Remote Sign app.
    Designed to work with MicroPython's socket implementation.
    """
    
    def __init__(self, remote_sign_app, port=8888, buffer_size=1024):
        self.app = remote_sign_app
        self.port = port
        self.buffer_size = buffer_size
        self.socket = None
        self.running = False
        self.stats = {
            'commands_received': 0,
            'commands_processed': 0,
            'errors': 0,
            'start_time': 0
        }
    
    async def start(self):
        """Start the UDP server."""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Set socket to non-blocking mode for async operation
            self.socket.setblocking(False)
            
            # Bind to all interfaces on specified port
            self.socket.bind(('0.0.0.0', self.port))
            
            self.running = True
            self.stats['start_time'] = time.ticks_ms()
            
            print(f"UDP Remote Sign Server started on port {self.port}")
            
            # Start the server loop
            asyncio.create_task(self._server_loop())
            
        except Exception as e:
            print(f"Failed to start UDP server: {e}")
            self.running = False
    
    async def stop(self):
        """Stop the UDP server."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        print("UDP Remote Sign Server stopped")
    
    async def _server_loop(self):
        """Main server loop - handles incoming UDP packets."""
        while self.running:
            try:
                # Check for incoming data (non-blocking)
                try:
                    data, addr = self.socket.recvfrom(self.buffer_size)
                    self.stats['commands_received'] += 1
                    
                    # Process the command
                    await self._handle_message(data, addr)
                    
                except OSError as e:
                    # No data available (EAGAIN/EWOULDBLOCK is expected in non-blocking mode)
                    if e.errno == 11:  # EAGAIN
                        continue
                    else:
                        print(f"Socket error: {e}")
                        self.stats['errors'] += 1
                
            except Exception as e:
                print(f"Server loop error: {e}")
                self.stats['errors'] += 1
            finally:
                await asyncio.sleep(0.1)  # Small sleep to yield control
    
    async def _handle_message(self, data, addr):
        """Handle a single incoming message."""
        try:
            # Decode JSON message
            message_str = data.decode('utf-8')
            message = json.loads(message_str)
            
            print(f"Received command from {addr}: {message}")
            
            # Convert network message to app command
            command = create_command_from_network_message(message)
            
            if command and command:  # Check command is not empty dict
                # Add command to app's queue
                self.app.command_queue.append(command)
                self.stats['commands_processed'] += 1
                
                # Send success response
                response = {
                    "status": "ok",
                    "message": "Command queued successfully",
                    "timestamp": time.ticks_ms()
                }
            else:
                # Invalid command
                response = {
                    "status": "error", 
                    "message": "Invalid or unsupported command",
                    "timestamp": time.ticks_ms()
                }
            
            # Send response back to client
            await self._send_response(response, addr)
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            self.stats['errors'] += 1
            await self._send_error_response("Invalid JSON format", addr)
            
        except Exception as e:
            print(f"Message handling error: {e}")
            self.stats['errors'] += 1
            await self._send_error_response("Internal server error", addr)
    
    async def _send_response(self, response, addr):
        """Send response back to client."""
        try:
            response_data = json.dumps(response).encode('utf-8')
            self.socket.sendto(response_data, addr)
        except Exception as e:
            print(f"Failed to send response: {e}")
    
    async def _send_error_response(self, error_message, addr):
        """Send error response back to client."""
        response = {
            "status": "error",
            "message": error_message,
            "timestamp": time.ticks_ms()
        }
        await self._send_response(response, addr)
    
    def get_stats(self):
        """Get server statistics."""
        uptime_ms = time.ticks_ms() - self.stats['start_time'] if self.stats['start_time'] else 0
        return {
            # **self.stats,
            'uptime_ms': uptime_ms,
            'uptime_seconds': uptime_ms // 1000,
            'running': self.running,
            'port': self.port
        }


# Integration with Remote Sign app
class RemoteSignWithUDP:
    """
    Enhanced Remote Sign app with built-in UDP server support.
    
    This can be used as a wrapper or integrated directly into the RemoteSign app.
    """
    
    def __init__(self, remote_sign_app, udp_port=8888, auto_start_udp=True):
        self.app = remote_sign_app
        self.udp_server = UDPRemoteSignServer(remote_sign_app, udp_port)
        self.auto_start_udp = auto_start_udp
    
    async def setup(self):
        """Setup the app and optionally start UDP server."""
        await self.app.setup()
        
        if self.auto_start_udp:
            await self.udp_server.start()
    
    async def teardown(self):
        """Teardown app and stop UDP server."""
        await self.udp_server.stop()
        await self.app.teardown()
    
    async def update(self):
        """Update the app (UDP server runs independently)."""
        await self.app.update()
    
    def get_network_info(self):
        """Get network information for client connections."""
        import network
        
        # Try to get WiFi interface info
        try:
            sta_if = network.WLAN(network.STA_IF)
            if sta_if.active() and sta_if.isconnected():
                ip, subnet, gateway, dns = sta_if.ifconfig()
                return {
                    'ip': ip,
                    'port': self.udp_server.port,
                    'interface': 'station',
                    'connected': True
                }
        except Exception:
            pass
        
        # Try AP mode
        try:
            ap_if = network.WLAN(network.AP_IF)
            if ap_if.active():
                ip, subnet, gateway, dns = ap_if.ifconfig()
                return {
                    'ip': ip,
                    'port': self.udp_server.port,
                    'interface': 'access_point',
                    'connected': True
                }
        except Exception:
            pass
        
        return {
            'ip': 'unknown',
            'port': self.udp_server.port,
            'interface': 'none',
            'connected': False
        }


# Example usage and testing functions
def create_test_client():
    """Create a simple UDP client for testing (for testing on computer, not badge)."""
    return """
import socket
import json
import time

class RemoteSignClient:
    def __init__(self, host, port=8888):
        self.host = host
        self.port = port
    
    def send_command(self, command):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            data = json.dumps(command).encode('utf-8')
            sock.sendto(data, (self.host, self.port))
            
            # Wait for response (with timeout)
            sock.settimeout(5.0)
            response_data, _ = sock.recvfrom(1024)
            return json.loads(response_data.decode('utf-8'))
        finally:
            sock.close()
    
    def set_message(self, display1, display2=None):
        command = {"action": "set_message", "display1": display1}
        if display2:
            command["display2"] = display2
        return self.send_command(command)
    
    def set_led(self, led_index, r, g, b, brightness=50):
        command = {
            "action": "set_led",
            "led": led_index,
            "color": [r, g, b],
            "brightness": brightness
        }
        return self.send_command(command)
    
    def emergency_alert(self):
        result1 = self.set_message("EMERGENCY", "Fire Drill")
        result2 = self.set_led(-1, 255, 0, 0, 80)  # Bright red
        return result1, result2

# Usage:
# client = RemoteSignClient("192.168.1.100")
# client.set_message("Hello", "World")
# client.set_led(-1, 0, 255, 0, 50)  # All LEDs green
# client.emergency_alert()
"""


# Example commands for testing
EXAMPLE_UDP_COMMANDS = [
    # Set display messages
    {
        "action": "set_message",
        "display1": "Hello UDP",
        "display2": "Remote Control"
    },
    
    # Set all LEDs red
    {
        "action": "set_led",
        "led": -1,
        "color": [255, 0, 0],
        "brightness": 75
    },
    
    # Set LED 0 to blue
    {
        "action": "set_led", 
        "led": 0,
        "color": [0, 0, 255],
        "brightness": 50
    },
    
    # Set timeout for 30 seconds
    {
        "action": "set_timeout",
        "timeout": 30,
        "timeout_action": "green"
    },
    
    # Clear timeout
    {
        "action": "clear_timeout"
    }
]


if __name__ == "__main__":
    print("UDP Remote Sign Server for MicroPython")
    print("=====================================")
    print()
    print("Example commands:")
    for i, cmd in enumerate(EXAMPLE_UDP_COMMANDS, 1):
        print(f"{i}. {json.dumps(cmd, indent=2)}")
    print()
    print("To test from command line:")
    print("echo '{\"action\":\"set_message\",\"display1\":\"Test\"}' | nc -u badge_ip 8888")