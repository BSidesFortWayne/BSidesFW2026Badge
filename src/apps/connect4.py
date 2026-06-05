import apps.app
import gc9a01
import machine
import micropython
import time
import framebuf
import asyncio
from lib.microfont import MicroFont
from ui.theme import FONT_BODY, SAFE_X, SAFE_WIDTH
from ui.menu import TextMenuWidget
import bluetooth
import lib.aioble as aioble
from lib.smart_config import (
    RangeConfig, ColorConfig, EnumConfig, BoolDropdownConfig, Config
)
import os

class Grid:
    def __init__(self, app, width, height):
        self.app = app
        self.config = self.app.config
        self.fbuf = self.app.display1.fbuf
        self.displays = self.app.controller.displays

        self.width = width
        self.height = height
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height+1)]
        self.grid_line_color = self.app.grid_line_color
    
    def add_config_values(app):
        app.config.add('grid_cell_spacing', 22)
        app.config.add('grid_x_offset', 45)
        app.config.add('grid_y_offset', 60)
        app.config.add('grid_line_thickness', 2)
        app.config.add('grid_disc_radius', 8)
        app.grid_line_color = app.config.add('grid_line_color', ColorConfig('Grid Line Color', app.controller.displays.COLOR_LOOKUP['fbuf']['white']))

    def draw_hline(self, x, y, w):
        self.fbuf.rect(
            x,
            y,
            w,
            self.config['grid_line_thickness'],
            self.grid_line_color.value(),
            True
        )

    def draw_vline(self, x, y, h):
        self.fbuf.rect(
            x,
            y,
            self.config['grid_line_thickness'],
            h,
            self.grid_line_color.value(),
            True
        )

    def draw_grid(self):
        # border
        self.fbuf.rect(
            self.config['grid_x_offset'] - self.config['grid_line_thickness'],
            self.config['grid_y_offset'] - self.config['grid_line_thickness'],
            (self.width * self.config['grid_cell_spacing']) + self.config['grid_line_thickness']*2,
            (self.height * self.config['grid_cell_spacing']) + self.config['grid_line_thickness']*2,
            self.grid_line_color.value(),
            True
        )

        self.fbuf.rect(
            self.config['grid_x_offset'],
            self.config['grid_y_offset'],
            (self.width * self.config['grid_cell_spacing']),
            (self.height * self.config['grid_cell_spacing']),
            self.app.bg_color.value(),
            True
        )


        for x in range(self.width):
            if x == 0:
                continue

            self.draw_vline(
                self.config['grid_x_offset'] + (x * self.config['grid_cell_spacing']),
                self.config['grid_y_offset'],
                (self.config['grid_cell_spacing'] * self.height)
            )
        
        for y in range(self.height):
            if y == 0:
                continue

            self.draw_hline(
                self.config['grid_x_offset'],
                self.config['grid_y_offset'] + (y * self.config['grid_cell_spacing']),
                (self.config['grid_cell_spacing'] * self.width)
            )
    
    def draw_disc(self, x, y, color):
        self.fbuf.ellipse(
            int((self.config['grid_x_offset'] + ((x * self.config['grid_cell_spacing']) - (self.config['grid_cell_spacing'] / 2))) + self.config['grid_cell_spacing']),
            int((self.config['grid_y_offset'] + ((y * self.config['grid_cell_spacing']) - (self.config['grid_cell_spacing'] / 2)))),
            int(self.config['grid_disc_radius']),
            int(self.config['grid_disc_radius']),
            color,
            True
        )

    def draw_discs(self):
        for y in range(self.height+1):
            for x in range(self.width):
                if (self.grid[y][x] == 0):
                    self.draw_disc(x, y, self.app.bg_color.value())
                elif (self.grid[y][x] == 1):
                    self.draw_disc(x, y, self.config['player1_color'].value())
                elif (self.grid[y][x] == 2):
                    self.draw_disc(x, y, self.config['player2_color'].value())

