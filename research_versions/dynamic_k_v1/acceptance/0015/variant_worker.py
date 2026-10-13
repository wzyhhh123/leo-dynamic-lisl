"""Bound P0F variant root and two isolated real N2 forecast branches."""
import os,sys,json,hashlib,traceback
from pathlib import Path
from dataclasses import asdict
import support as w
from runtime.n4_p0f_events import ExactObservedD2Engine
from runtime.n4_p0 import ForecastInput,causal_view,make_sanitized_root
from runtime.n2_actions import Hold,Add,Setup
from runtime.n1b_evaluator import DeliveredFluidEvaluator
from runtime.n2_controller import AtomicTopologyController
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.commodity import Commodity
from local_observer import InstanceAuditor
from diagnostic_measure import DiagnosticMeasure
fs=w.old.load('p0f_full_state',w.V/'acceptance/0014/full_state.py')
def verify():
    d=w.vc.read_json(w.A/'replay_recipe.json')
    assert os.environ.get('PYTHONHASHSEED')=='1414'
    for r in d['bound_files']:assert w.info(Path(r['path']))==r,'RECIPE_BINDING_DRIFT:'+r['path']
    w.vc.load_expected(w.P,w.ORIGIN,w.PARENT);w.binding().verify()
    return d
def snap(d,name,c):
    state=fs.capture(c);view=causal_view(c)
    w.write(d/(name+'_FULL_STATE.json'),state)
    with (d/(name+'_CAUSAL_PREIMAGE.json')).open('xb') as f:f.write(view.state_json.encode())
    row=dict(stage=name,now=c.engine.now,age_now=str(c.evaluator.age.now),age_cursor=c.evaluator.age.cursor,
        full_state_sha256=fs.sha(state),causal_sha256=view.state_sha256,
        energy=c.evaluator.base.ledger.metrics(),age=c.evaluator.age.metrics(),
        terminal_log_count=len(c.engine.executor.log),observations=len(c.engine.age_observations))
    w.write(d/(name+'_SUMMARY.json'),row);return state,row
def build(d,audited=False):
    verify();f=w.old.setup();template,rows=f.real_fixture(full_catalog=True)
    nodes=template.engine.nodes;ex=TerminalExecutor(nodes)
    ex.submit([Connect(('X0_1','D2'),('X1_1','D1'),600.,0.,0.,0.)])
    trace=PiecewiseConstantTrafficTrace(('f_bg','f_hot'),[TrafficSegment(0.,8.,dict(f_bg=200000.,f_hot=400000.),'CURRENT'),
        TrafficSegment(8.,20.,dict(f_bg=200000.,f_hot=1200000.),'REAL_FUTURE_NOT_EXPOSED')])
    e=ExactObservedD2Engine(nodes,template.engine.fixed_edges,1e6,[Commodity('f_bg','X0_1','X1_1'),Commodity('f_hot','X0_10','X1_10')],
        trace,template.engine.delay,ex,variant_binding=w.binding())
    c=f.wrap(e,template.validator.physical,30.)
    if audited:
        adir=d/'prefix_audit';adir.mkdir();audit=InstanceAuditor(e,c.evaluator.age,adir)
        try:
            with audit.context():audit.boundary('INITIAL_t0');c.advance_to(3.);audit.boundary('PRE_ACTION_t3')
        finally:audit.close()
        w.write(adir/'summary.json',audit.summary())
    else:c.advance_to(3.)
    fc=ForecastInput.from_current(causal_view(c).observation,T_s=30.,H_s=6.,mode='PERSIST')
    root=make_sanitized_root(c,fc,binding=w.old.guard())
    return c,root
def baseline():
    d=w.A/'ROOT_BASELINE';d.mkdir(exist_ok=False);c,r=build(d,True)
    snap(d,'LIVE_PRE_ACTION',c);snap(d,'SANITIZED_PRE_ACTION',r.atomic)
    w.write(d/'ROOT_FULL_STATE.json',fs.capture(r))
    w.write(d/'root_binding.json',dict(scene='P0F_0015_EXACT_NOMINAL_NEW_ROOT',causal_root_sha256=r.view.state_sha256,
        root_complete_sha256=fs.sha(fs.capture(r)),forecast_sha256=r.forecast.sha256,prefix_sha256=r.prefix_sha256,
        original_0014_root_equivalence_claimed=False))
    print('VARIANT_ROOT_SAVED',flush=True)
