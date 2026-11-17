"""CPU inference and an isolated, contiguous single-channel stream contract.

`valid` means the input passed quality/protocol checks, not that psychological
interpretation has been validated. Existing research checkpoints are unchanged.
"""
from pathlib import Path
from collections import deque
import hashlib
import json
import math
import re
import threading
import time
import numpy as np
import onnxruntime as ort
from .preprocess import prepare_window, features, normalize_wave
from .thinkgear import UV_PER_COUNT

ort.disable_telemetry_events()
ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATES = (128, 250, 256, 512)
SOURCES = ('device', 'external_live', 'public_replay', 'offline')
STREAM_TTL_SECONDS = 1.5


class InputError(ValueError):
    pass


def integer(value, name, low=0, high=2**53-1):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InputError(f'{name} must be an integer in [{low}, {high}]')
    return value


def validate_input(data, window=True):
    if not isinstance(data, dict):
        raise InputError('JSON object required')
    fs = integer(data.get('fs_hz'), 'fs_hz', 1, 2048)
    if fs not in SAMPLE_RATES:
        raise InputError(f'fs_hz must be one of {SAMPLE_RATES}')
    if data.get('channel') != 'Fp1':
        raise InputError('channel must be Fp1; multi-channel arrays are not accepted')
    unit = data.get('unit')
    if unit not in ('uV', 'neurosky_counts'):
        raise InputError('unit must be uV or neurosky_counts')
    source = data.get('source')
    if source not in SOURCES:
        raise InputError('source must be device, external_live, public_replay or offline')
    values = data.get('samples')
    if not isinstance(values, list) or not values or len(values) > 5*fs:
        raise InputError('samples must be a nonempty flat array, at most five seconds')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise InputError('samples must contain only numbers; no booleans, strings or nested channels')
    raw = np.asarray(values, dtype=np.float64)
    if not np.isfinite(raw).all():
        raise InputError('samples contain nonfinite values')
    if window and len(raw) != 5*fs:
        raise InputError(f'window requires exactly {5*fs} samples (five seconds)')
    if not window and len(raw) > fs:
        raise InputError('stream chunks must be no longer than one second')
    if unit == 'neurosky_counts':
        if fs != 512:
            raise InputError('neurosky_counts requires 512 Hz TGAM RAW')
        if np.any(raw != np.round(raw)) or np.any(raw < -32768) or np.any(raw > 32767):
            raise InputError('NeuroSky counts must be signed 16-bit integers')
        raw = raw * UV_PER_COUNT
    quality = data.get('quality')
    if quality is not None:
        integer(quality, 'quality', 0, 200)
    request_id = data.get('request_id')
    if request_id is not None and (not isinstance(request_id, str) or len(request_id) > 128):
        raise InputError('request_id must be a string up to 128 characters')
    timestamp = data.get('sample_time_end_unix_s')
    if timestamp is not None and (isinstance(timestamp, bool) or not isinstance(timestamp, (float,int)) or not math.isfinite(timestamp) or timestamp < 0):
        raise InputError('sample_time_end_unix_s must be finite and nonnegative')
    return raw, fs, quality


