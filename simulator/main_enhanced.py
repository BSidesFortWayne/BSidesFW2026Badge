import shutil
import subprocess
import argparse
import socket
import json
import os
import threading
import gui_enhanced

parser = argparse.ArgumentParser()

parser.add_argument('-p', '--project', type=str, help='Project directory', required=True)
parser.add_argument('-m', '--micropython', type=str, help='Micropython executable', required=False)

args = parser.parse_args()

if args.micropython == None:
    args.micropython = 'micropython' # Use PATH

if not os.path.exists(os.path.join(args.project, 'main.py')):
    print('No project found')
    exit(1)

emulator_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
emulator_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
emulator_socket.bind(('127.0.0.1', 4455))
emulator_socket.listen()

if os.path.exists('src'):
    shutil.rmtree('src')

shutil.copytree(args.project, 'src')
shutil.copytree('libraries', 'src', dirs_exist_ok=True) # add fake libraries in

os.chdir('src')

micropython_process = subprocess.Popen(
    [args.micropython, '-X', 'heapsize=8M', 'main.py'],
)

os.chdir('..')

emulator_conn, addr = emulator_socket.accept()

gui = gui_enhanced.GUIEnhanced()

def receive_commands():
    buffer = b''
    while gui.running:
        try:
            # Receive data in chunks with larger buffer for framebuffer data
            chunk = emulator_conn.recv(65536)
            if not chunk:
                print("Connection closed by MicroPython")
                break
            
            buffer += chunk
            
            # Try to parse JSON - keep accumulating if incomplete
            try:
                data = json.loads(buffer.decode('utf-8'))
                buffer = b''  # Clear buffer on successful parse
                
                data_to_send = {'status': 'ok'}
                if not (data['module'] == 'pca9535' and data['command'] == 'get_inputs'):
                    #print(data)
                    pass
                resp = gui.handle_command(data)
                data_to_send['resp'] = resp
                emulator_conn.send(json.dumps(data_to_send).encode())
                
            except json.JSONDecodeError:
                # Incomplete JSON, continue accumulating
                # But check if buffer is getting too large (sanity check)
                if len(buffer) > 10 * 1024 * 1024:  # 10MB limit
                    print(f"ERROR: Buffer overflow: {len(buffer)} bytes")
                    buffer = b''
                continue
                
        except BrokenPipeError:
            break
        except Exception as e:
            print(f"Error in receive loop: {e}")
            break

    micropython_process.terminate()

threading.Thread(target=receive_commands).start()
gui.gameloop()
