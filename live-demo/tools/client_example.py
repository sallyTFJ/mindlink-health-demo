"""A teammate's local/LAN client. No embedded key or former service address."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--url',default='http://127.0.0.1:9080')
    ap.add_argument('--token-file',required=True);ap.add_argument('--input');ap.add_argument('--watch',action='store_true');a=ap.parse_args()
    token=Path(a.token_file).read_text().strip()
    while True:
        data=json.loads(Path(a.input).read_text()) if a.input else None
        req=urllib.request.Request(a.url.rstrip('/')+('/api/v1/infer' if data else '/api/state'),data=json.dumps(data).encode() if data else None,
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=5) as r:result=json.load(r)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if not a.watch:break
        time.sleep(5)

if __name__=='__main__':main()
