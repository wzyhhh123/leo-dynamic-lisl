"""Shared file utilities and frozen epoch; no STK dependency."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[2]
EPOCH='01 Jan 2026 00:00:00.00'
EPOCH_JD=2461041.5
DURATION=86400.0

def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def new_output(prefix):
    p=PROJECT/'outputs'/(prefix+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    p.mkdir(parents=True,exist_ok=False);return p

