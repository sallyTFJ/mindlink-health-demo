"""Offline SDK inference, without starting an HTTP server or accessing hardware."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from eeg_decoder import EEGModel

if __name__=='__main__':
    d=json.loads((ROOT/'examples/attention_window.json').read_text());d['source']='offline'
    print(json.dumps(EEGModel(ROOT/'models').infer_window(d),ensure_ascii=False,indent=2))
