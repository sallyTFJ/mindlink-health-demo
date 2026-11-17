import json,sys,threading,unittest,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import model_api
class OptionalAPITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=model_api.make_server(0);cls.url='http://127.0.0.1:'+str(cls.server.server_port)
  threading.Thread(target=cls.server.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def request(self,path,data=None,headers=None,method=None):
  h={'Content-Type':'application/json'};h.update(headers or {})
  req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=h,method=method)
  try:
   with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
 def test_block_dns_host(self):self.assertEqual(self.request('/api/v1/health',headers={'Host':'untrusted.example'})[0],403)
 def test_stream_contiguity_and_reset(self):
  d=json.loads((ROOT/'examples/attention_window.json').read_text());fs=d['fs_hz'];raw=d.pop('samples');d['source']='offline'
  for i in range(5):
   status,r=self.request('/api/v1/streams/check/samples',{**d,'sample_index':i*fs,'samples':raw[i*fs:(i+1)*fs]})
   self.assertEqual(status,200);self.assertEqual(r['valid'],i==4)
  self.assertAlmostEqual(r['attention_score'],44.256985,places=4)
  status,r=self.request('/api/v1/streams/check/samples',{**d,'sample_index':1,'samples':raw[:fs]})
  self.assertEqual(status,400)
  self.assertFalse(self.request('/api/v1/streams/check/state')[1]['valid'])
  self.assertEqual(self.request('/api/v1/streams/check',method='DELETE')[0],200)
