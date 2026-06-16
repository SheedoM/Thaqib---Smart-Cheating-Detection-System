# Thaqib RF Scanner Node

A passive BLE scanner that reports the wireless devices it hears to the Thaqib
backend. It transmits nothing and jams nothing — it only listens.

## 1. Register the node (control room, once)

```bash
curl -X POST http://<backend>:8001/api/v1/rf/scanners \
  -H "Content-Type: application/json" \
  -b cookies.txt -H "X-CSRF-Token: <csrf>" \
  -d '{"hall_id":"<hall-uuid>","identifier":"front-left","position":{"label":"front-left rows 1-4","x":0.1,"y":0.0}}'
```

The response contains a one-time `api_key`. Copy it (and the `id`) into
`config.json`. Only a SHA-256 hash of the key is stored on the server.

## 2. Configure the node

Edit `config.json`:

```json
{
  "scanner_id": "<id from step 1>",
  "api_key":    "<api_key from step 1>",
  "backend_url":"http://<backend>:8001",
  "scan_seconds": 3.0,
  "post_seconds": 3.0
}
```

## 3. Run

- **ESP32 (MicroPython):** copy `main.py` + `config.json` to the board; it runs `main.py` on boot. Requires the built-in `bluetooth` and `urequests`.
- **Laptop / Raspberry Pi (CPython, for testing):** `pip install bleak requests`, then `python main.py`.

## 4. Baseline, then watch

Before the exam, the control room clicks **Start RF Baseline** (≈5 min). Every
device currently broadcasting — the cameras, the access point, the invigilator's
tablet and earbuds — is added to the hall whitelist. During the exam, any
non-whitelisted device, or a whitelisted one whose signal suddenly strengthens
(a hidden earbud powering on), raises a tier-2 alert that names the device and
its estimated zone.
