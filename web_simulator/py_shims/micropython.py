"""MicroPython module stub for WASM.
viper and native decorators become no-ops since WASM has no native code path.
"""


def viper(func):
    return func


def native(func):
    return func


def const(val):
    return val


def schedule(func, arg):
    func(arg)


def mem_info(verbose=False):
    print("[micropython] mem_info not available in WASM")


def opt_level(level=None):
    if level is None:
        return 0
    pass
