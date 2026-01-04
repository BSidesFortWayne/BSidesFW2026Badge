"""
Remote Sign Integration Example

This shows how the RemoteSign app could be integrated with other badge functionality
or controlled via web interface from the Settings app.
"""

# Example of how to add remote sign control to the Settings app's web interface

REMOTE_SIGN_HTML_FORM = """
<h2>Remote Sign Control</h2>
<form method="post" action="/remote_sign/control">
    <fieldset>
        <legend>Display Messages</legend>
        <label for="display1">Display 1 Text:</label>
        <input type="text" id="display1" name="display1" maxlength="20"><br><br>
        
        <label for="display2">Display 2 Text:</label>
        <input type="text" id="display2" name="display2" maxlength="20"><br><br>
    </fieldset>
    
    <fieldset>
        <legend>LED Control</legend>
        <label for="led_index">LED Index (-1 for all):</label>
        <select id="led_index" name="led_index">
            <option value="-1">All LEDs</option>
            <option value="0">LED 0</option>
            <option value="1">LED 1</option>
            <option value="2">LED 2</option>
            <option value="3">LED 3</option>
            <option value="4">LED 4</option>
            <option value="5">LED 5</option>
            <option value="6">LED 6</option>
        </select><br><br>
        
        <label for="led_color">LED Color:</label>
        <select id="led_color" name="led_color">
            <option value="255,0,0">Red</option>
            <option value="0,255,0">Green</option>
            <option value="0,0,255">Blue</option>
            <option value="255,255,0">Yellow</option>
            <option value="255,0,255">Magenta</option>
            <option value="0,255,255">Cyan</option>
            <option value="255,255,255">White</option>
            <option value="0,0,0">Off</option>
        </select><br><br>
        
        <label for="brightness">Brightness (0-100):</label>
        <input type="range" id="brightness" name="brightness" min="0" max="100" value="50"><br><br>
    </fieldset>
    
    <fieldset>
        <legend>Timeout Settings</legend>
        <label for="timeout_seconds">Timeout (seconds):</label>
        <input type="number" id="timeout_seconds" name="timeout_seconds" min="1" max="3600" value="60"><br><br>
        
        <label for="timeout_action">Timeout Action:</label>
        <select id="timeout_action" name="timeout_action">
            <option value="green">Turn Green</option>
            <option value="off">Turn Off</option>
            <option value="default">Return to Default</option>
        </select><br><br>
    </fieldset>
    
    <fieldset>
        <legend>Quick Actions</legend>
        <button type="submit" name="action" value="emergency">Emergency Alert</button>
        <button type="submit" name="action" value="status_ok">Status OK</button>
        <button type="submit" name="action" value="warning">Warning</button>
        <button type="submit" name="action" value="meeting">Meeting In Progress</button>
        <button type="submit" name="action" value="available">Room Available</button>
        <button type="submit" name="action" value="clear">Clear All</button>
    </fieldset>
    
    <button type="submit" name="action" value="update">Update Sign</button>
</form>
"""

# Example UDP server code (for future implementation)
UDP_SERVER_EXAMPLE = """
import socket
import json
from apps.remote_sign_controller import create_command_from_network_message

class RemoteSignUDPServer:
    def __init__(self, remote_sign_app, port=8888):
        self.app = remote_sign_app
        self.port = port
        self.sock = None
        self.running = False
    
    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        self.sock.bind(('0.0.0.0', self.port))
        self.running = True
        print(f"Remote Sign UDP server listening on port {self.port}")
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = json.loads(data.decode())
                command = create_command_from_network_message(message)
                
                if command:
                    self.app.command_queue.append(command)
                    response = {"status": "ok", "message": "Command queued"}
                else:
                    response = {"status": "error", "message": "Invalid command"}
                
                response_data = json.dumps(response).encode()
                self.sock.sendto(response_data, addr)
                
            except Exception as e:
                print(f"UDP server error: {e}")
    
    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()

# Example UDP client commands:
# echo '{"action":"set_message","display1":"Hello","display2":"World"}' | nc -u badge_ip 8888
# echo '{"action":"set_led","led":-1,"color":[255,0,0],"brightness":75}' | nc -u badge_ip 8888
# echo '{"action":"set_timeout","timeout":30,"timeout_action":"green"}' | nc -u badge_ip 8888
"""

