"""Standard BLE Heart Rate / Blood Pressure bridge for MindLink.

Many consumer watches do not expose these standard GATT services to Windows.
Apple Watch can be used through a broadcaster such as HeartCast; Huawei and
other vendor-locked products generally need their official Health SDK/export or
a phone companion that POSTs the same local event schema.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

HEART_RATE_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"
BLOOD_PRESSURE_MEASUREMENT = "00002a35-0000-1000-8000-00805f9b34fb"


def decode_heart_rate(data):
    if len(data) < 2:
        raise ValueError("short heart-rate packet")
    flags = data[0]
    width = 2 if flags & 1 else 1
    if len(data) < 1 + width:
        raise ValueError("short bpm value")
    bpm = int.from_bytes(data[1:1 + width], "little")
    contact = bool(flags & 2) if flags & 4 else None
    if not 20 <= bpm <= 250:
        raise ValueError("invalid bpm")
    return bpm, contact


def _sfloat(raw):
    value = int.from_bytes(raw, "little")
    mantissa = value & 0x0FFF
    exponent = value >> 12
    if mantissa >= 0x0800:
        mantissa -= 0x1000
    if exponent >= 0x0008:
        exponent -= 0x0010
    return mantissa * (10 ** exponent)


def decode_blood_pressure(data):
    if len(data) < 7:
        raise ValueError("short blood-pressure packet")
    systolic = _sfloat(data[1:3])
    diastolic = _sfloat(data[3:5])
    if not 50 <= systolic <= 260 or not 30 <= diastolic <= 180 or systolic <= diastolic:
        raise ValueError("invalid blood-pressure value")
    return int(round(systolic)), int(round(diastolic))


class EventWriter:
    def __init__(self, path, source):
        self.path = Path(path)
        self.source = source[:100]
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event_type, data):
        event = {"event_type": event_type, "received_unix_ms": int(time.time() * 1000), "source": self.source, "data": data}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return event


async def run(name=None, address=None):
    from bleak import BleakClient, BleakScanner

    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    output = root / config["heart_rate_file"]
    label = address or name or config.get("wearable_name") or "HeartCast"
    writer = EventWriter(output, "standard_ble:" + label)
    print("MindLink wearable output:", output, flush=True)
    while True:
        try:
            if address:
                device = await BleakScanner.find_device_by_address(address, timeout=15)
            else:
                needle = (name or config.get("wearable_name") or "HeartCast").lower()
                print("Scanning for:", needle, flush=True)
                device = await BleakScanner.find_device_by_filter(
                    lambda dev, adv: needle in (adv.local_name or dev.name or "").lower(), timeout=15
                )
            if not device:
                print("No matching standard BLE device. Check the watch/phone broadcaster.", flush=True)
                await asyncio.sleep(3)
                continue
            last = [time.monotonic()]

            def on_hr(_sender, payload):
                try:
                    bpm, contact = decode_heart_rate(payload)
                    writer.write("wearable.hr", {"bpm": bpm, "sensor_contact": contact})
                    last[0] = time.monotonic()
                    print("HR", bpm, "bpm", flush=True)
                except ValueError:
                    return

            def on_bp(_sender, payload):
                try:
                    systolic, diastolic = decode_blood_pressure(payload)
                    writer.write("wearable.bp", {"systolic": systolic, "diastolic": diastolic})
                    last[0] = time.monotonic()
                    print("BP", systolic, "/", diastolic, flush=True)
                except ValueError:
                    return

            async with BleakClient(device, timeout=20) as client:
                characteristics = {str(char.uuid).lower() for service in client.services for char in service.characteristics}
                subscriptions = 0
                if HEART_RATE_MEASUREMENT in characteristics:
                    await client.start_notify(HEART_RATE_MEASUREMENT, on_hr)
                    subscriptions += 1
                if BLOOD_PRESSURE_MEASUREMENT in characteristics:
                    await client.start_notify(BLOOD_PRESSURE_MEASUREMENT, on_bp)
                    subscriptions += 1
                if not subscriptions:
                    raise RuntimeError("device does not expose standard Heart Rate or Blood Pressure GATT characteristics")
                print("Connected. Keep this window open.", flush=True)
                while client.is_connected and time.monotonic() - last[0] < 45:
                    await asyncio.sleep(1)
        except Exception as exc:
            print("BLE:", type(exc).__name__, str(exc)[:180], flush=True)
        await asyncio.sleep(3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="part of the advertised device name")
    parser.add_argument("--address", help="exact Windows BLE address/device identifier")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.name, args.address))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
