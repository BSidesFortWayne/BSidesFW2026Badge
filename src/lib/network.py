import asyncio
import network

from controller import Controller
from lib.dns import MicroDNSSrv
from lib.microdot.microdot import Microdot, Request, Response


async def start_wifi(mode: str, ssid: str, password: str):
    # TODO load config from file

    if mode.upper() == "STA":
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        print(f"Connecting to {ssid} with password {password}")
        sta_if.connect(ssid, password)
        while not sta_if.isconnected():
            await asyncio.sleep(0.01)
    elif mode.upper() == "AP":
        sta_if = network.WLAN(network.AP_IF)
        sta_if.active(False)
        await asyncio.sleep(0.3)
        sta_if.active(True)
        sta_if.config(essid=ssid, authmode=network.AUTH_WPA2_PSK,
                      password=password, channel=6, hidden=False)
        while not sta_if.active():
            await asyncio.sleep(0.01)

        # Let the AP settle, then assert gateway + DNS as the AP's own IP so the
        # DHCP server hands out usable leases on this firmware (clients otherwise
        # fail to get an IP / show "IP configuration error").
        await asyncio.sleep(0.6)
        ap_ip = sta_if.ifconfig()[0]
        sta_if.ifconfig((ap_ip, "255.255.255.0", ap_ip, ap_ip))
        await asyncio.sleep(0.1)

    MicroDNSSrv.Create({"*": sta_if.ifconfig()[0]})

    print(sta_if.ifconfig())