# Example of integrating with Settings app web interface
SETTINGS_APP_INTEGRATION = """
# Add this to the Settings app's start_website method:

@app.route('/remote_sign')
async def remote_sign_control(request):
    # Check if RemoteSign app is currently running
    current_app = self.controller.current_view
    if not current_app or current_app.name != "Remote Sign":
        return "Remote Sign app is not currently active", 400
    
    return REMOTE_SIGN_HTML_FORM

@app.post('/remote_sign/control')
@with_form_data
async def handle_remote_sign_control(request):
    current_app = self.controller.current_view
    if not current_app or current_app.name != "Remote Sign":
        return "Remote Sign app is not currently active", 400
    
    action = request.form.get('action')
    
    if action == 'emergency':
        current_app.set_message("EMERGENCY", "Alert Active")
        current_app.set_all_leds((255, 0, 0), 80)  # Bright red
        current_app.set_timeout(60, "green")
        
    elif action == 'status_ok':
        current_app.set_message("STATUS", "All OK")
        current_app.set_all_leds((0, 255, 0), 30)  # Green
        
    elif action == 'warning':
        current_app.set_message("WARNING", "Check System")
        current_app.set_all_leds((255, 255, 0), 50)  # Yellow
        current_app.set_timeout(120, "default")
        
    elif action == 'meeting':
        current_app.set_message("MEETING", "In Progress")
        current_app.set_all_leds((255, 0, 0), 20)  # Dim red
        
    elif action == 'available':
        current_app.set_message("AVAILABLE", "Room Free")
        current_app.set_all_leds((0, 255, 0), 20)  # Dim green
        
    elif action == 'clear':
        current_app.set_message("Remote Sign", "Ready")
        current_app.set_all_leds((0, 0, 0), 0)  # Off
        current_app.clear_timeout()
        
    elif action == 'update':
        # Custom update based on form fields
        display1 = request.form.get('display1')
        display2 = request.form.get('display2')
        if display1 or display2:
            current_app.set_message(display1, display2)
        
        led_index = int(request.form.get('led_index', -1))
        led_color_str = request.form.get('led_color', '0,0,0')
        led_color = tuple(map(int, led_color_str.split(',')))
        brightness = int(request.form.get('brightness', 50))
        
        current_app.set_led_color(led_index, led_color, brightness)
        
        timeout_seconds = request.form.get('timeout_seconds')
        if timeout_seconds:
            timeout_action = request.form.get('timeout_action', 'green')
            current_app.set_timeout(int(timeout_seconds), timeout_action)
    
    return Response.redirect('/remote_sign')
"""

# Example command line interface
CLI_EXAMPLE = """
# Example CLI tool for remote sign control
# Save as remote_sign_cli.py

import socket
import json
import sys

def send_command(host, port, command):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        data = json.dumps(command).encode()
        sock.sendto(data, (host, port))
        response, _ = sock.recvfrom(1024)
        return json.loads(response.decode())
    finally:
        sock.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python remote_sign_cli.py <badge_ip> [command] [args...]")
        print("Commands:")
        print("  message <display1> <display2>")
        print("  led <index> <r> <g> <b> [brightness]")
        print("  timeout <seconds> [action]")
        print("  emergency [message]")
        print("  status_ok [message]")
        print("  warning [message]")
        return
    
    host = sys.argv[1]
    port = 8888
    
    if len(sys.argv) < 3:
        # Interactive mode
        while True:
            cmd = input("remote_sign> ").strip().split()
            if not cmd or cmd[0] == 'quit':
                break
            # Process command...
    else:
        # Single command mode
        cmd = sys.argv[2]
        args = sys.argv[3:]
        
        if cmd == 'message':
            command = {
                "action": "set_message",
                "display1": args[0] if len(args) > 0 else "",
                "display2": args[1] if len(args) > 1 else ""
            }
        elif cmd == 'led':
            command = {
                "action": "set_led", 
                "led": int(args[0]),
                "color": [int(args[1]), int(args[2]), int(args[3])],
                "brightness": int(args[4]) if len(args) > 4 else 50
            }
        elif cmd == 'emergency':
            command = {
                "action": "set_message",
                "display1": "EMERGENCY",
                "display2": args[0] if args else "Alert"
            }
        else:
            print(f"Unknown command: {cmd}")
            return
        
        response = send_command(host, port, command)
        print(f"Response: {response}")

if __name__ == "__main__":
    main()

# Usage examples:
# python remote_sign_cli.py 192.168.1.100 message "Hello" "World"  
# python remote_sign_cli.py 192.168.1.100 led -1 255 0 0 75
# python remote_sign_cli.py 192.168.1.100 emergency "Fire Drill"
"""

if __name__ == "__main__":
    print("Remote Sign Integration Examples")
    print("================================")
    print()
    print("1. HTML Form for web interface")
    print("2. UDP Server implementation") 
    print("3. Settings app integration")
    print("4. Command line interface")
    print()
    print("See the code in this file for implementation details.")