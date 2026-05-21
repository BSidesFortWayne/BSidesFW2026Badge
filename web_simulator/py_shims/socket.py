"""Socket module stub for WASM (no network sockets available)."""

AF_INET = 2
AF_INET6 = 10
SOCK_STREAM = 1
SOCK_DGRAM = 2
SOL_SOCKET = 1
SO_REUSEADDR = 2
IPPROTO_TCP = 6


def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return [(AF_INET, SOCK_STREAM, IPPROTO_TCP, '', (host, port))]


class socket:
    def __init__(self, af=AF_INET, type=SOCK_STREAM, proto=0):
        self._af = af
        self._type = type

    def connect(self, address):
        raise OSError("[SOCKET] No network in WASM")

    def bind(self, address):
        pass

    def listen(self, backlog=5):
        pass

    def accept(self):
        raise OSError("[SOCKET] No network in WASM")

    def send(self, data):
        return len(data)

    def sendto(self, data, address):
        return len(data)

    def recv(self, bufsize):
        return b''

    def recvfrom(self, bufsize):
        return b'', ('0.0.0.0', 0)

    def close(self):
        pass

    def setsockopt(self, level, optname, value):
        pass

    def settimeout(self, timeout):
        pass

    def setblocking(self, flag):
        pass
