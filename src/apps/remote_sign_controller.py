"""
Remote Sign Controller Demo

This script demonstrates how to control the RemoteSign app programmatically.
In the future, this functionality could be exposed via UDP or HTTP interface.
"""

import time


class RemoteSignController:
    """
    Controller class for the RemoteSign app.
    
    This demonstrates the API that could be exposed via network interface.
    """
    
    def __init__(self, remote_sign_app):
        self.app = remote_sign_app
    
    def show_message(self, display1_text: str | None = None, display2_text: str | None = None):
        """Set messages on displays."""
        self.app.set_message(display1_text, display2_text)
        print(f"Set message: display1='{display1_text}', display2='{display2_text}'")
    
    def set_led_color(self, led_index: int, r: int, g: int, b: int, brightness: int = 50):
        """Set color of a specific LED (0-6) or all LEDs (-1)."""
        self.app.set_led_color(led_index, (r, g, b), brightness)
        print(f"Set LED {led_index} to RGB({r},{g},{b}) at {brightness}% brightness")
    
    def set_all_leds_red(self, brightness: int = 50):
        """Set all LEDs to red."""
        self.set_led_color(-1, 255, 0, 0, brightness)
    
    def set_all_leds_green(self, brightness: int = 50):
        """Set all LEDs to green."""
        self.set_led_color(-1, 0, 255, 0, brightness)
    
    def set_all_leds_blue(self, brightness: int = 50):
        """Set all LEDs to blue."""
        self.set_led_color(-1, 0, 0, 255, brightness)
    
    def turn_off_leds(self):
        """Turn off all LEDs."""
        self.set_led_color(-1, 0, 0, 0, 0)
    
    def set_timer(self, seconds: int, action: str = "green"):
        """Set a timer for automatic state change."""
        self.app.set_timeout(seconds, action)
        print(f"Set timer for {seconds} seconds with action '{action}'")
    
    def clear_timer(self):
        """Clear any active timer."""
        self.app.clear_timeout()
        print("Timer cleared")
    
    def emergency_alert(self, message: str = "EMERGENCY", duration: int = 30):
        """Display emergency alert with red LEDs and timeout."""
        self.show_message("ALERT", message)
        self.set_all_leds_red(brightness=80)
        self.set_timer(duration, "green")  # Auto-clear to green after duration
    
    def status_ok(self, message: str = "System OK"):
        """Display OK status with green LEDs."""
        self.show_message("STATUS", message)
        self.set_all_leds_green(brightness=30)
    
    def status_warning(self, message: str = "Warning", duration: int = 60):
        """Display warning status with yellow LEDs and timeout."""
        self.show_message("WARNING", message)
        self.set_led_color(-1, 255, 255, 0, brightness=50)  # Yellow
        self.set_timer(duration, "default")  # Auto-clear after duration
    
    def meeting_in_progress(self, room: str = "Conference Room"):
        """Display meeting in progress sign."""
        self.show_message("MEETING", f"In Progress - {room}")
        self.set_all_leds_red(brightness=20)  # Dim red
    
    def meeting_available(self, room: str = "Conference Room"):
        """Display room available sign."""
        self.show_message("AVAILABLE", room)
        self.set_all_leds_green(brightness=20)  # Dim green
    
    def presentation_mode(self, presenter: str = "Speaker"):
        """Display presentation mode."""
        self.show_message("PRESENTING", presenter)
        self.set_all_leds_blue(brightness=30)
    
    def break_time(self, minutes: int = 15):
        """Display break time with countdown."""
        self.show_message("BREAK TIME", f"{minutes} minutes")
        self.set_led_color(-1, 255, 165, 0, brightness=40)  # Orange
        self.set_timer(minutes * 60, "green")  # Auto-signal break over


