"""
Background Service Base Class

Provides a common interface for background services that need configuration,
lifecycle management, and integration with the system controller.
"""

from lib.smart_config import Config


class BackgroundService:
    """
    Base class for background services.
    
    Background services are system-level components that run continuously
    and provide functionality like power management, monitoring, or connectivity.
    They differ from apps in that they:
    - Run continuously in the background
    - Don't have UI (though they may expose config via web interface)
    - Provide system-level functionality
    - Can be enabled/disabled via system config
    """
    
    name = ""
    description = ""
    
    def __init__(self, controller, config_namespace: str | None = None):
        self.controller = controller
        self.name = self.name or self.__class__.__name__
        
        # Each service gets its own config namespace
        namespace = config_namespace or f"services/{self.name.lower()}"
        self.config = Config(f"config/{namespace}.json")
        
        # Register this service's config with the controller for web access
        if hasattr(controller, 'service_configs'):
            controller.service_configs[self.name] = self.config
        
        self._running = False
        self._setup_default_config()
    
    def _setup_default_config(self):
        """Override in subclasses to add service-specific configuration."""
        pass
    
    async def start(self):
        """Start the background service. Called during system initialization."""
        self._running = True
    
    async def stop(self):
        """Stop the background service. Called during system shutdown."""
        self._running = False
    
    async def update(self):
        """
        Called periodically by the system. Use for service-specific updates.
        Should be lightweight and non-blocking.
        Override in subclasses to add functionality.
        """
        pass
    
    def is_running(self) -> bool:
        """Check if the service is currently running."""
        return self._running
    
    def get_status(self) -> dict:
        """
        Get service status information for system monitoring.
        Override in subclasses to provide service-specific status.
        """
        return {
            'name': self.name,
            'running': self._running,
            'description': self.description
        }