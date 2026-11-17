"""Offline installation check. Never opens a COM port or a Bluetooth device."""
import hashlib
import importlib
import json
import platform
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    checks=[]
    def check(name,fn):
        try:value=fn();checks.append({'check':name,'passed':True,'detail':value})
        except Exception as e:checks.append({'check':name,'passed':False,'detail':type(e).__name__+': '+str(e)[:180]})
    for mod in ['numpy','scipy','onnxruntime','serial','sqlite3']+(['bleak','bleak_winrt'] if sys.platform=='win32' else []):
        check('import '+mod,lambda m=mod:getattr(importlib.import_module(m),'__version__','available'))
    def inference():
        from eeg_decoder.sdk import EEGModel
        model=EEGModel(ROOT/'models');result={}
        for fold in range(5): EEGModel(ROOT/'models',fold=fold)
        for task in ['attention','valence']:
            d=json.loads((ROOT/'examples'/f'{task}_window.json').read_text())
            d['source']='offline';r=model.infer_window(d)
            if not r['valid']:raise AssertionError(r)
            expected=json.loads((ROOT/'examples'/f'{task}_expected_output.json').read_text())
            for field in ('attention_score','valence_score'):
                if abs(r[field]-expected[field])>0.00005:raise AssertionError('Unexpected offline score: '+field)
            result[task]={k:r[k] for k in ['valid','attention_score','valence_score','inference_ms']}
        return result
    check('ONNX offline inference (not live hardware)',inference)
    def hashes():
        p=ROOT/'MANIFEST.sha256.json'
        if not p.exists():return 'manifest not yet generated'
        manifest=json.loads(p.read_text());bad=[name for name,digest in manifest.items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
        if bad:raise AssertionError(str(bad[:10]))
        return f'{len(manifest)} immutable files verified'
    check('package hashes',hashes)
    result={'platform':platform.platform(),'python':sys.version,'checks':checks,'passed':all(c['passed'] for c in checks),'hardware_tested':False}
    (ROOT/'SELF_CHECK_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
