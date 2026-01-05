# Simulator Interrupt Handling Architecture

## Overview
The simulator implements a **polling-based interrupt system** that mimics hardware pin interrupts in MicroPython. This allows hardware events (like accelerometer motion detection) to trigger interrupt handlers in simulated firmware code.

## Architecture Components

### 1. Interrupt Queue (GUI Layer)
**File:** `gui_enhanced.py`

The GUI maintains an interrupt queue that collects hardware events:
```python
self.interrupt_queue = []  # List of {'pin': int, 'edge': str}
```

When a hardware event occurs (e.g., shake detection):
```python
self.interrupt_queue.append({'pin': 34, 'edge': 'rising'})
```

The GUI responds to `poll_interrupts` commands by returning and clearing the queue:
```python
elif command['command'] == 'poll_interrupts':
    interrupts = self.interrupt_queue.copy()
    self.interrupt_queue.clear()
    return interrupts
```

### 2. Emulator Communication Layer
**File:** `libraries/emulator.py`

Provides `poll_interrupts()` function that MicroPython code uses to check for pending interrupts:
```python
def poll_interrupts():
    """Poll for pending hardware interrupts from the GUI.
    Returns list of interrupt events: [{'pin': 34, 'edge': 'rising'}, ...]
    """
    result = send_command('pin', 'poll_interrupts')
    return result.get('resp', [])
```

### 3. Interrupt Dispatch Thread (Machine Layer)
**File:** `libraries/machine.py`

A background thread continuously polls for interrupts and dispatches them:

```python
def _interrupt_poll_thread():
    """Background thread that polls for interrupts and dispatches them."""
    while _interrupt_poll_enabled:
        interrupts = emulator.poll_interrupts()
        for interrupt in interrupts:
            pin_num = interrupt['pin']
            if pin_num in Pin._pin_registry:
                pin_obj = Pin._pin_registry[pin_num]
                micropython.schedule(_dispatch_interrupt, (pin_obj, interrupt['edge']))
        time.sleep(0.05)  # Poll at 20Hz
```

**Why polling instead of push?**
- MicroPython simulator runs in separate process from GUI
- Socket communication is one-way (MicroPython → GUI for commands)
- Polling is simple, reliable, and 20Hz is fast enough for user interactions
- Alternative would require bidirectional sockets or shared memory

### 4. Pin IRQ Registration
**File:** `libraries/machine.py` - `Pin` class

Pins register interrupt handlers using the standard MicroPython API:
```python
pin = machine.Pin(34, machine.Pin.IN)
pin.irq(handler=my_handler, trigger=machine.Pin.IRQ_RISING)
```

The `Pin` class maintains a registry of all pins:
```python
_pin_registry = {}  # Class-level dict: {pin_num: Pin_instance}
```

When an interrupt is dispatched, it triggers the registered handlers:
```python
def _check_and_trigger_irq(self, old_value, new_value):
    """Check if interrupt conditions are met and trigger handlers"""
    for irq_config in self.interrupts:
        trigger = irq_config['trigger']
        handler = irq_config['handler']
        
        should_trigger = False
        if trigger == Pin.IRQ_RISING and old_value == 0 and new_value == 1:
            should_trigger = True
        elif trigger == Pin.IRQ_FALLING and old_value == 1 and new_value == 0:
            should_trigger = True
        elif trigger == Pin.IRQ_ANY_EDGE and old_value != new_value:
            should_trigger = True
        
        if should_trigger and handler:
            handler(self)
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  USER INTERACTION                                               │
│  (Clicks "Shake Device" button)                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  GUI (gui_enhanced.py)                                          │
│  - Detects shake event                                          │
│  - Appends {'pin': 34, 'edge': 'rising'} to interrupt_queue     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │  (Waits for poll)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  INTERRUPT POLL THREAD (machine.py)                             │
│  - Runs every 50ms (20Hz)                                       │
│  - Calls emulator.poll_interrupts()                             │
│  - Receives list of pending interrupts                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │  (For each interrupt)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  MICROPYTHON.SCHEDULE                                           │
│  - Thread-safe callback scheduler                               │
│  - Queues interrupt dispatch on main thread                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  _dispatch_interrupt()                                          │
│  - Simulates pin edge (0→1 for rising)                          │
│  - Calls pin_obj._check_and_trigger_irq()                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  USER IRQ HANDLER                                               │
│  - SleepService._on_motion() or other registered handler        │
│  - Executes in main MicroPython thread context                  │
└─────────────────────────────────────────────────────────────────┘
```

## Hardware Event Sources

### Currently Implemented
1. **Accelerometer Shake (Pin 34)**
   - Source: "Shake Device" button in GUI
   - Pin: 34 (LIS3DH INT2)
   - Edge: Rising
   - Use case: Wake from sleep, reset activity timer

### Future Expandable Events
The queue-based architecture easily supports additional interrupt sources:
- Button press/release (GPIO pins)
- Timer expiration
- UART data received
- I2C/SPI events
- RTC alarm

To add a new interrupt source:
1. In GUI: `self.interrupt_queue.append({'pin': <pin_num>, 'edge': 'rising'|'falling'})`
2. In firmware: Register handler with `pin.irq(handler=..., trigger=...)`

## Usage Example

### In Firmware (src/services/sleep_service.py)
```python
import machine

# Configure accelerometer interrupt pin
self.lis3dh_int2_pin = machine.Pin(34, machine.Pin.IN)
self.lis3dh_int2_pin.irq(
    trigger=machine.Pin.IRQ_RISING, 
    handler=self._on_motion
)

def _on_motion(self, pin):
    """Called when accelerometer detects motion"""
    print('[Sleep] Motion interrupt triggered!')
    # Clear interrupt latch
    self.bsp.imu._read_register_byte(0x39)
    # Reset activity timer
    self._reset_activity_timer()
```

### In Simulator GUI
```python
# When user clicks "Shake Device" button
def _apply_shake(self):
    self.accel_data = [random.uniform(-2.0, 2.0) for _ in range(3)]
    self.interrupt_queue.append({'pin': 34, 'edge': 'rising'})
```

## Performance Characteristics

- **Polling frequency:** 20Hz (50ms intervals)
- **Latency:** Worst case ~50ms from event to handler
- **Overhead:** Minimal - only active when interrupt handlers are registered
- **Thread safety:** Uses `micropython.schedule()` for main-thread dispatch

## Debugging

### Enable interrupt logging
In GUI constructor:
```python
self.logger.log_info('Motion interrupt queued for pin 34')
self.logger.log_info('Returning X pending interrupt(s)')
```

In machine.py:
```python
print(f"Error in interrupt poll thread: {e}")
print(f"Error dispatching interrupt for pin {pin_obj.pin}: {e}")
```

### Common issues
1. **Handler not called:** Check pin is registered in `Pin._pin_registry`
2. **Multiple triggers:** GUI may queue duplicate events - ensure proper debouncing
3. **Thread conflicts:** Always use `micropython.schedule()` for thread-safe callbacks

## Comparison with Hardware

### Real ESP32 Hardware
- Hardware pin interrupts fire immediately (microseconds)
- Interrupt handler runs in interrupt context
- Must use `micropython.schedule()` for non-trivial work

### Simulator
- Software polling with ~50ms latency
- Handler already runs in main thread (via `micropython.schedule()`)
- Functionally equivalent for user-level testing

## Testing

Create test apps that:
1. Register interrupt handlers on various pins
2. Verify handler is called when GUI events occur
3. Test edge types (rising, falling, any)
4. Verify thread safety with concurrent operations

See `src/test/test_interrupts.py` for examples (TODO: create this test).
