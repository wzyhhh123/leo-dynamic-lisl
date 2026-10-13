"""Exact coverage and complete-ledger differential tests before timing."""
import ast,hashlib,inspect,json,textwrap,time,traceback
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction as F
from types import SimpleNamespace
import common as c
from runtime.n1b_fifo import AgeSemanticConflict
from runtime.n4_p0f_events import ExactObservedD2Engine
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect,Disconnect
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.commodity import Commodity
from runtime.n1b_evaluator import DeliveredFluidEvaluator

def empty_engine():
    z=SimpleNamespace(total=lambda:0)
    return SimpleNamespace(now=0,queues=z,in_flight=z,arrived={},delivered={},nodes=('src','dst'),
        commodities=(SimpleNamespace(commodity_id='c',source='src',destination='dst'),))
def layouts():
    e=F(1,10**30)
    return dict(empty=[],disjoint=[(F(i,8),F(i+1,8)) for i in range(8)],
        identical=[(F(0),F(1))]*8,nested=[(F(i,20),F(1)-F(i,20)) for i in range(8)],
        same_endpoint=[(F(0),F(1,2)),(F(1,2),F(1)),(F(0),F(1)),(F(1,2),F(1))],
        tiny=[(F(0),e),(e,2*e),(e,F(1)),(2*e,3*e)],
        partial_overlap=[(F(0),F(3,4)),(F(1,4),F(1)),(F(1,2),F(2,3))],
        zero_length=[(F(1,2),F(1,2)),(F(0),F(1))])
def parts_test(name,windows):
    incoming=[c.Stream(a,b,F(i+1),((F(1),F(1,2),F(0)),)) for i,(a,b) in enumerate(windows)]
    cuts=sorted({F(0),F(1)}|{t for pair in windows for t in pair})
    before=deepcopy(incoming)
    expected=[(a,b,[s.clip(a,b) for s in incoming if s.start<=a and s.end>=b]) for a,b in zip(cuts,cuts[1:])]
    actual=list(c.coverage_parts(incoming,cuts))
    assert actual==expected,(name,'PARTS_ORDER_OR_EXACT_VALUE_MISMATCH')
    assert incoming==before
    return dict(case=name,exact_parts_order=True,exact_Fraction_values=True,input_unmodified=True,
        intervals=len(expected),clips=sum(len(x[2]) for x in expected))
def interval_test(name,windows):
    windows=[(a,b) for a,b in windows if b>a]
    old=c.DeliveredAgeLedger(empty_engine());new=c.SweepDeliveredAgeLedger(empty_engine())
    streams=[c.Stream(a,b,F(i+1),((F(1),F(1,2),F(0)),)) for i,(a,b) in enumerate(windows)]
    mass=sum((s.mass() for s in streams),F())
    for ledger in (old,new):ledger.flight[(('src','dst'),'c')]=deepcopy(streams);ledger.arrived['c']=mass
    record=dict(start=0,end=1,external={'c':0},service={},arrival={(('src','dst'),'c'):1},
        after=dict(A={'c':mass},D={'c':mass},Q={},I={}))
    old._interval(deepcopy(record));new._interval(deepcopy(record))
    assert c.norm(vars(old))==c.norm(vars(new)),(name,'STATE_DIFFERENCE')
    assert old.metrics()==new.metrics()
    assert c.digest_state(old)==c.digest_state(new)
    clone=new.clone();assert type(clone) is c.SweepDeliveredAgeLedger
    assert c.digest_state(clone)==c.digest_state(new)
    clone.MD['c']+=1;assert clone.MD['c']!=new.MD['c']
    return dict(case=name,state_sha256=c.digest_state(new),all_fields_equal=True,clone_independent=True)
def closure_test(credit):
    old=c.DeliveredAgeLedger(empty_engine());new=c.SweepDeliveredAgeLedger(empty_engine())
    for ledger in (old,new):
        ledger.now=F(1);ledger.arrived['c']=F(3)
        ledger.flight[(('src','dst'),'c')]=[c.Stream(F(0),F(1),F(3),((F(1),F(1,2),F(0)),))]
    event=dict(edge=['src','dst'],commodity_id='c',closed_bits=3.,credited_to=credit,time_s=1.)
    for ledger in (old,new):
        ledger._closure(deepcopy(event))
        raw=dict(A={'c':3},D={'c':3 if credit=='DELIVERED' else 0},
            Q={} if credit=='DELIVERED' else {('dst','c'):3},I={})
        ledger._check_state(raw,'CLOSURE_PROBE')
    assert c.norm(vars(old))==c.norm(vars(new)) and old.metrics()==new.metrics()
    return dict(case='closure_'+credit,all_fields_equal=True,sha256=c.digest_state(new))

