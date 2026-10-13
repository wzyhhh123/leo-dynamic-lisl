"""Version-local bounded acceptance helpers, not a simulator implementation."""
import sys,importlib.util,json,hashlib,time
from pathlib import Path
from dataclasses import asdict
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(A),str(V/'acceptance/0016'),str(V),str(P/'src')]
import epoch_workflow as w
PARENT='e9554ecfd9a256dc766ac65ea1757e07d4eab00d6addb4b9a896d09154b5b22c'
ORIGIN=w.ORIGIN;vc=w.vc
# Acceptance-helper output/chain context only; frozen files/classes untouched.
w.A=A;w.PARENT=PARENT
def write(name,data):w.write(A/name,data)
def bind(p):return vc.binding(P,Path(p).relative_to(P).as_posix())
def canonical(x):return json.loads(json.dumps(x,sort_keys=True,allow_nan=False))
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def root(label):return w.load_live(label)[0]
def actions(c):
    from runtime.n2_actions import Hold,Add,Drop,Replace,LinkRef
    ref=LinkRef.from_link(next(iter(c.engine.executor.links.values())))
    hot=(('X0_10','D2'),('X1_10','D1'));other=None
    for line in (V/'acceptance/0016/CATALOG_VALIDATION_PREFIX.jsonl').open(encoding='utf-8'):
        r=json.loads(line)
        if r['accepted'] and r['action']['kind']=='ADD':
            pair=tuple(tuple(r['action'][k]) for k in ('a','b'))
            if pair!=hot:other=pair;break
    assert other is not None
    return [('HOLD',Hold()),('ADD_hot',Add(*hot,w.SETUP)),('ADD_other',Add(*other,w.SETUP)),
        ('DROP',Drop(ref)),('BBM_hot',Replace((ref,),*hot,w.SETUP,'BBM')),
        ('MBB_hot',Replace((ref,),*hot,w.SETUP,'MBB')),
        ('ADD_occupied',Add(*ref.endpoints,w.SETUP))]
def verdict(result):
    r=dict(result)
    if 'trial' in r:
        ex=r.pop('trial');r['trial_snapshot']=ex.snapshot();r['trial_log']=ex.log
    from runtime.n4_p0 import encode
    return canonical(encode(r))
