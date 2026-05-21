"""utime module stub - delegates to time module."""
from time import *

def sleep_ms(ms):
    import time
    time.sleep(ms / 1000)

def sleep_us(us):
    import time
    time.sleep(us / 1000000)

def ticks_ms():
    import time
    return int(time.time() * 1000) & 0x3FFFFFFF

def ticks_us():
    import time
    return int(time.time() * 1000000) & 0x3FFFFFFF

def ticks_diff(t1, t2):
    return (t1 - t2) & 0x3FFFFFFF

def ticks_add(t, delta):
    return (t + delta) & 0x3FFFFFFF
