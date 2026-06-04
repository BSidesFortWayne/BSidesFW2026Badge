#!/usr/bin/env python3
"""
Quick Remote Sign Command Tool

A simple command-line tool to send messages to the Remote Sign badge.
This is a standalone script that doesn't require typer.

Usage:
    python remote_sign_cmd.py <badge_ip> <display1_text> [display2_text]
    
Examples:
    python remote_sign_cmd.py 192.168.1.100 "Alert" "System Down"
    python remote_sign_cmd.py 192.168.1.100 "UDP|Active" "Port|8888"
    python remote_sign_cmd.py 192.168.1.100 "Hello"
    
LED Control:
    python remote_sign_cmd.py <badge_ip> led <led_index> <r> <g> <b> [brightness]
    python remote_sign_cmd.py 192.168.1.100 led -1 255 0 0 75
    python remote_sign_cmd.py 192.168.1.100 led 0 0 255 0 50
    
Tips:
    - Use '|' in text to split into top/bottom lines: "UDP|Enabled"
    - LED index -1 controls all LEDs at once
    - Brightness is 0-100 (default 50)
"""

import socket
import json
import sys


def send_message(badge_ip, display1, display2=None, port=8888, timeout=5.0):
    """Send a message to the Remote Sign badge."""
    try:
        command = {
            "action": "set_message",
            "display1": display1
        }
        if display2:
            command["display2"] = display2
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        data = json.dumps(command).encode('utf-8')
        sock.sendto(data, (badge_ip, port))
        
        response_data, _ = sock.recvfrom(1024)
        response = json.loads(response_data.decode('utf-8'))
        sock.close()
        
        if response.get("status") == "ok":
            print(f"✓ Message sent to {badge_ip}:{port}")
            print(f"  Display 1: {display1}")
            if display2:
                print(f"  Display 2: {display2}")
            return True
        else:
            print(f"✗ Error: {response.get('message', 'Unknown error')}")
            return False
            
    except socket.timeout:
        print(f"✗ Timeout - no response from {badge_ip}:{port}")
        print("  Check: Badge is on? WiFi connected? Remote Sign app running? UDP enabled?")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def send_led_command(badge_ip, led_index, r, g, b, brightness=50, port=8888, timeout=5.0):
    """Send LED control command to the badge."""
    try:
        command = {
            "action": "set_led",
            "led": led_index,
            "color": [r, g, b],
            "brightness": brightness
        }
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        data = json.dumps(command).encode('utf-8')
        sock.sendto(data, (badge_ip, port))
        
        response_data, _ = sock.recvfrom(1024)
        response = json.loads(response_data.decode('utf-8'))
        sock.close()
        
        if response.get("status") == "ok":
            led_desc = "All LEDs" if led_index == -1 else f"LED {led_index}"
            print(f"✓ {led_desc} set to RGB({r},{g},{b}) at {brightness}%")
            return True
        else:
            print(f"✗ Error: {response.get('message', 'Unknown error')}")
            return False
            
    except socket.timeout:
        print(f"✗ Timeout - no response from {badge_ip}:{port}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    
    badge_ip = sys.argv[1]
    
    # Check if it's an LED command
    if sys.argv[2].lower() == 'led':
        if len(sys.argv) < 7:
            print("LED command requires: led <index> <r> <g> <b> [brightness]")
            print("Example: python remote_sign_cmd.py 192.168.1.100 led -1 255 0 0 75")
            return 1
        
        try:
            led_index = int(sys.argv[3])
            r = int(sys.argv[4])
            g = int(sys.argv[5])
            b = int(sys.argv[6])
            brightness = int(sys.argv[7]) if len(sys.argv) > 7 else 50
            
            success = send_led_command(badge_ip, led_index, r, g, b, brightness)
            return 0 if success else 1
            
        except ValueError as e:
            print(f"✗ Invalid numeric value: {e}")
            return 1
    else:
        # Message command
        display1 = sys.argv[2]
        display2 = sys.argv[3] if len(sys.argv) > 3 else None
        
        success = send_message(badge_ip, display1, display2)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
