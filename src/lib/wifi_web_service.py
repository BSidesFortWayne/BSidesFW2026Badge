import asyncio
import socket
from time import sleep_ms

import machine
import network

from lib.dns import MicroDNSSrv
from lib.microdot import Microdot, Response

try:
    import ubinascii as _binascii
except Exception:
    import binascii as _binascii


class HttpBasicCredentials:
    def __init__(self, username, password, realm="Device Admin"):
        self.username = "" if username is None else str(username)
        self.password = "" if password is None else str(password)
        self.realm = realm if realm else "Device Admin"


def derive_device_password(prefix="BSFW", salt="", length=10):
    """Generate a deterministic per-device password from unique ID hash."""
    uid = machine.unique_id()
    h = 0x811C9DC5
    for b in uid:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    for ch in str(salt):
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    out = []
    for _ in range(max(4, int(length))):
        h ^= (h << 13) & 0xFFFFFFFF
        h ^= (h >> 17) & 0xFFFFFFFF
        h ^= (h << 5) & 0xFFFFFFFF
        out.append(alphabet[h % len(alphabet)])
    return "{}{}".format(prefix, "".join(out))


class _AsyncDnsServer:
    def __init__(self, ip):
        self.ip = ip
        self.ip_bytes = self._ip_to_bytes(ip)
        self.sock = None
        self.task = None
        self.running = False

    def _ip_to_bytes(self, ip):
        parts = ip.split(".")
        if len(parts) != 4:
            raise ValueError("Invalid IPv4")
        return bytes([int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])])

    def _extract_name(self, packet):
        try:
            pos = 12
            labels = []
            while True:
                ln = packet[pos]
                if ln == 0:
                    break
                labels.append(packet[pos + 1 : pos + 1 + ln].decode())
                pos += 1 + ln
            return ".".join(labels)
        except Exception:
            return None

    def _answer_a(self, packet):
        try:
            query_end = 12
            while True:
                ln = packet[query_end]
                if ln == 0:
                    break
                query_end += 1 + ln
            query_end += 5
            return b"".join(
                [
                    packet[:2],
                    b"\x85\x80",
                    packet[4:6],
                    b"\x00\x01",
                    b"\x00\x00",
                    b"\x00\x00",
                    packet[12:query_end],
                    b"\xc0\x0c",
                    b"\x00\x01",
                    b"\x00\x01",
                    b"\x00\x00\x00\x1E",
                    b"\x00\x04",
                    self.ip_bytes,
                ]
            )
        except Exception:
            return None

    async def _loop(self):
        self.running = True
        while self.running:
            try:
                packet, addr = self.sock.recvfrom(256)
            except OSError:
                await asyncio.sleep_ms(10)
                continue
            except Exception:
                await asyncio.sleep_ms(10)
                continue

            if not packet:
                await asyncio.sleep_ms(1)
                continue

            name = self._extract_name(packet)
            if name is None:
                continue

            resp = self._answer_a(packet)
            if not resp:
                continue
            try:
                self.sock.sendto(resp, addr)
            except Exception:
                pass

    def start(self):
        self.stop()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", 53))
        self.sock.setblocking(False)
        self.task = asyncio.create_task(self._loop())
        return True

    def stop(self):
        self.running = False
        if self.task:
            try:
                self.task.cancel()
            except Exception:
                pass
        self.task = None
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None


