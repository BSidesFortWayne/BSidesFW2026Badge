"""Thread module stub for WASM (threads not available)."""


class LockType:
    def __init__(self):
        self._locked = False

    def acquire(self, blocking=True, timeout=-1):
        self._locked = True
        return True

    def release(self):
        self._locked = False

    def locked(self):
        return self._locked

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def allocate_lock():
    return LockType()


def start_new_thread(function, args, kwargs=None):
    print(f"[_thread] Warning: start_new_thread called but threads not available in WASM")
    print(f"[_thread] Function {function.__name__} will not run in background")
    pass


def get_ident():
    return 1


def exit():
    pass
