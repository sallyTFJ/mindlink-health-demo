"""NeuroSky TGAM RAW serial to the documented stream endpoint.

Sample indices are host counters, not hardware packet sequence numbers.
Checksum/arrival/quality gating cannot prove detection of all radio losses.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json,time,uuid
from urllib.request import Request,urlopen
import serial
from eeg_decoder.thinkgear import PacketParser

def post(url,data):
    req=Request(url,data=json.dumps(data,allow_nan=False).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(req,timeout=5) as response:return json.load(response)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',required=True,help='e.g. COM5')
    ap.add_argument('--baud',type=int,default=57600);ap.add_argument('--url',default='http://127.0.0.1:8881')
    ap.add_argument('--stream-id',default=None);args=ap.parse_args()
    sid=args.stream_id or 'neurosky_'+uuid.uuid4().hex[:12]
    root=args.url.rstrip('/')+'/api/v1/streams/'+sid
    parser=PacketParser();queue=[];index=0;quality=None;quality_time=None;last_raw=None;last_flush=time.monotonic()
    print('Stream:',sid,'| close other software holding',args.port,flush=True)
    post(root+'/reset',{})
    try:
        with serial.Serial(args.port,args.baud,timeout=.1) as port:
            while True:
                data=port.read(4096);now=time.monotonic()
                if last_raw is not None and now-last_raw>.35:
                    post(root+'/reset',{});queue=[];quality=None;quality_time=None;last_raw=None
                    parser=PacketParser()
                for rows in parser.feed(data) if data else []:
                    if rows is None:
                        post(root+'/reset',{});queue=[];quality=None;quality_time=None;last_raw=None;continue
                    for code,value in rows:
                        if code==2 and len(value)==1:
                            changed=quality!=value[0];quality=value[0];quality_time=now
                            if changed:post(root+'/reset',{});queue=[]
                        elif code==0x80 and len(value)==2:
                            last_raw=now
                            if quality==0 and quality_time is not None and now-quality_time<=2:
                                queue.append(int.from_bytes(value,'big',signed=True))
                if quality_time is not None and now-quality_time>2:
                    quality=None;quality_time=None;queue=[];post(root+'/reset',{})
                if queue and (len(queue)>=128 or now-last_flush>=.25):
                    while queue:
                        chunk=queue[:128];del queue[:128]
                        payload={'samples':chunk,'fs_hz':512,'unit':'neurosky_counts','channel':'Fp1',
                                 'source':'device','quality':quality,'sample_index':index,
                                 'request_id':f'{sid}-{index}'}
                        response=post(root+'/samples',payload);index+=len(chunk)
                        if response.get('valid'):
                            print(f'attention={response["attention_score"]:.2f} valence={response["valence_score"]:.4f}',flush=True)
                    last_flush=now
    except KeyboardInterrupt:pass
    finally:
        try:post(root+'/reset',{})
        except Exception:pass

if __name__=='__main__':main()
