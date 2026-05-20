import asyncio

from lib.microdot import Microdot, Response


class PortalServer:
    def __init__(self, render_home, submit_handler, redirect_url, host="0.0.0.0", port=80, submit_path="/submit", code_param="code"):
        self.render_home = render_home
        self.submit_handler = submit_handler
        self.redirect_url = redirect_url
        self.host = host
        self.port = int(port)
        self.submit_path = submit_path
        self.code_param = code_param
        self.app = None
        self.task = None
        self.running = False

    def stop(self):
        self.running = False
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

    def start(self):
        self.stop()
        app = Microdot()
        Response.default_content_type = "text/html"

        @app.route("/")
        async def home(_request):
            return self.render_home()

        @app.route(self.submit_path)
        async def submit(request):
            code = (request.args.get(self.code_param) or "").strip().upper()
            return self.submit_handler(code)

        @app.route("/generate_204")
        async def g204(_request):
            return "", 302, {"Location": self.redirect_url()}

        @app.route("/hotspot-detect.html")
        async def hs(_request):
            return "", 302, {"Location": self.redirect_url()}

        @app.route("/ncsi.txt")
        async def ncsi(_request):
            return "", 302, {"Location": self.redirect_url()}

        @app.route("/<path:path>")
        async def fallback(_request, _path):
            return self.render_home()

        self.app = app
        try:
            self.task = asyncio.create_task(app.start_server(host=self.host, port=self.port))
            self.running = True
            return True
        except Exception:
            self.app = None
            self.task = None
            self.running = False
            return False
