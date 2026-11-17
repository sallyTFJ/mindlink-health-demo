import copy
import json
import math
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

import numpy as np
from scipy.signal import welch
from eeg_decoder.sdk import EEGModel
from eeg_decoder.thinkgear import PacketParser, RawBuffer
from .coach import SupportCoach
from .signals import eeg_window, display_wave
from .storage import Ledger
from .wearable import WearableTail

def get_json(url):
    with urllib.request.urlopen(url,timeout=2) as r:
        raw=r.read(2_000_001)
    if len(raw)>2_000_000: raise ValueError('response_too_large')
    return json.loads(raw)

class Runtime:
    def __init__(self,root,cfg):
        self.root=Path(root); self.cfg=cfg; self.lock=threading.RLock(); self.stop=threading.Event()
        self.ledger=Ledger(root); self.model=EEGModel(self.root/'models')
        self.wearable=WearableTail(self.root/cfg['heart_rate_file']); self.coach=SupportCoach()
        self.demo_mode=bool(cfg.get('demo_mode',False)); self.demo_started=time.time()
        self.eeg={'valid':False,'reason':'waiting_for_eeg','total':0,'quality':None,'raw':[], 'envelope':[]}
        self.decoded={'valid':False,'reason':'waiting_for_contiguous_5_seconds'}
        self.generation=0; self.window=None; self.raw_at=0; self.window_id=None
        self.smooth=None; self.smooth_at=0; self.bands=deque(maxlen=60)
        self.last_heart_id=None

    def start(self):
        if self.demo_mode:
            return
        reader={'serial':self._serial,'http':self._http,'disabled':self._disabled}[self.cfg['eeg_mode']]
        jobs=[reader,self._decode,self._wearable]
        for fn in jobs: threading.Thread(target=fn,daemon=True,name=fn.__name__).start()

    def invalidate(self,reason):
        with self.lock:
            self.generation+=1; self.window=None; self.smooth=None
            self.decoded={'valid':False,'reason':reason}
            self.eeg.update(valid=False,reason=reason,raw=[],envelope=[])
            self.bands.clear()

    def _publish(self,raw,quality,total,source,window,identity,reason=None,reported_age=0):
        now=time.time()
        with self.lock:
            if identity==self.window_id: return
            if self.window_id is not None and identity[0]!=self.window_id[0]:
                self.invalidate('eeg_session_changed')
            elif self.window_id is not None and type(total) is int and type(self.eeg.get('total')) is int and total<self.eeg['total']:
                self.invalidate('sample_counter_reset')
            self.window_id=identity; self.raw_at=now-reported_age
            if window is None:
                self.generation+=1; self.smooth=None
                self.decoded={'valid':False,'reason':reason or 'poor_contact_or_warming_up'}
            self.window=window
            vals=raw[-2560:]
            wave=display_wave({'raw_original':vals,'times':[i/512 for i in range(len(vals))]})
            self.eeg={'valid':True,'reason':reason,'source':source,'quality':quality,'total':total,
                'unit':'neurosky_counts','sampling_hz':512,'raw':wave['raw'][::4],
                'envelope':wave['envelope'][::4],'display_stride':4,
                'display_includes_noise':True,'updated_at':self.raw_at,
                'time_basis':'host_receipt_minus_reported_age' if source=='existing_eeg_http' else 'host_serial_receipt'}
            if len(vals)>=1024 and all(v is not None for v in vals[-1024:]):
                freq,power=welch(np.asarray(vals[-1024:],float),fs=512,nperseg=512)
                denom=float(power[(freq>=1)&(freq<45)].sum())
                v=[float(power[(freq>=a)&(freq<b)].sum()/denom) if denom>0 else 0 for a,b in [(1,4),(4,8),(8,13),(13,30),(30,45)]]
                if not self.bands or now-self.bands[-1]['t']>=.9:
                    self.bands.append({'t':now,'relative_power':v,'quality':quality})

    def _http(self):
        while not self.stop.is_set():
            try:
                d=get_json(self.cfg['eeg_http_url'])
                if not isinstance(d,dict): raise ValueError('invalid_eeg_state')
                window,reason=eeg_window(d)
                if d.get('live') is not True or d.get('connected') is not True or not isinstance(d.get('age'),(int,float)) or not 0<=d['age']<=1.5:
                    self.invalidate('eeg_upstream_stale')
                else:
                    vals=d.get('raw_original',[])
                    vals=[v if type(v) is int and -32768<=v<=32767 else None for v in vals[-2560:]]
                    self._publish(vals,d.get('quality'),d.get('total'), 'existing_eeg_http',window,(d.get('session_id'),d.get('total')),reason,d['age'])
            except Exception as e: self.invalidate('eeg_http_unavailable:'+type(e).__name__)
            self.stop.wait(.4)

    def _serial(self):
        import serial
        while not self.stop.is_set():
            try:
                self.invalidate('opening_serial')
                with serial.Serial(self.cfg['eeg_com'],self.cfg['eeg_baud'],timeout=.2) as ser:
                    parser=PacketParser(); buf=RawBuffer(); display=deque(maxlen=2560)
                    last_byte=last_raw=last_publish=time.monotonic(); serial_epoch=time.time()
                    while not self.stop.is_set():
                        chunk=ser.read(4096); now=time.monotonic()
                        if chunk:last_byte=now
                        records=buf.ingest(parser.feed(chunk),now=now)
                        if records:
                            if now-last_raw>.35: display.clear(); self.invalidate('serial_gap')
                            for row in records: display.append(int(row[1]))
                            last_raw=now
                        if now-last_raw>1.5:self.invalidate('no_raw_samples')
                        if now-last_raw>8: raise TimeoutError('no_raw_for_8s')
                        if records and now-last_publish>=.2:
                            samples,reason=buf.snapshot(now=now)
                            # SDK performs the same counts-to-uV conversion once.
                            win=list(display) if samples is not None and len(display)==2560 else None
                            self._publish(list(display),buf.quality,buf.total,'serial',win,(serial_epoch,buf.total),reason)
                            with self.lock:self.eeg.update(last_byte_age_s=now-last_byte,com=self.cfg['eeg_com'])
                            last_publish=now
            except Exception as e:
                self.invalidate('serial_error:'+type(e).__name__)
                self.stop.wait(2)

    def _decode(self):
        last_id=None
        while not self.stop.is_set():
            with self.lock:
                window=copy.deepcopy(self.window); epoch=self.generation; ident=self.window_id; stamp=self.raw_at
            if window and ident!=last_id and time.time()-stamp<1.5:
                try:
                    result=self.model.infer_window({'fs_hz':512,'channel':'Fp1','unit':'neurosky_counts',
                        'source':'external_live' if self.cfg['eeg_mode']=='http' else 'device',
                        'quality':0,'samples':window,'sample_time_end_unix_s':stamp})
                    result['sample_time_end_unix_s']=stamp
                    with self.lock:
                        if epoch==self.generation and self.window is not None and time.time()-self.raw_at<1.5:
                            if result['valid']:
                                xy={'x':result['valence_score'],'y':result['attention_score']}; now=time.time()
                                alpha=1-math.exp(-max(0,now-self.smooth_at)/10)
                                self.smooth=xy if self.smooth is None else {k:self.smooth[k]+alpha*(xy[k]-self.smooth[k]) for k in xy}
                                self.smooth_at=now; result['display_xy']=self.smooth.copy()
                            self.decoded=result
                            self.ledger.add('eeg',result)
                    last_id=ident
                except Exception as e:
                    with self.lock:self.decoded={'valid':False,'reason':'decoder_error:'+type(e).__name__}
            self.stop.wait(max(1,float(self.cfg['decode_interval_s'])))

    def _wearable(self):
        while not self.stop.is_set():
            try:
                self.wearable.poll(); d=self.wearable.snapshot()['heart_rate']
                if d.get('valid') and d.get('received_unix_ms')!=self.last_heart_id:
                    self.ledger.add('heart_rate',d); self.last_heart_id=d['received_unix_ms']
            except (OSError,ValueError): pass
            self.stop.wait(.5)

    def _disabled(self):
        self.invalidate('eeg_input_disabled')

    def record_check_in(self,kind,note=''):
        event=self.coach.check_in(kind,note)
        self.ledger.add('check_in',event)
        return event

    def record_wearable(self,event):
        saved=self.wearable.append(event)
        self.wearable.poll()
        self.ledger.add(saved['event_type'],saved)
        return saved

    def _demo_state(self,now):
        """Clearly labelled synthetic stream for judge demos without hardware."""
        elapsed=max(0,now-self.demo_started)
        bpm=int(round(72+4*math.sin(elapsed/8)+2*math.sin(elapsed/2.7)))
        attention=68+10*math.sin(elapsed/13)
        valence=.28+.14*math.sin(elapsed/17)
        raw=[]; envelope=[]
        for i in range(640):
            t=elapsed+i/128
            value=120*math.sin(2*math.pi*10.2*t)+38*math.sin(2*math.pi*5.1*t)+14*math.sin(2*math.pi*22*t)
            raw.append(round(value,2)); envelope.append(round(abs(value)*.72+42,2))
        history=[]
        for i in range(36):
            t=now-(35-i)
            alpha=.34+.08*math.sin((elapsed+i)/7)
            history.append({'t':t,'relative_power':[.12,.18,alpha,.28,.08],'quality':0})
        heart_history=[{'t':now-(29-i)*2,'bpm':int(round(72+4*math.sin((elapsed+i)/8)))} for i in range(30)]
        state={'schema_version':'mindlink.state.v2','generated_at':now,'mode':'demo_simulation',
            'eeg':{'valid':True,'reason':None,'source':'demo_simulation','quality':0,'total':int(elapsed*512),
                'unit':'synthetic_display_units','sampling_hz':512,'raw':raw,'envelope':envelope,'display_stride':4,
                'display_includes_noise':False,'updated_at':now,'age_s':0},
            'brain_state':{'valid':True,'reason':None,'source':'demo_simulation','attention_score':attention,
                'valence_score':valence,'display_xy':{'x':valence,'y':attention},'state_xy':{'x':valence,'y':attention},
                'sample_time_end_unix_s':now,'score_semantics':'Synthetic demo values; not a person or a diagnosis.'},
            'band_history':history,'band_names':['δ 1–4','θ 4–8','α 8–13','β 13–30','γ 30–45'],
            'heart_rate':{'valid':True,'reason':None,'bpm':bpm,'age_s':0,'source':'demo_watch','event_id':str(int(now)),
                'received_unix_ms':int(now*1000),'sensor_contact':True,'history':heart_history,
                'measurement_kind':'synthetic_demo_heart_rate'},
            'blood_pressure':{'valid':True,'reason':None,'systolic':118,'diastolic':76,'source':'demo_watch','age_s':0,'history':[]},
            'spo2':{'valid':True,'reason':None,'percent':98,'source':'demo_watch','age_s':0,'history':[]},
            'ecg':{'valid':False,'reason':'raw_ecg_not_integrated','samples':None},
            'semantics':'All values in demo_simulation mode are synthetic and must not be presented as measured data.'}
        state['support']=self.coach.assess(state,now)
        state['wellness_score']=int(round(max(0,min(100,80+valence*12-(abs(bpm-72)*.35)))))
        return state

    def state(self):
        now=time.time()
        if self.demo_mode:
            return self._demo_state(now)
        with self.lock:
            eeg=copy.deepcopy(self.eeg); decoded=copy.deepcopy(self.decoded)
            age=now-self.raw_at if self.raw_at else None
            if age is None or age>1.5:
                eeg.update(valid=False,raw=[],envelope=[])
                decoded={'valid':False,'reason':'eeg_stale'}
            eeg['age_s']=age
            if decoded.get('valid') and now-decoded.get('sample_time_end_unix_s',0)>max(12,float(self.cfg['decode_interval_s'])*2):
                decoded={'valid':False,'reason':'decoder_stale'}
            wearable=self.wearable.snapshot(now)
            state={'schema_version':'mindlink.state.v2','generated_at':now,'mode':'live_hardware','eeg':eeg,'brain_state':decoded,
                'band_history':list(self.bands) if eeg['valid'] else [],'band_names':['δ 1–4','θ 4–8','α 8–13','β 13–30','γ 30–45'],
                **wearable,'ecg':{'valid':False,'reason':'raw_ecg_not_integrated','samples':None},
                'semantics':'Research estimates are uncalibrated. valid indicates protocol and freshness only.'}
            state['support']=self.coach.assess(state,now)
            hr=state['heart_rate'].get('bpm') if state['heart_rate'].get('valid') else None
            valence=decoded.get('valence_score') if decoded.get('valid') else None
            state['wellness_score']=None if hr is None and valence is None else int(round(max(0,min(100,
                72+(float(valence) if valence is not None else 0)*12-(abs(float(hr)-72)*.35 if hr is not None else 0)))))
            return state