class EEGModel:
    def __init__(self, models_dir=None, fold=0):
        self.root = Path(models_dir) if models_dir else ROOT/'models'
        self.manifest = json.loads((self.root/'model_manifest.json').read_text(encoding='utf8'))
        integer(fold, 'fold', 0, 4)
        self.fold = fold
        self.sessions = {}
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        for task, info in self.manifest['folds'][str(fold)].items():
            self.sessions[task] = []
            for member in info['members']:
                path = self.root/member['file']
                if hashlib.sha256(path.read_bytes()).hexdigest() != member['sha256']:
                    raise RuntimeError(f'Model checksum mismatch: {member["file"]}')
                self.sessions[task].append(ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider']))

    def base_result(self, source, request_id=None):
        return {'schema_version':'1.0', 'model_version':self.manifest['model_version'],
                'fold':self.fold, 'temporal_unit':'window', 'source':source,
                'request_id':request_id, 'generated_at_unix_s':time.time(),
                'valid':False, 'reason':'no_input', 'attention_score':None,
                'attention_class':None, 'valence_score':None, 'state_xy':None,
                'score_semantics':'Uncalibrated research model outputs; valid indicates signal/protocol QC only.'}

    def predict_processed(self, waves, aggregate_trial=False):
        """Exact raw-score aggregation; processed input is [windows, 512] microvolts.

        aggregate_trial=True is offline-only: all windows must belong to ONE
        trial. This function does not infer labels or group unrelated windows.
        """
        waves = np.asarray(waves, dtype=np.float32)
        if waves.ndim != 2 or waves.shape[1] != 512 or not len(waves) or not np.isfinite(waves).all():
            raise InputError('processed input must have finite shape [windows, 512]')
        inputs = {'wave':normalize_wave(waves)[:,None], 'features':features(waves)}
        result = {}
        for task, sessions in self.sessions.items():
            members = []
            for session in sessions:
                raw = session.run(None, inputs)[0].reshape(-1)
                if aggregate_trial:
                    raw = np.asarray([raw.mean()], dtype=np.float64)
                p = 1/(1+np.exp(-np.clip(raw,-40,40))) if task=='attention' else np.clip(raw,-1,1)
                members.append(p)
            result[task] = np.mean(members, axis=0)
        return result

    def _predict_uv(self, raw, fs, source, request_id=None):
        start = time.perf_counter()
        result = self.base_result(source, request_id)
        wave, reason = prepare_window(raw, fs)
        if wave is None:
            result['reason'] = reason
            return result
        p = self.predict_processed(wave[None])
        attention = float(p['attention'][0]*100)
        valence = float(p['valence'][0])
        result.update(valid=True, reason=None, attention_score=attention,
                      attention_class='low_mind_wandering' if attention >= 50 else 'high_mind_wandering',
                      valence_score=valence, state_xy={'x':valence,'y':attention},
                      inference_ms=(time.perf_counter()-start)*1000)
        return result

    def infer_window(self, data):
        raw, fs, quality = validate_input(data)
        result = self.base_result(data['source'], data.get('request_id'))
        if quality != 0:
            result['reason'] = 'quality_unknown' if quality is None else 'poor_contact'
        else:
            result = self._predict_uv(raw, fs, data['source'], data.get('request_id'))
        result.update(input_fs_hz=fs,input_samples=len(raw),input_unit=data['unit'],quality=quality,
                      sample_time_end_unix_s=data.get('sample_time_end_unix_s'))
        return result


class EEGStream:
    """A session-local buffer, no implicit mixing between users or sources."""
    def __init__(self, model, stream_id, clock=time.monotonic):
        if not isinstance(stream_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',stream_id):
            raise InputError('stream_id must contain 1-64 letters, digits, underscores or hyphens')
        self.model=model;self.stream_id=stream_id;self.clock=clock
        self.lock=threading.RLock();self.sequence=0;self.segment=0
        self.buffer=deque();self.config=None;self.expected=None;self.last_received=None
        self.last_inferred_index=None;self.result=model.base_result('offline')
        self.result['reason']='waiting_for_signal'

    def _invalidate(self, reason, reset_config=False):
        source=self.config[2] if self.config else 'offline'
        self.result=self.model.base_result(source)
        self.result['reason']=reason
        self.buffer.clear();self.expected=None;self.last_inferred_index=None
        self.sequence+=1;self.segment+=1
        if reset_config:self.config=None

    def reset(self, reason='client_reset'):
        with self.lock:
            self._invalidate(reason,True);self.last_received=None
            return self.snapshot()

    def push(self, data):
        # Any malformed stream chunk invalidates the old output rather than
        # leaving a previously valid point visible after corrupted input.
        with self.lock:
            try:
                raw,fs,quality=validate_input(data,window=False)
                index=integer(data.get('sample_index'),'sample_index')
                integer(index+len(raw),'sample_end_index_exclusive')
            except (InputError,OverflowError):
                self._invalidate('invalid_chunk')
                raise
            now=self.clock();new_config=(fs,data['unit'],data['source'])
            discontinuity=None
            if self.config is not None and new_config!=self.config:
                self._invalidate('stream_config_changed',True)
                raise InputError('stream configuration changed; reset/new stream required before retry')
            if self.last_received is not None and now-self.last_received>STREAM_TTL_SECONDS:
                discontinuity='arrival_gap';self._invalidate(discontinuity)
            if self.expected is not None and index!=self.expected:
                self._invalidate('sample_index_discontinuity')
                raise InputError('sample_index is not the next expected index; buffer cleared, retry with a new session/reset')
            self.config=new_config;self.last_received=now
            self.expected=index+len(raw);self.sequence+=1
            if quality!=0:
                self._invalidate('quality_unknown' if quality is None else 'poor_contact')
                # Preserve sequence expectation even while contact is bad.
                self.expected=index+len(raw)
                return self.snapshot()
            self.buffer.extend(raw.tolist())
            while len(self.buffer)>5*fs:self.buffer.popleft()
            if len(self.buffer)<5*fs:
                self.result=self.model.base_result(data['source'],data.get('request_id'))
                self.result['reason']='warming_up'
            elif self.last_inferred_index is None or self.expected-self.last_inferred_index>=fs:
                try:
                    self.result=self.model._predict_uv(np.asarray(self.buffer),fs,data['source'],data.get('request_id'))
                except Exception:
                    self._invalidate('inference_error')
                    raise
                self.result.update(sample_start_index=self.expected-5*fs,sample_end_index_exclusive=self.expected,
                                   sample_time_end_unix_s=data.get('sample_time_end_unix_s'))
                self.last_inferred_index=self.expected
                if not self.result['valid']:
                    reason=self.result['reason'];self._invalidate(reason)
                    self.expected=index+len(raw)
            self.result.update(quality=quality,input_fs_hz=fs,input_unit=data['unit'])
            if discontinuity:self.result['discontinuity']=discontinuity
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            age=None if self.last_received is None else max(0.,self.clock()-self.last_received)
            if age is not None and age>STREAM_TTL_SECONDS and (self.buffer or self.result['valid']):
                self._invalidate('stream_stale')
            return {**self.result,'stream_id':self.stream_id,'sequence':self.sequence,'segment':self.segment,
                    'buffered_samples':len(self.buffer),'next_sample_index':self.expected,
                    'last_chunk_age_s':age,'stale_after_s':STREAM_TTL_SECONDS}
