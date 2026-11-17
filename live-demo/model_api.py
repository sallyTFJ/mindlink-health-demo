"""Loopback HTTP/JSON adapter for the same portable EEG SDK."""
import argparse,json,re,threading,webbrowser,platform
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from eeg_decoder import EEGModel,EEGStream,InputError

ROOT=Path(__file__).resolve().parent
MAX_BODY=1024*1024

class App:
    def __init__(self,model):self.model=model;self.streams={};self.lock=threading.RLock()
    def stream(self,key,create=False):
        with self.lock:
            if key not in self.streams:
                if not create:raise KeyError(key)
                if len(self.streams)>=32:raise InputError('At most 32 streams; DELETE an unused stream first')
                self.streams[key]=EEGStream(self.model,key)
            return self.streams[key]
    def delete(self,key):
        with self.lock:
            if key not in self.streams:raise KeyError(key)
            # Reset referenced stream instances before removing the lookup.
            self.streams[key].reset('deleted');del self.streams[key]

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(10)
    def log_message(self,*args):pass
    def origin_ok(self):
        try:
            if urlsplit('http://'+self.headers.get('Host','')).hostname not in ('127.0.0.1','localhost','::1'):
                return False
        except ValueError:return False
        origin=self.headers.get('Origin')
        return origin is None or origin in self.server.allowed_origins
    def send(self,data,status=200,ctype='application/json; charset=utf-8'):
        body=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        origin=self.headers.get('Origin')
        if origin in self.server.allowed_origins:self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_OPTIONS(self):
        if not self.origin_ok():return self.send({'error':'origin_not_allowed'},403)
        self.send_response(204)
        if self.headers.get('Origin'):self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
        self.send_header('Access-Control-Allow-Methods','GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.send_header('Content-Length','0');self.end_headers()
    def route(self,method):
        if not self.origin_ok():return self.send({'error':'origin_not_allowed'},403)
        path=urlsplit(self.path).path;app=self.server.app
        try:
            data={}
            if method=='POST':
                if self.headers.get('Transfer-Encoding'):raise InputError('Chunked HTTP bodies are not supported; use Content-Length')
                if self.headers.get('Content-Type','').split(';')[0].lower()!='application/json':raise InputError('Content-Type must be application/json')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=MAX_BODY:raise InputError('JSON body must be 1..1048576 bytes')
                raw=self.rfile.read(size)
                if len(raw)!=size:raise InputError('Incomplete request body')
                data=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(InputError('Nonfinite JSON constant')))
                if not isinstance(data,dict):raise InputError('JSON object required')
            if method=='GET' and path=='/':return self.send(b'<html><meta charset=utf-8><h1>Local EEG Model API</h1><p>See docs/API.md. Dashboard: http://127.0.0.1:9080/</p></html>',ctype='text/html; charset=utf-8')
            if method=='GET' and path=='/example-input.json':return self.send((ROOT/'examples/attention_window.json').read_bytes())
            if method=='GET' and path=='/api/v1/health':return self.send({'status':'ok','schema_version':'1.0','model_version':app.model.manifest['model_version'],'fold':app.model.fold,'provider':'CPUExecutionProvider','platform':platform.system(),'hardware_efficacy_validated':False})
            if method=='GET' and path=='/api/v1/model':return self.send(app.model.manifest)
            if method=='GET' and path=='/api/v1/streams':
                with app.lock:keys=list(app.streams)
                return self.send({'stream_ids':keys})
            if method=='GET' and path=='/api/v1/ports':
                from serial.tools.list_ports import comports
                return self.send({'ports':[{'port':p.device,'description':p.description} for p in comports()]})
            if method=='GET' and path=='/openapi.json':return self.send((ROOT/'docs/model_openapi.json').read_bytes())
            if method=='POST' and path=='/api/v1/infer':return self.send(app.model.infer_window(data))
            match=re.fullmatch(r'/api/v1/streams/([A-Za-z0-9_-]{1,64})(?:/(samples|state|reset))?',path)
            if match:
                sid,action=match.groups()
                if method=='DELETE' and action is None:
                    app.delete(sid);return self.send({'deleted':sid})
                if method=='POST' and action=='samples':return self.send(app.stream(sid,True).push(data))
                if method=='POST' and action=='reset':return self.send(app.stream(sid,True).reset())
                if method=='GET' and action=='state':return self.send(app.stream(sid).snapshot())
            return self.send({'error':'not_found'},404)
        except KeyError:return self.send({'error':'stream_not_found'},404)
        except (InputError,ValueError,TypeError,OverflowError,UnicodeError) as exc:
            bad_stream=re.fullmatch(r'/api/v1/streams/([A-Za-z0-9_-]{1,64})/samples',path)
            if bad_stream:
                try:app.stream(bad_stream.group(1)).reset('invalid_request')
                except KeyError:pass
            return self.send({'error':'invalid_request','detail':str(exc)},400)
        except Exception as exc:
            failed_stream=re.fullmatch(r'/api/v1/streams/([A-Za-z0-9_-]{1,64})/samples',path)
            if failed_stream:
                try:app.stream(failed_stream.group(1)).reset('inference_error')
                except KeyError:pass
            print(f'Inference server error: {type(exc).__name__}: {exc}',flush=True)
            return self.send({'error':'internal_error','detail':'See server terminal; no prediction returned'},500)
    def do_GET(self):self.route('GET')
    def do_POST(self):self.route('POST')
    def do_DELETE(self):self.route('DELETE')

def make_server(port=8881,fold=0,allow_origins=()):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True;server.app=App(EEGModel(fold=fold))
    server.allowed_origins={f'http://127.0.0.1:{server.server_port}',f'http://localhost:{server.server_port}',*allow_origins}
    return server

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8881);ap.add_argument('--fold',type=int,choices=range(5),default=0)
    ap.add_argument('--no-browser',action='store_true');ap.add_argument('--allow-origin',action='append',default=[])
    args=ap.parse_args();server=make_server(args.port,args.fold,args.allow_origin)
    url=f'http://127.0.0.1:{server.server_port}';print(f'NeuroEcho EEG API: {url} | fixed fold {args.fold}',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
