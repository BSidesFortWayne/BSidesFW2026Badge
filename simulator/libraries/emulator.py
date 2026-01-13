"""
Unified emulator communication module.
Supports both binary (high-performance graphics) and JSON (text/sensors) protocols.
"""

import sys
import socket
import json
import struct
import _thread

# ============================================================================
# Binary Protocol Configuration
# ============================================================================

# Magic bytes for protocol identification
MAGIC = b'\xEB\x01'

# Command IDs (keep in sync with gui.py)
CMD_FILL = 0x01
CMD_PIXEL = 0x02
CMD_FILL_RECT = 0x03
CMD_LINE = 0x04
CMD_CIRCLE = 0x05
CMD_FILL_CIRCLE = 0x06
CMD_BLIT_BUFFER = 0x10
CMD_GET_INPUTS = 0x20
CMD_PIN_VALUE = 0x21
CMD_POLL_INTERRUPTS = 0x22
CMD_NEOPIXEL_WRITE = 0x30

# ============================================================================
# Binary Protocol Communication
# ============================================================================

class EmulatorBinaryCommunication:
    def __init__(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            addr_info = socket.getaddrinfo('127.0.0.1', 4456)[0][-1]
            self.socket.connect(addr_info)
            self.lock = _thread.allocate_lock()
            print("[EMULATOR] Binary protocol connected")
        except Exception as e:
            print(f"[EMULATOR] Binary protocol connection failed: {e}")
            self.socket = None
            self.lock = _thread.allocate_lock()

    def send_command(self, cmd_id, payload):
        """Send binary command and receive response"""
        if self.socket is None:
            return 1, None  # Error status
            
        with self.lock:
            try:
                # Build packet: MAGIC + CMD_ID + LENGTH + PAYLOAD
                packet = MAGIC + bytes([cmd_id]) + struct.pack('<I', len(payload)) + payload
                self.socket.send(packet)
                
                # Receive response: STATUS + LENGTH + DATA
                status = self.socket.recv(1)[0]
                length_bytes = self.socket.recv(4)
                length = struct.unpack('<I', length_bytes)[0]
                
                if length > 0:
                    data = self._recv_all(length)
                    return status, data
                return status, None
            except Exception as e:
                print(f"[EMULATOR] Binary command {cmd_id} error: {e}")
                return 1, None
    
    def _recv_all(self, length):
        """Receive exactly length bytes"""
        data = b''
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Socket closed")
            data += chunk
        return data

def get_binary_socket():
    """Singleton pattern for binary communication"""
    if hasattr(sys.modules[__name__], '_binary_s'):
        return sys.modules[__name__]._binary_s
    
    s = EmulatorBinaryCommunication()
    setattr(sys.modules[__name__], '_binary_s', s)
    return s

# ============================================================================
# JSON Protocol Communication (for text rendering, sensors, etc.)
# ============================================================================

class EmulatorJSONCommunication:
    def __init__(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            addr_info = socket.getaddrinfo('127.0.0.1', 4455)[0][-1]
            self.socket.connect(addr_info)
            self.lock = _thread.allocate_lock()
            print("[EMULATOR] JSON protocol connected")
        except Exception as e:
            print(f"[EMULATOR] JSON protocol connection failed: {e}")
            self.socket = None
            self.lock = _thread.allocate_lock()

    def send_command(self, device, command, **kwargs):
        """Send JSON command and receive response"""
        if self.socket is None:
            return {'status': 'error'}
            
        with self.lock:
            try:
                data = {'module': device, 'command': command, 'parameters': kwargs}
                json_data = json.dumps(data)
                self.socket.send(json_data.encode())
                
                # Receive response
                buffer = b''
                while True:
                    chunk = self.socket.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    try:
                        response = json.loads(buffer.decode('utf-8'))
                        return response
                    except json.JSONDecodeError:
                        # Incomplete JSON, keep reading
                        continue
                return {'status': 'error'}
            except Exception as e:
                print(f"[EMULATOR] JSON command {device}.{command} error: {e}")
                return {'status': 'error'}

def get_json_socket():
    """Singleton pattern for JSON communication"""
    if hasattr(sys.modules[__name__], '_json_s'):
        return sys.modules[__name__]._json_s
    
    s = EmulatorJSONCommunication()
    setattr(sys.modules[__name__], '_json_s', s)
    return s

# ============================================================================
# High-Level Binary Protocol Functions (Graphics)
# ============================================================================

def send_fill(display, color):
    """Fill display with color (RGB565)"""
    payload = struct.pack('<BH', display, color)
    return get_binary_socket().send_command(CMD_FILL, payload)

def send_pixel(display, x, y, color):
    """Set pixel at (x,y) to color (RGB565)"""
    payload = struct.pack('<BhhH', display, x, y, color)
    return get_binary_socket().send_command(CMD_PIXEL, payload)

def send_fill_rect(display, x, y, w, h, color):
    """Fill rectangle with color (RGB565)"""
    payload = struct.pack('<BhhhhH', display, x, y, w, h, color)
    return get_binary_socket().send_command(CMD_FILL_RECT, payload)

def send_line(display, x0, y0, x1, y1, color):
    """Draw line from (x0,y0) to (x1,y1) with color (RGB565)"""
    payload = struct.pack('<BhhhhH', display, x0, y0, x1, y1, color)
    return get_binary_socket().send_command(CMD_LINE, payload)

def send_circle(display, x, y, r, color, filled=False):
    """Draw circle at (x,y) with radius r and color (RGB565)"""
    cmd = CMD_FILL_CIRCLE if filled else CMD_CIRCLE
    payload = struct.pack('<BhhhH', display, x, y, r, color)
    return get_binary_socket().send_command(cmd, payload)

def send_blit_buffer(display, buffer, x, y, width, height):
    """Blit RGB565 buffer to display - OPTIMIZED for binary transfer"""
    # Convert buffer to bytes if needed
    if hasattr(buffer, 'tobytes'):
        buffer_bytes = buffer.tobytes()
    elif isinstance(buffer, (bytes, bytearray)):
        buffer_bytes = bytes(buffer)
    else:
        buffer_bytes = bytes(buffer)
    
    # Build payload: display + x + y + width + height + buffer_data
    header = struct.pack('<BhhHH', display, x, y, width, height)
    payload = header + buffer_bytes
    return get_binary_socket().send_command(CMD_BLIT_BUFFER, payload)

def send_get_inputs():
    """Get button input state from PCA9535"""
    status, data = get_binary_socket().send_command(CMD_GET_INPUTS, b'')
    if status == 0 and data:
        return struct.unpack('<H', data)[0]
    return 0xFFFF

def send_pin_value(pin):
    """Read GPIO pin value"""
    payload = struct.pack('<B', pin)
    status, data = get_binary_socket().send_command(CMD_PIN_VALUE, payload)
    if status == 0 and data:
        return struct.unpack('<B', data)[0]
    return 1

def send_neopixel_write(leds):
    """Write LED data (7 LEDs, GRB format, 3 bytes each)"""
    payload = b''
    for led in leds[:7]:  # Max 7 LEDs
        g, r, b = led
        payload += struct.pack('BBB', g, r, b)
    return get_binary_socket().send_command(CMD_NEOPIXEL_WRITE, payload)

def poll_interrupts():
    """Poll for pending hardware interrupts from the GUI.
    Returns list of interrupt events: [{'pin': 34, 'edge': 'rising'}, ...]
    """
    status, data = get_binary_socket().send_command(CMD_POLL_INTERRUPTS, b'')
    if status == 0 and data:
        return json.loads(data.decode('utf-8'))
    return []

# ============================================================================
# High-Level JSON Protocol Functions (Text, Images, Sensors)
# ============================================================================

def send_command(device, command, **kwargs):
    """Send JSON command to emulator (for text rendering, sensors, etc.)"""
    return get_json_socket().send_command(device, command, **kwargs)

# ============================================================================
# Initialization - Connect to binary protocol immediately
# ============================================================================

try:
    _init_socket = get_binary_socket()
    if _init_socket.socket:
        print("[EMULATOR] Ready (binary + JSON protocols)")
except Exception as e:
    print(f"[EMULATOR] Warning: {e}")
