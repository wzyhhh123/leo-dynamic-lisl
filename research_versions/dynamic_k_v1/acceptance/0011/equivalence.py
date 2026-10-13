"""Pre/post reader equivalence; all fields except nondeterministic timings."""
from copy import deepcopy
import hashlib,json,time
import workflow as w
from runtime.n4_p0r_handle_reader import HandleReaderLease
from runtime.n4_p0 import ForecastInput,PilotCost,make_sanitized_root,score_action,encode,causal_view
from runtime.n2_actions import Hold,Add,Drop,Replace,Setup,LinkRef
from dynamic_lisl.traffic_trace import TrafficSegment
def bind_live(c,lease):
    c.binding=lease.guard(c.binding);c.evaluator.binding=lease.guard(c.evaluator.binding)
    c.evaluator.base.evidence_binding=lease.guard(c.evaluator.base.evidence_binding)
    return c
def stable(x):
    x=deepcopy(x);x.pop('timings',None);return x
def count(x):
    if isinstance(x,dict):return sum(count(v) for v in x.values())
    if isinstance(x,(list,tuple)):return sum(count(v) for v in x)
    return 1
def main():
    f=w.setup();g=w.guard();deps=w.old.dependencies();results=[]
    for kind in ('HOLD','ADD','DROP','BBM','MBB','ILLEGAL_ADD'):
        pairs=((f.A1,f.C1),) if kind in ('BBM','ILLEGAL_ADD') else ((f.A2,f.C2),) if kind=='MBB' else ((f.A1,f.B1),)
        c=f.synthetic(T=30.,connected=kind!='ADD',pairs=pairs,destination=f.C if kind in ('BBM','MBB') else f.B,
            tx_end=5.,capacity=8.,segments=[TrafficSegment(0.,2.25,{'f':4.}),TrafficSegment(2.25,20.,{'f':2.})])
        c.advance_to(3.);forecast=ForecastInput.from_current(f.observe_current(c),T_s=30.,H_s=6.,mode='PERSIST')
        ref=LinkRef.from_link(next(iter(c.engine.executor.links.values()))) if c.engine.executor.links else None
        action=Hold() if kind=='HOLD' else Add(*(pairs[0] if kind=='ILLEGAL_ADD' else (f.A1,f.B1)),Setup(.5,.5,.5)) if kind in ('ADD','ILLEGAL_ADD') else Drop(ref) if kind=='DROP' else Replace((ref,),*pairs[0],Setup(.5,.5,.5),kind)
        before=causal_view(c);original=score_action(make_sanitized_root(c,forecast,binding=g),action,PilotCost(6.,1000.),cadence_s=3.)
        with HandleReaderLease(deps+[g],w.vc) as lease:
            optimized=score_action(make_sanitized_root(bind_live(c.clone(),lease),forecast,binding=lease.guard(g)),action,PilotCost(6.,1000.),cadence_s=3.)
        a,b=stable(original),stable(optimized);assert a==b,(kind,'FIELD_MISMATCH');assert before==causal_view(c)
        results.append(dict(action=kind,accepted=a['accepted'],exact_field_equality=True,
            scalar_leaf_count=count(a),stable_result=a,stable_result_sha256=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest(),
            excluded_fields=['timings'],tolerance_relaxation=False))
        print('EXACT_EQUIVALENCE '+kind,flush=True)
    w.write('final_pre_post_all_action_equivalence.json',dict(status='PASS',results=results))
if __name__=='__main__':main()
