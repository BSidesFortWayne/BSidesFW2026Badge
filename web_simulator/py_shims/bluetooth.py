"""Bluetooth module stub for WASM."""


class BLE:
    def __init__(self):
        self._active = False
        self._irq_handler = None

    def active(self, state=None):
        if state is None:
            return self._active
        self._active = state

    def irq(self, handler):
        self._irq_handler = handler

    def gap_advertise(self, interval_us, adv_data=None, resp_data=None, connectable=True):
        pass

    def gap_scan(self, duration_ms=0, interval_us=1280000, window_us=11250, active=False):
        pass

    def gap_connect(self, addr_type, addr):
        pass

    def gap_disconnect(self, conn_handle):
        pass

    def gatts_register_services(self, services):
        return []

    def gatts_read(self, value_handle):
        return b''

    def gatts_write(self, value_handle, data, send_update=False):
        pass

    def gatts_notify(self, conn_handle, value_handle, data=None):
        pass

    def config(self, *args, **kwargs):
        if args:
            return b''
        pass
