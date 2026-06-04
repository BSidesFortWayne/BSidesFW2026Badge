import js
import json
import emulator


_timer_callbacks = []


def _dispatch_interrupt(args):
    pin_obj, edge = args
    try:
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


def _poll_interrupts_callback():
    try:
        interrupts = emulator.poll_interrupts()
        if interrupts:
            for interrupt in interrupts:
                pin_num = interrupt['pin']
                if pin_num in Pin._pin_registry:
                    pin_obj = Pin._pin_registry[pin_num]
                    _dispatch_interrupt((pin_obj, interrupt['edge']))
    except Exception:
        pass


class Pin:
    IRQ_FALLING = 0
    IRQ_RISING = 1
    IRQ_ANY_EDGE = 2
    IN = 0
    OUT = 1

    _pin_registry = {}

    def __init__(self, pin, mode=None):
        self.interrupts = []
        self._value = 0
        self.pin = pin
        self.mode = mode
        Pin._pin_registry[pin] = self

    def init(self, *args, **kwargs):
        pass

    def value(self, state=None):
        if state is None:
            if self.mode == Pin.IN:
                return emulator.send_pin_value(self.pin)
            return self._value
        else:
            old_value = self._value
            self._value = state
            if old_value != state:
                self._check_and_trigger_irq(old_value, state)

    def _check_and_trigger_irq(self, old_value, new_value):
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
        if pin_num in cls._pin_registry:
            pin_obj = cls._pin_registry[pin_num]
            pin_obj._value = 1
            pin_obj._check_and_trigger_irq(0, 1)
            pin_obj._value = 0

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0

    def irq(self, handler=None, trigger=None):
        if handler is None:
            self.interrupts = []
        else:
            self.interrupts.append({'handler': handler, 'trigger': trigger})


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
        import emulator
        if not emulator._in_js_call:
            emulator._in_js_call = True
            try:
                js.bridgePwmSetDuty(value)
            finally:
                emulator._in_js_call = False

    def duty_u16(self, value=None):
        if value is None:
            return self._duty_u16
        self._duty_u16 = value

    def freq(self, value=None):
        if value is None:
            return self._freq
        self._freq = value
        import emulator
        if not emulator._in_js_call:
            emulator._in_js_call = True
            try:
                js.bridgePwmSetFreq(value)
            finally:
                emulator._in_js_call = False

    def deinit(self):
        import emulator
        if not emulator._in_js_call:
            emulator._in_js_call = True
            try:
                js.bridgePwmDeinit()
            finally:
                emulator._in_js_call = False


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
        import struct

        if address == 0x18 and port == 0x0F:
            return bytes([0x33])

        if address == 0x18 and (port & 0x7F) == 0x28:
            accel_data = emulator.send_command('lis3dh', 'get_acceleration')
            if accel_data and 'resp' in accel_data:
                x_g = accel_data['resp']['x']
                y_g = accel_data['resp']['y']
                z_g = accel_data['resp']['z']
                STANDARD_GRAVITY = 9.806
                divider = 16380
                x_raw = int((x_g * STANDARD_GRAVITY) * divider / STANDARD_GRAVITY)
                y_raw = int((y_g * STANDARD_GRAVITY) * divider / STANDARD_GRAVITY)
                z_raw = int((z_g * STANDARD_GRAVITY) * divider / STANDARD_GRAVITY)
                return struct.pack('<hhh', x_raw, y_raw, z_raw)
            return struct.pack('<hhh', 0, 0, 16380)

        if address == 0x18 and (port & 0x7F) >= 0x08 and (port & 0x7F) <= 0x0D:
            adc_data = emulator.send_command('adc', 'get_voltage')
            if adc_data and 'resp' in adc_data:
                voltage_mV = adc_data['resp']
                raw_value = int(((voltage_mV - 1800) * 65024 / -900) - 32512)
                return struct.pack('<h', raw_value)
            return struct.pack('<h', -10000)

        if address == 0x20 and port in [0x00, 0x01]:
            full_state = emulator.send_get_inputs()
            if port == 0x00:
                return bytes([full_state & 0xFF])
            else:
                return bytes([(full_state >> 8) & 0xFF])

        return bytes([0 for x in range(byte_amount)])

    def readfrom_mem_into(self, address, byte_amount, stop=True, addrsize=8):
        return [0 for x in range(byte_amount)]

    def writeto(self, address, buffer, stop=True):
        return len(buffer)

    def writeto_mem(self, address, memory_address, buffer, addrsize=8):
        return len(buffer)

    def writevto(self, address, vector, stop=True):
        total_len = sum(len(v) for v in vector)
        return total_len

    def write(self, buf):
        return len(buf)


class SPI:
    def __init__(self, *args, **kwargs):
        pass


class Timer:
    PERIODIC = 0
    ONE_SHOT = 1
    _active_timers = []

    def __init__(self, id=-1):
        self.id = id
        self._running = False
        self._task = None

    def init(self, mode=PERIODIC, period=100, callback=None):
        self.deinit()
        if callback is None:
            return
        try:
            import asyncio
        except ImportError:
            import uasyncio as asyncio
        self._running = True
        self._in_callback = False

        timer_self = self

        async def _timer_loop():
            while timer_self._running:
                if not timer_self._in_callback:
                    timer_self._in_callback = True
                    try:
                        callback(timer_self)
                    except Exception as e:
                        print(f"Timer callback error: {e}")
                    finally:
                        timer_self._in_callback = False
                await asyncio.sleep_ms(period)

        self._task = asyncio.create_task(_timer_loop())
        Timer._active_timers.append(self)

    def deinit(self):
        self._running = False
        if self in Timer._active_timers:
            Timer._active_timers.remove(self)


class ADC:
    def __init__(self, *args, **kwargs):
        pass


class RTC:
    def __init__(self):
        pass

    def datetime(self, date_tuple=None):
        if date_tuple is None:
            import time
            t = time.localtime()
            return (t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0)
        else:
            pass


def lightsleep(duration_ms=None):
    print(f"[MACHINE] lightsleep({duration_ms}ms) - no-op in web")


def deepsleep(duration_ms=None):
    print(f"[MACHINE] deepsleep({duration_ms}ms) - no-op in web")


def freq(value=None):
    if value is None:
        return 240_000_000
    pass


# Start interrupt polling as an asyncio task (not setInterval, to avoid re-entrancy).
# Called from main.js boot sequence after the event loop is running.
_interrupt_poll_task = None

def start_interrupt_polling():
    global _interrupt_poll_task
    if _interrupt_poll_task is not None:
        return
    try:
        import asyncio
    except ImportError:
        import uasyncio as asyncio

    async def _poll_loop():
        while True:
            _poll_interrupts_callback()
            await asyncio.sleep_ms(50)

    _interrupt_poll_task = asyncio.create_task(_poll_loop())
