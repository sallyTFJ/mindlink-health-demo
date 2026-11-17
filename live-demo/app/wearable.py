"""Validated local wearable event log for heart rate, blood pressure and SpO2."""

from __future__ import annotations

import collections
import copy
import json
import math
import threading
import time
from pathlib import Path


def finite(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


class WearableTail:
    def __init__(self, filename):
        self.path = Path(filename)
        self.lock = threading.RLock()
        self.offset = 0
        self.identity = None
        self.pending = b""
        self.latest = {"hr": None, "bp": None, "spo2": None}
        self.histories = {
            "hr": collections.deque(maxlen=180),
            "bp": collections.deque(maxlen=60),
            "spo2": collections.deque(maxlen=60),
        }

    def append(self, event):
        event = self.validate_event(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return event

    @staticmethod
    def validate_event(event):
        if not isinstance(event, dict):
            raise ValueError("wearable event must be an object")
        kind = event.get("event_type")
        if kind not in ("wearable.hr", "wearable.bp", "wearable.spo2"):
            raise ValueError("unsupported wearable event_type")
        data = event.get("data")
        if not isinstance(data, dict):
            raise ValueError("wearable data must be an object")
        stamp = event.get("received_unix_ms", int(time.time() * 1000))
        if not finite(stamp, 1, 10**14):
            raise ValueError("invalid received_unix_ms")
        source = str(event.get("source", "local_bridge"))[:100]
        clean = {"event_type": kind, "received_unix_ms": int(stamp), "source": source, "data": {}}
        if kind == "wearable.hr":
            if not finite(data.get("bpm"), 20, 250):
                raise ValueError("heart rate must be 20-250 bpm")
            clean["data"] = {"bpm": int(round(data["bpm"])), "sensor_contact": data.get("sensor_contact")}
        elif kind == "wearable.bp":
            if not finite(data.get("systolic"), 50, 260) or not finite(data.get("diastolic"), 30, 180):
                raise ValueError("blood pressure is outside supported display bounds")
            if data["systolic"] <= data["diastolic"]:
                raise ValueError("systolic must exceed diastolic")
            clean["data"] = {"systolic": int(round(data["systolic"])), "diastolic": int(round(data["diastolic"]))}
        else:
            if not finite(data.get("percent"), 50, 100):
                raise ValueError("SpO2 must be 50-100 percent")
            clean["data"] = {"percent": round(float(data["percent"]), 1)}
        return clean

    def poll(self):
        try:
            stat = self.path.stat()
        except OSError:
            return
        identity = (stat.st_dev, stat.st_ino)
        reset = identity != self.identity or stat.st_size < self.offset
        with self.path.open("rb") as stream:
            if reset:
                self.identity = identity
                self.offset = max(0, stat.st_size - 262144)
                self.pending = b""
                stream.seek(self.offset)
                if self.offset:
                    stream.readline()
                    self.offset = stream.tell()
            stream.seek(self.offset)
            chunk = stream.read(262144)
            self.offset = stream.tell()
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        if len(self.pending) > 65536:
            self.pending = b""
        with self.lock:
            for raw in lines:
                try:
                    event = self.validate_event(json.loads(raw))
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
                key = event["event_type"].rsplit(".", 1)[1]
                previous = self.latest[key]
                if previous and event["received_unix_ms"] <= previous["received_unix_ms"]:
                    continue
                self.latest[key] = event
                point = {"t": event["received_unix_ms"] / 1000, **event["data"]}
                self.histories[key].append(point)

    @staticmethod
    def _fresh(event, now_ms, ttl_ms):
        if not event:
            return False, None
        age_ms = max(0, now_ms - event["received_unix_ms"])
        return age_ms <= ttl_ms, age_ms / 1000

    def snapshot(self, now=None):
        now_ms = int((time.time() if now is None else float(now)) * 1000)
        with self.lock:
            latest = copy.deepcopy(self.latest)
            histories = {key: list(value) for key, value in self.histories.items()}
        hr_ok, hr_age = self._fresh(latest["hr"], now_ms, 15000)
        bp_ok, bp_age = self._fresh(latest["bp"], now_ms, 30 * 60 * 1000)
        spo2_ok, spo2_age = self._fresh(latest["spo2"], now_ms, 5 * 60 * 1000)
        hr_event, bp_event, spo2_event = latest["hr"], latest["bp"], latest["spo2"]
        hr = hr_event or {"data": {}}
        bp = bp_event or {"data": {}}
        spo2 = spo2_event or {"data": {}}
        return {
            "heart_rate": {
                "valid": hr_ok,
                "reason": None if hr_ok else ("stale" if hr_event else "waiting_for_wearable"),
                "bpm": hr["data"].get("bpm") if hr_ok else None,
                "sensor_contact": hr["data"].get("sensor_contact"),
                "source": hr.get("source"),
                "event_id": str(hr.get("received_unix_ms")) if hr else None,
                "received_unix_ms": hr.get("received_unix_ms"),
                "age_s": round(hr_age, 3) if hr_age is not None else None,
                "history": histories["hr"],
                "measurement_kind": "heart_rate_bpm_not_raw_ecg",
            },
            "blood_pressure": {
                "valid": bp_ok,
                "reason": None if bp_ok else ("stale" if bp_event else "waiting_for_measurement"),
                "systolic": bp["data"].get("systolic") if bp_ok else None,
                "diastolic": bp["data"].get("diastolic") if bp_ok else None,
                "source": bp.get("source"),
                "age_s": round(bp_age, 3) if bp_age is not None else None,
                "history": histories["bp"],
            },
            "spo2": {
                "valid": spo2_ok,
                "reason": None if spo2_ok else ("stale" if spo2_event else "waiting_for_measurement"),
                "percent": spo2["data"].get("percent") if spo2_ok else None,
                "source": spo2.get("source"),
                "age_s": round(spo2_age, 3) if spo2_age is not None else None,
                "history": histories["spo2"],
            },
        }
