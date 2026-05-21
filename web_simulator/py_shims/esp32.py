"""ESP32 module stub for WASM."""

WAKEUP_ALL_LOW = 0
WAKEUP_ANY_HIGH = 1
HEAP_DATA = 0
HEAP_EXEC = 1


def wake_on_ext0(pin=None, level=None):
    pass


def wake_on_ext1(pins=None, level=None):
    pass


def raw_temperature():
    return 50


def idf_heap_info(caps):
    return [(131072, 65536, 32768, 4, 16)]


class NVS:
    def __init__(self, namespace):
        self._namespace = namespace
        self._data = {}

    def get_i32(self, key):
        return self._data.get(key, 0)

    def set_i32(self, key, value):
        self._data[key] = value

    def erase_key(self, key):
        self._data.pop(key, None)

    def commit(self):
        pass


class Partition:
    BOOT = 0
    RUNNING = 1

    def __init__(self, id, block_size=4096):
        pass

    def info(self):
        return (0, 0, 0x10000, 0x1F0000, 'app', False)

    @staticmethod
    def find(type=None, subtype=None, label=None):
        p = Partition(0)
        return [p]
