"""
System Configuration Manager

Manages system-wide configurations for background services and core functionality.
This provides a centralized way to configure system behavior separate from individual apps.
"""

from lib.smart_config import Config, BoolDropdownConfig, RangeConfig


class SystemConfig:
    """
    Central system configuration manager.
    
    Provides a unified interface for system-wide settings that affect
    background services, power management, and core device behavior.
    """
    
    def __init__(self, config_file: str = "config/system.json"):
        self.config = Config(config_file)
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Initialize default system configurations."""
        
        # Sleep/Power Management Settings
        self.config.add('sleep_enabled', BoolDropdownConfig("Sleep Enabled", True))
        self.config.add('sleep_timeout_ms', RangeConfig("Sleep Timeout (ms)", 10_000, 600_000, 120_000, 5_000))
        self.config.add('sleep_sensitivity', RangeConfig("Motion Sensitivity", 50, 200, 100, 10))
        
        # Display Settings
        self.config.add('display_brightness', RangeConfig("Display Brightness", 10, 100, 80, 5))
        self.config.add('auto_display_off_ms', RangeConfig("Auto Display Off (ms)", 30_000, 300_000, 60_000, 10_000))
        
        # System Behavior
        self.config.add('debug_mode', BoolDropdownConfig("Debug Mode", False))
        self.config.add('performance_monitoring', BoolDropdownConfig("Performance Monitoring", False))
        
        # LED Settings
        self.config.add('led_brightness', RangeConfig("LED Brightness", 0, 100, 50, 5))
        self.config.add('led_idle_enabled', BoolDropdownConfig("LED Idle Animation", False))
    
    def get_sleep_config(self) -> dict:
        """Get all sleep-related configuration values."""
        return {
            'enabled': self.config['sleep_enabled'].value(),
            'timeout_ms': self.config['sleep_timeout_ms'],
            'sensitivity': self.config['sleep_sensitivity']
        }
    
    def get_display_config(self) -> dict:
        """Get all display-related configuration values."""
        return {
            'brightness': self.config['display_brightness'],
            'auto_off_ms': self.config['auto_display_off_ms']
        }
    
    def get_led_config(self) -> dict:
        """Get all LED-related configuration values."""
        return {
            'brightness': self.config['led_brightness'],
            'idle_enabled': self.config['led_idle_enabled'].value()
        }
    
    def is_debug_enabled(self) -> bool:
        """Check if debug mode is enabled."""
        return self.config['debug_mode'].value()
    
    def is_performance_monitoring_enabled(self) -> bool:
        """Check if performance monitoring is enabled."""
        return self.config['performance_monitoring'].value()
    
    def __getitem__(self, key):
        """Allow direct access to config values."""
        return self.config[key]
    
    def __setitem__(self, key, value):
        """Allow direct setting of config values."""
        self.config[key] = value