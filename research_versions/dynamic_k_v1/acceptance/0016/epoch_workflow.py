"""PILOT_ONLY restored single-epoch acceptance, no matrix or training."""
import sys,os,json,time,hashlib,traceback,types
from pathlib import Path
from dataclasses import asdict
from collections import Counter,defaultdict
from contextlib import ExitStack
from unittest.mock import patch
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(V/'acceptance/0015'),str(V/'acceptance/0011'),str(V),str(P/'src')]
import support as s15
import variant_worker as v15
old=s15.old;vc=s15.vc
ORIGIN=s15.ORIGIN
PARENT='a5c427c4225bbd4850c3979079b18d68afa92d64cdffe1f90025904537ac7318'
from runtime.n4_p0 import ForecastInput,PilotCost,make_sanitized_root,score_action,causal_view,retain_small_domain
from runtime.n2_actions import Hold,Add,Drop,Replace,Setup,LinkRef,action_key
from runtime.n4_p0r_handle_reader import HandleReaderLease
from equivalence import bind_live
fs=v15.fs
memory=old.load('p0g_memory',V/'acceptance/0010/cost_measurement.py').memory
SETUP=Setup(.5,.5,.5);COST=PilotCost(6.,1000.)
def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def bind(path):return vc.binding(P,Path(path).relative_to(P).as_posix())
def load_live(label):
    assert os.environ.get('PYTHONHASHSEED')=='1414','REPLAY_SEED_REQUIRED'
    starts=time.perf_counter();recipe=vc.read_json(V/'acceptance/0015/replay_recipe.json')
    def verify():
        assert sys.version==recipe['python']
        for r in recipe['bound_files']:assert s15.info(Path(r['path']))==r,'RECIPE_SOURCE_CHANGED:'+r['path']
        vc.load_expected(P,ORIGIN,PARENT);s15.binding().verify();return recipe
    v15.verify=verify
    live,root=v15.build(A);built=time.perf_counter()-starts
    comparisons={}
    for name,obj in [('LIVE_PRE_ACTION',live),('SANITIZED_PRE_ACTION',root.atomic),('ROOT',root)]:
        source=V/'acceptance/0015/ROOT_BASELINE'/('ROOT_FULL_STATE.json' if name=='ROOT' else name+'_FULL_STATE.json')
        previous=vc.read_json(source);current=fs.capture(obj);diff=fs.first_diff(previous,current)
        comparisons[name]=dict(exact_equal=diff is None,first_difference=diff,expected_sha256=fs.sha(previous),actual_sha256=fs.sha(current))
    ok=all(x['exact_equal'] for x in comparisons.values())
    write(A/(label+'_ROOT_RECONSTRUCTION.json'),dict(status='PASS' if ok else 'STOP_ROOT_MISMATCH',
        comparisons=comparisons,build_and_binding_s=built,pid=os.getpid(),semantics='P0F_EXACT_NOMINAL_V1'))
    assert ok,'ROOT_RECONSTRUCTION_MISMATCH'
    return live,built
def open_lease(live):
    deps=old.old.dependencies();g=old.guard();start=time.perf_counter();lease=HandleReaderLease(deps+[g],vc)
    lease.__enter__();startup=time.perf_counter()-start
    optimized=bind_live(live.clone(),lease)
    assert causal_view(optimized)==causal_view(live),'READER_ADAPTER_ROOT_DIFF'
    return lease,optimized,lease.guard(g),startup
