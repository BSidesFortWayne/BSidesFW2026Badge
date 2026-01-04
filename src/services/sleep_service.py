"""
Enhanced Sleep Management Service

Provides configurable sleep/power management with system-level configuration support.
"""

import time
import machine
import esp32
import micropython
from lib.background_service import BackgroundService
from lib.smart_config import BoolDropdownConfig, RangeConfig
from drivers.audio import AUDIO_PLAYING


class SleepService(BackgroundService):
    """
    Enhanced sleep management service with configurable parameters.
    
    Handles device sleep/wake functionality with user-configurable:
    - Sleep timeout
    - Motion sensitivity for wake detection  
    - Enable/disable sleep functionality
    - Wake sources (buttons, motion, etc.)
    """
    
    name = "Sleep"
    description = "Power management and sleep detection service"
    
    def __init__(self, controller):
        super().__init__(controller)
        self.bsp = controller.bsp
        self.state_before_sleeping = {}
        
        # Set up motion detection pin
        self.lis3dh_int2_pin = machine.Pin(34, machine.Pin.IN)
        
        # Track last activity for timeout
        self.last_activity_time = time.ticks_ms()
        
        # Timer for periodic sleep checks (can't use asyncio in sleep context)
        self.timer = machine.Timer(2)
        
    def _setup_default_config(self):
        """Set up sleep-specific configuration options."""
        self.config.add('enabled', BoolDropdownConfig("Sleep Enabled", True))
        self.config.add('timeout_ms', RangeConfig("Sleep Timeout (ms)", 30_000, 600_000, 120_000, 5_000))
        self.config.add('motion_sensitivity', RangeConfig("Motion Sensitivity", 50, 200, 100, 10))
        self.config.add('button_wake_enabled', BoolDropdownConfig("Wake on Button Press", True))
        self.config.add('motion_wake_enabled', BoolDropdownConfig("Wake on Motion", True))
        
    async def start(self):
        """Initialize and start the sleep service."""
        await super().start()
        
        print("Starting Sleep Service")
        
        # Configure accelerometer for motion detection
        sensitivity = self.config['motion_sensitivity']
        self._configure_motion_detection(sensitivity)
        
        # Set up wake sources
        if self.config['motion_wake_enabled'].value():
            self.lis3dh_int2_pin.irq(trigger=machine.Pin.IRQ_RISING, handler=self._on_motion)
            esp32.wake_on_ext0(self.lis3dh_int2_pin, esp32.WAKEUP_ANY_HIGH)
        
        # Register button callback if button wake is enabled
        if self.config['button_wake_enabled'].value():
            self.bsp.buttons.button_pressed_callbacks.append(self._on_activity)
        
        # Start periodic sleep checking
        self.timer.init(
            period=1000, 
            mode=machine.Timer.PERIODIC,
            callback=lambda t: micropython.schedule(self._check_sleep_timeout, 0)
        )
        
        # Initialize activity tracking
        self._reset_activity_timer()
        
    async def stop(self):
        """Stop the sleep service."""
        await super().stop()
        
        print("Stopping Sleep Service")
        
        # Stop timer
        self.timer.deinit()
        
        # Remove callbacks
        if self._on_activity in self.bsp.buttons.button_pressed_callbacks:
            self.bsp.buttons.button_pressed_callbacks.remove(self._on_activity)
        
        # Disable interrupt
        self.lis3dh_int2_pin.irq(handler=None)
    
    async def update(self):
        """Periodic update for sleep service."""
        # Update motion sensitivity if changed
        current_sensitivity = self.config['motion_sensitivity']
        self._configure_motion_detection(current_sensitivity)
        
        # Update wake sources based on config  
        # TODO: Could add logic here to reconfigure wake sources if settings changed
        # motion_wake = self.config['motion_wake_enabled'].value()
        # button_wake = self.config['button_wake_enabled'].value()
        
    def _configure_motion_detection(self, sensitivity):
        """Configure accelerometer motion detection with given sensitivity."""
        try:
            # Extract actual value if it's a config object
            threshold = sensitivity.value() if hasattr(sensitivity, 'value') else sensitivity
            
            # Configure LIS3DH registers for motion detection
            # These are the same registers as the original implementation
            self.bsp.imu.set_tap(tap=1, threshold=threshold)
            self.bsp.imu._write_register_byte(0x24, 0x28)
            self.bsp.imu._write_register_byte(0x22, 0x00) 
            self.bsp.imu._write_register_byte(0x25, 0x80)
            
            # Clear any existing interrupts
            self.bsp.imu._read_register_byte(0x39)
        except Exception as e:
            print(f"Error configuring motion detection: {e}")
    
    def _on_motion(self, pin):
        """Handle motion detection interrupt."""
        if self.config['motion_wake_enabled'].value():
            print('Motion detected, resetting sleep timer')
            self._reset_activity_timer()
            # Clear interrupt latch
            try:
                self.bsp.imu._read_register_byte(0x39)
            except Exception:
                pass
    
    def _on_activity(self, *args):
        """Handle any activity that should reset sleep timer."""
        print('Activity detected, resetting sleep timer')
        self._reset_activity_timer()
    
    def _reset_activity_timer(self):
        """Reset the activity timer to current time."""
        self.last_activity_time = time.ticks_ms()
    
    def _check_sleep_timeout(self, _):
        """Check if sleep timeout has been reached and initiate sleep if needed."""
        if not self.config['enabled'].value():
            return
        
        # Debug: check what type timeout_ms is
        timeout_config = self.config['timeout_ms']
        
        timeout_ms = timeout_config.value() if hasattr(timeout_config, 'value') else timeout_config
        
        time_since_activity = time.ticks_diff(time.ticks_ms(), self.last_activity_time)
        
        if time_since_activity >= timeout_ms:
            print(f"Sleep timeout reached ({time_since_activity}ms), initiating sleep")
            self._enter_sleep()
    
    def _save_hardware_state(self):
        """Save current hardware state before sleeping."""
        try:
            self.state_before_sleeping['audio_state'] = self.bsp.speaker.state
            self.state_before_sleeping['leds'] = list(self.bsp.leds.leds)
        except Exception as e:
            print(f"Error saving hardware state: {e}")
    
    def _restore_hardware_state(self):
        """Restore hardware state after waking up."""
        try:
            # Clear motion interrupt latch
            self.bsp.imu._read_register_byte(0x39)
            
            # Restore LEDs
            if 'leds' in self.state_before_sleeping:
                for led, color in enumerate(self.state_before_sleeping['leds']):
                    self.bsp.leds.leds[led] = color
                self.bsp.leds.leds.write()
            
            # Restore audio
            if self.state_before_sleeping.get('audio_state') == AUDIO_PLAYING:
                self.bsp.speaker.resume_song()
            
            # Re-enable displays
            self.bsp.displays.disp_en.value(1)
            
        except Exception as e:
            print(f"Error restoring hardware state: {e}")
    
    def _enter_sleep(self):
        """Enter sleep mode with proper state management."""
        print("Entering sleep mode")
        
        # Save current state
        self._save_hardware_state()
        
        # Prepare hardware for sleep
        self.bsp.leds.turn_off_all()
        self.bsp.displays.disp_en.value(0)
        
        if self.state_before_sleeping.get('audio_state') == AUDIO_PLAYING:
            self.bsp.speaker.pause_song()
        
        # Enter light sleep (preserves RAM, allows wake on GPIO)
        machine.lightsleep()
        
        # We wake up here
        print("Waking up from sleep")
        self._restore_hardware_state()
        self._reset_activity_timer()
    
    def force_sleep(self):
        """Force immediate sleep regardless of timeout."""
        print("Forcing immediate sleep")
        self._enter_sleep()
    
    def get_status(self) -> dict:
        """Get detailed sleep service status."""
        status = super().get_status()
        
        time_since_activity = time.ticks_diff(time.ticks_ms(), self.last_activity_time)
        timeout_ms = self.config['timeout_ms'].value() if hasattr(self.config['timeout_ms'], 'value') else self.config['timeout_ms']
        time_until_sleep = max(0, timeout_ms - time_since_activity)
        
        motion_sensitivity = self.config['motion_sensitivity'].value() if hasattr(self.config['motion_sensitivity'], 'value') else self.config['motion_sensitivity']
        
        status.update({
            'enabled': self.config['enabled'].value(),
            'timeout_ms': timeout_ms,
            'time_since_activity_ms': time_since_activity,
            'time_until_sleep_ms': time_until_sleep,
            'motion_sensitivity': motion_sensitivity,
            'motion_wake_enabled': self.config['motion_wake_enabled'].value(),
            'button_wake_enabled': self.config['button_wake_enabled'].value(),
        })
        
        return status