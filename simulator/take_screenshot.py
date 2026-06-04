#!/usr/bin/env python3
"""
Screenshot utility for the badge simulator.

This script can be used to capture screenshots from a running simulator,
similar to how browser MCP tools capture webpage screenshots.

Usage:
    # Take a screenshot with auto-generated filename
    python take_screenshot.py
    
    # Take a screenshot with custom filename
    python take_screenshot.py --output my_badge_screenshot.png
    
    # Wait for simulator to be in a specific state (manual timing)
    python take_screenshot.py --wait 2.0
"""

import socket
import json
import argparse
import time
import sys
from pathlib import Path


def send_screenshot_command(host='127.0.0.1', port=4465, filepath=None, include_controls=False, timeout=5.0):
    """Send screenshot command to simulator via external command protocol
    
    Args:
        host: Simulator host (default: 127.0.0.1)
        port: External command port (default: 4465, which is JSON port + 10)
        filepath: Optional custom filepath for screenshot
        include_controls: Whether to include control panel in screenshot (default: False)
        timeout: Connection timeout in seconds
    
    Returns:
        Path to saved screenshot file, or None on error
    """
    try:
        # Connect to simulator
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        
        # Build command
        command = {
            'module': 'screenshot',
            'command': 'take',
            'parameters': {
                'include_controls': include_controls
            }
        }
        
        if filepath:
            command['parameters']['filepath'] = filepath
        
        # Send command
        sock.sendall(json.dumps(command).encode('utf-8'))
        
        # The server doesn't close the connection, so we need to:
        # 1. Receive with a timeout
        # 2. Stop when we have a complete JSON response
        sock.settimeout(2.0)
        response_data = b''
        
        # Keep receiving until we get a complete JSON response
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                # Try to parse as soon as we have data
                try:
                    response = json.loads(response_data.decode('utf-8'))
                    # Successfully parsed - we have the complete response
                    sock.close()
                    break
                except json.JSONDecodeError:
                    # Incomplete JSON, keep receiving
                    continue
                    
            except socket.timeout:
                # Timeout means no more data is coming
                # Try to parse what we have
                if response_data:
                    try:
                        response = json.loads(response_data.decode('utf-8'))
                        sock.close()
                        break
                    except json.JSONDecodeError:
                        print(f"Error: Incomplete JSON response: {response_data[:100]}", file=sys.stderr)
                        sock.close()
                        return None
                else:
                    # No data received at all
                    sock.close()
                    raise
        
        # Extract filepath from response
        if response.get('status') == 'ok' and 'resp' in response:
            return response['resp']
        else:
            print(f"Error: Unexpected response: {response}", file=sys.stderr)
            return None
            
    except socket.timeout:
        print(f"Error: Connection timeout. Is the simulator running?", file=sys.stderr)
        return None
    except ConnectionRefusedError:
        print(f"Error: Connection refused. Is the simulator running on {host}:{port}?", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Capture screenshot from running badge simulator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Auto-generated filename
  %(prog)s -o badge.png                 # Custom filename
  %(prog)s --wait 2.0 -o myapp.png     # Wait 2s then capture
  %(prog)s --host localhost --port 4455 # Custom host/port
        """
    )
    
    parser.add_argument('-o', '--output', type=str,
                       help='Output filepath (default: auto-generated in screenshots/)')
    parser.add_argument('--include-controls', action='store_true',
                       help='Include control panel in screenshot (default: False)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help='Simulator host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=4465,
                       help='External command port (default: 4465)')
    parser.add_argument('--wait', type=float, default=0.0,
                       help='Seconds to wait before capturing (default: 0)')
    parser.add_argument('--timeout', type=float, default=5.0,
                       help='Connection timeout in seconds (default: 5.0)')
    
    args = parser.parse_args()
    
    # Wait if requested
    if args.wait > 0:
        print(f"Waiting {args.wait} seconds...")
        time.sleep(args.wait)
    
    # Capture screenshot
    print(f"Capturing screenshot from simulator at {args.host}:{args.port}...")
    filepath = send_screenshot_command(
        host=args.host,
        port=args.port,
        filepath=args.output,
        include_controls=args.include_controls,
        timeout=args.timeout
    )
    
    if filepath:
        print(f"✓ Screenshot saved to: {filepath}")
        return 0
    else:
        print("✗ Failed to capture screenshot", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
