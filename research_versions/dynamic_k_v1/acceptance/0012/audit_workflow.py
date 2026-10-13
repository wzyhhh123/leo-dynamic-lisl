"""N4-P0C diagnostic helpers; no writes to older revisions."""
import importlib.util,json,sys
from pathlib import Path
A=Path(__file__).parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(V/'acceptance/0011'),str(V),str(P/'src')]
import workflow as upstream
vc=upstream.vc
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='89046f4c855a6f7830c620889216ef131577887ee15b04593d501b6ddf06b71f'
EXPECTED=vc.load_expected(P,ORIGIN,PARENT)[2]
def bound(path):
    path=Path(path);relative=path.relative_to(P).as_posix();actual=vc.file_info(path)
    if actual!=EXPECTED[relative]:raise ValueError('P0C_INPUT_BINDING_MISMATCH:'+relative)
    return dict(path=relative,**actual)
def read_old(name):
    p=V/'acceptance/0011'/name;bound(p);return vc.read_json(p)
def write(name,data):
    p=A/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(data,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def key(x):return tuple(key(v) for v in x) if isinstance(x,list) else x
def state(x):
    return {name:{key(k):v for k,v in rows} for name,rows in x}
def intervals(doc):
    observations=doc['records'][1]['age_observations']
    for i,row in enumerate(observations):
        r=dict(row)
        if r.get('kind')=='INTERVAL':
            yield i,{**r,'before':state(r['before']),'after':state(r['after'])}
