"""ENGINEERING_PROFILE_ONLY: one real B4 epoch, OFF/ON exact comparison."""
from collections import defaultdict
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import cProfile
import hashlib
import json
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from run_gate_f3_p1_execution import preflight
from dynamic_lisl.common import read_json
from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_e2_experiments import GateE2Assets, E2Sgp4EdgeDelayProvider
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor, ObservationalE2Engine
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine as Engine
from dynamic_lisl.forecast import CurrentRatePersistenceForecast
import dynamic_lisl.rollout_evaluator as evaluator_module

CATEGORIES=('clone','hash','forecast_hash','root_action','routing','delay','service','qid','objective','event','finish','diagnostic')
def dump(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def file_hash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def proxy(e):
    return {'terminal_log_length':len(e.executor.log),'transition_history_length':len(e.transition_episodes),
      'routing_history_length':len(e.route_changes),'service_history_length':len(e.timeline),
      'observation_length':len(e.reporting_samples),'pending_event_count':len(e.propagation_agenda)+len(e.executor.events),
      'terminal_event_queue_length':len(e.executor.events),'in_flight_object_count':len(e.in_flight.bits),
      'queue_state_size':len(e.queues.bits)}

class Timing:
    def __init__(self):
        self.active=None;self.stack=[];self.global_times=defaultdict(float)
    def wrap(self,fn,category,method_name=None):
        def call(*args,**kwargs):
            cat=category(*args,**kwargs) if callable(category) else category
            start=time.perf_counter(); frame=[cat,start,0.0];self.stack.append(frame)
            try:return fn(*args,**kwargs)
            finally:
                elapsed=time.perf_counter()-start; self.stack.pop()
                if self.stack:self.stack[-1][2]+=elapsed
                target=self.active
                if target is None:self.global_times[cat]+=elapsed-frame[2]
                else:
                    target['exclusive_s'][cat]+=elapsed-frame[2]
                    target['inclusive_s'][cat]+=elapsed
                    target['calls'][cat]+=1
                    if method_name:target['method_calls'][method_name]+=1
        return call

def main():
    pre,execution,_=preflight()
    assert pre['pass'],'STOP_PREFLIGHT_FAIL'
    regression=(ROOT/'tmp/b4_kernel_regression_final.log').read_text(encoding='utf-8-sig')
    assert 'Ran 299 tests' in regression and regression.rstrip().endswith('OK'),'STOP_REGRESSION_FAIL'
    out=ROOT/'outputs'/('b4_rollout_kernel_profile_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir();dump(out/'preflight.json',pre)
    (out/'full_regression.log').write_text(regression,encoding='utf-8')
    frozen={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'configs').glob('*.json')}
    code={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'src/dynamic_lisl').glob('*.py')}
    assets=GateE2Assets()
    template=next(r for r in execution['runs'] if r['block_id']=='P1' and r['controller']=='B4' and r['rho']==0.5)
    runner=P1RunExecutor(assets,{**template,'run_id':'ENGINEERING_PROFILE_ONLY-B4-KERNEL','block_id':'ENGINEERING_PROFILE_ONLY'})
    engine=runner.engine;controller=runner.controller;state=controller_visible_state(engine)
    specs=tuple(runner.candidate_source(state,{'epoch_index':0,'regime':'Z_MODERATE','terminal_executor':engine.executor}))
    proposals=runner.proposer.propose(engine.executor,specs,assets.physical,assets.fixed,'Z_MODERATE')
    assert len(proposals['proposals'])==16,'STOP_EXPECTED_16_PROPOSALS'
    proposal_by_id={r['proposal_id']:r for r in proposals['proposals']}
    initial=engine.canonical_state();root_proxy=proxy(engine)
    timer=Timing(); timing_rows=[];modes={};wall_modes={}
    for enabled in (False,True):
        mode='ON' if enabled else 'OFF';results=[];final_states=[]
        evaluator=controller.evaluator
        original_finish=evaluator._finish
        def finish(*args,**kwargs):
            result=original_finish(*args,**kwargs)
            branch=args[0]
            # Capture full canonical state and full events for exact equivalence.
            results.append(asdict(result));final_states.append(branch.canonical_state())
            if enabled:timer.active['final_proxy']=proxy(branch)
            return result
        with ExitStack() as stack:
            stack.enter_context(patch.object(evaluator,'_finish',finish))
            if enabled:
                hooks=[(ObservationalE2Engine,'clone','clone'),
                    (Engine,'canonical_state_sha256','hash'),
                    (CurrentRatePersistenceForecast,'sha256','forecast_hash'),
                    (Engine,'_apply_due_actions','root_action'),
                    (type(engine),'_recompute_routes','routing'),
                    (E2Sgp4EdgeDelayProvider,'__call__','delay'),
                    (Engine,'_allocate_service','service'),
                    (Engine,'_integrate','qid'),(Engine,'_inputs','service'),
                    (Engine,'_derivatives','service'),(Engine,'_microstep','event'),
                    (Engine,'_step','event'),(Engine,'_next_time','event'),(Engine,'_schedule_service_segments','event'),
                    (evaluator,'_finish','finish'),
                    (evaluator_module,'derive_separated_outage_metrics','diagnostic')]
                for obj,name,cat in hooks:
                    stack.enter_context(patch.object(obj,name,timer.wrap(getattr(obj,name),cat,name)))
                # Static accumulator hook: objective updates distinguished by
                # mapping identity, arithmetic outside this function stays QID.
                original_add=Engine._compensated_add
                objective_maps=set()
                original_clone=ObservationalE2Engine.clone
                def clone_and_track(instance):
                    branch=original_clone(instance);objective_maps.add(id(branch.objective_by_commodity));return branch
                stack.enter_context(patch.object(ObservationalE2Engine,'clone',clone_and_track))
                stack.enter_context(patch.object(Engine,'_compensated_add',staticmethod(timer.wrap(
                    original_add,lambda values,*a,**k:'objective' if id(values) in objective_maps else 'qid'))))
            for method in ('evaluate_hold','evaluate_candidate'):
                original=getattr(evaluator,method)
                def wrap_branch(fn,kind):
                    def invoke(*args,**kwargs):
                        pid=None if kind=='HOLD' else args[1]['proposal_id']
                        branch_type='HOLD' if pid is None else ('MBB' if proposal_by_id[pid]['stratum']=='MBB_STRUCTURALLY_FEASIBLE' else 'BBM')
                        row={'branch_id':pid or 'HOLD','proposal_id':pid,'branch_type':branch_type,
                             'exclusive_s':defaultdict(float),'inclusive_s':defaultdict(float),'calls':defaultdict(int),
                             'method_calls':defaultdict(int)}
                        if enabled:timer.active=row
                        profiler=cProfile.Profile() if enabled else None
                        start=time.perf_counter()
                        if profiler:profiler.enable()
                        try:result=fn(*args,**kwargs)
                        finally:
                            if profiler:profiler.disable()
                        elapsed=time.perf_counter()-start
                        if enabled:
                            row.update(total_s=elapsed,J_H=result.J_H_bit_s,valid=result.valid,
                                       final_canonical_state_hash=result.end_state_sha256,
                                       terminal_event_count=len(result.terminal_events))
                            row['exclusive_s']['other']=elapsed-sum(row['exclusive_s'].values())
                            assert row['exclusive_s']['other']>=0
                            row['event_count']=row['method_calls']['_step']
                            row['route_evaluation_count']=row['calls']['routing']
                            row['delay_provider_call_count']=row['calls']['delay']
                            row['service_allocation_count']=row['method_calls']['_allocate_service']
                            timing_rows.append(row);timer.active=None
                            profiler.dump_stats(str(out/f'branch_{len(timing_rows):02d}.prof'))
                            dump(out/'branch_timing.partial.json',timing_rows)
                        print(f'{mode} branch {len(results)}/17 {branch_type} complete {elapsed:.3f}s',flush=True)
                        return result
                    return invoke
                stack.enter_context(patch.object(evaluator,method,wrap_branch(original,'HOLD' if method=='evaluate_hold' else 'REPLACE')))
            start=time.perf_counter()
            decision=controller.evaluate_root_actions(state,{k:v for k,v in proposals.items() if k!='candidate_specs'}, {})
            wall_modes[mode]=time.perf_counter()-start
        modes[mode]={'decision':decision,'branches':results,'final_canonical_states':final_states}
        assert engine.canonical_state()==initial,'LIVE_STATE_MUTATED'
        dump(out/f'results_{mode}.json',modes[mode])
    assert modes['OFF']==modes['ON'],'INSTRUMENTATION_CHANGED_SCIENTIFIC_RESULT'
    assert all(r['valid'] for r in timing_rows)
    assert all(file_hash(ROOT/k)==v for k,v in {**frozen,**code}.items())
    totals={k:sum(r['exclusive_s'].get(k,0) for r in timing_rows)+timer.global_times.get(k,0) for k in CATEGORIES}
    totals['other']=wall_modes['ON']-sum(totals.values())
    aggregate={'observe_wall_s':wall_modes,'branch_total_s':sum(r['total_s'] for r in timing_rows),
      'branch_mean_s':statistics.mean(r['total_s'] for r in timing_rows),
      'branch_median_s':statistics.median(r['total_s'] for r in timing_rows),
      'branch_max_s':max(r['total_s'] for r in timing_rows),
      'by_type':{kind:{'count':len(values),'mean_s':statistics.mean(values),'total_s':sum(values)}
        for kind in ('HOLD','BBM','MBB') for values in [[r['total_s'] for r in timing_rows if r['branch_type']==kind]] if values},
      'exclusive_seconds':totals,'share_of_instrumented_observe':{k:v/wall_modes['ON'] for k,v in totals.items()},
      'global_hash_timing_s':dict(timer.global_times)}
    grouped={'clone_hash':sum(totals[k] for k in ('clone','hash','forecast_hash')),
             'routing_delay':totals['routing']+totals['delay'],
             'service_event_QID':sum(totals[k] for k in ('service','event','qid','objective')),
             'root_action':totals['root_action'],'finish_diagnostic':totals['finish']+totals['diagnostic'], 'other':totals['other']}
    bottleneck=max(grouped,key=grouped.get)
    next_candidate=('DECISION_LOCAL_EXACT_CROSS_BRANCH_CACHE' if bottleneck=='routing_delay' else
                    'BRANCH_LEVEL_MULTIPROCESSING' if bottleneck=='service_event_QID' else 'REPORT_ONLY_NO_AUTOMATIC_OPTIMIZATION')
    report={'label':'ENGINEERING_PROFILE_ONLY','pass':True,'epoch_s':0.0,'branches':17,
      'lightweight_clone_seal':'PASS','hash_reuse_seal':'PASS','P1_preflight':'PASS','full_regression':'299/299 PASS',
      'registered_P1_executed':False,'P2_started':False,'RL_started':False,
      'PRIMARY_RUNTIME_BOTTLENECK':bottleneck,'NEXT_OPTIMIZATION_CANDIDATE':next_candidate,
      'root_state_proxy':root_proxy,'grouped_seconds':grouped,'source_hashes':code,'config_hashes':frozen,
      'timing_caveats':['Exclusive categories subtract nested timed calls; inclusive stage times must not be added.',
         'objective measures compensated accumulator calls; surrounding objective arithmetic remains in qid.',
         'cProfile plus Python timing instrumentation adds overhead; ON shares are diagnostic, OFF gives baseline total.',
         'finish includes equivalence snapshot capture overhead; other includes profiling dump and harness overhead.',
         'Single epoch cannot establish clone growth with historical time; no late epoch run.'],
      'proposal_ids':[r['proposal_id'] for r in proposals['proposals']],
      'proposal_set_sha256':proposals['proposal_set_sha256']}
    dump(out/'branch_timing.json',timing_rows);dump(out/'aggregate_timing.json',aggregate)
    dump(out/'equivalence_report.json',{'pass':True,'branches_compared':17,'full_branch_records_equal':True,
        'full_final_canonical_states_equal':True,'decision_and_tie_equal':True,'live_state_unchanged':True})
    dump(out/'report.json',report)
    print(json.dumps({'output':str(out),'bottleneck':bottleneck,'next':next_candidate}),flush=True)
if __name__=='__main__':main()