class WiFiWebService:
    """Simple AP + captive DNS + Microdot host service.

    Route registration stays in the caller through `route_builder(app)`.
    """

    def __init__(
        self,
        ssid,
        wifi_password,
        route_builder,
        host="0.0.0.0",
        port=80,
        channel=6,
        authmode=None,
        captive_dns=True,
        captive_portal=True,
        redirect_url=None,
        auth_credentials=None,
        auth_validator=None,
        auth_paths=None,
        auth_exempt_paths=None,
        compat_endpoints=False,
        fallback_ports=None,
        response_content_type="text/html",
    ):
        self.ssid = ssid
        self.wifi_password = wifi_password
        self.route_builder = route_builder
        self.host = host
        self.port = int(port)
        self.channel = channel
        self.authmode = authmode if authmode is not None else getattr(network, "AUTH_WPA2_PSK", 3)
        self.captive_dns = bool(captive_dns)
        self.captive_portal = bool(captive_portal)
        self.redirect_url = redirect_url if redirect_url else self.url
        self.auth_credentials = auth_credentials
        self.auth_validator = auth_validator
        self.auth_paths = auth_paths[:] if auth_paths else ["/*"]
        self.auth_exempt_paths = auth_exempt_paths[:] if auth_exempt_paths else []
        self.compat_endpoints = bool(compat_endpoints)
        self.fallback_ports = fallback_ports[:] if fallback_ports else []
        self.response_content_type = response_content_type

        self.ap = None
        self.dns = None
        self._async_dns = None
        self.ip = "192.168.4.1"
        self.app = None
        self.task = None
        self.running = False
        self.last_error = None

    def url(self):
        ip = str(self.ip).strip() if self.ip else "192.168.4.1"
        if self.port == 80:
            return "http://{}/".format(ip)
        return "http://{}:{}/".format(ip, self.port)

    def set_wifi_credentials(self, ssid, wifi_password):
        self.ssid = ssid
        self.wifi_password = wifi_password

    def stop(self):
        self.running = False
        self._stop_web_server()
        self._stop_dns()
        self._stop_access_point()

    def start(self):
        self.stop()
        self.last_error = None
        if not self._start_access_point():
            self.last_error = "ap_start_failed"
            return False
        self._start_dns()
        if not self._start_web_server():
            if not self.last_error:
                self.last_error = "web_start_failed"
            self.stop()
            return False
        self.running = True
        return True

    def restart(self):
        return self.start()

    def is_web_running(self):
        if not self.task:
            return False
        try:
            if not self.task.done():
                return True
            exc = self.task.exception()
            if exc:
                self.last_error = str(exc)
            else:
                self.last_error = "web_task_ended"
        except Exception as exc:
            self.last_error = str(exc)
        return False

    def ensure_web_running(self):
        if self.is_web_running():
            return True
        return self._start_web_server()

    def _start_access_point(self):
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(True)
        try:
            self.ap.config(
                essid=self.ssid,
                authmode=self.authmode,
                password=self.wifi_password,
                channel=self.channel,
                hidden=False,
            )
        except Exception:
            try:
                self.ap.config(essid=self.ssid, password=self.wifi_password)
            except Exception:
                return False

        for _ in range(400):
            if self.ap.active():
                break
            sleep_ms(10)

        if not self.ap.active():
            return False

        sleep_ms(600)
        ifc = self.ap.ifconfig()
        if ifc and len(ifc) >= 1 and ifc[0]:
            self.ip = ifc[0]

        # Ensure DHCP announces a usable gateway + DNS for clients like Android.
        try:
            self.ap.ifconfig((self.ip, "255.255.255.0", self.ip, self.ip))
            sleep_ms(100)
            ifc = self.ap.ifconfig()
            if ifc and len(ifc) >= 1 and ifc[0]:
                self.ip = ifc[0]
        except Exception:
            pass
        return True

    def _stop_access_point(self):
        if self.ap:
            try:
                self.ap.active(False)
            except Exception:
                pass
            self.ap = None

    def _start_dns(self):
        if not self.captive_dns:
            return
        self._stop_dns()
        # Prefer async DNS server because the threaded DNS helper is unreliable
        # on this firmware build.
        try:
            self._async_dns = _AsyncDnsServer(self.ip)
            self._async_dns.start()
            return
        except Exception:
            self._async_dns = None

        # Fallback to legacy threaded DNS implementation.
        try:
            self.dns = MicroDNSSrv.Create({"*": self.ip})
        except Exception:
            self.dns = None

    def _stop_dns(self):
        if self._async_dns:
            try:
                self._async_dns.stop()
            except Exception:
                pass
            self._async_dns = None
        if self.dns:
            try:
                self.dns.Stop()
            except Exception:
                pass
            self.dns = None

    def _route_needs_auth(self, path):
        if not self.auth_credentials and not self.auth_validator:
            return False

        for exempt in self.auth_exempt_paths:
            if self._path_match(path, exempt):
                return False

        for protected in self.auth_paths:
            if self._path_match(path, protected):
                return True
        return False

    def _path_match(self, path, rule):
        if not rule:
            return False
        if rule == "/*":
            return True
        if rule.endswith("*"):
            return path.startswith(rule[:-1])
        return path == rule

    def _parse_basic_credentials(self, request):
        header = request.headers.get("Authorization", "")
        if not header or not header.startswith("Basic "):
            return None, None

        encoded = header[6:].strip()
        if not encoded:
            return None, None

        try:
            if isinstance(encoded, str):
                encoded = encoded.encode()
            decoded = _binascii.a2b_base64(encoded).decode().strip()
        except Exception:
            return None, None

        if ":" not in decoded:
            return None, None
        username, password = decoded.split(":", 1)
        return username, password

    def _auth_ok(self, request):
        username, password = self._parse_basic_credentials(request)
        if username is None:
            return False

        if self.auth_validator:
            try:
                return bool(self.auth_validator(username, password))
            except Exception:
                return False

        if not self.auth_credentials:
            return True

        expected = "{}:{}".format(self.auth_credentials.username, self.auth_credentials.password)
        return "{}:{}".format(username, password) == expected

    def _auth_challenge(self):
        realm = self.auth_credentials.realm if self.auth_credentials else "Device Admin"
        headers = {
            "WWW-Authenticate": 'Basic realm="{}"'.format(realm),
            "Cache-Control": "no-store",
        }
        return "Authentication required", 401, headers

    def _register_captive_routes(self, app):
        @app.route("/generate_204")
        async def _g204(_request):
            return "", 302, {"Location": self.redirect_url()}

        @app.route("/hotspot-detect.html")
        async def _hs(_request):
            return "", 302, {"Location": self.redirect_url()}

        @app.route("/ncsi.txt")
        async def _ncsi(_request):
            return "", 302, {"Location": self.redirect_url()}

        @app.route("/<path:path>")
        async def _fallback(_request, _path):
            return "", 302, {"Location": self.redirect_url()}

    def _register_compat_routes(self, app):
        # Android
        @app.route("/generate_204")
        @app.route("/gen_204")
        @app.route("/.well-known/gen_204")
        async def _android_probe(_request):
            return "", 204

        @app.route("/generate204")
        async def _android_probe_alt(_request):
            return "", 204

        # Apple
        @app.route("/hotspot-detect.html")
        @app.route("/library/test/success.html")
        async def _apple_probe(_request):
            return "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>", 200

        # Microsoft
        @app.route("/ncsi.txt")
        async def _windows_ncsi(_request):
            return "Microsoft NCSI", 200, {"Content-Type": "text/plain"}

        @app.route("/connecttest.txt")
        async def _windows_connecttest(_request):
            return "Microsoft Connect Test", 200, {"Content-Type": "text/plain"}

        @app.route("/redirect")
        async def _windows_redirect(_request):
            return "", 204

        @app.route("/success.txt")
        async def _success_txt(_request):
            return "success", 200, {"Content-Type": "text/plain"}

        # Reduce browser retries for missing favicon.
        @app.route("/favicon.ico")
        async def _favicon(_request):
            return "", 204

    def _start_web_server(self):
        candidate_ports = [self.port]
        for p in self.fallback_ports:
            pi = int(p)
            if pi not in candidate_ports:
                candidate_ports.append(pi)

        for port in candidate_ports:
            self._stop_web_server()
            app = Microdot()
            Response.default_content_type = self.response_content_type

            @app.before_request
            async def _check_auth(request):
                if not self._route_needs_auth(request.path):
                    return None
                if self._auth_ok(request):
                    return None
                return self._auth_challenge()

            self.route_builder(app)

            if self.compat_endpoints:
                self._register_compat_routes(app)

            if self.captive_portal:
                self._register_captive_routes(app)

            self.app = app
            self.port = int(port)
            try:
                self.task = asyncio.create_task(app.start_server(host=self.host, port=self.port))
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self.app = None
                self.task = None

        return False

    def _stop_web_server(self):
        if self.app:
            try:
                self.app.shutdown()
            except Exception:
                pass
        self.app = None

        if self.task:
            try:
                self.task.cancel()
            except Exception:
                pass
        self.task = None