def demo_sequence(controller: RemoteSignController):
    """Demonstrate various remote sign functions."""
    print("Starting Remote Sign Demo Sequence")
    
    # Initial state
    controller.show_message("Remote Sign", "Demo Starting")
    time.sleep(2)
    
    # Status OK
    print("\\n1. Status OK Demo")
    controller.status_ok("All Systems Normal")
    time.sleep(3)
    
    # Warning demo
    print("\\n2. Warning Demo")
    controller.status_warning("Temperature High", duration=10)
    time.sleep(3)
    
    # Meeting in progress
    print("\\n3. Meeting Demo")
    controller.meeting_in_progress("Board Room A")
    time.sleep(3)
    
    # Presentation mode
    print("\\n4. Presentation Demo")
    controller.presentation_mode("Dr. Smith")
    time.sleep(3)
    
    # Break time
    print("\\n5. Break Time Demo")
    controller.break_time(5)  # 5 minute break
    time.sleep(3)
    
    # Emergency alert
    print("\\n6. Emergency Alert Demo")
    controller.emergency_alert("Fire Drill", duration=15)
    time.sleep(3)
    
    # LED color cycling
    print("\\n7. LED Color Demo")
    colors = [
        ("Red", 255, 0, 0),
        ("Green", 0, 255, 0), 
        ("Blue", 0, 0, 255),
        ("Yellow", 255, 255, 0),
        ("Purple", 255, 0, 255),
        ("Cyan", 0, 255, 255),
        ("White", 255, 255, 255)
    ]
    
    for color_name, r, g, b in colors:
        controller.show_message("LED DEMO", color_name)
        controller.set_led_color(-1, r, g, b, brightness=60)
        time.sleep(1)
    
    # Reset to default
    print("\\n8. Returning to Default")
    controller.show_message("Remote Sign", "Demo Complete")
    controller.turn_off_leds()
    controller.clear_timer()
    
    print("\\nDemo sequence complete!")


# Example usage:
# This would be called from within the RemoteSign app or externally via network
def run_demo_on_app(remote_sign_app):
    """Run demo sequence on a RemoteSign app instance."""
    controller = RemoteSignController(remote_sign_app)
    demo_sequence(controller)


# Network interface functions (for future UDP/HTTP implementation)
def create_command_from_network_message(message: dict) -> dict | None:
    """
    Convert network message to RemoteSign command format.
    
    Expected message format:
    {
        "action": "set_message" | "set_led" | "set_timeout" | "emergency" | "status_ok",
        "display1": "text for display 1",
        "display2": "text for display 2", 
        "led": led_index (-1 for all),
        "color": [r, g, b],
        "brightness": 0-100,
        "timeout": seconds,
        "timeout_action": "green" | "off" | "default"
    }
    """
    action = message.get("action")
    
    if action == "set_message":
        return {
            "type": "set_message",
            "display1": message.get("display1"),
            "display2": message.get("display2")
        }
    
    elif action == "set_led":
        return {
            "type": "set_led",
            "led": message.get("led", 0),
            "color": tuple(message.get("color", [0, 0, 0])),
            "brightness": message.get("brightness", 50)
        }
    
    elif action == "set_timeout":
        return {
            "type": "set_timeout", 
            "seconds": message.get("timeout", 60),
            "action": message.get("timeout_action", "green")
        }
    
    elif action == "clear_timeout":
        return {"type": "clear_timeout"}
    
    else:
        return {}


# Example network messages for testing:
EXAMPLE_NETWORK_COMMANDS = [
    {
        "action": "set_message",
        "display1": "Hello",
        "display2": "Network Control"
    },
    {
        "action": "set_led",
        "led": -1,
        "color": [255, 0, 0],
        "brightness": 75
    },
    {
        "action": "set_timeout",
        "timeout": 30,
        "timeout_action": "green"
    }
]


if __name__ == "__main__":
    print("Remote Sign Controller Demo")
    print("This script demonstrates programmatic control of the RemoteSign app.")
    print("\\nExample network commands:")
    for i, cmd in enumerate(EXAMPLE_NETWORK_COMMANDS, 1):
        print(f"{i}. {cmd}")
    
    print("\\nTo use this with a RemoteSign app instance:")
    print("controller = RemoteSignController(your_remote_sign_app)")
    print("controller.emergency_alert('Fire Drill', 60)")