class BranchTimings:
    """Timers wrap only cloned branch instance methods; no runtime global patch."""
    def __init__(self):self.parts=defaultdict(float);self.calls=Counter();self.stack=[];self.callbacks=0
    def invoke(self,category,fn,*args,**kwargs):
        start=time.perf_counter();row=[category,start,0.];self.stack.append(row);self.calls[category]+=1;self.callbacks+=1
        try:return fn(*args,**kwargs)
        finally:
            elapsed=time.perf_counter()-start;self.stack.pop();self.parts[category]+=elapsed-row[2]
            if self.stack:self.stack[-1][2]+=elapsed
    def install(self,obj,name,category,context):
        fn=getattr(obj,name)
        context.enter_context(patch.object(obj,name,lambda *a,**k:self.invoke(category,fn,*a,**k)))
    def context(self,branch):
        context=ExitStack()
        for obj,name,category in [(branch,'_verify','binding_and_dynamic_physical'),
            (branch,'submit','action_submission'),(branch.engine,'advance_to','network_event_clock'),
            (branch.evaluator.age,'consume','FIFO'),(branch.evaluator.age,'metrics','FIFO_metrics'),
            (branch.evaluator.base.ledger,'capture','energy'),(branch.evaluator.base.ledger,'metrics','energy_metrics'),
            (branch.evaluator.base,'measure','energy_and_measurement')]:
            self.install(obj,name,category,context)
        return context
def score(root,action,instrumented=False):
    # Frozen scorer clones before submitting. Attach instrumentation only to the
    # exact returned branch; reference object/root and global classes untouched.
    timer=BranchTimings();saved={};original=root.atomic.clone
    def clone():
        start=time.perf_counter();branch=original();saved['branch']=branch;saved['clone_s']=time.perf_counter()-start
        if instrumented:saved['context']=timer.context(branch)
        return branch
    start=time.perf_counter();result=None;error=None;guard_original=root.atomic.clone
    try:
        with patch.object(root.atomic,'clone',clone):result=score_action(root,action,COST,cadence_s=3.)
    except Exception as exc:error=dict(message=str(exc),type=type(exc).__name__,traceback=traceback.format_exc())
    finally:
        if 'context' in saved:saved['context'].close()
    elapsed=time.perf_counter()-start;branch=saved.get('branch')
    state_checks=None
    if branch is not None:
        # Original numerical validations have already run during score_action;
        # additionally verify exact cohort mass and both real clocks here.
        state_checks=dict(clock_s=branch.engine.now,terminal_clock_s=branch.engine.executor.now,
            age_clock_s=str(branch.evaluator.age.now),energy_clock_s=branch.evaluator.base.ledger.now,
            causal_final_sha256=causal_view(branch).state_sha256)
        branch.engine.executor.assert_invariants()
    return dict(result=result,error=error,actual_wall_s=elapsed,clone_s=saved.get('clone_s'),
        state_checks=state_checks,instrumentation=dict(enabled=instrumented,method_calls=dict(timer.calls),
            exclusive_s=dict(timer.parts),wrapper_callbacks=timer.callbacks,
            description='instance-local Python timers; exclusive totals include wrapper overhead'),memory=memory())
def stable(r):
    d=dict(r);d.pop('timings',None);return d
def select_success(rows):
    valid=[x['result'] for x in rows if x['error'] is None and x['result']['accepted'] and x['result'].get('prediction_completed')]
    assert len(valid)==len(rows),'FAILED_BRANCH_CANNOT_BE_SCORED'
    ranked=sorted(valid,key=lambda r:(r['cost_bit_s'],0 if r['action']['kind']=='HOLD' else 1,r['action_key']))
    return dict(selected_action=ranked[0]['action'],selected_cost_bit_s=ranked[0]['cost_bit_s'],
        ranked_actions=[dict(action=r['action'],cost_bit_s=r['cost_bit_s'],action_key=r['action_key']) for r in ranked])
