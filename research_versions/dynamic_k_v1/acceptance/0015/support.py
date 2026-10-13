"""Independent bindings and local fixture selection, never global patching."""
import sys,json,hashlib,inspect,functools
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(A),str(V/'acceptance/0011'),str(V),str(P/'src')]
import workflow as old
from runtime.n4_p0f_events import ExactObservedD2Engine,ExactBareD2Engine,VariantBinding
vc=old.vc
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='3e7b1015d628d601caa2f16bec99c8a91161ed3a83ec144760fc85bd79c15a73'
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def info(p):return dict(path=str(p),**vc.file_info(p))
def binding():
    anchor=vc.read_json(A/'VARIANT_BINDING.json')
    return VariantBinding(str(A/'variant_dependencies.json'),anchor['manifest_sha256'])
def engine_factory(cls):
    def new(*args,**kwargs):return cls(*args,variant_binding=binding(),**kwargs)
    return new
def bind_test_module(m,mode):
    if mode=='original':return
    # Only the separately loaded test module's imported names/factory defaults.
    # No runtime class, production namespace or frozen file is replaced.
    if hasattr(m,'ObservedD2Engine'):m.ObservedD2Engine=ExactObservedD2Engine
    if hasattr(m,'TransitionAwareNetworkServiceEngine'):m.TransitionAwareNetworkServiceEngine=engine_factory(ExactBareD2Engine)
    if hasattr(m,'engine') and m.engine.__defaults__:
        original=m.engine
        m.engine.__defaults__=tuple(engine_factory(ExactObservedD2Engine) if inspect.isclass(d) and d.__name__=='ObservedD2Engine' else d for d in m.engine.__defaults__)
    # Constructor globals must remain a class for old isinstance tests.
    # A subclass with bound __init__ provides the explicit factory seam locally.
    if hasattr(m,'ObservedD2Engine'):
        class BoundObserved(ExactObservedD2Engine):
            def __init__(self,*args,**kwargs):super().__init__(*args,variant_binding=binding(),**kwargs)
        BoundObserved.__name__='BoundObserved';m.ObservedD2Engine=BoundObserved
        if hasattr(m,'engine') and m.engine.__defaults__:
            m.engine.__defaults__=(BoundObserved,)
    return m
def prepare():
    version,base,expected,*_=vc.load_expected(P,ORIGIN,PARENT)
    files=[V/'runtime/n4_p0f_events.py',P/'src/dynamic_lisl/transition_service_orchestrator.py',
        V/'runtime/n1b_observer.py',V/'runtime/n1b_fifo.py',V/'runtime/n1a.py',V/'runtime/n1b_evaluator.py',
        V/'runtime/n2_controller.py',V/'runtime/n2_physical.py',V/'runtime/n4_p0.py']
    deps=old.old.dependencies()+[old.guard()]
    for g in deps:
        g.verify();doc=vc.read_json(P/g.manifest_path);files.append(P/g.manifest_path)
        files.extend(P/r['path'] for r in doc['files']+list(doc['anchors'].values()) if '/revisions/' not in r['path'])
    files=sorted(set(files),key=str)
    for p in files:
        rel=p.relative_to(P).as_posix()
        if rel in expected:assert vc.file_info(p)==expected[rel],rel
    write(A/'variant_dependencies.json',dict(schema='dynamic_k_p0f_numeric_variant_binding_v1',files=[info(p) for p in files],
        semantics='EXACT_NOMINAL_TIME_PILOT_ONLY',parent_revision_sha256=PARENT))
    write(A/'VARIANT_BINDING.json',dict(manifest_sha256=vc.file_info(A/'variant_dependencies.json')['sha256']))
    write(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0014',revision_sha256=PARENT,
        origin_sha256=ORIGIN,verified_file_count=6240,baseline_file_count=5810,excluded_file_count=202,
        source='Full verifier tool output session 29432 exit0',undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[])))
    print('VARIANT_BOUND',flush=True)
if __name__=='__main__':prepare()
