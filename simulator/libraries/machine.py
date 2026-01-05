import _thread
import time
import emulator
import micropython

# Start interrupt polling thread
_interrupt_poll_enabled = True

def _interrupt_poll_thread():
    """Background thread that polls for interrupts and dispatches them."""
    while _interrupt_poll_enabled:
        try:
            # Poll for pending interrupts from GUI
            interrupts = emulator.poll_interrupts()
            for interrupt in interrupts:
                pin_num = interrupt['pin']
                # Dispatch to the registered pin handler
                if pin_num in Pin._pin_registry:
                    # Use micropython.schedule for thread-safe callback
                    pin_obj = Pin._pin_registry[pin_num]
                    micropython.schedule(_dispatch_interrupt, (pin_obj, interrupt['edge']))
        except Exception as e:
            print(f"Error in interrupt poll thread: {e}")
        time.sleep(0.05)  # Poll at 20Hz

def _dispatch_interrupt(args):
    """Dispatch interrupt to handler (called via micropython.schedule)."""
    pin_obj, edge = args
    try:
        # Simulate edge by setting pin value and triggering handlers
        if edge == 'rising':
            pin_obj._value = 0
            pin_obj._check_and_trigger_irq(0, 1)
            pin_obj._value = 1
        elif edge == 'falling':
            pin_obj._value = 1
            pin_obj._check_and_trigger_irq(1, 0)
            pin_obj._value = 0
    except Exception as e:
        print(f"Error dispatching interrupt for pin {pin_obj.pin}: {e}")

# Start polling thread immediately
_thread.start_new_thread(_interrupt_poll_thread, ())

class Pin:
    IRQ_FALLING = 0
    IRQ_RISING = 1
    IRQ_ANY_EDGE = 2
    IN = 0
    OUT = 1
    
    # Class-level registry of all pins with IRQ handlers
    _pin_registry = {}

    def __init__(self, pin, mode=None):
        self.interrupts = []
        self._value = 0
        self.pin = pin
        self.mode = mode
        # Register this pin instance
        Pin._pin_registry[pin] = self
    
    def init(self, *args, **kwargs):
        pass

    def value(self, state=None):
        if state == None:
            # Read state from emulator for input pins
            if self.mode == Pin.IN:
                result = emulator.send_command('pin', 'value', pin=self.pin, value=self._value)
                if 'resp' in result:
                    return result['resp']
            return self._value
        else:
            old_value = self._value
            self._value = state
            emulator.send_command('pin', 'value', pin=self.pin, value=self._value)
            
            # Check if we should trigger interrupts
            if old_value != state:
                self._check_and_trigger_irq(old_value, state)
    
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
                try:
                    handler(self)
                except Exception as e:
                    print(f"Error in IRQ handler for pin {self.pin}: {e}")
    
    @classmethod
    def trigger_interrupt(cls, pin_num):
        """Trigger an interrupt on a specific pin (for simulator events like shake)"""
        if pin_num in cls._pin_registry:
            pin_obj = cls._pin_registry[pin_num]
            # Simulate a rising edge pulse
            pin_obj._value = 1
            pin_obj._check_and_trigger_irq(0, 1)
            # Reset back to 0 after trigger
            pin_obj._value = 0
    
    def on(self):
        self._value = 1
        emulator.send_command('pin', 'value', pin=self.pin, value=self._value)
    
    def off(self):
        self._value = 0
        emulator.send_command('pin', 'value', pin=self.pin, value=self._value)

    def irq(self, handler=None, trigger=None):
        if handler is None:
            # Clear all interrupts
            self.interrupts = []
        else:
            self.interrupts.append({
                'handler': handler,
                'trigger': trigger
            })

class PWM:
    def __init__(self, pin, freq=None, duty=None, duty_u16=None):
        self.pin = pin
        self._freq = freq or 1000
        self._duty = duty or 0
        self._duty_u16 = duty_u16 or 0
    
    def duty(self, value=None):
        if value is None:
            return self._duty
        self._duty = value
        emulator.send_command('pwm', 'duty', value=value)
    
    def duty_u16(self, value=None):
        if value is None:
            return self._duty_u16
        self._duty_u16 = value
        emulator.send_command('pwm', 'duty_u16', value=value)
    
    def freq(self, value=None):
        if value is None:
            return self._freq
        self._freq = value
        emulator.send_command('pwm', 'freq', value=value)