def check(c,r,d):
    rows={}
    for name,obj in [('LIVE_PRE_ACTION',c),('SANITIZED_PRE_ACTION',r.atomic),('ROOT',r)]:
        old=w.vc.read_json(w.A/'ROOT_BASELINE'/('ROOT_FULL_STATE.json' if name=='ROOT' else name+'_FULL_STATE.json'))
        new=fs.capture(obj);diff=fs.first_diff(old,new)
        rows[name]=dict(exact_equal=diff is None,first_difference=diff,expected_sha256=fs.sha(old),actual_sha256=fs.sha(new))
    root=w.vc.read_json(w.A/'ROOT_BASELINE/root_binding.json')
    ok=all(x['exact_equal'] for x in rows.values()) and r.view.state_sha256==root['causal_root_sha256']
    w.write(d/'reconstruction.json',dict(status='PASS' if ok else 'STOP',full_state_comparisons=rows,root_binding=root,
        clean_process=True,pid=os.getpid(),hashseed=os.environ['PYTHONHASHSEED']))
    assert ok,'STOP_VARIANT_ROOT_RECONSTRUCTION_MISMATCH'
def rebuild():
    d=w.A/'CLEAN_REBUILD';d.mkdir(exist_ok=False);c,r=build(d);check(c,r,d)
    print('VARIANT_ROOT_REPLAY_PASS',flush=True)
def branch(kind):
    assert w.vc.read_json(w.A/'CLEAN_REBUILD/reconstruction.json')['status']=='PASS'
    d=w.A/kind;d.mkdir(exist_ok=False);c,r=build(d);check(c,r,d);c=r.atomic.clone()
    snap(d,'PRE_ACTION',c);initial=c.evaluator.base.measure()
    c.evaluator.base.__class__=DiagnosticMeasure;c.evaluator.base.diagnostic_directory=d
    action=Hold() if kind=='HOLD' else Add(('X0_10','D2'),('X1_10','D1'),Setup(.5,.5,.5))
    audit=InstanceAuditor(c.engine,c.evaluator.age,d);error=None;result=None;cuts=[]
    try:
        with audit.context():audit.boundary('PRE_ACTION_t3');receipt=c.submit(action);audit.boundary('POST_ACTION_t3')
        w.write(d/'receipt.json',receipt);assert receipt['accepted'];snap(d,'POST_ACTION',c)
        for t in (6.,9.):
            with audit.context():result=c.advance_to(t);audit.boundary('PREDICTION_CHECKPOINT_'+str(t))
            snap(d,'CHECKPOINT_'+str(int(t)),c);cuts.append(t)
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),now=c.engine.now)
        w.write(d/'STOP_EXCEPTION.json',error);audit.boundary('UNCHANGED_EXCEPTION_STATE');snap(d,'STOP_STATE',c)
    finally:audit.close()
    w.write(d/'audit_summary.json',audit.summary())
    report=dict(status='PASS_SINGLE_BRANCH' if error is None else 'BLOCKED',action=kind,error=error,now=c.engine.now,completed_cuts=cuts,
        original_0014_replay=False,accepted_n2_result=result if not error else None)
    if not error:
        f=result['n1b_result']['n1a_result'];report.update(J_h_bit_s=f['J_T_bit_s']-initial['J_T_bit_s'],N_end_bits=f['N_T_bits'],
            E_h_J=f['E_LCT_J']-initial['E_LCT_J'],DeltaE_h_J=f['DeltaE_LCT_J']-initial['DeltaE_LCT_J'])
    w.write(d/'branch_result.json',report);print(kind+' '+report['status'],flush=True)
    if error:raise SystemExit(2)
def prepare():
    external=w.vc.read_json(w.V/'acceptance/0014/replay_recipe.json')['bound_files']
    files=[Path(r['path']) for r in external]+list(w.A.glob('*.py'))+[w.V/'runtime/n4_p0f_events.py',w.A/'variant_dependencies.json',w.A/'VARIANT_BINDING.json']
    files=sorted(set(files),key=str)
    w.write(w.A/'replay_recipe.json',dict(schema='p0f_exact_nominal_executable_reconstruction_v1',bound_files=[w.info(p) for p in files],
        parent=w.PARENT,hashseed='1414',python=sys.version,constructor='variant_worker.build',t=3.,T=30.,T_A=20.,H=6.,
        original_equivalence_claimed=False,full_native_reconstruction='Pinned SGP4 binary/TLE, constructor and event call recipe; complete graph equality'))
    print('RECIPE_BOUND',flush=True)
if __name__=='__main__':{'prepare':prepare,'baseline':baseline,'rebuild':rebuild,'HOLD':lambda:branch('HOLD'),'ADD':lambda:branch('ADD')}[sys.argv[1]]()
