"""Explicit source extraction into a new subclass; frozen bytes never edited."""
import ast,difflib,hashlib,json
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
def main():
    p=P/'src/dynamic_lisl/transition_service_orchestrator.py';source=p.read_text(encoding='utf-8')
    tree=ast.parse(source);cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='TransitionAwareNetworkServiceEngine')
    methods=['_settle_propagation_rate_events','_next_time','advance_to','settle_current_time','_step','_microstep','_apply_due_actions']
    changed=[];chunks=[]
    for name in methods:
        node=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
        before='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])+'\n';after=before
        for x,y in [('self.now+1e-12','self.now'),('self.now+1e-13','self.now'),('until_s-1e-13','until_s')]:after=after.replace(x,y)
        if name=='advance_to':after=after.replace('            self._step(until_s)','            prior = self.now\n            self._step(until_s)\n            if not prior < self.now <= until_s:\n                raise RuntimeError("P0F_NON_FORWARD_OR_OVERSHOOT")')
        if name in ('_step','settle_current_time'):
            after=after.replace('                self.next_refresh += self.geometry_refresh_s','                prior_refresh = self.next_refresh\n                self.next_refresh += self.geometry_refresh_s\n                if self.next_refresh <= prior_refresh:\n                    raise RuntimeError("P0F_UNREPRESENTABLE_REFRESH_INCREMENT")')
        chunks.append(after);changed.append(dict(method=name,original_start_line=node.lineno,
            original_end_line=node.end_lineno,diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='frozen/'+name,tofile='variant/'+name))))
    header='''"""PILOT_ONLY isolated exact-nominal event clock over unchanged D2 service.

Original global classes/functions are never patched. Only explicit construction
of these subclasses selects the new numeric event timing semantics.
"""
import heapq,math,hashlib,json
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine
from dynamic_lisl.transition_connectivity import profile_transition
from runtime.n1b_observer import ObservedD2Engine

@dataclass(frozen=True)
class VariantBinding:
    manifest_path: str
    sha256: str
    def verify(self):
        p=Path(self.manifest_path)
        assert hashlib.sha256(p.read_bytes()).hexdigest()==self.sha256,'P0F_MANIFEST_DRIFT'
        doc=json.loads(p.read_text(encoding='utf-8'))
        for r in doc['files']:
            q=Path(r['path']);data=q.read_bytes()
            assert len(data)==r['byte_count'] and hashlib.sha256(data).hexdigest()==r['sha256'],'P0F_DEPENDENCY_DRIFT:'+str(q)
        return {'status':'PASS','semantic_version':'P0F_EXACT_NOMINAL_V1'}

class ExactEventClock:
    def __init__(self,*args,variant_binding,**kwargs):
        variant_binding.verify()
        self.variant_binding=variant_binding
        super().__init__(*args,**kwargs)
'''
    out=header+'\n'.join(chunks)+'''
class ExactObservedD2Engine(ExactEventClock,ObservedD2Engine):
    pass

class ExactBareD2Engine(ExactEventClock,TransitionAwareNetworkServiceEngine):
    pass
'''
    # Locate original helper module from the import in the frozen source.
    helper=next(line for line in source.splitlines() if line.startswith('from .') and 'profile_transition' in line)
    if 'from .transition_connectivity' not in helper:
        module=helper.split('from .',1)[1].split(' import',1)[0]
        out=out.replace('from dynamic_lisl.transition_connectivity import profile_transition',
                        'from dynamic_lisl.'+module+' import profile_transition')
    dest=V/'runtime/n4_p0f_events.py'
    with dest.open('x',encoding='utf-8',newline='\n') as f:f.write(out)
    with (A/'MINIMAL_SOURCE_DIFF.json').open('x',encoding='utf-8') as f:json.dump(dict(
        original_path=str(p),original_raw_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        generated_variant_path=str(dest),methods=changed,unchanged_service_and_integrate=True,
        global_monkeypatch=False),f,indent=2,sort_keys=True)
    print('VARIANT_GENERATED',flush=True)
if __name__=='__main__':main()
