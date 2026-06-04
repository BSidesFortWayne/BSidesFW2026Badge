"""
Web emulator communication module.
Replaces socket-based communication with direct JS bridge calls.
"""

import js
import json

# Global re-entrancy guard. In the WASM port, js.* proxy calls go through
# Emscripten ASYNCIFY which makes them implicit yield points. If two js.*
# calls overlap (e.g. timer callback fires while a display update is in
# progress), MicroPython aborts with "proxy_c_to_js_call is running
# asynchronously". This flag lets us skip calls that would re-enter.
_in_js_call = False


def _guard(fn):
    def wrapper(*args, **kwargs):
        global _in_js_call
        if _in_js_call:
            return fn.__defaults__[-1] if fn.__defaults__ else None
        _in_js_call = True
        try:
            return fn(*args, **kwargs)
        finally:
            _in_js_call = False
    return wrapper


def send_fill(display, color):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayFill(display, color)
    finally:
        _in_js_call = False
    return 0, None


def send_pixel(display, x, y, color):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayPixel(display, x, y, color)
    finally:
        _in_js_call = False
    return 0, None


def send_fill_rect(display, x, y, w, h, color):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayFillRect(display, x, y, w, h, color)
    finally:
        _in_js_call = False
    return 0, None


def send_line(display, x0, y0, x1, y1, color):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayLine(display, x0, y0, x1, y1, color)
    finally:
        _in_js_call = False
    return 0, None


def send_circle(display, x, y, r, color, filled=False):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayCircle(display, x, y, r, color, 1 if filled else 0)
    finally:
        _in_js_call = False
    return 0, None


def send_text(display, string, x, y, fg_color, bg_color, char_width, char_height, font_name=None):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayText(display, string, x, y, fg_color, bg_color, char_width, char_height, font_name)
    except Exception as e:
        print(f"[EMULATOR] text error (non-fatal): {e}")
    finally:
        _in_js_call = False
    return 0, None


def send_jpg(display, filename, x, y):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        js.bridgeDisplayJpg(display, filename, x, y)
    except Exception as e:
        print(f"[EMULATOR] jpg error (non-fatal): {e}")
    finally:
        _in_js_call = False
    return 0, None


import uctypes


def send_blit_buffer(display, buffer, x, y, width, height):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        # Zero-copy: hand JS the buffer's address in WASM linear memory and its
        # length, and let it view the bytes directly via Module.HEAPU8. Copying
        # byte-by-byte across the proxy boundary (one js_buf[i]=... per byte) is
        # ~115k ASYNCIFY-bridged ops for a full-screen blit — slow enough that an
        # app blitting every frame keeps the bridge busy and aborts the runtime.
        # The view is read synchronously on the JS side before any GC moves the
        # buffer, so it's safe.
        js.bridgeDisplayBlitBufferPtr(
            display, uctypes.addressof(buffer), len(buffer),
            x, y, width, height,
        )
    finally:
        _in_js_call = False
    return 0, None


def send_get_inputs():
    global _in_js_call
    if _in_js_call:
        return 0xFFFF
    _in_js_call = True
    try:
        return js.bridgeGetInputs()
    finally:
        _in_js_call = False


def send_pin_value(pin):
    global _in_js_call
    if _in_js_call:
        return 1
    _in_js_call = True
    try:
        return js.bridgeGetPinValue(pin)
    finally:
        _in_js_call = False


def send_neopixel_write(leds):
    global _in_js_call
    if _in_js_call:
        return 0, None
    _in_js_call = True
    try:
        led_list = []
        for led in leds[:7]:
            g, r, b = led
            led_list.append([g, r, b])
        js.bridgeNeopixelWrite(json.dumps(led_list))
    finally:
        _in_js_call = False
    return 0, None


def poll_interrupts():
    global _in_js_call
    if _in_js_call:
        return []
    _in_js_call = True
    try:
        result = js.bridgePollInterrupts()
        if result:
            return json.loads(result)
        return []
    finally:
        _in_js_call = False


def send_command(device, command, **kwargs):
    global _in_js_call
    if _in_js_call:
        return {'status': 'ok'}
    _in_js_call = True
    try:
        if device == 'lis3dh' and command in ('acceleration', 'get_acceleration'):
            result = js.bridgeGetAcceleration()
            data = json.loads(result)
            return {'resp': data}
        elif device == 'adc' and command in ('read', 'get_voltage'):
            voltage = js.bridgeGetAdcVoltage()
            return {'resp': voltage}
        elif device == 'gc9a01':
            return {'status': 'ok'}
        return {'status': 'ok'}
    finally:
        _in_js_call = False


print("[EMULATOR] Web bridge ready")
