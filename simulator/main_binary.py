"""
Binary protocol version of simulator main.
Runs both JSON (port 4455) and binary (port 4456) servers for compatibility.
Binary protocol is MUCH faster for blit_buffer operations.
"""

import shutil
import subprocess
import argparse
import socket
import json
import os
import threading
import struct
import gui
from gui_binary import BinaryProtocolHandler

parser = argparse.ArgumentParser(description='Badge simulator with binary protocol support')
parser.add_argument('-p', '--project', type=str, help='Project directory', required=True)
parser.add_argument('-m', '--micropython', type=str, help='Micropython executable', required=False)
parser.add_argument('--binary-only', action='store_true', 
                   help='Use binary protocol only (faster, but requires gc9a01_binary.py)')

args = parser.parse_args()

if args.micropython is None:
    args.micropython = 'micropython'  # Use PATH

if not os.path.exists(os.path.join(args.project, 'main.py')):
    print('No project found')
    exit(1)

# Setup project directory
if os.path.exists('src'):
    shutil.rmtree('src')

shutil.copytree(args.project, 'src')
shutil.copytree('libraries', 'src', dirs_exist_ok=True)

# If binary-only mode, replace gc9a01.py with binary version
if args.binary_only:
    print("Using binary protocol for maximum performance")
    shutil.copy('libraries/gc9a01_binary.py', 'src/gc9a01.py')

# Start sockets
json_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
json_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
json_socket.bind(('127.0.0.1', 4455))
json_socket.listen()

binary_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
binary_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
binary_socket.bind(('127.0.0.1', 4456))
binary_socket.listen()

# Start micropython process
os.chdir('src')
micropython_process = subprocess.Popen([args.micropython, 'main.py'])
os.chdir('..')

# Accept connections
json_conn, _ = json_socket.accept()
binary_conn, _ = binary_socket.accept()
print("Both JSON and binary connections established")

# Create GUI
gui_instance = gui.GUI()
binary_handler = BinaryProtocolHandler(gui_instance)

# JSON protocol handler (for compatibility)
def handle_json_commands():
    """Handle legacy JSON protocol commands"""
    while gui_instance.running:
        try:
            data = json.loads(json_conn.recv(1024).decode('utf-8'))
            data_to_send = {'status': 'ok'}
            resp = gui_instance.handle_command(data)
            data_to_send['resp'] = resp
            json_conn.send(json.dumps(data_to_send).encode())
        except (BrokenPipeError, ConnectionResetError):
            break
        except Exception as e:
            print(f"JSON handler error: {e}")
            break
    micropython_process.terminate()

# Binary protocol handler (high performance)
def handle_binary_commands():
    """Handle binary protocol commands"""
    MAGIC = b'\xEB\x01'
    
    while gui_instance.running:
        try:
            # Read magic bytes
            magic = binary_conn.recv(2)
            if magic != MAGIC:
                print(f"Invalid magic bytes: {magic.hex()}")
                continue
            
            # Read command ID
            cmd_id = binary_conn.recv(1)[0]
            
            # Read payload length
            length_bytes = binary_conn.recv(4)
            length = struct.unpack('<I', length_bytes)[0]
            
            # Read payload
            payload = b''
            while len(payload) < length:
                chunk = binary_conn.recv(length - len(payload))
                if not chunk:
                    raise ConnectionError("Connection closed")
                payload += chunk
            
            # Process command
            status, response_data = binary_handler.handle_command(cmd_id, payload)
            
            # Send response
            if response_data:
                response = bytes([status]) + struct.pack('<I', len(response_data)) + response_data
            else:
                response = bytes([status]) + struct.pack('<I', 0)
            
            binary_conn.sendall(response)
            
        except (BrokenPipeError, ConnectionResetError):
            break
        except Exception as e:
            print(f"Binary handler error: {e}")
            break
    
    micropython_process.terminate()

# Start both protocol handlers
json_thread = threading.Thread(target=handle_json_commands, daemon=True)
binary_thread = threading.Thread(target=handle_binary_commands, daemon=True)

json_thread.start()
binary_thread.start()

# Run GUI main loop
gui_instance.gameloop()

# Cleanup
micropython_process.terminate()
json_socket.close()
binary_socket.close()