def small():
    live,built=load_live('SMALL');lease,live,g,startup=open_lease(live)
    try:
        ref=LinkRef.from_link(next(iter(live.engine.executor.links.values())));hot=(('X0_10','D2'),('X1_10','D1'))
        actions=sorted([Hold(),Add(*hot,SETUP),Drop(ref),Replace((ref,),*hot,SETUP,'BBM'),Replace((ref,),*hot,SETUP,'MBB')],key=action_key)
        masks=[]
        for a in actions:
            result=live.validator.validate(live.engine.executor,a);masks.append(dict(action=asdict(a),accepted=result['accepted'],reason=result['reason'],mode=result.get('mode')))
        write(A/'SMALL_LEGALITY.json',dict(masks=masks,full_legal_catalog_count=None))
        assert all(x['accepted'] for x in masks),'SMALL_REQUESTED_ACTION_NOT_LEGAL'
        roots={};results={}
        for mode in ('PERSIST','ZERO'):
            fc=ForecastInput.from_current(causal_view(live).observation,T_s=30.,H_s=6.,mode=mode)
            start=time.perf_counter();root=make_sanitized_root(live,fc,binding=g);sanitize=time.perf_counter()-start;roots[mode]=root
            root.verify_isolation();before=causal_view(root.atomic);rows=[]
            for index,a in enumerate(actions):
                print('SMALL '+mode+' '+a.kind+' '+getattr(a,'mode',''),flush=True)
                r=score(root,a);rows.append(r);write(A/'small'/mode/(str(index+1).zfill(2)+'_'+a.kind+'_'+getattr(a,'mode','')+'.json'),r)
                if r['error'] or not r['result']['accepted']:
                    write(A/'SMALL_STOP.json',dict(status='STOP_BRANCH_ERROR',mode=mode,action=asdict(a),evidence=r));raise RuntimeError('SMALL_BRANCH_ERROR')
            assert causal_view(root.atomic)==before,'SMALL_ROOT_MUTATED'
            decision=select_success(rows);results[mode]=dict(rows=rows,decision=decision,forecast_sha256=fc.sha256,
                root_sha256=root.view.state_sha256,prefix_sha256=root.prefix_sha256,sanitize_s=sanitize,
                scoring_wall_s=sum(r['actual_wall_s'] for r in rows))
            write(A/('SMALL_'+mode+'_SUMMARY.json'),results[mode])
        assert roots['PERSIST'].view==roots['ZERO'].view and roots['PERSIST'].prefix_sha256==roots['ZERO'].prefix_sha256
        check=[]
        for kind in ('HOLD','ADD'):
            row=next(x['result'] for x in results['PERSIST']['rows'] if x['result']['action']['kind']==kind)
            prev=vc.read_json(V/'acceptance/0015'/kind/'branch_result.json')
            expected={k:prev[source] for k,source in [('J_h_bit_s','J_h_bit_s'),('N_end_bits','N_end_bits'),('DeltaE_h_J','DeltaE_h_J')]}
            for k,value in expected.items():assert row[k]==value,'0015_SCORE_FIELD_DIFF:'+kind+':'+k
            cost=expected['J_h_bit_s']+6.*expected['N_end_bits']+1000.*expected['DeltaE_h_J'];assert row['cost_bit_s']==cost
            check.append(dict(action=kind,expected=expected,cost_bit_s=cost,exact_score_equal=True))
        write(A/'SCORING_RULE_0015_CHECK.json',dict(status='PASS',lambda_N_s=6.,lambda_E_bit_s_per_J=1000.,checks=check,
            science_values_frozen=False))
        # One same-action paired measurement discloses actual timer overhead;
        # scorer output must stay exactly identical, including all N1a/N1b fields.
        paired=score(roots['PERSIST'],Hold(),instrumented=True)
        write(A/'SMALL_INSTRUMENTED_HOLD.json',paired)
        plain=next(x for x in results['PERSIST']['rows'] if x['result']['action']['kind']=='HOLD')
        assert paired['error'] is None and stable(paired['result'])==stable(plain['result']),'INSTRUMENTATION_CHANGED_RESULT'
        write(A/'SMALL_DOMAIN_ACCEPTANCE.json',dict(status='PASS',per_mode_branches=5,modes=['ZERO','PERSIST'],same_root_view=True,
            same_history_prefix=True,all_costs_from_real_fixed_horizon_execution=True,legal_actions=masks,
            full_catalog_domain_claimed=False,instrumentation_result_exact_equal=True,
            plain_HOLD_wall_s=plain['actual_wall_s'],instrumented_HOLD_wall_s=paired['actual_wall_s'],
            observed_timer_overhead_s=paired['actual_wall_s']-plain['actual_wall_s'],startup_s=startup,root_build_s=built,
            instrumentation_extra_branches=1,main_pilot_runs=0))
    finally:lease.__exit__(None,None,None)
    print('SMALL_DOMAIN_PASS',flush=True)
if __name__=='__main__':small()