class Game:
    def __init__(self, app):
        self.app = app
        self.grid = Grid(app, self.app.config['width'], self.app.config['height'])
        self.height = self.grid.height
        self.width = self.grid.width

        self.turn = 1
        self.turn_number = 1
        self.player_position = 0
        self.grid.grid[0][0] = 1
    
    def update(self):
        self.grid.draw_grid()
        self.grid.draw_discs()

    def button_press(self, button, player):
        if player == self.turn or player == None:
            if button == 4:
                self.grid.grid[0][self.player_position] = 0
                if self.player_position >= self.width-1:
                    self.player_position = -1
                self.player_position += 1
                self.grid.grid[0][self.player_position] = self.turn

            elif button == 5:
                self.grid.grid[0][self.player_position] = 0
                if self.player_position <= 0:
                    self.player_position = self.width
                self.player_position -= 1
                self.grid.grid[0][self.player_position] = self.turn
            
            elif button == 6:
                self.next_turn()
    
    def find_lines(self):
        grid = []
        for y in range(self.height+1):
            if y == 0:
                continue
            grid.append(self.grid.grid[y])
        
        if not grid or not grid[0]:
            return []

        rows, cols = len(grid), len(grid[0])
        # right, down, down-right, down-left
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        found = []

        for r in range(rows):
            for c in range(cols):
                value = grid[r][c]
                if value == 0:
                    continue
                for dr, dc in directions:
                    pr, pc = r - dr, c - dc
                    if 0 <= pr < rows and 0 <= pc < cols and grid[pr][pc] == value:
                        continue

                    line = []
                    nr, nc = r, c
                    while 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == value:
                        line.append((nr, nc))
                        nr, nc = nr + dr, nc + dc

                    if len(line) >= 4:
                        found.append((value, line))

        return found

    def check_for_win(self):
        lines = self.find_lines()
        for line in lines:
            self.app.winner = line[0]
            self.app.winner_screen = True
            print(f'Player {self.app.winner} won!')
            break

    def next_turn(self):
        for y in range(1, self.height+1):
            if not self.grid.grid[y][self.player_position] == 0:
                y -= 1
                break
        
        if y == 0:
            return

        self.grid.grid[y][self.player_position] = self.turn
        
        self.check_for_win()

        if not self.app.winner == None:
            self.grid.grid[0][self.player_position] = 0
            self.app.game_running = False
            return

        self.turn_number += 1
        if self.turn == 1:
            self.turn = 2
        else:
            self.turn = 1
        
        self.grid.grid[0][self.player_position] = 0
        self.player_position = 0
        self.grid.grid[0][self.player_position] = self.turn

