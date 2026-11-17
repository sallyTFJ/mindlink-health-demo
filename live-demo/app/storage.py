"""Local observations only. No remote logging or cloud upload."""
import json
import sqlite3
import threading
import time
from pathlib import Path

class Ledger:
    def __init__(self,root):
        folder=Path(root)/'data';folder.mkdir(exist_ok=True)
        self.lock=threading.Lock()
        self.db=sqlite3.connect(folder/'events.sqlite3',check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,t REAL,kind TEXT,payload TEXT)')
        self.db.commit()
    def add(self,kind,payload):
        with self.lock:
            cur=self.db.execute('INSERT INTO events(t,kind,payload) VALUES(?,?,?)',(time.time(),kind,json.dumps(payload,ensure_ascii=False,allow_nan=False)))
            self.db.commit();return cur.lastrowid
