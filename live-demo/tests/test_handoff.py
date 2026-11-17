import copy,json,shutil,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.runtime import Runtime
from app.coach import SupportCoach
from app.signals import HeartTail,eeg_window
from app.wearable import WearableTail
from eeg_decoder import EEGModel,EEGStream,InputError
from eeg_decoder.thinkgear import PacketParser
from heartcast import decode_hr
from server import handler

class KitTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);shutil.copytree(ROOT/'models',cls.root/'models')
  cls.rt=Runtime(cls.root,json.loads((ROOT/'config.json').read_text()));cls.token='test-token-not-a-shipped-credential'
  cls.srv=ThreadingHTTPServer(('127.0.0.1',0),handler(cls.rt,cls.token));cls.url='http://127.0.0.1:'+str(cls.srv.server_port)
  threading.Thread(target=cls.srv.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.srv.shutdown();cls.srv.server_close();cls.rt.ledger.db.close();cls.tmp.cleanup()
 def req(self,path,data=None,auth=True,headers=None):
  h={'Content-Type':'application/json'}
  if auth:h['Authorization']='Bearer '+self.token
  h.update(headers or {})
  req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
  try:
   with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
 def test_default_no_com_open(self):self.assertEqual(self.rt.cfg['eeg_mode'],'disabled')
 def test_samples_match_original_scores(self):
  for task in ['attention','valence']:
   d=json.loads((ROOT/'examples'/f'{task}_window.json').read_text());r=self.rt.model.infer_window(d)
   expected=json.loads((ROOT/'examples'/f'{task}_expected_output.json').read_text());self.assertTrue(r['valid'])
   for f in ['attention_score','valence_score']:self.assertAlmostEqual(r[f],expected[f],places=4)
 def test_all_fold_models_load(self):
  for i in range(5):self.assertEqual(EEGModel(ROOT/'models',fold=i).fold,i)
 def test_source_required(self):
  d=json.loads((ROOT/'examples/attention_window.json').read_text());d.pop('source')
  with self.assertRaises(InputError):self.rt.model.infer_window(d)
 def test_bad_quality_model_invalid(self):
  d=json.loads((ROOT/'examples/attention_window.json').read_text());d['quality']=200
  self.assertFalse(self.rt.model.infer_window(d)['valid'])
 def test_noise_wave_still_visible(self):
  self.rt._publish([100]*2560,200,1,'test',None,('test',time.time()),'poor_contact');s=self.rt.state()
  self.assertTrue(s['eeg']['valid']);self.assertEqual(len(s['eeg']['raw']),640);self.assertFalse(s['brain_state']['valid'])
 def test_stale_wave_invalid(self):
  self.rt.raw_at=time.time()-2;s=self.rt.state();self.assertFalse(s['eeg']['valid']);self.assertFalse(s['brain_state']['valid']);self.assertEqual(s['band_history'],[])
 def test_session_change_clears_old_prediction(self):
  self.rt._publish([100]*2560,0,2560,'test',[100]*2560,('subject_a',2560))
  self.rt.decoded={'valid':True,'attention_score':90};self.rt.smooth={'x':.7,'y':90};epoch=self.rt.generation
  self.rt._publish([110]*2560,0,2560,'test',[110]*2560,('subject_b',2560))
  self.assertGreater(self.rt.generation,epoch);self.assertFalse(self.rt.decoded['valid']);self.assertIsNone(self.rt.smooth)
 def test_upstream_age_is_preserved(self):
  self.rt._publish([100]*2560,0,3000,'existing_eeg_http',[100]*2560,('age_test',3000),reported_age=.9)
  self.assertGreaterEqual(self.rt.state()['eeg']['age_s'],.9)
 def test_no_business_or_cloud_fields(self):
  s=self.rt.state()
  for k in ['robot','screen','decision','gateway_url','api_key']:self.assertNotIn(k,s)
  self.assertEqual(s['schema_version'],'mindlink.state.v2');self.assertIn('support',s)
 def test_hr_8bit(self):self.assertEqual(decode_hr(bytes([6,72])),(72,True))
 def test_hr_16bit(self):self.assertEqual(decode_hr(bytes([1,180,0])),(180,None))
 def test_bad_hr_packet(self):
  with self.assertRaises(ValueError):decode_hr(bytes([1,180]))
 def test_heart_fresh_then_stale(self):
  path=self.root/'data/test-heart.jsonl';event={'event_type':'wearable.hr','received_unix_ms':1000000,'source':'test','usable_for_adaptation':True,'data':{'bpm':72,'sensor_contact':True}}
  path.write_text(json.dumps(event)+'\n');h=HeartTail(path);h.poll(now=10,wall=1000);self.assertTrue(h.snapshot(now=11)['valid']);self.assertFalse(h.snapshot(now=26)['valid'])
 def test_wearable_multi_metric(self):
  path=self.root/'data/wearable.jsonl';w=WearableTail(path);now=int(time.time()*1000)
  w.append({'event_type':'wearable.hr','received_unix_ms':now,'source':'test','data':{'bpm':74,'sensor_contact':True}})
  w.append({'event_type':'wearable.bp','received_unix_ms':now+1,'source':'test','data':{'systolic':118,'diastolic':76}})
  w.poll();s=w.snapshot();self.assertTrue(s['heart_rate']['valid']);self.assertEqual(s['heart_rate']['bpm'],74)
  self.assertTrue(s['blood_pressure']['valid']);self.assertEqual(s['blood_pressure']['systolic'],118)
 def test_support_urgent_only_from_self_report(self):
  coach=SupportCoach();empty={'eeg':{'valid':False},'brain_state':{'valid':False},'heart_rate':{'valid':False}}
  self.assertNotEqual(coach.assess(empty)['level'],'urgent')
  coach.check_in('unsafe');urgent=coach.assess(empty);self.assertEqual(urgent['level'],'urgent');self.assertFalse(urgent['can_diagnose'])
  self.assertFalse(urgent['stimulation']['automatic_control'])
 def test_support_celebrates_completed_task(self):
  coach=SupportCoach();coach.check_in('task_complete')
  support=coach.assess({'eeg':{'valid':False},'brain_state':{'valid':False},'heart_rate':{'valid':False}})
  self.assertEqual(support['level'],'celebrate')
 def test_duplicate_hr_does_not_refresh(self):
  path=self.root/'data/duplicate.jsonl';e={'event_type':'wearable.hr','received_unix_ms':1000000,'data':{'bpm':72}}
  path.write_text(json.dumps(e)+'\n');h=HeartTail(path);h.poll(now=10,wall=1000)
  with path.open('a') as f:f.write(json.dumps(e)+'\n')
  h.poll(now=30,wall=1020);self.assertFalse(h.snapshot(now=30)['valid'])
 def test_parser_checksum(self):
  p=b'\x80\x02\x00\x7b';frame=b'\xaa\xaa'+bytes([len(p)])+p+bytes([255-(sum(p)&255)])
  self.assertEqual(PacketParser().feed(frame),[[(128,b'\x00\x7b')]]);self.assertEqual(PacketParser().feed(frame[:-1]+b'\x00'),[None])
 def test_api_auth(self):self.assertEqual(self.req('/api/state',auth=False)[0],401)
 def test_bad_host(self):self.assertEqual(self.req('/api/bootstrap',headers={'Host':'other.invalid'})[0],403)
 def test_cross_origin(self):self.assertEqual(self.req('/api/state',headers={'Origin':'http://other.invalid'})[0],401)
 def test_api_routes(self):
  for p in ['/api/state','/api/v1/model','/api/v1/health','/api/ports','/api/example-input']:self.assertEqual(self.req(p)[0],200,p)
 def test_offline_infer_api_does_not_set_live(self):
  d=json.loads((ROOT/'examples/attention_window.json').read_text());d['source']='offline'
  before=copy.deepcopy(self.rt.decoded);status,r=self.req('/api/v1/infer',d)
  self.assertEqual(status,200);self.assertTrue(r['valid']);self.assertEqual(r['source'],'offline');self.assertEqual(before,self.rt.decoded)
 def test_bad_infer_request(self):self.assertEqual(self.req('/api/v1/infer',{})[0],400)
 def test_check_in_api(self):
  status,result=self.req('/api/v1/check-in',{'kind':'tense'});self.assertEqual(status,200);self.assertEqual(result['check_in']['kind'],'tense')
 def test_wearable_api(self):
  status,result=self.req('/api/v1/wearable',{'event_type':'wearable.hr','source':'test','data':{'bpm':71}})
  self.assertEqual(status,200);self.assertEqual(result['event']['data']['bpm'],71)
 def test_removed_cloud_route(self):self.assertEqual(self.req('/api/image',{})[0],404)

if __name__=='__main__':unittest.main(verbosity=2)
