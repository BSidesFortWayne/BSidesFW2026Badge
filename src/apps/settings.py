from apps.app import BaseApp
import gc9a01 
from time import sleep_ms

import fonts.arial32px as arial32px
from lib.random_password import generate_random_password
from lib.wifi_web_service import derive_device_password
from lib.uQR import QRCode, QRData, MODE_8BIT_BYTE
from lib.dns import MicroDNSSrv
from lib.microdot import Microdot, Response, send_file, with_form_data
from lib.microdot.utemplate import Template
import asyncio
import os
import json

from lib.smart_config import BoolDropdownConfig, ColorConfig, EnumConfig

def hex_to_rgb565(hex_color: str) -> int:
    hex_color = hex_color.lower().lstrip('#')
    if len(hex_color) != 6:
        raise ValueError("Input must be a 6-digit hex colour in RRGGBB format")

    # Split into 8-bit RGB components
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # Pack into 5-6-5 bits: RRRR R GGGGGG BBBB B
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return rgb565

def rgb565_to_hex(rgb565: int) -> str:
    if not (0 <= rgb565 <= 0xFFFF):
        raise ValueError("Value must be in the range 0x0000–0xFFFF")

    # Extract 5-6-5 bit fields
    r5 = (rgb565 >> 11) & 0x1F       # 5 bits for red
    g6 = (rgb565 >> 5)  & 0x3F       # 6 bits for green
    b5 =  rgb565        & 0x1F       # 5 bits for blue

    # Expand to 8-bit channels:
    # 5-bit -> 8-bit: replicate the high 5 bits (<<3) and copy top 3 again (>>2)
    # 6-bit -> 8-bit: replicate the high 6 bits (<<2) and copy top 2 again (>>4)
    r8 = (r5 << 3) | (r5 >> 2)
    g8 = (g6 << 2) | (g6 >> 4)
    b8 = (b5 << 3) | (b5 >> 2)

    return f'#{r8:02X}{g8:02X}{b8:02X}'

