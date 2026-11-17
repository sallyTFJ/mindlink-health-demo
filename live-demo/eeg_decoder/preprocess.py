"""Identical trailing-window preprocessing in training and deployment.

All operations use only the five seconds available at prediction time.
One second is filter warm-up; the final four seconds enter the model.
No multi-electrode referencing, ICA, cross-window normalization or future data.
"""
import numpy as np
from scipy import signal
from math import gcd

FS=128
BUFFER_SECONDS=5
WINDOW_SECONDS=4
N_SAMPLES=FS*WINDOW_SECONDS
SOS=signal.butter(4,[1,40],btype='bandpass',fs=FS,output='sos')

def prepare_window(raw,fs):
    raw=np.asarray(raw,dtype=np.float64)
    fs=int(fs)
    if raw.ndim!=1 or len(raw)!=fs*BUFFER_SECONDS:
        raise ValueError('Expected exactly five seconds of one-channel EEG')
    if not np.isfinite(raw).all():return None,'nonfinite'
    if np.ptp(raw)<0.1:return None,'flat'
    g=gcd(fs,FS)
    y=signal.resample_poly(raw-raw[0],FS//g,fs//g)
    y=signal.sosfilt(SOS,y)[FS:]
    y=y-y.mean()
    sd=float(y.std())
    if sd<0.5:return None,'flat_filtered'
    if sd>100 or np.ptp(y)>600 or np.max(np.abs(np.diff(y)))>150:return None,'artifact'
    return y.astype('float32'),'ok'

def features(wave):
    """Window-local spectrum and shape; supports [..., 512]."""
    x=np.asarray(wave,dtype=np.float64)
    f,p=signal.welch(x,fs=FS,nperseg=256,noverlap=128,axis=-1)
    mask=(f>=1)&(f<=40);p=p[...,mask];f=f[mask]
    p=np.maximum(p,1e-12);total=p.sum(axis=-1,keepdims=True)
    rel=p/total
    bands=np.stack([np.sum(rel[...,(f>=lo)&(f<hi)],axis=-1) for lo,hi in [(1,4),(4,8),(8,13),(13,30),(30,40.1)]],axis=-1)
    var=np.var(x,axis=-1)+1e-12;d=np.diff(x,axis=-1);vd=np.var(d,axis=-1)+1e-12
    mobility=np.sqrt(vd/var);complexity=np.sqrt((np.var(np.diff(d,axis=-1),axis=-1)+1e-12)/vd)/mobility
    z=x/np.sqrt(var)[...,None]
    shape=np.stack([np.log(var),mobility,complexity,np.mean(z**3,axis=-1),
                    np.mean(z**4,axis=-1),-np.sum(rel*np.log(rel),axis=-1)],axis=-1)
    return np.concatenate([np.log(rel),np.log(bands+1e-12),shape],axis=-1).astype('float32')

def normalize_wave(wave):
    x=np.asarray(wave,dtype=np.float32)
    return np.clip((x-x.mean(axis=-1,keepdims=True))/(x.std(axis=-1,keepdims=True)+1e-6),-8,8).astype('float32')