class FramebufferDisplay:
    def __init__(self, display, width, height):
        self.display = display
        self.width = width
        self.height = height
        self.fbuf_mem = bytearray(self.width * self.height * 2)
        self.fbuf_mv = memoryview(self.fbuf_mem)
        self.fbuf = framebuf.FrameBuffer(
            self.fbuf_mem, width, height, framebuf.RGB565
        )

        self.font = MicroFont(FONT_BODY, cache_index=True, cache_chars=True)
    
    def update(self):
        self.display.blit_buffer(self.fbuf_mv, 0, 0, 240, 240)
    
    def draw_text(self, text, x, y, color):
        self.font.write(
            text,
            self.fbuf_mv,
            framebuf.RGB565,
            self.width,
            self.height,
            x, y,
            color
        )

    def draw_text_centered(self, text, y, color):
        w, _ = self.font.measure(text)
        x = max(0, (self.width - w) // 2)
        self.draw_text(text, x, y, color)

class Bluetooth:
    _SERVICE_UUID = bluetooth.UUID("a3c87500-8ed3-4bdf-8a39-a01bebede295")
    _CHAL_UUID    = bluetooth.UUID("a3c87502-8ed3-4bdf-8a39-a01bebede295")
    _MFG_ID = 0xABCD
    _MAGIC  = b"BG"
    _ADV_INTERVAL_US = 200_000
    _SCAN_MS         = 3000
    _ENTRY_TTL_MS    = 8000
    _PROTO = 1

    NO_CHALLENGE = 0
    CHALLENGING = 1

    DECLINE_REMATCH = -1
    ACCEPT_REMATCH = -2

    def __init__(self, app, identifier):
        self.identifier = identifier
        self.nearby = {}
        self.state = "IDLE"
        self.app = app
        self.active_connection = None
        self.challenger = ""
        self.message_to_show = ""
        self.challenge_state = Bluetooth.NO_CHALLENGE
        self.running = True
        self.opponent_rematching = False
        self.rematching = False

        self._service = aioble.Service(Bluetooth._SERVICE_UUID)
        self._chal = aioble.Characteristic(
            self._service, Bluetooth._CHAL_UUID, write=True, notify=True, capture=True
        )
    
    def _prune(self):
        now = time.ticks_ms()
        for addr in list(self.nearby):
            if time.ticks_diff(now, self.nearby[addr]["seen"]) > Bluetooth._ENTRY_TTL_MS:
                del self.nearby[addr]

    async def accept(self):
        self._chal.notify(self.active_connection, b'ACCEPT')
        asyncio.create_task(self.receive_game_data())
        self.app.start_new_game()
        self.app._dirty = True
    
    async def decline(self):
        self._chal.notify(self.active_connection, b'DECLINE')
        self.exit_game()
        await self.active_connection.disconnect()
        self.state = "IDLE"
        self.app._dirty = True
    
    def send_game_data(self, message):
        conn = self.active_connection
        if conn is not None and conn.is_connected():
            try:
                self._chal.notify(conn, b'GAME:' + message.encode())
                return True
            except Exception as e:
                print('send_game_data failed: ' + str(e))
        # Opponent is gone — surface it instead of crashing
        if self.state != "IDLE":
            asyncio.create_task(self.disconnected(message='Opponent left'))
        return False
    
    async def receive_game_data(self):
        try:
            while self.running:
                answer = await self.chal.notified()
                answer = answer.decode('utf-8')
                print(f'Received data: ' + answer)
                if answer.startswith('GAME:'):
                    answer = int(answer[5:])
                    if self.app.player == 1:
                        player = 2
                    else:
                        player = 1
                    
                    if answer == Bluetooth.DECLINE_REMATCH:
                        await self.disconnected(message='Declined')
                        break
                    elif answer == Bluetooth.ACCEPT_REMATCH:
                        self.opponent_rematching = True
                        if self.rematching:
                            self._start_rematch()
                        self.app._dirty = True
                        continue

                    self.app.game.button_press(answer, player)
                    self.app._dirty = True
        except OSError as e:
            if e.errno == -128 and not self.state == "IDLE":
                await self.disconnected()
        except Exception as e:
            if not self.state == "IDLE":
                await self.disconnected()
            else:
                print("receive_game_data_task exited: " + str(e))

    async def disconnected(self, message=None):
        if message == None:
            message = "Lost connection"
        print(message)
        self.state = "IDLE"
        self.challenge_state = Bluetooth.CHALLENGING
        self.app.game_running = False
        self.app.on_menu = False
        self.show_message(message)
        self.app.exit_to_menu_next_press = True
        self.app._dirty = True
        try:
            await self.active_connection.disconnect()
        except:
            pass

    def request_rematch(self):
        if not self.send_game_data(str(Bluetooth.ACCEPT_REMATCH)):
            # Opponent already left — return to matchmaking instead of blanking
            self.exit_game()
            return
        if self.opponent_rematching:
            self._start_rematch()
        else:
            self.rematching = True
            self.challenge_state = Bluetooth.CHALLENGING
            self.show_message('Waiting...')

    def _start_rematch(self):
        self.rematching = False
        self.opponent_rematching = False
        self.challenge_state = Bluetooth.NO_CHALLENGE
        self.app.start_new_game()
        self.app._dirty = True

    def exit_game(self):
        self.state = "IDLE"
        self.challenge_state = Bluetooth.NO_CHALLENGE
        self.app.on_menu = True
        self.app.game_running = False
        self.app.menu_stage = App.MATCHMAKING_MENU
        self.app._dirty = True

    def show_message(self, message):
        self.message_to_show = message
        self.app._dirty = True
    
    async def challenge(self, entry):
        self.state = "BUSY"
        self.challenge_state = Bluetooth.CHALLENGING
        self.show_message('Connecting...')
        for attempt in range(1, 11):
            entry['device']._connection = None
            try:
                self.active_connection = await entry['device'].connect(timeout_ms=5000)
            except (asyncio.TimeoutError, OSError):
                print(f'Connect failed, retrying {attempt}/10')
                await asyncio.sleep_ms(300)
                continue

            self.opponent = entry

            try:
                if not self.active_connection.is_connected():
                    print(f'Connection dropped before discovery, retrying {attempt}/10')
                    await asyncio.sleep_ms(300)
                    continue
                self.service = await self.active_connection.service(Bluetooth._SERVICE_UUID)
                self.chal = (
                    await self.service.characteristic(Bluetooth._CHAL_UUID)
                    if self.service else None
                )
                if self.chal is None:
                    print(f'Service not ready, retrying {attempt}/10')
                    try:
                        await self.active_connection.disconnect()
                    except:
                        pass
                    await asyncio.sleep_ms(300)
                    continue
                await self.chal.subscribe(notify=True)
                await self.chal.write(b"CHAL:" + self.identifier.encode(), response=True)
                self.show_message('Waiting...')
                answer = await self.chal.notified(timeout_ms=30_000)

            except asyncio.TimeoutError:
                await self.disconnected(message="No answer")
                return

            except OSError as e:
                if e.errno == -128:
                    print(f'Connection dropped, retrying {attempt}/10')
                    try:
                        await self.active_connection.disconnect()
                    except:
                        pass
                    await asyncio.sleep_ms(300)
                    continue
                raise

            except TypeError:
                print(f'Connection dropped during discovery, retrying {attempt}/10')
                try:
                    await self.active_connection.disconnect()
                except:
                    pass
                await asyncio.sleep_ms(300)
                continue

            else:
                if answer == b'ACCEPT':
                    self.app.player = 1
                    self.app.start_new_game()
                    asyncio.create_task(self.receive_game_data())
                    self.app._dirty = True
                else:
                    await self.disconnected(message="Declined")
                return

        await self.disconnected(message="Could not connect")


    async def _handle_incoming(self, connection):
        self.state = "BUSY"
        self.active_connection = connection
        try:
            self.service = await self.active_connection.service(Bluetooth._SERVICE_UUID)
            self.chal = (
                await self.service.characteristic(Bluetooth._CHAL_UUID)
                if self.service else None
            )
            if self.chal is None:
                print('Incoming peer service not found')
                await connection.disconnect()
                self.state = "IDLE"
                return
            await self.chal.subscribe(notify=True)
            _, data = await self._chal.written(timeout_ms=10_000)
            if data.startswith(b"CHAL:"):
                self.challenger = data[5:].decode()
                self.app.switch_to_menu(App.CHALLENGE_MENU)
                self.app._dirty = True
        except asyncio.TimeoutError:
            await connection.disconnect()
            self.state = "IDLE"

    async def advertise_task(self):
        while self.running:
            if self.state != "IDLE":
                await asyncio.sleep_ms(300)
                continue
            try:
                connection = await aioble.advertise(
                    Bluetooth._ADV_INTERVAL_US,
                    name=self.identifier,
                    manufacturer=(Bluetooth._MFG_ID, Bluetooth._MAGIC + bytes([Bluetooth._PROTO])),
                    timeout_ms=2000,
                )
            except asyncio.TimeoutError:
                continue
            await self._handle_incoming(connection)
    
    async def scanner_task(self):
        while self.running:
            if self.state != "IDLE":
                await asyncio.sleep_ms(300)
                continue
            async with aioble.scan(
                Bluetooth._SCAN_MS, interval_us=30_000, window_us=20_000, active=True
            ) as scanner:
                async for r in scanner:
                    for code, data in r.manufacturer():
                        if code == Bluetooth._MFG_ID and data[:2] == Bluetooth._MAGIC:
                            self.nearby[r.device.addr] = {
                                "device": r.device,
                                "addr": r.device.addr,
                                "handle": r.name() or "?",
                                "rssi": r.rssi,
                                "seen": time.ticks_ms(),
                            }

                            break
            self._prune()
            print(self.nearby)
            if self.app.menu_stage == App.MATCHMAKING_MENU:
                items = ['> Back']
                for addr, device in self.nearby.items():
                    items.append(device['handle'])
                self.app.menu.items = items
                if self.app.menu.selected_index >= len(self.app.menu.items):
                    self.app.menu.selected_index = len(self.app.menu.items) - 1
                self.app._dirty = True
            await asyncio.sleep_ms(200)

    async def start(self):
        self.app.controller.bsp.bluetooth.ble.active(False)
        aioble.register_services(self._service)
        asyncio.create_task(self.scanner_task())
        asyncio.create_task(self.advertise_task())

class App(apps.app.BaseApp):
    name = "Connect Four"
    version = "0.0.1"

    LOCAL_MULTIPLAYER_MENU = 0
    MATCHMAKING_MENU = 1
    TRY_AGAIN_MENU = 2
    CHALLENGE_MENU = 3

    MENU = [
        [ # LOCAL_MULTIPLAYER_MENU
            "Local",
            "Multiplayer"
        ],
        [ # MATCHMAKING_MENU
            "> Back"
        ],
        [ # TRY_AGAIN_MENU
            "Yes",
            "No"
        ],
        [ # CHALLENGE_MENU
            "Accept",
            "Decline"
        ]
    ]

    def __init__(self, controller: apps.app.IController):
        super().__init__(controller)
        self.display1 = FramebufferDisplay(self.controller.bsp.displays.display1, 240, 240)
        self.display2 = FramebufferDisplay(self.controller.bsp.displays.display2, 240, 240)

        self.bg_color = self.config.add('bg_color', ColorConfig('Background Color', self.controller.displays.COLOR_LOOKUP['fbuf']['black']))
        self.fg_color = self.config.add('fg_color', ColorConfig('Foreground Color', self.controller.displays.COLOR_LOOKUP['fbuf']['white']))
        self.player1_color = self.config.add('player1_color', ColorConfig('Player 1 Color', self.controller.displays.COLOR_LOOKUP['fbuf']['red']))
        self.player2_color = self.config.add('player2_color', ColorConfig('Player 2 Color', self.controller.displays.COLOR_LOOKUP['fbuf']['yellow']))

        self.display1.fbuf.fill(self.bg_color.value())
        self.display2.fbuf.fill(self.bg_color.value())

        self.display1.update()
        self.display2.update()

        Grid.add_config_values(self)

        self.config.add('height', 6)
        self.config.add('width', 7)

        try:
            self.badge_app_config = Config('config/apps/Badge.json')
            self.ble_identifier = self.badge_app_config['first_name'] + ' ' + self.badge_app_config['last_name']

            if self.ble_identifier == 'WhatAbout Bob':
                raise Exception('generic name')
        except:
            self.ble_identifier = 'badge-' + machine.unique_id()[-2:].hex().upper()

        print(f'Using BLE identifier: {self.ble_identifier}')

        self.game_running = False
        self.winner = None
        self.winner_screen = False
        self.start_game_next_press = False
        self.exit_to_menu_next_press = False
        self._dirty = True

        self.menu_stage = App.LOCAL_MULTIPLAYER_MENU
        self.menu = self.menu = TextMenuWidget(
            ["Local", "Multiplayer"],
            width=SAFE_WIDTH,
            visible_items=5,
            center=True,
            buffer=self.display2.fbuf_mv,
            on_select=self.on_menu_select,
        )
        self.on_menu = True
        self.player = None

        if not self.controller.isSimulator:
            self.bluetooth = Bluetooth(self, self.ble_identifier)
        else:
            print('Running in simulator, not using BLE')
    
    async def setup(self):
        if not self.bluetooth == None:
            await self.bluetooth.start()

    def switch_to_menu(self, menu_stage):
        print(f'Switching to menu {menu_stage}')
        self.menu_stage = menu_stage
        self.on_menu = True
        self.menu.items = App.MENU[menu_stage]
        self.menu.selected_index = 0

    def on_menu_select(self, path, value):
        if self.menu_stage == App.LOCAL_MULTIPLAYER_MENU:
            if value == "Local":
                self.on_menu = False
                self.player = None
                self.start_new_game()
            elif value == "Multiplayer":
                self.local = False
                self.switch_to_menu(App.MATCHMAKING_MENU)
        elif self.menu_stage == App.MATCHMAKING_MENU:
            if value == '> Back':
                self.switch_to_menu(App.LOCAL_MULTIPLAYER_MENU)
            else:
                for addr, entry in self.bluetooth.nearby.items():
                    if entry['handle'] == value:
                        self.on_menu = False
                        self.bluetooth.challenge_state = Bluetooth.CHALLENGING
                        self.bluetooth.show_message('Connecting...')
                        asyncio.create_task(self.bluetooth.challenge(entry))
        elif self.menu_stage == App.TRY_AGAIN_MENU:
            if value == "Yes":
                self.on_menu = False
                if self.player == None:
                    self.start_new_game()
                else:
                    self.bluetooth.request_rematch()
            elif value == "No":
                if self.player != None:
                    self.bluetooth.send_game_data(str(Bluetooth.DECLINE_REMATCH))
                asyncio.create_task(self.controller.switch_app("Menu"))
        elif self.menu_stage == App.CHALLENGE_MENU:
            if value == "Accept":
                self.on_menu = False
                self.player = 2
                asyncio.create_task(self.bluetooth.accept())
            elif value == "Decline":
                asyncio.create_task(self.bluetooth.decline())
                self.switch_to_menu(App.MATCHMAKING_MENU)
                self.exit_to_menu_next_press = True

    def start_new_game(self):
        self.game = Game(self)
        self.game_running = True

    def _player_name(self, player_num):
        if self.player is None:
            return f'Player {player_num}'
        if player_num == self.player:
            return self.ble_identifier
        if self.bluetooth.challenger:
            return self.bluetooth.challenger
        opponent = getattr(self.bluetooth, 'opponent', None)
        if opponent:
            return opponent.get('handle', f'Player {player_num}')
        return f'Player {player_num}'

    def _winner_name(self):
        return self._player_name(self.winner)

    def _opponent_rssi(self):
        if self.player is None:
            return None
        bt = self.bluetooth
        opponent = getattr(bt, 'opponent', None)
        if opponent and 'rssi' in opponent:
            return opponent['rssi']
        if bt.challenger:
            for entry in bt.nearby.values():
                if entry['handle'] == bt.challenger:
                    return entry['rssi']
        return None

    def _draw_game_hud(self):
        d = self.display2
        fg = self.fg_color.value()
        d.draw_text_centered(f'Turn {self.game.turn_number}', 15, fg)

        turn_color = (
            self.player1_color.value() if self.game.turn == 1
            else self.player2_color.value()
        )
        d.draw_text_centered(self._player_name(self.game.turn), 100, turn_color)
        d.draw_text_centered('to move', 130, fg)

        rssi = self._opponent_rssi()
        if rssi is not None:
            d.draw_text_centered(f'RSSI {rssi}', 205, fg)

    def button_press(self, button):
        if self.game_running:
            self.game.button_press(button, self.player)
            if not self.player == None:
                self.bluetooth.send_game_data(str(button))
                print('Sent game data')

        if self.on_menu:
            if button == 4:
                self.menu.move_down()
            elif button == 5:
                self.menu.move_up()
            elif button == 6:
                self.menu.select()

        if self.start_game_next_press:
            self.start_game_next_press = False
            self.winner = None
            self.winner_screen = False
            self.switch_to_menu(App.TRY_AGAIN_MENU)
        
        if self.exit_to_menu_next_press:
            self.switch_to_menu(App.MATCHMAKING_MENU)
            self.bluetooth.challenge_state = Bluetooth.NO_CHALLENGE
            self.exit_to_menu_next_press = False

        if not self.winner == None and self.winner_screen:
            self.start_game_next_press = True
        
        self._dirty = True

    async def update(self):
        if not self._dirty:
            return

        self.display1.fbuf.fill(self.bg_color.value())
        self.display2.fbuf.fill(self.bg_color.value())

        if self.game_running:
            self.game.update()
            self._draw_game_hud()
        elif self.winner_screen:
            self.display2.draw_text_centered(self._winner_name(), 90, self.fg_color.value())
            self.display2.draw_text_centered('won!', 125, self.fg_color.value())
            self.game.update()
        elif self.on_menu:
            if self.menu_stage == App.TRY_AGAIN_MENU:
                self.display1.draw_text(f'Try again?', 30, 100, self.fg_color.value())
            self.menu.render(SAFE_X, 30, self.display2.fbuf, self.display2.width, self.display2.height)
        elif self.bluetooth.challenge_state == Bluetooth.CHALLENGING:
            self.display2.draw_text(self.bluetooth.message_to_show, 30, 100, self.fg_color.value())
        else:
            # Transient state between transitions — render the current menu rather than a blank
            # frame, but don't mutate navigation state (that can hijack an in-progress challenge/accept)
            self.menu.render(SAFE_X, 30, self.display2.fbuf, self.display2.width, self.display2.height)
        self.display1.update()
        self.display2.update()
        self._dirty = False

    async def teardown(self):
        self.bluetooth.running = False
        self.controller.bsp.bluetooth.ble.active(True)