class I2C:
    def __init__(self, *args, **kwargs):
        pass

    def scan(self):
        return [0x18, 0x20]
    
    def start(self):
        pass

    def stop(self):
        pass

    def init(self):
        pass

    def readfrom(self, buffer, nack=True):
        return [0 for x in range(len(buffer))]
    
    def readinto(self, address, byte_amount, stop=True):
        return [0 for x in range(byte_amount)]

    def readfrom_mem(self, address, port, byte_amount, stop=True):
        # Return device-specific values for simulator
        # LIS3DH WHO_AM_I register (0x0F) should return 0x33
        if address == 0x18 and port == 0x0F:
            return bytes([0x33])
        
        # LIS3DH Accelerometer data registers (0x28-0x2D: X_L, X_H, Y_L, Y_H, Z_L, Z_H)
        # Reading with auto-increment (0x80 bit set) returns 6 bytes
        if address == 0x18 and (port & 0x7F) == 0x28:
            import emulator
            import struct
            # Get acceleration data from GUI (in g's)
            accel_data = emulator.send_command('lis3dh', 'get_acceleration')
            if accel_data and 'resp' in accel_data:
                x_g = accel_data['resp']['x']
                y_g = accel_data['resp']['y']
                z_g = accel_data['resp']['z']
                
                # Convert from g's to raw values (assuming 2G range, divider=16380)
                # raw = (g_value * divider) / STANDARD_GRAVITY
                STANDARD_GRAVITY = 9.806
                divider = 16380  # Default 2G range
                x_raw = int((x_g * STANDARD_GRAVITY) * divider / STANDARD_GRAVITY)
                y_raw = int((y_g * STANDARD_GRAVITY) * divider / STANDARD_GRAVITY)
                z_raw = int((z_g * STANDARD_GRAVITY) * divider / STANDARD_GRAVITY)
                
                # Pack as 3 signed 16-bit little-endian values
                return struct.pack('<hhh', x_raw, y_raw, z_raw)
            # Default to 0,0,1g if no data
            return struct.pack('<hhh', 0, 0, 16380)
        
        # LIS3DH ADC registers (0x08-0x0D: ADC1_L, ADC1_H, ADC2_L, ADC2_H, ADC3_L, ADC3_H)
        if address == 0x18 and (port & 0x7F) >= 0x08 and (port & 0x7F) <= 0x0D:
            import emulator
            import struct
            # Get ADC voltage from GUI (in mV)
            adc_data = emulator.send_command('adc', 'get_voltage')
            if adc_data and 'resp' in adc_data:
                voltage_mV = adc_data['resp']
                # Convert mV back to raw ADC value
                # From read_adc_mV: return 1800+(raw+32512)*(-900/65024)
                # Solve for raw: raw = ((voltage_mV - 1800) * 65024 / -900) - 32512
                raw_value = int(((voltage_mV - 1800) * 65024 / -900) - 32512)
                return struct.pack('<h', raw_value)
            # Default to ~1000mV
            return struct.pack('<h', -10000)
        
        # PCA9535 I2C GPIO expander (button controller)
        # Reads input port registers (0x00 = Port 0, 0x01 = Port 1)
        if address == 0x20 and port in [0x00, 0x01]:
            import emulator
            # Get full 16-bit input state from emulator
            full_state = emulator.send_command('pca9535', 'get_inputs')['resp']
            # Return the appropriate byte based on port
            if port == 0x00:
                # Port 0 (lower 8 bits)
                return bytes([full_state & 0xFF])
            else:
                # Port 1 (upper 8 bits)
                return bytes([(full_state >> 8) & 0xFF])
        
        return bytes([0 for x in range(byte_amount)])
    
    def readfrom_mem_into(self, address, byte_amount, stop=True, addrsize=8):
        return [0 for x in range(byte_amount)]

    def writeto(self, address, buffer, stop=True):
        return len(buffer)
    
    def writeto_mem(self, address, memory_address, buffer, addrsize=8):
        return len(buffer)

    def writevto(self, address, vector, stop=True):
        return len(buffer)
    
    def write(self, buffer):
        return len(buffer)

class SPI:
    def __init__(self, *args, **kwargs):
        pass

class Timer:
    PERIODIC = 0

    def __init__(self, id):
        self.id = id
    
    def init(self, mode, period, callback):
        _thread.start_new_thread(self.timer_thread, (period, callback))
    
    def timer_thread(self, delay, function):
        while True:
            function(self)
            time.sleep_ms(delay)

class ADC:
    def __init__(self, *args, **kwargs):
        pass

class RTC:
    def __init__(self):
        pass
    
    def datetime(self, date_tuple=None):
        if date_tuple is None:
            # Return current time as (year, month, day, weekday, hours, minutes, seconds, subseconds)
            import time
            t = time.localtime()
            return (t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0)
        else:
            # Set time (not implemented in simulator)
            pass

def lightsleep(duration_ms=None):
    """Simulate light sleep mode.
    
    Args:
        duration_ms: Optional sleep duration in milliseconds.
                     If None, sleeps indefinitely until woken by interrupt.
    """
    print(f"[MACHINE] Entering lightsleep (duration_ms={duration_ms})")
    # In simulator, we just log the sleep event
    # The actual wake-up would be triggered by GPIO interrupts or timeout
    # For now, just return immediately to allow the simulator to continue
    pass

def deepsleep(duration_ms=None):
    """Simulate deep sleep mode.
    
    Args:
        duration_ms: Optional sleep duration in milliseconds.
    """
    print(f"[MACHINE] Entering deepsleep (duration_ms={duration_ms})")
    # In simulator, just log the deep sleep event
    pass