"""Bluetooth simulator module for badge simulator"""

class BLE:
    """Simulated BLE interface"""
    
    def __init__(self):
        self._active = False
        self._irq_handler = None
    
    def active(self, state=None):
        """Get or set BLE active state"""
        if state is None:
            return self._active
        self._active = state
    
    def irq(self, handler):
        """Set IRQ handler for BLE events"""
        self._irq_handler = handler
    
    def gap_scan(self, duration, interval_us, window_us):
        """Start BLE scanning (no-op in simulator)"""
        pass
    
    def gap_advertise(self, interval_ms, adv_data, connectable=False):
        """Start BLE advertising (no-op in simulator)"""
        pass
