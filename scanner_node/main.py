"""
Thaqib RF scanner node.

A single-file firmware for an ESP32 (MicroPython) or any small Linux board
(CPython). It passively scans for BLE advertisements, batches what it hears, and
POSTs the batch to the Thaqib backend every few seconds. It transmits nothing and
jams nothing — it only listens.

Config is read from config.json next to this file:

    {
      "scanner_id": "<uuid from POST /api/v1/rf/scanners>",
      "api_key":    "<plaintext key returned once at registration>",
      "backend_url":"http://192.168.1.50:8001",
      "scan_seconds": 3.0,
      "post_seconds": 3.0
    }

On MicroPython, `bluetooth` and `urequests` are used; on CPython, the script
falls back to `bleak` (if installed) and `requests`, which is handy for testing
the whole pipeline from a laptop without dedicated hardware.
"""

import json
import sys
import time

try:
    with open("config.json") as _f:
        CONFIG = json.load(_f)
except Exception as exc:  # pragma: no cover
    print("Cannot read config.json:", exc)
    sys.exit(1)

SCANNER_ID = CONFIG["scanner_id"]
API_KEY = CONFIG["api_key"]
BACKEND = CONFIG["backend_url"].rstrip("/")
SCAN_SECONDS = float(CONFIG.get("scan_seconds", 3.0))
POST_SECONDS = float(CONFIG.get("post_seconds", 3.0))
PUSH_URL = "{}/api/v1/rf-push/{}/detections".format(BACKEND, SCANNER_ID)


# --------------------------------------------------------------------------
# Platform abstraction: scan() returns a list of {mac, name, rssi, signal_type}
# --------------------------------------------------------------------------
def _scan_micropython(duration):
    import bluetooth  # type: ignore

    found = {}

    def _irq(event, data):
        # 5 == _IRQ_SCAN_RESULT
        if event == 5:
            addr_type, addr, adv_type, rssi, adv_data = data
            mac = ":".join("{:02x}".format(b) for b in bytes(addr))
            name = _adv_name(bytes(adv_data))
            found[mac] = {"mac": mac, "name": name, "rssi": rssi, "signal_type": "ble"}

    ble = bluetooth.BLE()
    ble.active(True)
    ble.irq(_irq)
    ble.gap_scan(int(duration * 1000), 30000, 30000, False)
    time.sleep(duration + 0.2)
    try:
        ble.gap_scan(None)  # stop
    except Exception:
        pass
    return list(found.values())


def _adv_name(adv):
    i = 0
    while i + 1 < len(adv):
        length = adv[i]
        if length == 0:
            break
        ad_type = adv[i + 1]
        if ad_type in (0x08, 0x09):  # shortened / complete local name
            try:
                return bytes(adv[i + 2:i + 1 + length]).decode("utf-8")
            except Exception:
                return None
        i += 1 + length
    return None


def _scan_cpython(duration):
    import asyncio

    from bleak import BleakScanner  # type: ignore

    async def _go():
        devices = await BleakScanner.discover(timeout=duration, return_adv=True)
        out = []
        for _addr, (dev, adv) in devices.items():
            out.append({
                "mac": dev.address,
                "name": adv.local_name or dev.name,
                "rssi": adv.rssi,
                "signal_type": "ble",
            })
        return out

    return asyncio.run(_go())


def scan(duration):
    if sys.implementation.name == "micropython":
        return _scan_micropython(duration)
    return _scan_cpython(duration)


# --------------------------------------------------------------------------
# HTTP abstraction
# --------------------------------------------------------------------------
def post_batch(detections):
    body = json.dumps({"detections": detections})
    headers = {"Content-Type": "application/json", "X-RF-Key": API_KEY}
    if sys.implementation.name == "micropython":
        import urequests  # type: ignore

        resp = urequests.post(PUSH_URL, data=body, headers=headers)
        status = resp.status_code
        resp.close()
        return status
    import requests  # type: ignore

    resp = requests.post(PUSH_URL, data=body, headers=headers, timeout=10)
    return resp.status_code


def run():
    print("Thaqib RF node", SCANNER_ID, "->", PUSH_URL)
    while True:
        try:
            detections = scan(SCAN_SECONDS)
            if detections:
                code = post_batch(detections)
                print("posted", len(detections), "->", code)
        except Exception as exc:  # keep the node alive across transient errors
            print("scan/post error:", exc)
        time.sleep(POST_SECONDS)


if __name__ == "__main__":
    run()
