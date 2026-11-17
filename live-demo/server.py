"""Portable local EEG/heart-rate handoff. No former cloud accounts or API clients."""
import argparse
import hmac
import ipaddress
import json
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from eeg_decoder import InputError

ROOT=Path(__file__).resolve().parent

def handler(runtime,token):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def log_message(self,*args):pass
        def send(self,value,status=200,mime='application/json; charset=utf-8'):
            raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode() if mime.startswith('application/json') else value
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
        def json_body(self,limit=1048576):
            if self.headers.get('Transfer-Encoding'):raise ValueError('use_content_length')
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=limit:raise ValueError(f'body_1_to_{limit}_bytes')
            if self.headers.get_content_type()!='application/json':raise ValueError('application_json_required')
            raw=self.rfile.read(n)
            if len(raw)!=n:raise ValueError('incomplete_body')
            return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite_json')))
        def host_ok(self):
            try:
                host=urllib.parse.urlsplit('http://'+self.headers.get('Host','')).hostname
                if host=='localhost':return True
                ipaddress.ip_address(host);return True
            except ValueError:return False
        def origin_ok(self):
            return self.headers.get('Origin') in (None,'http://'+self.headers.get('Host',''))
        def auth(self):
            return self.host_ok() and self.origin_ok() and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
        def do_GET(self):
            path=urllib.parse.urlsplit(self.path).path
            if not self.host_ok():return self.send({'error':'invalid_host'},403)
            static={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if path in static:
                name,mime=static[path];return self.send((ROOT/'web'/name).read_bytes(),mime=mime)
            if path=='/api/bootstrap':
                if self.client_address[0] not in ('127.0.0.1','::1') or not self.origin_ok():return self.send({'error':'local_only'},403)
                return self.send({'token':token,'config':runtime.cfg})
            if not self.auth():return self.send({'error':'bearer_token_required'},401)
            if path=='/api/example-input':
                sample=json.loads((ROOT/'examples/attention_window.json').read_text())
                sample['source']='offline';return self.send(sample)
            if path=='/api/state':return self.send(runtime.state())
            if path=='/api/ports':
                from serial.tools import list_ports
                return self.send({'ports':[{'port':p.device,'description':p.description} for p in list_ports.comports()],'serial_opened':False})
            if path=='/api/v1/model':return self.send(runtime.model.manifest)
            if path=='/api/v1/health':return self.send({'status':'ok','schema_version':'mindlink.state.v2','cloud_dependency':False,'hardware_efficacy_validated':False})
            return self.send({'error':'not_found'},404)
        def do_POST(self):
            if not self.auth():return self.send({'error':'bearer_token_required'},401)
            path=urllib.parse.urlsplit(self.path).path
            try:
                if path=='/api/v1/infer':return self.send(runtime.model.infer_window(self.json_body()))
                if path=='/api/v1/check-in':
                    data=self.json_body(8192)
                    return self.send({'ok':True,'check_in':runtime.record_check_in(data.get('kind'),data.get('note',''))})
                if path=='/api/v1/wearable':
                    return self.send({'ok':True,'event':runtime.record_wearable(self.json_body(16384))})
                return self.send({'error':'not_found'},404)
            except (InputError,ValueError,TypeError) as e:return self.send({'error':'invalid_request','detail':str(e)[:250]},400)
            except Exception as e:return self.send({'error':'inference_failed','type':type(e).__name__},500)
    return Handler

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--no-browser',action='store_true')
    ap.add_argument('--demo',action='store_true',help='Use clearly labelled synthetic data; never opens EEG or BLE hardware')
    args=ap.parse_args()
    from app.runtime import Runtime
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    if args.demo:cfg['demo_mode']=True
    if cfg['eeg_mode'] not in ('disabled','serial','http'):raise ValueError('eeg_mode must be disabled, serial or http')
    cfg['decode_interval_s']=max(5,min(10,float(cfg['decode_interval_s'])))
    folder=ROOT/'private';folder.mkdir(exist_ok=True);path=folder/'api.token'
    if not path.exists():path.write_text(secrets.token_urlsafe(32),encoding='utf-8')
    token=path.read_text().strip()
    if len(token)<24:raise ValueError('local API token must be at least 24 characters')
    rt=Runtime(ROOT,cfg);srv=ThreadingHTTPServer((cfg['host'],int(cfg['port'])),handler(rt,token))
    rt.start();url=f"http://127.0.0.1:{cfg['port']}/";print('Biosignal Team Kit:',url,flush=True)
    print('Mode:', 'SYNTHETIC DEMO' if rt.demo_mode else 'LIVE HARDWARE',flush=True)
    print('No cloud account required. Keep this window open; Ctrl+C stops this application.',flush=True)
    if not args.no_browser:threading.Timer(1,lambda:webbrowser.open(url)).start()
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:rt.stop.set();srv.server_close()

if __name__=='__main__':main()