class App(BaseApp):
    name = "WiFi Settings"
    def __init__(self, controller):
        super().__init__(controller)
        self.display1 = self.controller.bsp.displays.display1
        self.display2 = self.controller.bsp.displays.display2

        self.bg_color = gc9a01.WHITE
        self.fg_color = gc9a01.BLACK
        
        self.font = arial32px

        self.center = self.display1.width() // 2

        self.display1.fill(gc9a01.WHITE)
        self.display2.fill(gc9a01.WHITE)
        # Derive the badge id deterministically from the device's unique id so
        # the hotspot SSID is stable across reboots (no re-pairing each boot).
        self.badge_id = derive_device_password(prefix='', salt='badge', length=8)

        self.config['test_config_var'] = 'test'
        self.config.add('test_bool_config', BoolDropdownConfig('Test Bool Config', True))
        self.config.add('test_color_config', ColorConfig('Test Color Config', gc9a01.BLACK))
        self.config.add('test_enum_config', EnumConfig('Test Enum Config', ['Option 1', 'Option 2', 'Option 3'], 'Option 1'))

        self.draw_status()

        # Hosting the hotspot/website must outlive the idle-sleep timeout. The
        # sleep service light-sleeps the badge (~2 min default), which tears down
        # WiFi and never restarts it, so the AP silently disappears. This app
        # configures OTHER apps over the web UI, so the hotspot has to keep
        # serving even after you navigate away from this screen -- so sleep is
        # disabled here and intentionally left disabled (it returns to its
        # configured default on the next reboot). It is deliberately NOT restored
        # on teardown: that would let the badge sleep and kill the live hotspot.
        self._inhibit_sleep()
        # An active BLE scan shares the radio with WiFi and starves it enough
        # that DHCP replies get dropped, so clients associate but never get an
        # IP ("IP configuration failure"). Pause scanning while hosting; like
        # sleep, it is intentionally not resumed on teardown so the hotspot keeps
        # serving new clients after you leave this screen.
        self._pause_ble_scan()

        try: # no os.path.exists function
            wifi_file = open('wifi.json')
        except OSError:
            ap = True
        else:
            ap = False

        if not ap:
            wifi_file = open('wifi.json')
            wifi_config = json.loads(wifi_file.read())
            wifi_file.close()
            self.ssid = wifi_config['essid']
            self.password = wifi_config['password']

        # TODO start random password generation and QRCode generation
        # on a thread and mark loading until complete
        if ap:
            # Deterministic password too, so the SSID *and* passphrase are stable
            # across reboots and the QR/printed credentials stay valid.
            self.password = derive_device_password(prefix='', salt='wifi', length=12)
            self.ssid = f'Badge {self.badge_id}'

        self.start_wifi(self.ssid, self.password, ap=ap)

        asyncio.create_task(self.start_website())

        print(f"Pre-fill, SSID is \"{self.ssid}\", password is {self.password}")

        # Only show QR code for AP mode, show network info for normal WiFi
        if ap:
            qr_data = QRData(f'WIFI:S:{self.ssid};T:WPA;P:{self.password};H:false;;'.encode(), mode=MODE_8BIT_BYTE)
            self.qr = QRCode()
            self.qr.add_data(qr_data) # WiFi QR code
            
            while self.qr is None:
                sleep_ms(10)
            
            matrix = self.qr.get_matrix()
            if matrix is None or matrix[0] is None:
                self.draw_status("Error Generating")
                return
            
            self.display1.fill(gc9a01.WHITE)

            for y, row in enumerate(matrix):
                for x, value in enumerate(row): # type: ignore
                    if value:
                        # TODO calculate width and height and scale?
                        self.display1.fill_rect(15+x*5, 15+y*5, 5, 5, gc9a01.BLACK)
        else:
            # For normal WiFi connections, display network information
            self.display_network_info()

    def _pause_ble_scan(self):
        """Stop BLE scanning so it stops starving WiFi/DHCP of radio time."""
        try:
            ble = self.controller.bsp.bluetooth.ble
            if ble.active():
                ble.gap_scan(None)
        except Exception:
            pass

    def _inhibit_sleep(self):
        """Disable idle-sleep so the hotspot/website keeps serving.

        Intentionally not restored on teardown: the web config UI is used after
        leaving this screen, and re-enabling sleep would let the badge drop the
        live hotspot. Sleep returns to its configured default on the next reboot.
        """
        sleep_service = getattr(self.controller, 'sleep_service', None)
        if sleep_service is None:
            return
        cfg = sleep_service.config.get('enabled')
        if cfg is not None:
            cfg['current'] = 'False'

    def start_wifi(self, essid, password, ap=True):
        import network

        if ap:
            ap = network.WLAN(network.AP_IF)
            # Start from a clean slate; a stale AP/DHCP state stops leases.
            ap.active(False)
            sleep_ms(300)
            ap.active(True)
            ap.config(essid=essid, authmode=network.AUTH_WPA2_PSK,
                      password=password, channel=6, hidden=False)

            while not ap.active():
                sleep_ms(10)

            # Let the AP settle, then explicitly assert the gateway + DNS as the
            # AP's own IP. On this firmware the DHCP server only hands out usable
            # leases when ifconfig is set this way (clients otherwise fail to get
            # an IP / show "IP configuration error").
            sleep_ms(600)
            ap_ip = ap.ifconfig()[0]
            ap.ifconfig((ap_ip, '255.255.255.0', ap_ip, ap_ip))
            sleep_ms(100)

            MicroDNSSrv.Create({ '*' : ap.ifconfig()[0] })

            if_config = ap.ifconfig()
        
        else:
            sta_if = network.WLAN(network.STA_IF)
            sta_if.active(True)
            sta_if.connect(essid, password)

            while not sta_if.isconnected():
                sleep_ms(10)
        
            MicroDNSSrv.Create({ '*' : sta_if.ifconfig()[0] })

            if_config = sta_if.ifconfig()
        
        ip = if_config[0] if if_config and len(if_config) > 0 else 'Not Connected'

        self.controller.bsp.displays.display_center_text(
            ip,
            fg=gc9a01.BLACK,
            bg=gc9a01.WHITE,
            display_index=2
        )
    
    async def start_website(self):
        try:
            app = Microdot()

            Template.initialize('website/templates')

            Response.default_content_type = 'text/html'

            @app.route('/static/<path:path>')
            async def static(request, path):
                if '..' in path:
                    # directory traversal
                    return 'Not found', 404
                return send_file('/website/static/' + path, max_age=86400)

            @app.route('/')
            async def home(request):
                return Template('home.html').render(
                    path='/',
                    badge_id=self.badge_id,
                    battery_voltage=str(self.controller.battery.mv_average.average()/100) + 'v',
                    battery_percentage='{}%'.format(self.controller.battery.get_battery_percentage()),
                    current_app=self.controller.current_view.name if self.controller.current_view else 'None',
                )



            @app.get('/add_app')
            async def add_app(request):
                # Get list of existing app files
                apps = [f[:-3] for f in os.listdir('apps') if f.endswith('.py') and f != '__init__.py']
                return Template('add_app.html').render(
                    path='/add_app',
                    apps=apps
                )

            @app.get('/get_app_code')
            async def get_app_code(request):
                app_name = request.args.get('app_name')
                if app_name:
                    try:
                        with open(f'apps/{app_name}.py', 'r') as f:
                            return f.read()
                    except Exception:
                        return 'Error: App not found', 404
                return 'Error: No app specified', 400

            @app.post('/add_app/submit')
            @with_form_data
            async def handle_add_app(request):
                app_name = request.form['app_name']
                app_code = request.form['app_code']

                # Save the new app file
                with open(f'apps/{app_name}.py', 'w') as f:
                    f.write(app_code)
                
                return Response.redirect('/add_app')

            @app.get('/config')
            async def config(request):
                return Template('config.html').render(
                    path='/config',
                    rgb565_to_hex=rgb565_to_hex,
                    app_configs=self.controller.app_configs.items(),
                    service_configs=self.controller.service_configs.items(),
                    system_config=self.controller.system_config.config
                )
            
            
            @app.post('/config/update')
            @with_form_data
            async def update_config(request):
                config_type = request.form.get('configType', 'app')
                
                if config_type == 'system':
                    # Handle system configuration updates
                    system_config = self.controller.system_config.config
                    for config_name, value in request.form.items():
                        if config_name in ['configType']:  # Skip form metadata
                            continue
                        if config_name not in system_config:
                            print(f"Skipping unknown system config: {config_name}")
                            continue
                        
                        existing_config = system_config[config_name]
                        print(f"Updating system config: {config_name} = {value}")
                        self._update_config_value(existing_config, value)
                            
                elif config_type == 'service':
                    # Handle service configuration updates
                    service_name = request.form.get('serviceSelection')
                    if service_name and service_name in self.controller.service_configs:
                        service_config = self.controller.service_configs[service_name]
                        for config_name, value in request.form.items():
                            if config_name in ['configType', 'serviceSelection']:  # Skip form metadata
                                continue
                            if config_name not in service_config:
                                print(f"Skipping unknown config: {config_name} for service {service_name}")
                                continue
                            
                            existing_config = service_config[config_name]
                            print(f"Updating {service_name} service config: {config_name} = {value}")
                            self._update_config_value(existing_config, value)
                            
                else:
                    # Handle app configuration updates (existing logic)
                    app = request.form['appSelection']
                    app_config = self.controller.app_configs[app]
                    for config_name, value in request.form.items():
                        if config_name in ['configType', 'appSelection']:  # Skip form metadata
                            continue
                        if config_name not in app_config:
                            print(f"Skipping unknown config: {config_name} for app {app}")
                            continue
                        
                        existing_config = app_config[config_name]
                        print(f"Updating {app} config: {config_name} = {value}")
                        self._update_config_value(existing_config, value)

                return Response.redirect('/config')
            
            print("Microdot: Starting web server on 192.168.4.1:80")
            await app.start_server(host='0.0.0.0', port=80)
        except Exception as e:
            print(f"Error starting web server: {e}")
            import traceback
            traceback.print_exc()
            return
        
    def _update_config_value(self, existing_config, value):
        """Helper method to update config values based on their type."""
        existing_type = type(existing_config)
        if existing_type is not str and existing_type is not int and 'type' in existing_config:
            existing_config_type = existing_config['type']
            # Convert value
            if existing_config_type == 'BoolDropdownConfig':
                value = True if len(str(value)) == 2 else False
            else:
                value = value[0] if isinstance(value, list) else value
            if existing_config_type == 'BoolDropdownConfig':
                existing_config['current'] = value
            elif existing_config_type == 'EnumConfig':
                existing_config['current'] = value
            elif existing_config_type == 'ColorConfig':
                existing_config['current'] = hex_to_rgb565(str(value))
            elif existing_config_type == 'RangeConfig':
                existing_config['current'] = int(value)
        elif existing_type is str:
            existing_config = str(value[0] if isinstance(value, list) else value)
        elif existing_type is int:
            try:
                existing_config = int(value[0] if isinstance(value, list) else value)
            except ValueError:
                pass
        else:
            print(f"Unknown config type: {existing_type}")


    def display_network_info(self):
        """Display network connection information instead of QR code"""
        self.display1.fill(gc9a01.WHITE)
        
        # Display WiFi network name
        self.display1.write(
            self.font,
            'Connected to:',
            10,
            30,
            gc9a01.BLACK,
            gc9a01.WHITE
        )
        
        # Display SSID (truncate if too long)
        ssid_display = self.ssid[:15] + '...' if len(self.ssid) > 15 else self.ssid
        self.display1.write(
            self.font,
            ssid_display,
            10,
            70,
            gc9a01.BLACK,
            gc9a01.WHITE
        )
        
        # Display connection status
        self.display1.write(
            self.font,
            'Status: Active',
            10,
            110,
            gc9a01.BLACK,
            gc9a01.WHITE
        )
        
        # Display web interface info
        self.display1.write(
            self.font,
            'Web Config:',
            10,
            150,
            gc9a01.BLACK,
            gc9a01.WHITE
        )
        
        self.display1.write(
            self.font,
            'See IP below',
            10,
            190,
            gc9a01.BLACK,
            gc9a01.WHITE
        )

    def draw_status(self, status: str = 'Loading...'):
        self.display1.write(
            self.font,
            'Loading...',
            10,
            100,
            gc9a01.BLACK,
            gc9a01.WHITE
        )


if __name__ == "__main__":
    from single_app_runner import run_app
    run_app(App, perf=True)
