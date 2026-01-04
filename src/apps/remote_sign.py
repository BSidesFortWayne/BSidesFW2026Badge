"""
Remote Sign App

A controllable sign that can display messages and control LEDs via external commands.
Supports timeouts for automatic state changes and can be used for conference signage,
status indicators, or remote messaging. Includes optional UDP server for network control.
"""

import time
import gc9a01
from apps.app import BaseApp
from lib.smart_config import BoolDropdownConfig, EnumConfig, RangeConfig
import fonts.arial16px as arial16px
import fonts.arial32px as arial32px

# UDP server imports (imported conditionally to avoid errors if not available)
try:
    from lib.udp_server import UDPRemoteSignServer
    UDP_AVAILABLE = True
except ImportError:
    UDP_AVAILABLE = False
    print("UDP server not available - network control disabled")


class SignState:
    """Represents the current state of the remote sign."""
    
    def __init__(self):
        self.message_display1 = "Remote Sign"
        self.message_display2 = "Ready"
        self.bg_color_display1 = gc9a01.BLACK
        self.fg_color_display1 = gc9a01.WHITE
        self.bg_color_display2 = gc9a01.BLACK
        self.fg_color_display2 = gc9a01.WHITE
        self.led_colors = [(0, 0, 0)] * 7  # All LEDs off initially
        self.timeout_enabled = False
        self.timeout_end_time = 0
        self.timeout_action = "green"  # "green", "off", "default"
        self.last_update_time = time.ticks_ms()
        
    def set_timeout(self, seconds: int, action: str = "green"):
        """Set a timeout for automatic state change."""
        self.timeout_enabled = True
        self.timeout_end_time = time.ticks_ms() + (seconds * 1000)
        self.timeout_action = action
        
    def clear_timeout(self):
        """Clear any active timeout."""
        self.timeout_enabled = False
        self.timeout_end_time = 0
        
    def is_timeout_expired(self) -> bool:
        """Check if the timeout has expired."""
        if not self.timeout_enabled:
            return False
        return time.ticks_ms() >= self.timeout_end_time
        
    def get_timeout_remaining_seconds(self) -> int:
        """Get remaining timeout seconds."""
        if not self.timeout_enabled:
            return 0
        remaining_ms = self.timeout_end_time - time.ticks_ms()
        return max(0, remaining_ms // 1000)


class RemoteSign(BaseApp):
    name = "Remote Sign"
    
    def __init__(self, controller):
        super().__init__(controller)
        self.display1 = self.controller.bsp.displays.display1
        self.display2 = self.controller.bsp.displays.display2
        self.leds = self.controller.bsp.leds
        
        # Configuration options
        self.config.add('auto_refresh_enabled', BoolDropdownConfig("Auto Refresh Display", True))
        self.config.add('refresh_rate_ms', RangeConfig("Refresh Rate (ms)", 100, 2000, 500, 100))
        self.config.add('default_font_size', EnumConfig("Default Font Size", ["Small", "Large"], "Large"))
        self.config.add('show_timeout_countdown', BoolDropdownConfig("Show Timeout Countdown", True))
        self.config.add('default_led_brightness', RangeConfig("LED Brightness", 0, 100, 30, 5))
        
        # UDP server configuration (only add if UDP is available)
        if UDP_AVAILABLE:
            self.config.add('udp_enabled', BoolDropdownConfig("UDP Server Enabled", True))
            self.config.add('udp_port', RangeConfig("UDP Port", 1024, 65535, 8888, 1))
            self.config.add('show_network_info', BoolDropdownConfig("Show Network Info", True))
        
        # Sign state
        self.state = SignState()
        
        # Font selection
        self.font_small = arial16px
        self.font_large = arial32px
        
        # Commands queue for external control
        self.command_queue = []
        
        # Last refresh time for rate limiting
        self.last_refresh_time = 0
        
        # UDP server instance (if enabled)
        self.udp_server = None
        
        # Network info for display
        self.network_info = {
            'ip': 'No Network',
            'port': 8888,
            'connected': False
        }
    
    async def setup(self):
        """Initialize the remote sign app."""
        print("Setting up Remote Sign")
        
        # Initialize displays
        self.display1.fill(self.state.bg_color_display1)
        self.display2.fill(self.state.bg_color_display2)
        
        # Initialize LEDs (start with all off)
        for i in range(7):
            self.leds.leds[i] = (0, 0, 0)  # Start with LEDs off
        self.leds.leds.write()
        
        # Start UDP server if enabled and available
        if UDP_AVAILABLE and self.config['udp_enabled'].value():
            await self._start_udp_server()
        
        # Get network info for display
        self._update_network_info()
        
        # Show initial status (with network info if enabled)
        if UDP_AVAILABLE and self.config['show_network_info'].value():
            self._show_network_status()
        else:
            # Display initial messages
            self._refresh_displays()
        
    async def teardown(self):
        """Clean up when leaving the app."""
        print("Tearing down Remote Sign")
        
        # Stop UDP server if running
        if self.udp_server:
            await self.udp_server.stop()
            self.udp_server = None
        
        # Turn off all LEDs
        self.leds.turn_off_all()
        
        # Clear displays
        self.display1.fill(gc9a01.BLACK)
        self.display2.fill(gc9a01.BLACK)
    
    async def update(self):
        """Main update loop for the remote sign."""
        current_time = time.ticks_ms()
        
        # Process any pending commands
        self._process_commands()
        
        # Check for timeout expiration
        if self.state.is_timeout_expired():
            self._handle_timeout_action()
        
        # UDP server management (if available)
        if UDP_AVAILABLE:
            udp_enabled = self.config['udp_enabled'].value()
            
            if udp_enabled and not self.udp_server:
                await self._start_udp_server()
            elif not udp_enabled and self.udp_server:
                await self.udp_server.stop()
                self.udp_server = None
        
        # Update network info periodically
        if UDP_AVAILABLE and hasattr(self, '_last_network_update'):
            if time.ticks_diff(current_time, self._last_network_update) > 10000:  # Every 10 seconds
                self._update_network_info()
        elif UDP_AVAILABLE:
            self._last_network_update = current_time
        
        # Auto-refresh display if enabled and enough time has passed
        if self.config['auto_refresh_enabled'].value():
            refresh_rate = self.config['refresh_rate_ms'].value()
            if time.ticks_diff(current_time, self.last_refresh_time) >= refresh_rate:
                self._refresh_displays()
                self.last_refresh_time = current_time
    
    def _process_commands(self):
        """Process any pending commands from the queue."""
        while self.command_queue:
            command = self.command_queue.pop(0)
            self._execute_command(command)
    
    def _execute_command(self, command: dict):
        """Execute a single command."""
        cmd_type = command.get('type')
        
        if cmd_type == 'set_message':
            self._handle_set_message_command(command)
        elif cmd_type == 'set_led':
            self._handle_set_led_command(command)
        elif cmd_type == 'set_timeout':
            self._handle_set_timeout_command(command)
        elif cmd_type == 'clear_timeout':
            self.state.clear_timeout()
        elif cmd_type == 'set_colors':
            self._handle_set_colors_command(command)
        else:
            print(f"Unknown command type: {cmd_type}")
    
    def _handle_set_message_command(self, command: dict):
        """Handle setting display messages."""
        if 'display1' in command:
            self.state.message_display1 = command['display1']
        if 'display2' in command:
            self.state.message_display2 = command['display2']
        
        # Force immediate refresh
        self._refresh_displays()
    
    def _handle_set_led_command(self, command: dict):
        """Handle LED control commands."""
        led_index = command.get('led', 0)
        color = command.get('color', (0, 0, 0))
        brightness = command.get('brightness', self.config['default_led_brightness'])
        
        if 0 <= led_index < 7:
            # Apply brightness scaling
            r, g, b = color
            scale = brightness / 100.0
            scaled_color = (int(r * scale), int(g * scale), int(b * scale))
            
            if led_index == -1:  # All LEDs
                for i in range(7):
                    self.leds.leds[i] = scaled_color
            else:
                self.leds.leds[led_index] = scaled_color
            
            self.leds.leds.write()
    
    def _handle_set_timeout_command(self, command: dict):
        """Handle timeout setting commands."""
        seconds = command.get('seconds', 60)
        action = command.get('action', 'green')
        self.state.set_timeout(seconds, action)
    
    def _handle_set_colors_command(self, command: dict):
        """Handle display color commands."""
        if 'display1_bg' in command:
            self.state.bg_color_display1 = command['display1_bg']
        if 'display1_fg' in command:
            self.state.fg_color_display1 = command['display1_fg']
        if 'display2_bg' in command:
            self.state.bg_color_display2 = command['display2_bg']
        if 'display2_fg' in command:
            self.state.fg_color_display2 = command['display2_fg']
        
        # Force immediate refresh
        self._refresh_displays()
    
    def _handle_timeout_action(self):
        """Handle what happens when timeout expires."""
        print(f"Timeout expired, executing action: {self.state.timeout_action}")
        
        if self.state.timeout_action == "green":
            # Set all LEDs to green
            for i in range(7):
                self.leds.leds[i] = (0, 255, 0)
            self.leds.leds.write()
            self.state.message_display1 = "TIMEOUT"
            self.state.message_display2 = "Complete"
            self.state.bg_color_display1 = gc9a01.BLACK
            self.state.fg_color_display1 = gc9a01.GREEN
            
        elif self.state.timeout_action == "off":
            # Turn off all LEDs
            self.leds.turn_off_all()
            self.state.message_display1 = "Sign"
            self.state.message_display2 = "Disabled"
            self.state.bg_color_display1 = gc9a01.BLACK
            self.state.fg_color_display1 = gc9a01.RED
            
        elif self.state.timeout_action == "default":
            # Return to default state
            self.leds.turn_off_all()
            self.state.message_display1 = "Remote Sign"
            self.state.message_display2 = "Ready"
            self.state.bg_color_display1 = gc9a01.BLACK
            self.state.fg_color_display1 = gc9a01.WHITE
            self.state.bg_color_display2 = gc9a01.BLACK
            self.state.fg_color_display2 = gc9a01.WHITE
        
        # Clear the timeout
        self.state.clear_timeout()
        
        # Force refresh
        self._refresh_displays()
    
    def _draw_centered_text(self, display, text, y_pos, fg_color, bg_color, font=None):
        """Draw centered text at specified y position."""
        if font is None:
            font = self.font_large if self.config['default_font_size'].value() == "Large" else self.font_small
        
        # Rough estimate for centering
        text_width = len(text) * 8
        x_pos = max(0, (240 - text_width) // 2)
        
        display.write(font, text, x_pos, y_pos, fg_color, bg_color)
    
    def _refresh_displays(self):
        """Refresh both displays with current messages."""
        font = self.font_large if self.config['default_font_size'].value() == "Large" else self.font_small
        # Use large font for multi-line too (was too small with font_small)
        font_multiline = self.font_large
        
        # Display 1 - Check if message contains a '|' separator for top/bottom text
        self.display1.fill(self.state.bg_color_display1)
        message1 = self.state.message_display1
        
        # Add timeout countdown if enabled and active
        if (self.config['show_timeout_countdown'].value() and 
            self.state.timeout_enabled):
            remaining = self.state.get_timeout_remaining_seconds()
            message1 += f" ({remaining}s)"
        
        if '|' in message1:
            # Split into top and bottom text - use large font with adjusted positions
            parts = message1.split('|', 1)
            self._draw_centered_text(self.display1, parts[0].strip(), 70, 
                                    self.state.fg_color_display1, self.state.bg_color_display1, font_multiline)
            self._draw_centered_text(self.display1, parts[1].strip(), 150, 
                                    self.state.fg_color_display1, self.state.bg_color_display1, font_multiline)
        else:
            # Center the text vertically
            self._draw_centered_text(self.display1, message1, 120 - 16, 
                                    self.state.fg_color_display1, self.state.bg_color_display1, font)
        
        # Display 2 - Check if message contains a '|' separator for top/bottom text
        self.display2.fill(self.state.bg_color_display2)
        message2 = self.state.message_display2
        
        if '|' in message2:
            # Split into top and bottom text - use large font with adjusted positions
            parts = message2.split('|', 1)
            self._draw_centered_text(self.display2, parts[0].strip(), 70, 
                                    self.state.fg_color_display2, self.state.bg_color_display2, font_multiline)
            self._draw_centered_text(self.display2, parts[1].strip(), 150, 
                                    self.state.fg_color_display2, self.state.bg_color_display2, font_multiline)
        else:
            # Center the text vertically
            self._draw_centered_text(self.display2, message2, 120 - 16, 
                                    self.state.fg_color_display2, self.state.bg_color_display2, font)
    
    # UDP Server methods
    async def _start_udp_server(self):
        """Start the UDP server."""
        if not UDP_AVAILABLE:
            return
            
        try:
            port = self.config['udp_port'].value()
            self.udp_server = UDPRemoteSignServer(self, port)
            await self.udp_server.start()
            
            print(f"UDP server started on port {port}")
            
            # Update display to show server status
            if self.config['show_network_info'].value():
                self._show_network_status()
                
        except Exception as e:
            print(f"Failed to start UDP server: {e}")
            self.udp_server = None
    
    def _update_network_info(self):
        """Update network information."""
        if not UDP_AVAILABLE:
            return
            
        import network
        
        # Try station mode first
        try:
            sta_if = network.WLAN(network.STA_IF)
            if sta_if.active() and sta_if.isconnected():
                ip, subnet, gateway, dns = sta_if.ifconfig()
                self.network_info = {
                    'ip': ip,
                    'port': self.config['udp_port'].value(),
                    'interface': 'WiFi',
                    'connected': True
                }
                self._last_network_update = time.ticks_ms()
                return
        except Exception:
            pass
        
        # Try AP mode
        try:
            ap_if = network.WLAN(network.AP_IF)
            if ap_if.active():
                ip, subnet, gateway, dns = ap_if.ifconfig()
                self.network_info = {
                    'ip': ip,
                    'port': self.config['udp_port'].value(),
                    'interface': 'AP',
                    'connected': True
                }
                self._last_network_update = time.ticks_ms()
                return
        except Exception:
            pass
        
        # No network available
        self.network_info = {
            'ip': 'No Network',
            'port': self.config['udp_port'].value(),
            'interface': 'None',
            'connected': False
        }
        self._last_network_update = time.ticks_ms()
    
    def _show_network_status(self):
        """Show current network status on displays."""
        if not UDP_AVAILABLE or not self.config['show_network_info'].value():
            return
        
        udp_enabled = self.config['udp_enabled'].value()
        
        if udp_enabled and self.network_info['connected']:
            # Show IP and port using top/bottom format
            self.state.message_display1 = f"UDP|{self.network_info['ip']}"
            self.state.message_display2 = f"Port|{self.network_info['port']}"
            self.state.fg_color_display1 = gc9a01.GREEN
            self.state.fg_color_display2 = gc9a01.GREEN
        elif udp_enabled:
            # UDP enabled but no network
            self.state.message_display1 = "UDP|Enabled"
            self.state.message_display2 = "No|Network"
            self.state.fg_color_display1 = gc9a01.YELLOW
            self.state.fg_color_display2 = gc9a01.YELLOW
        else:
            # UDP disabled
            self.state.message_display1 = "Remote|Sign"
            self.state.message_display2 = "UDP|Disabled"
            self.state.fg_color_display1 = gc9a01.WHITE
            self.state.fg_color_display2 = gc9a01.RED
        
        # Force refresh display
        self._refresh_displays()

    # Button handlers for manual control/testing
    def button_press(self, button: int):
        """Handle button presses for manual testing and UDP controls."""
        if button == 4:  # Down button - simulate command
            self._add_test_command()
        elif button == 5:  # Up button - clear timeout
            self.state.clear_timeout()
            self._refresh_displays()
        elif button == 6:  # Select button - cycle LED colors
            self._cycle_led_test()
        elif button == 1 and UDP_AVAILABLE:  # A button - show network info
            self._update_network_info()
            self._show_network_status()
        elif button == 2 and UDP_AVAILABLE:  # B button - show server stats
            if self.udp_server:
                stats = self.udp_server.get_stats()
                self.state.message_display1 = f"Commands: {stats['commands_processed']}"
                self.state.message_display2 = f"Uptime: {stats['uptime_seconds']}s"
                self._refresh_displays()
            else:
                self.state.message_display1 = "UDP Server"
                self.state.message_display2 = "Not Running"
                self._refresh_displays()
    
    def _add_test_command(self):
        """Add a test command to demonstrate functionality."""
        import random
        
        test_commands = [
            {
                'type': 'set_message',
                'display1': 'ALERT',
                'display2': 'System Status'
            },
            {
                'type': 'set_led',
                'led': -1,  # All LEDs
                'color': (255, 0, 0),  # Red
                'brightness': 50
            },
            {
                'type': 'set_timeout',
                'seconds': 10,
                'action': 'green'
            },
            {
                'type': 'set_colors',
                'display1_bg': gc9a01.RED,
                'display1_fg': gc9a01.WHITE
            }
        ]
        
        command = random.choice(test_commands)
        self.command_queue.append(command)
        print(f"Added test command: {command}")
    
    def _cycle_led_test(self):
        """Cycle through LED colors for testing."""
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (0, 0, 0)       # Off
        ]
        
        # Get current LED state and cycle to next color
        current_color = self.leds.leds[0]
        try:
            current_index = colors.index(current_color)
            next_index = (current_index + 1) % len(colors)
        except ValueError:
            next_index = 0
        
        new_color = colors[next_index]
        brightness = self.config['default_led_brightness'].value()
        scale = brightness / 100.0
        scaled_color = (int(new_color[0] * scale), int(new_color[1] * scale), int(new_color[2] * scale))
        
        for i in range(7):
            self.leds.leds[i] = scaled_color
        self.leds.leds.write()
    
    # Public API methods for external control (UDP interface would call these)
    def set_message(self, display1: str | None = None, display2: str | None = None):
        """Public API to set display messages."""
        command = {'type': 'set_message'}
        if display1 is not None:
            command['display1'] = display1
        if display2 is not None:
            command['display2'] = display2
        self.command_queue.append(command)
    
    def set_led_color(self, led_index: int, color: tuple, brightness: int | None = None):
        """Public API to set LED colors."""
        command = {
            'type': 'set_led',
            'led': led_index,
            'color': color
        }
        if brightness is not None:
            command['brightness'] = brightness
        self.command_queue.append(command)
    
    def set_all_leds(self, color: tuple, brightness: int | None = None):
        """Public API to set all LED colors."""
        self.set_led_color(-1, color, brightness)
    
    def set_timeout(self, seconds: int, action: str = "green"):
        """Public API to set timeout."""
        command = {
            'type': 'set_timeout',
            'seconds': seconds,
            'action': action
        }
        self.command_queue.append(command)
    
    def clear_timeout(self):
        """Public API to clear timeout."""
        command = {'type': 'clear_timeout'}
        self.command_queue.append(command)
    
    def get_server_stats(self):
        """Get UDP server statistics."""
        if UDP_AVAILABLE and self.udp_server:
            return self.udp_server.get_stats()
        return {
            'running': False,
            'commands_received': 0,
            'commands_processed': 0,
            'errors': 0
        }
    
    def get_connection_info(self):
        """Get connection information for clients."""
        base_info = {
            # **self.network_info,
            'udp_available': UDP_AVAILABLE,
            'server_stats': self.get_server_stats()
        }
        
        if UDP_AVAILABLE:
            base_info.update({
                'udp_enabled': self.config['udp_enabled'].value(),
                'udp_running': self.udp_server is not None and self.udp_server.running,
            })
        else:
            base_info.update({
                'udp_enabled': False,
                'udp_running': False,
            })
        
        return base_info


if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(RemoteSign)