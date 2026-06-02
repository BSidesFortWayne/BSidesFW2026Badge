import asyncio
import time
import json

import machine
import vga2_8x16

import badgechal
from apps.app import BaseApp
from lib.flag_display import display_flag
from lib.uQR import MODE_8BIT_BYTE, QRCode, QRData
from lib.wifi_web_service import WiFiWebService, derive_device_password


BLACK = 0x0000
WHITE = 0xFFFF


class App(BaseApp):
    name = "CTF Challenge 6"
    version = "0.4.1"

    def __init__(self, controller):
        super().__init__(controller)
        self.nonce_hex = ""
        self.payload_hex = ""
        self.ssid = ""
        self.password = ""
        self.ip = "192.168.4.1"
        self.channel = 6
        self.web_port = 80
        self.web = None
        self.pending_flag = None
        self.solved_flag = None
        self.ble_scan_paused = False
        self._last_web_health_ms = 0
        self._vfs = {}
        self._sleep_prev_setting = None
        self._sleep_forced_off = False
        self._sleep_prev_update = None
        self._sleep_prev_sleep = None
        self._new_round()

    def _new_round(self):
        nonce_hex, payload_hex = badgechal.c6_new_round()
        self.nonce_hex = str(nonce_hex)
        self.payload_hex = str(payload_hex)
        uid = machine.unique_id()
        mac_suffix = "{:02X}{:02X}{:02X}".format(uid[-3], uid[-2], uid[-1])
        self.ssid = "BSFW-C6-{}-{}".format(mac_suffix, self.nonce_hex[:4].upper())
        self.password = derive_device_password(prefix="C6", salt="C6", length=10)
        self.channel = 6
        self._build_vfs()

    def _build_vfs(self):
        uptime_hint = "Kernel uptime: {} sec".format(time.ticks_ms() // 1000)
        self._vfs = {
            "/srv/public/status.json": json.dumps(
                {
                    "device_id": "edge-gw-01",
                    "firmware": "v2.7.13",
                    "wifi_mode": "AP",
                    "radio": "nominal",
                    "diag_service": "enabled",
                }
            ),
            "/srv/public/logs/system.log": (
                "INFO boot complete\n"
                "INFO httpd started :80\n"
                "WARN backup path validator: legacy mode\n"
                "{}\n".format(uptime_hint)
            ),
            "/srv/public/help.txt": (
                "Diagnostics reader endpoint:\n"
                "GET /api/fs?path=<relative_file>\n"
                "Examples: status.json, logs/system.log\n"
            ),
        }

    def _wifi_escape(self, s):
        out = []
        for ch in s:
            if ch in ("\\", ";", ",", ":", "\""):
                out.append("\\")
            out.append(ch)
        return "".join(out)

    def _short(self, s, max_len):
        if len(s) <= max_len:
            return s
        if max_len < 4:
            return s[:max_len]
        return s[:max_len - 3] + "..."

    def _portal_url(self):
        if self.web:
            return self.web.url()
        ip = str(self.ip).strip() if self.ip else "192.168.4.1"
        if self.web_port == 80:
            return "http://{}/".format(ip)
        return "http://{}:{}/".format(ip, self.web_port)

    def _center_text(self, displays, display_index, text, y, fg, bg):
        safe_w = 224
        x = 8 + max(0, (safe_w - (len(text) * vga2_8x16.WIDTH)) // 2)
        displays.display_text(text, x, y, fg=fg, bg=bg, display_index=display_index, font=vga2_8x16)

    def _draw_qr(self):
        displays = self.controller.bsp.displays
        d1 = displays.display1
        d2 = displays.display2

        wifi_text = "WIFI:T:WPA;S:{};P:{};H:false;;".format(self._wifi_escape(self.ssid), self._wifi_escape(self.password))
        wifi_qr_data = QRData(wifi_text.encode(), mode=MODE_8BIT_BYTE)
        wifi_qr = QRCode()
        wifi_qr.add_data(wifi_qr_data)
        wifi_matrix = wifi_qr.get_matrix()

        url_text = self._portal_url()
        url_qr_data = QRData(url_text.encode(), mode=MODE_8BIT_BYTE)
        url_qr = QRCode()
        url_qr.add_data(url_qr_data)
        url_matrix = url_qr.get_matrix()

        def draw_matrix(display, matrix, top_pad, bottom_pad):
            if not matrix:
                return
            rows = len(matrix)
            cols = len(matrix[0]) if rows else 0
            avail_w = 224
            avail_h = 240 - top_pad - bottom_pad
            if rows <= 0 or cols <= 0 or avail_h <= 0:
                return
            cell = min(5, max(3, min(avail_w // cols, avail_h // rows)))
            w = cols * cell
            h = rows * cell
            sx = (240 - w) // 2
            sy = top_pad + ((avail_h - h) // 2)
            for y, row in enumerate(matrix):
                for x, value in enumerate(row):
                    if value:
                        display.fill_rect(sx + x * cell, sy + y * cell, cell, cell, BLACK)

        d1.fill(WHITE)
        d2.fill(WHITE)
        self._center_text(displays, 1, "1) JOIN WIFI", 6, BLACK, WHITE)
        self._center_text(displays, 2, "2) OPEN PAGE", 6, BLACK, WHITE)
        draw_matrix(d1, wifi_matrix, 20, 48)
        draw_matrix(d2, url_matrix, 20, 48)
        max_chars = max(6, 224 // vga2_8x16.WIDTH)
        self._center_text(displays, 1, self._short("SSID:" + self.ssid, max_chars), 196, BLACK, WHITE)
        self._center_text(displays, 1, self._short("PASS:" + self.password, max_chars), 214, BLACK, WHITE)
        url_line = self._portal_url()
        self._center_text(displays, 2, self._short("OPEN URL", max_chars), 196, BLACK, WHITE)
        self._center_text(displays, 2, self._short(url_line, max_chars), 214, BLACK, WHITE)

    def _mute_audio(self):
        try:
            spk = self.controller.bsp.speaker
            try:
                spk.stop_song()
            except Exception:
                pass
            try:
                spk.pwm.duty_u16(0)
            except Exception:
                pass
            try:
                spk.pwm.duty(0)
            except Exception:
                pass
        except Exception:
            pass

    def _pause_ble_scan(self):
        self.ble_scan_paused = False
        try:
            ble = self.controller.bsp.bluetooth.ble
            if ble.active():
                ble.gap_scan(None)
                self.ble_scan_paused = True
        except Exception:
            pass

    def _resume_ble_scan(self):
        if not self.ble_scan_paused:
            return
        try:
            self.controller.bsp.bluetooth.ble.gap_scan(0, 30000, 30000)
        except Exception:
            pass
        self.ble_scan_paused = False

    def _disable_badge_sleep(self):
        sleep_ctl = getattr(self.controller, "sleep", None)
        if sleep_ctl is None:
            return
        try:
            cfg = sleep_ctl.config
            self._sleep_prev_setting = cfg.get("sleep_enabled")
            # Use dict.__setitem__ to avoid persisting this to disk config.
            dict.__setitem__(cfg, "sleep_enabled", False)
            sleep_ctl.last_shaken = time.ticks_ms()
            self._sleep_prev_update = getattr(sleep_ctl, "update", None)
            self._sleep_prev_sleep = getattr(sleep_ctl, "sleep", None)

            def _blocked_update(_):
                sleep_ctl.last_shaken = time.ticks_ms()

            def _blocked_sleep():
                sleep_ctl.last_shaken = time.ticks_ms()
                try:
                    sleep_ctl.bsp.displays.disp_en.value(1)
                except Exception:
                    pass

            sleep_ctl.update = _blocked_update
            sleep_ctl.sleep = _blocked_sleep
            self._sleep_forced_off = True
        except Exception:
            self._sleep_prev_setting = None
            self._sleep_forced_off = False
            self._sleep_prev_update = None
            self._sleep_prev_sleep = None

    def _restore_badge_sleep(self):
        if not self._sleep_forced_off:
            return
        sleep_ctl = getattr(self.controller, "sleep", None)
        if sleep_ctl is None:
            self._sleep_forced_off = False
            self._sleep_prev_setting = None
            return
        try:
            if self._sleep_prev_setting is not None:
                dict.__setitem__(sleep_ctl.config, "sleep_enabled", self._sleep_prev_setting)
            if self._sleep_prev_update is not None:
                sleep_ctl.update = self._sleep_prev_update
            if self._sleep_prev_sleep is not None:
                sleep_ctl.sleep = self._sleep_prev_sleep
            sleep_ctl.last_shaken = time.ticks_ms()
        except Exception:
            pass
        self._sleep_forced_off = False
        self._sleep_prev_setting = None
        self._sleep_prev_update = None
        self._sleep_prev_sleep = None

    def _dashboard_html(self, notice="", ok=False):
        notice_html = ""
        if notice:
            bg = "#0f8a3b" if ok else "#b42318"
            notice_html = "<p style='padding:10px;border-radius:8px;background:{};color:white'>{}</p>".format(bg, notice)
        html = """<!doctype html>
<html>
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>IoT Device Dashboard</title>
<style>
body{font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;background:#0b1220;color:#f3f6ff;padding:20px}
main{max-width:980px;margin:0 auto;background:#121d33;padding:20px;border-radius:12px}
h1{margin:0 0 8px 0}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.card{background:#0f172b;border:1px solid #1f2b48;border-radius:10px;padding:12px}
.mono{font-family:ui-monospace,Menlo,Monaco,Consolas,monospace}
input{width:100%;padding:10px;font-size:16px}
button{margin-top:8px;padding:9px 14px;font-size:15px}
a{color:#9ec5ff}
pre{background:#09101f;color:#cde1ff;padding:10px;border-radius:6px;overflow:auto}
</style>
</head>
<body>
<main>
<h1>IoT Management Dashboard</h1>
<p>Device: <b>edge-gw-01</b> | Role: <b>field gateway</b></p>
__NOTICE__
<div class="grid">
  <div class="card">
    <h3>Runtime</h3>
    <pre>{"cpu":"240MHz","wifi":"AP","http":"online"}</pre>
  </div>
  <div class="card">
    <h3>Actions</h3>
    <p><a href="/api/fs?path=status.json">Read status.json</a></p>
    <p><a href="/api/fs?path=logs/system.log">Read system.log</a></p>
    <p><a href="/api/fs?path=help.txt">Read help.txt</a></p>
  </div>
  <div class="card">
    <h3>Diagnostics Reader</h3>
    <form action="/api/fs" method="GET">
      <label>Path</label>
      <input class="mono" name="path" value="status.json" />
      <button type="submit">Read File</button>
    </form>
  </div>
  <div class="card">
    <h3>Challenge Gate</h3>
    <p>Recover the unlock code and submit it.</p>
    <form action=\"/submit\" method=\"GET\">
      <label>Code</label>
      <input class="mono" name=\"code\" maxlength=\"10\" autocomplete=\"off\" required />
      <button type=\"submit\">Submit Code</button>
    </form>
  </div>
</div>
</main>
</body>
</html>"""
        return html.replace("__NOTICE__", notice_html)

    def _normalize_abs_path(self, path):
        parts = []
        for part in path.split("/"):
            if part == "" or part == ".":
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts)

    def _read_diag_path(self, user_path):
        rel = (user_path or "status.json").replace("\\", "/")
        abs_path = self._normalize_abs_path("/srv/public/" + rel)
        data = self._vfs.get(abs_path)
        if data is None:
            c_data = badgechal.c6_fs_read(abs_path)
            if c_data is not None:
                data = str(c_data)
        if data is None:
            return "File not found: {}\n".format(abs_path), 404, {"Content-Type": "text/plain"}
        return data, 200, {"Content-Type": "text/plain"}

    def _submit_code(self, code):
        if self.solved_flag:
            return self._dashboard_html("Challenge already solved.", ok=True)
        if badgechal.c6_check(code):
            flag = badgechal.claim_flag(6)
            if flag:
                self.solved_flag = str(flag)
                self.pending_flag = self.solved_flag
                return self._dashboard_html("Correct. Flag unlocked on badge.", ok=True)
            return self._dashboard_html("Verify fail. Restart challenge.", ok=False)
        return self._dashboard_html("Incorrect code.", ok=False)

    def _register_routes(self, app):
        @app.route("/")
        async def home(_request):
            return self._dashboard_html()

        @app.route("/api/fs")
        async def api_fs(request):
            path = request.args.get("path") or "status.json"
            return self._read_diag_path(path)

        @app.route("/submit")
        async def submit(request):
            code = (request.args.get("code") or "").strip().upper()
            return self._submit_code(code)

    def _auth_check(self, username, password):
        return bool(badgechal.c6_auth_check(username, password))

    def _start_wifi_web(self):
        self._stop_wifi_web()
        self.web = WiFiWebService(
            self.ssid,
            self.password,
            self._register_routes,
            port=self.web_port,
            channel=self.channel,
            auth_validator=self._auth_check,
            auth_paths=["/", "/submit"],
            auth_exempt_paths=["/generate_204", "/gen_204", "/.well-known/gen_204", "/generate204", "/hotspot-detect.html", "/library/test/success.html", "/ncsi.txt", "/connecttest.txt", "/redirect", "/success.txt", "/favicon.ico"],
            captive_dns=True,
            captive_portal=False,
            compat_endpoints=True,
            fallback_ports=[],
        )
        if not self.web.start():
            self.web = None
            return
        self.ip = self.web.ip

    def _stop_wifi_web(self):
        if self.web:
            self.web.stop()
            self.web = None

    async def setup(self):
        self._mute_audio()
        self._pause_ble_scan()
        self._disable_badge_sleep()
        self._start_wifi_web()
        self._last_web_health_ms = time.ticks_ms()
        self._draw_qr()

    async def update(self):
        if self.pending_flag:
            flag = self.pending_flag
            self.pending_flag = None
            display_flag("C6 WiFi Portal", flag, self.controller.bsp.displays)

        if self.web:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_web_health_ms) >= 1500:
                self._last_web_health_ms = now
                if not self.web.is_web_running():
                    self.web.ensure_web_running()
                    if not self.solved_flag:
                        self._draw_qr()

    async def teardown(self):
        self._mute_audio()
        self._stop_wifi_web()
        self._restore_badge_sleep()
        self._resume_ble_scan()

    def button_click(self, button):
        if button == 0:
            if self.solved_flag:
                return
            self._stop_wifi_web()
            self.pending_flag = None
            self.solved_flag = None
            self._new_round()
            self._start_wifi_web()
            self._draw_qr()
        elif button == 3:
            asyncio.create_task(self.controller.switch_app("Menu"))
