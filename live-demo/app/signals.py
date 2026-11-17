"""Signal validation. Display may contain noise; inference never fills real gaps."""
import collections
import json
import math
from pathlib import Path
import time
import threading
import copy

FS = 512
WINDOW = 2560


def finite(v, lo=-float('inf'), hi=float('inf')):
    return type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi


def eeg_window(state):
    """Return exactly the latest contiguous unmasked 5 seconds, never interpolated."""
    if not isinstance(state, dict) or state.get('live') is not True or state.get('connected') is not True:
        return None, 'eeg_disconnected_or_stale'
    if state.get('quality') != 0 or isinstance(state.get('quality'), bool):
        return None, 'poor_or_unknown_contact'
    if not finite(state.get('age'), 0, 1):
        return None, 'raw_stale'
    if not finite(state.get('dt'), 1 / FS - 1e-8, 1 / FS + 1e-8):
        return None, 'unexpected_sampling_interval'
    arrays = [state.get(k) for k in ('raw_original', 'times', 'raw_mask')]
    if not all(isinstance(v, list) for v in arrays) or len({len(v) for v in arrays}) != 1:
        return None, 'raw_api_fields_missing'
    if len(arrays[0]) < WINDOW:
        return None, 'waiting_for_contiguous_5_seconds'
    raw, times, mask = [a[-WINDOW:] for a in arrays]
    if any(type(v) is not int or not -32768 <= v <= 32767 for v in raw):
        return None, 'raw_gap_or_invalid_counts'
    if any(v is not False for v in mask):
        return None, 'artifact_or_quality_mask_in_window'
    # The source reconstructs timestamps from serial chunk arrival, not hardware
    # clocks: a burst may be compressed. Real loss inserts null/mask and gaps.
    if any(not finite(t, 0) for t in times) or any(not 0 < b-a <= .25 for a, b in zip(times, times[1:])):
        return None, 'noncontiguous_sample_clock'
    gaps = state.get('gaps')
    if not isinstance(gaps, list):
        return None, 'gap_metadata_missing'
    if any(isinstance(g, dict) and finite(g.get('t')) and times[0] <= g['t'] <= times[-1] for g in gaps):
        return None, 'recorded_gap_in_window'
    if not isinstance(state.get('session_id'), str) or not state['session_id'] or type(state.get('total')) is not int:
        return None, 'sample_identity_missing'
    return list(raw), None


def display_wave(state):
    times, raw = state.get('times', []), state.get('raw_original', [])
    if not isinstance(times, list) or not isinstance(raw, list) or len(times) != len(raw):
        return {'times': [], 'raw': [], 'envelope': []}
    # RMS is for display only. Reset at real gaps; retain poor-contact samples.
    out, squares, previous, square_sum = [], collections.deque(maxlen=128), None, 0.0
    safe_t, safe_raw = [], []
    for t, v in zip(times[-6000:], raw[-6000:]):
        if not finite(t, 0):
            continue
        if previous is not None and not 0 < t-previous <= .25:
            squares.clear(); square_sum = 0.0
        previous = t
        good = finite(v, -32768, 32767)
        if not good:
            squares.clear(); square_sum = 0.0
        else:
            if len(squares) == 128: square_sum -= squares[0]
            squares.append(v*v)
            square_sum += v*v
        out.append(math.sqrt(max(0, square_sum)/128) if len(squares) == 128 else None)
        safe_t.append(t); safe_raw.append(v if good else None)
    return {'times': safe_t, 'raw': safe_raw, 'envelope': out,
            'display_end': state.get('display_end'), 'unit': 'neurosky_counts',
            'envelope_kind': '250ms_RMS_including_noise', 'includes_poor_contact': True}


class HeartTail:
    def __init__(self, filename):
        self._lock = threading.Lock()
        self._published = None
        self.path = Path(filename)
        self.offset = 0
        self.identity = None
        self.pending = b''
        self.latest = None
        self.anchor = None
        self.last_stamp = None
        self.error = 'waiting_for_heart_file'
        self.history = collections.deque(maxlen=120)

    def poll(self, now=None, wall=None):
        self._poll(now, wall)
        with self._lock:
            self._published = (copy.deepcopy(self.latest), self.anchor, self.error, list(self.history))

    def _poll(self, now=None, wall=None):
        now = time.monotonic() if now is None else now
        wall = time.time() if wall is None else wall
        try:
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino)
            reset = identity != self.identity or stat.st_size < self.offset
            with self.path.open('rb') as stream:
                if reset:
                    self.identity = identity
                    self.offset = max(0, stat.st_size - 131072)
                    self.pending = b''
                    # Never combine a previous file's last half-line with this file.
                    stream.seek(self.offset)
                    if self.offset:
                        stream.readline(); self.offset = stream.tell()
                stream.seek(self.offset)
                chunk = stream.read(131072)
                self.offset = stream.tell()
            lines = (self.pending+chunk).split(b'\n')
            self.pending = lines.pop()
            if len(self.pending) > 65536:
                self.pending = b''
            for line in lines:
                try:
                    event = json.loads(line)
                    data = event.get('data', {})
                    stamp = event.get('received_unix_ms')
                    if event.get('event_type') != 'wearable.hr' or not finite(stamp, 1):
                        continue
                    if stamp == self.last_stamp:
                        continue  # A duplicate does not renew freshness.
                    if self.last_stamp is not None and stamp < self.last_stamp:
                        continue
                    age = wall-stamp/1000
                    if age < -1:
                        self.error = 'heart_clock_in_future'; continue
                    self.last_stamp = stamp
                    self.latest = {'event_id': str(stamp), 'bpm': data.get('bpm'),
                        'sensor_contact': data.get('sensor_contact'),
                        'source': str(event.get('source', 'heartcast'))[:100],
                        'received_unix_ms': stamp, 'usable_for_adaptation': event.get('usable_for_adaptation', False)}
                    self.anchor = now-max(0, age)
                    if finite(data.get('bpm'), 20, 250):
                        self.history.append({'t': stamp/1000, 'bpm': data['bpm']})
                except (ValueError, TypeError, AttributeError):
                    continue
            if self.error != 'heart_clock_in_future' or (self.anchor is not None and now-self.anchor <= 15):
                self.error = None
        except OSError:
            self.error = 'heart_file_unavailable'

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            latest, anchor, error, history = self._published or (None, None, 'waiting_for_heart_file', [])
        e = latest or {}
        age = max(0, now-anchor) if anchor is not None else None
        reason = error or ('missing' if age is None else 'stale' if age > 15 else
                 'sensor_not_in_contact' if e.get('sensor_contact') is False else
                 'invalid_bpm' if not finite(e.get('bpm'), 20, 250) else None)
        return {'valid': reason is None, 'reason': reason, 'bpm': e.get('bpm') if reason is None else None,
                'age_s': round(age, 3) if age is not None else None,
                'source': e.get('source'), 'event_id': e.get('event_id'),
                'sensor_contact': e.get('sensor_contact'), 'received_unix_ms': e.get('received_unix_ms'),
                'age_basis': 'receiver_timestamp_then_local_monotonic',
                'measurement_kind': 'heart_rate_bpm_not_raw_ecg', 'rr_intervals_ms': None, 'hrv': None,
                'semantics': 'heart_rate_is_not_an_emotion_label',
                'usable_for_adaptation': e.get('usable_for_adaptation', False),
                'history': history}
