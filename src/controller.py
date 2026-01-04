import asyncio
import json
import random

import time
import os

from app_directory import AppDirectory, AppMetadata
import apps.app
from bsp import BSP
from hardware_rev import HardwareRev
from icontroller import IController
import lib.battery
from drivers.displays import Displays
import utime
from lib.smart_config import Config
from lib.system_config import SystemConfig
from services.sleep_service import SleepService
from services.wifi_service import WiFiService



class Controller(IController):
    def __init__(self, displays, start_app_on_launch: bool = True):
        if not displays:
            displays = Displays()
        
        super().__init__(HardwareRev.V3, displays)

        # System-wide configuration
        self.system_config = SystemConfig()
        
        # Controller-specific config (app selection, etc.)
        self.config = Config("config/controller.json")
        self.config.add('default_app', 'Badge')
        
        # some things that the views will need
        self._bsp = BSP(HardwareRev.V3, displays)

        self.battery = lib.battery.Battery(self)

        # Config storage for apps and services
        self.app_configs: dict[str, Config] = {}
        self.service_configs: dict[str, Config] = {}
        
        # Background services
        self.services: list = []

        print("Callback handlers")

        self.app_directory = AppDirectory()
        self.current_view: apps.app.BaseApp | None = None

        try:
            name_file = open('name.json')
            self.name = json.loads(name_file.read())
            name_file.close()
        except OSError:
           print("Name file not found")
           self.name = {
               'first': "Bilbo",
               'last': "Baggins",
                'background_image': [
                    'img/bsides_logo.jpg',
                    'img/bsides_logo.jpg'
                ],
                'fg_color': [
                    '#FFFFFF',
                    '#FFFFFF'
                ],
                'bg_color': [
                    '#000000',
                    '#000000'
                ],
                'company': 'Company',
                'title': 'Title'
           }
        
        print('Bluetooth callbacks')
        self.bsp.bluetooth.ble_callbacks.append(self.update_time)
        self.bsp.bluetooth.ble_callbacks.append(self.lights)

        self.reset_buttons_pressed = 0

        # Initialize background services
        self._initialize_services()

        print("Register buttons")
        self.bsp.buttons.button_pressed_callbacks.append(self.button_press)
        self.bsp.buttons.button_clicked_callbacks.append(self.button_click)
        self.bsp.buttons.button_released_callbacks.append(self.button_release)
        self.bsp.buttons.button_long_press_callbacks.append(self.button_long_press)

        self.current_app_lock = asyncio.Lock()

        if start_app_on_launch:
            asyncio.create_task(self.switch_app(self.config['default_app']))
    
    def _initialize_services(self):
        """Initialize background services."""
        print("Initializing background services")
        
        # Initialize WiFi service (should start before other network-dependent services)
        self.wifi_service = WiFiService(self)
        self.services.append(self.wifi_service)
        
        # Initialize sleep service
        self.sleep_service = SleepService(self)
        self.services.append(self.sleep_service)
        
        # Start all services
        for service in self.services:
            asyncio.create_task(service.start())
    
    async def start_services(self):
        """Start all background services."""
        for service in self.services:
            if not service.is_running():
                await service.start()
    
    async def stop_services(self):
        """Stop all background services."""
        for service in self.services:
            if service.is_running():
                await service.stop()
    
    def get_service_status(self) -> dict:
        """Get status of all background services."""
        return {
            service.name: service.get_status()
            for service in self.services
        }

    async def run(self):
        total_times = 0
        total_counts = 0
        
        # Start services if not already started
        await self.start_services()
        
        while True:
            x = time.ticks_ms()
            
            # Update current app
            async with self.current_app_lock:
                if self.current_view:
                    await self.current_view.update()
            
            # Update background services
            for service in self.services:
                if service.is_running():
                    try:
                        await service.update()
                    except Exception as e:
                        print(f"Error updating service {service.name}: {e}")
            
            await asyncio.sleep(0.01)
            
            # Performance monitoring (if enabled)
            if self.system_config.is_performance_monitoring_enabled():
                d = time.ticks_diff(time.ticks_ms(), x)
                total_times += d
                total_counts += 1
                if total_counts % 100 == 0:
                    average = total_times/total_counts
                    print(f"Average: {average} ms")
                    print(f"Average Hz: {int(1000/average)} Hz")

    def update_time(self, payload):
        if payload.startswith('time'):
            payload = payload.split(':')
            unix_time = int(payload[1])
            epoch_difference = 946_684_800 # 0 seconds is January 1, 2000 instead of January 1, 1970
            tz_offset = -4 * 3600 # UTC-5 with DST
            t = utime.localtime(tz_offset + unix_time - epoch_difference)
            self.bsp.rtc.datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
            print(f'Time updated, new time: {self.bsp.rtc.datetime()}, {time.time()}')

    def lights(self, payload):
        if payload == 'turn_on_lights':
            time_now = self.bsp.rtc.datetime()
            if not time_now[4] == 10:
                print(f'Lights triggered at the wrong time: {time_now}')
                return
            try:
                open('led_flag', 'r')
            except OSError:
                pass
            else:
                print('Lights triggered but flag exists')
                return
            
            open('led_flag', 'x').close()
            for led in range(7):
                self.bsp.leds.leds[led] = (30, 0, 0)
            self.bsp.leds.leds.write()

            time.sleep(10)

            self.bsp.leds.turn_off_all()

    def button_long_press(self, button: int):
        print(f'Button long press {button}')

        # if up and down are long pressed it clears the led flag if it is there
        if button == 5 or button == 4:
            self.reset_buttons_pressed += 1
            print(self.reset_buttons_pressed)

        if self.current_view:
            self.current_view.button_long_press(button)
        if button == 3:
            asyncio.create_task(self.switch_app("Menu"))
        
        if self.reset_buttons_pressed == 2:
            print('Clearing LED flag')
            try:
                os.remove('led_flag')
            except Exception as e:
                print('failed clearing flag: ' + str(e))
            else:
                for led in range(7):
                    self.bsp.leds.leds[led] = (50, 0, 0)
                self.bsp.leds.leds.write()
                for led in range(7):
                    self.bsp.leds.leds[led] = (0, 0, 0)
                self.bsp.leds.leds.write()

    def button_press(self, button: int):
        if self.current_view:
            self.current_view.button_press(button)
        print(f"Button Press {button}")

    def button_click(self, button: int):
        print(f'Button click {button}')
        if self.current_view:
            self.current_view.button_click(button)

    def button_release(self, button: int):
        if button == 5 or button == 4:
            self.reset_buttons_pressed -= 1
        
        if self.current_view:
            self.current_view.button_release(button)
        print(f"Button Released {button}")

    def is_current_app(self, app_instance):
        """
        Check if the current app is the same as the one passed in
        """
        if not self.current_view:
            return False
        return self.current_view == app_instance
    

    async def update(self):
        if self.current_view:
            await self.current_view.update()

    async def random_app(self):
        app = random.choice(self.app_directory)
        await self.switch_app(app.module_name)

    async def switch_app(self, app_name: str):
        if not app_name:
            # TODO show a popup or just return?
            print("No view provided")
            return

        app: AppMetadata = self.app_directory.get_app_by_name(app_name) # type: ignore
        if not app:
            print(f"App {app_name} not found")
            return

        self.bsp.speaker.stop_song()

        if not app.constructor:
            module_name = app.module_name
            print(f"Loading {module_name}")
            __import__(f"apps.{module_name}")
            module = getattr(apps, module_name, None)
            if not module:
                # TODO show a popup or just return?
                print("No module found")
                return

            # TODO normalize with code in module metadata?
            for _, obj in module.__dict__.items():
                # This check makes sure we don't just load the first "BaseApp" we find and instead
                # load the correct app based on `name`
                if isinstance(obj, type) \
                        and issubclass(obj, apps.app.BaseApp) \
                        and obj != apps.app.BaseApp \
                        and obj.name == app.friendly_name: 
                    print(f"Found constructor, switched to {app_name} with {obj}")

                    app.constructor = obj
                    break
        
        if not app.constructor:
            print(f"App {app_name} not found")
            return

        if self.current_view:
            print("teardown current view")
            await self.current_view.teardown()

        print("Starting attempt to lock")
        async with self.current_app_lock:
            print(f"creating new instance of {app_name}")
            self.current_view = None
            self.current_view = app.constructor(self)
        
        print(f"Calling {app_name} app setup function")
        await self.current_view.setup()

        print("Done with app switch")
        
        await asyncio.sleep(0.01)

        print("Switching to new app")

        return  