def real_service_tests():
    rows=[];N=tuple('S%03d'%i for i in range(160));a,b,d=N[:3]
    for dynamic in (False,True):
        engines=[]
        for repeat in range(2):
            ex=TerminalExecutor(N)
            if dynamic:ex.submit([Connect((b,'D1'),(d,'D1'),20.,0.,0.,0.)])
            trace=PiecewiseConstantTrafficTrace(('f','g'),[TrafficSegment(0.,1.,{'f':6.,'g':3.}),
                TrafficSegment(1.,2.,{'f':0.,'g':3.}),TrafficSegment(2.,3.,{'f':4.,'g':0.})])
            e=ExactObservedD2Engine(N,((a,b),) if dynamic else ((a,b),(b,d)),6.,
                [Commodity('f',a,d),Commodity('g',b,d)],trace,lambda edge,t:.25,ex,variant_binding=c.variant_binding())
            engines.append(e)
        ledgers=[c.DeliveredAgeLedger(engines[0]),c.SweepDeliveredAgeLedger(engines[1])]
        hashes=[]
        for t in (.25,.5,1.,1.25,2.,2.25,3.,4.,5.):
            if dynamic and t==1.25:
                for e in engines:e.executor.submit([Disconnect((b,'D1'),(d,'D1'))])
            if dynamic and t==2.:
                for e in engines:e.executor.submit([Connect((b,'D1'),(d,'D1'),20.,.1,.1,.1)])
            for e,l in zip(engines,ledgers):e.advance_to(t);l.consume(e)
            assert engines[0].canonical_state()==engines[1].canonical_state()
            assert c.norm(vars(ledgers[0]))==c.norm(vars(ledgers[1]))
            assert ledgers[0].metrics()==ledgers[1].metrics()
            old_hash=c.data_hash((engines[0].canonical_state(),vars(ledgers[0])))
            new_hash=c.data_hash((engines[1].canonical_state(),vars(ledgers[1])))
            assert old_hash==new_hash
            hashes.append(dict(t=t,state_sha256=new_hash,metrics=ledgers[1].metrics()))
        replay_eng=engines[1].clone();replay_age=ledgers[1].clone()
        replay_eng.advance_to(5.25);replay_age.consume(replay_eng)
        engines[1].advance_to(5.25);ledgers[1].consume(engines[1])
        assert c.data_hash((replay_eng.canonical_state(),vars(replay_age)))==c.data_hash((engines[1].canonical_state(),vars(ledgers[1])))
        rows.append(dict(case='D2_partition_recovery' if dynamic else 'D2_multi_commodity_multihop_partial',
            checkpoints=hashes,clone_replay_exact=True))
    return rows

def negative():
    old=c.old_context();deps=old.old.dependencies()
    f=old.setup();a,b=f.NODES[:2]
    e=ExactObservedD2Engine(f.NODES,((a,b),),100.,[Commodity('f',a,b)],
        PiecewiseConstantTrafficTrace(('f',),[TrafficSegment(0.,1.,{'f':10.})]),lambda edge,t:.25,
        TerminalExecutor(f.NODES),variant_binding=c.variant_binding())
    ev=DeliveredFluidEvaluator(e,T_s=2.,time_tolerance_s=1e-9,energy_tolerance_J=1e-6,
        business_tolerance_bits=1e-6,n1a_binding=deps[0],n1b_binding=deps[1])
    ev.age=c.SweepDeliveredAgeLedger.from_ledger(ev.age);ev.run();e.delivered['f']-=1.
    try:ev.base.measure()
    except ValueError as exc:assert str(exc)=='BUSINESS_CONSERVATION_MISMATCH'
    else:raise AssertionError('REAL_ONE_BIT_LOSS_NOT_REJECTED')
    return dict(case='deliberate_1bit_loss',rejected=True,threshold_bits=1e-6)

def main():
    c.source_verify();rows=[]
    for name,windows in layouts().items():
        for suffix,items in [('',windows),('_reversed',list(reversed(windows)))]:rows.append(parts_test(name+suffix,items))
        rows.append(interval_test(name,windows))
    rows.extend([closure_test('DELIVERED'),closure_test('QUEUED')]);rows.extend(real_service_tests());rows.append(negative())
    c.write('CORRECTNESS.json',dict(status='PASS_EXACT_FIELDS_AND_ORDER',cases=rows,case_count=len(rows),
        parts_exact=True,business_state_and_p0_state_hashes_exact=True,all_audits_exact=True,
        semantics='ONLY_INCOMING_COVERAGE_LOOKUP_DIFF',full_native_graph_class_identifier_equal=False,
        class_identifier_boundary='NEW_SEAM_TYPE_CODE_PROVENANCE_DIFFERS; existing numeric/causal/vars state hashes unchanged',
        tolerances_modified=False,source_bindings=c.source_verify()))
    print('CORRECTNESS_PASS '+str(len(rows)),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as exc:
        c.write('CORRECTNESS_STOP.json',dict(status='STOP_EQUIVALENCE_OR_VALIDATION_FAILURE',error=str(exc),traceback=traceback.format_exc()))
        raise
