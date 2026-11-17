"""ThinkGear packets and conservative 512-Hz raw stream quality gate.
Specification: developer.neurosky.com/docs/doku.php?id=thinkgear_communications_protocol
"""
from collections import deque
import time
import numpy as np

UV_PER_COUNT=1.8/4096/2000*1e6

class PacketParser:
    def __init__(self):self.buffer=bytearray()
    def feed(self,data):
        self.buffer.extend(data);packets=[]
        while True:
            start=self.buffer.find(b'\xaa\xaa')
            if start<0:
                if len(self.buffer)>1:packets.append(None)
                if self.buffer[-1:]==b'\xaa':self.buffer[:]=b'\xaa'
                else:self.buffer.clear()
                break
            if start:del self.buffer[:start];packets.append(None)
            if len(self.buffer)<3:break
            n=self.buffer[2]
            if n>169:del self.buffer[0];packets.append(None);continue
            if len(self.buffer)<n+4:break
            payload=bytes(self.buffer[3:3+n]);checksum=self.buffer[n+3];del self.buffer[:n+4]
            if ((sum(payload)&255)^255)!=checksum:packets.append(None);continue
            rows=[];i=0;valid=True
            while i<len(payload):
                level=0
                while i<len(payload) and payload[i]==0x55:level+=1;i+=1
                if i>=len(payload):valid=False;break
                code=payload[i];i+=1
                if code>=0x80:
                    if i>=len(payload):valid=False;break
                    length=payload[i];i+=1
                else:length=1
                if i+length>len(payload):valid=False;break
                if level==0:rows.append((code,payload[i:i+length]))
                i+=length
            packets.append(rows if valid else None)
        return packets

class RawBuffer:
    def __init__(self):
        self.values=deque(maxlen=2560);self.last_raw=None;self.quality=None;self.quality_time=None
        self.generation=0;self.total=0;self.reason='waiting_for_signal';self.esense=None;self.esense_time=None
    def reset(self,reason):
        self.values.clear();self.generation+=1;self.reason=reason
        self.quality=None;self.quality_time=None;self.last_raw=None;self.esense=None;self.esense_time=None
    def ingest(self,packets,now=None):
        now=time.monotonic() if now is None else now;record=[]
        if self.last_raw is not None and now-self.last_raw>.35:self.reset('stream_gap')
        for rows in packets:
            if rows is None:self.reset('bad_packet');continue
            for code,value in rows:
                if code==2 and len(value)==1:
                    self.quality=value[0];self.quality_time=now
                    if self.quality!=0:self.values.clear();self.generation+=1;self.reason='poor_contact'
                elif code==4 and len(value)==1:
                    self.esense=int(value[0]) if value[0] else None;self.esense_time=now
                elif code==0x80 and len(value)==2:
                    raw=int.from_bytes(value,'big',signed=True);self.total+=1;self.last_raw=now
                    valid=self.quality==0 and self.quality_time is not None and now-self.quality_time<=2
                    record.append([now,raw,self.quality,valid,self.generation,self.total])
                    if valid:self.values.append(raw*UV_PER_COUNT);self.reason='warming_up' if len(self.values)<2560 else 'ready'
                    else:self.values.clear();self.reason='quality_unknown_or_bad'
        return record
    def snapshot(self,now=None):
        now=time.monotonic() if now is None else now
        if self.last_raw is None or now-self.last_raw>1:return None,'signal_stale'
        if self.quality!=0 or self.quality_time is None or now-self.quality_time>2:return None,'quality_unknown_or_bad'
        if len(self.values)<2560:return None,'warming_up'
        return np.asarray(self.values,dtype='float32'),None
