"""ESP32-specific simulator module"""

# Wake-up constants
WAKEUP_ANY_HIGH = 1
WAKEUP_ALL_LOW = 0

def wake_on_ext0(pin, level):
    """Configure wake on external interrupt (no-op in simulator)"""
    pass

def wake_on_ext1(pins, level):
    """Configure wake on multiple external interrupts (no-op in simulator)"""
    pass

def wake_on_touch(enable):
    """Enable/disable wake on touch (no-op in simulator)"""
    pass

def wake_on_ulp(enable):
    """Enable/disable wake on ULP (no-op in simulator)"""
    pass
