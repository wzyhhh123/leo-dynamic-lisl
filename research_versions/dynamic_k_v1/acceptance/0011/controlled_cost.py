"""Authorized paired branches, small domains and bounded full-catalog diagnosis.

No completed global decision epoch or pilot matrix is executed here.
"""
import argparse,hashlib,json,time
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict
from contextlib import ExitStack
from unittest.mock import patch
import workflow as w
from trace_costs import CallTrace
from equivalence import bind_live,stable
from runtime.n4_p0r_handle_reader import HandleReaderLease
from runtime.n4_p0 import (ForecastInput,PilotCost,make_sanitized_root,score_action,score_candidates,causal_view,data_hash)
from runtime.n2_actions import Hold,Add,Drop,Replace,Setup,LinkRef,action_key
from runtime.n2_physical import Sgp4PhysicalGuard
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace,TrafficSegment
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.sgp4_model import Sgp4Model
from runtime.n1b_observer import ObservedD2Engine
old_cost=w.load('p0r_old_cost',w.V/'acceptance/0010/cost_measurement.py')
SETUP=Setup(.5,.5,.5);COST=PilotCost(6.,1000.)

def stage_manifest(sha):
    path=w.A/'implementation_manifest.json';assert w.vc.file_info(path)['sha256']==sha
    doc=w.vc.read_json(path);assert doc['schema']=='dynamic_k_n4_p0r_candidate_v1'
    for row in doc['files']+list(doc['anchors'].values()):assert w.vc.binding(w.P,row['path'])==row,row['path']
    return dict(path=path.relative_to(w.P).as_posix(),sha256=sha)
def real_fixture():
    f=w.setup();template,rows=f.real_fixture(full_catalog=True);nodes=template.engine.nodes;ex=TerminalExecutor(nodes)
    ex.submit([Connect(('X0_1','D2'),('X1_1','D1'),600.,0.,0.,0.)])
    trace=PiecewiseConstantTrafficTrace(('f_bg','f_hot'),[
        TrafficSegment(0.,8.,{'f_bg':200000.,'f_hot':400000.},'CURRENT'),
        TrafficSegment(8.,20.,{'f_bg':200000.,'f_hot':1200000.},'REAL_FUTURE_NOT_EXPOSED')])
    e=ObservedD2Engine(nodes,template.engine.fixed_edges,1e6,
        [Commodity('f_bg','X0_1','X1_1'),Commodity('f_hot','X0_10','X1_10')],trace,template.engine.delay,ex)
    live=f.wrap(e,template.validator.physical,30.);live.advance_to(3.);return live,rows
def plain(fn):
    start=time.perf_counter();value=fn();return value,dict(wallclock_s=time.perf_counter()-start,instrumentation='NONE',memory=old_cost.memory())
def timed(fn,instrumented):return CallTrace().run(fn) if instrumented else plain(fn)

class DiagnosticDeadline(RuntimeError):pass
class CatalogAudit:
    def __init__(self,live,wall_s):
        self.live=live;self.wall_s=wall_s;self.start=0.;self.rows=[];self.metrics={};self.keys=defaultdict(Counter);self.output_keys={};self.stack=[];self.exclusive=defaultdict(float)
    def wrap(self,category,old,key=None):
        def call(obj,*args,**kwargs):
            start=time.perf_counter();entry=[category,start,0.];self.stack.append(entry)
            try:
                result=old(obj,*args,**kwargs)
                if key:
                    k=key(obj,args,kwargs);self.keys[category][repr(k)]+=1
                    if category=='sgp4':
                        fp=hashlib.sha256(result[0].tobytes()+result[1].tobytes()).hexdigest()
                        previous=self.output_keys.get(repr(k));assert previous is None or previous==fp,'NONDETERMINISTIC_SGP4_OUTPUT'
                        self.output_keys[repr(k)]=fp
                return result
            finally:
                elapsed=time.perf_counter()-start;self.stack.pop();r=self.metrics.setdefault(category,dict(calls=0,inclusive_wallclock_s=0.))
                r['calls']+=1;r['inclusive_wallclock_s']+=elapsed;self.exclusive[category]+=elapsed-entry[2]
                if self.stack:self.stack[-1][2]+=elapsed
        return call
    def validate(self,ex,action):
        if time.perf_counter()-self.start>=self.wall_s:raise DiagnosticDeadline('FULL_CATALOG_DIAGNOSTIC_WALL_LIMIT')
        start=time.perf_counter();result=self.original_validate(ex,action)
        self.rows.append(dict(action=asdict(action),accepted=result['accepted'],reason=result['reason'],wallclock_s=time.perf_counter()-start,
            real_release_refs=[asdict(x) for x in result.get('release_refs',())],actual_immediate_release_ids=result.get('actual_immediate_release_ids')))
        return result
    def run(self):
        before=causal_view(self.live);ex=self.live.engine.executor;windows=self.live.validator.physical.catalog.terminal_pair_candidates(ex.now,ex.satellite_ids)
        self.original_validate=self.live.validator.validate
        def sgp4_key(obj,args,kwargs):
            times=args[0] if args else kwargs['times'];ids=args[1] if len(args)>1 else kwargs.get('ids')
            return (self.live.physical_sha256,tuple(float(t).hex() for t in times),tuple(ids) if ids is not None else None)
        with ExitStack() as context:
            for cls,name,category,key in [(Sgp4Model,'state','sgp4',sgp4_key),
                (Sgp4PhysicalGuard,'evaluate','LOS_FOR_geometry',lambda obj,args,kw:(self.live.physical_sha256,args[0],args[1],float(args[2]).hex())),
                (TerminalExecutor,'clone_for_transaction','transaction_clone',None),
                (TerminalExecutor,'snapshot','snapshot_320_terminals',None),(TerminalExecutor,'_log','log_320_terminals',None)]:
                context.enter_context(patch.object(cls,name,self.wrap(category,getattr(cls,name),key)))
            context.enter_context(patch.object(self.live.validator,'validate',self.validate))
            self.start=time.perf_counter();source=None;stop=None
            try:source=self.live.candidates(SETUP)
            except DiagnosticDeadline as error:stop=str(error)
            elapsed=time.perf_counter()-self.start
        assert before==causal_view(self.live),'CATALOG_DIAGNOSTIC_MUTATED_ROOT'
        counts=Counter(r['action']['kind'] for r in self.rows);legal=Counter(r['action']['kind'] for r in self.rows if r['accepted'])
        return dict(status='COMPLETE_CATALOG_ENUMERATION' if source else 'STOP_COST_EXCESSIVE_PARTIAL_CATALOG',
            wallclock_s=elapsed,diagnostic_wall_limit_s=self.wall_s,limit_checked_between_indivisible_real_validations=True,
            eligible_window_count=len(windows),completed_validation_count=len(self.rows),completed_counts_by_kind=dict(counts),
            accepted_in_completed_prefix_by_kind=dict(legal),reasons_in_completed_prefix=dict(Counter(r['reason'] or 'ACCEPTED' for r in self.rows)),
            complete_legal_counts=source['diagnostics'] if source else None,
            complete_masks=[dict(action=asdict(x['action']),legal=x['legal'],reason=x['reason']) for x in source['masks']] if source else None,
            selected_global_action=None,completed_global_epoch_count=0,stop_reason=stop,completed_prefix=self.rows,
            method_metrics=self.metrics,exclusive_method_s=dict(self.exclusive),
            pure_key_diagnostic={k:dict(calls=sum(v.values()),distinct_exact_keys=len(v),repeated_exact_keys=sum(v.values())-len(v),
                key_components='pinned physical input SHA + exact binary64 time hex + ordered satellite IDs/terminal endpoints; no rounded keys',
                reuse_implemented=False) for k,v in self.keys.items()},
            repeated_sgp4_outputs_bitwise_verified=True,terminal_rows_per_snapshot_or_log=len(ex.terminals),
            candidate_budget=None,catalog_narrowed=False,worker_count=1,physical_checks_skipped=False,
            instrumentation='coarse method observers + bounded validator observer; original operations exactly once',memory=old_cost.memory())

def main(sha):
    for name in ('p0_original.json','p0_handle.json','final_reader_tests.json','final_pre_post_all_action_equivalence.json',
        'final_regression_N1a.json','final_regression_N1b.json','final_regression_N2.json','final_regression_N3.json','version_protection_tests.json'):
        assert w.vc.read_json(w.A/name)['status']=='PASS',name
    h=w.vc.read_json(w.A/'historical_regression.json');old=w.vc.read_json(w.V/'acceptance/0010/historical_regression.json')
    assert h['base']['failures']==old['base']['failures'] and h['physical_gate_c']['failures']==[]
    start=time.perf_counter();new_binding=stage_manifest(sha);binding_s=time.perf_counter()-start
    live,rows=real_fixture();view=causal_view(live);forecast=ForecastInput.from_current(view.observation,T_s=30.,H_s=6.,mode='PERSIST')
    deps=w.old.dependencies();g=w.guard();results={};baseline_memory=old_cost.memory()
    # Serial same-root paired measurement, no concurrent testing workers.
    for instrumented in (False,True):
        mode='instrumented' if instrumented else 'plain';print('PAIRED_ORIGINAL_'+mode,flush=True)
        root,rt=timed(lambda:make_sanitized_root(live,forecast,binding=g),instrumented)
        value,bt=timed(lambda:score_action(root,Hold(),COST,cadence_s=3.),instrumented)
        results['original_'+mode]=dict(root=rt,branch=bt,result=value)
        w.write('paired_original_'+mode+'.json',results['original_'+mode])
    start=time.perf_counter();lease=HandleReaderLease(deps+[g],w.vc);construction_s=time.perf_counter()-start
    start=time.perf_counter();lease.__enter__();lock_acquisition_and_postlock_verification_s=time.perf_counter()-start
    try:
        stage_manifest(sha)
        optimized=bind_live(live.clone(),lease);p0=lease.guard(g)
        for instrumented in (False,True):
            mode='instrumented' if instrumented else 'plain';print('PAIRED_HANDLE_'+mode,flush=True)
            read_start=lease.reads;bytes_start=lease.bytes_hashed
            root,rt=timed(lambda:make_sanitized_root(optimized,forecast,binding=p0),instrumented)
            value,bt=timed(lambda:score_action(root,Hold(),COST,cadence_s=3.),instrumented)
            results['handle_'+mode]=dict(root=rt,branch=bt,result=value,fresh_native_file_reads=lease.reads-read_start,
                fresh_native_bytes_hashed=lease.bytes_hashed-bytes_start)
            w.write('paired_handle_'+mode+'.json',results['handle_'+mode])
        reference=stable(results['original_plain']['result'])
        assert all(stable(r['result'])==reference for r in results.values()),'PAIRED_COST_FIELDS_NOT_EXACT'
        w.write('paired_cost_summary.json',dict(status='PASS_EXACT_EQUIVALENCE',new_binding=new_binding,new_binding_startup_s=binding_s,
            reader_construction_original_full_checks_s=construction_s,
            lock_acquisition_and_original_postlock_full_checks_s=lock_acquisition_and_postlock_verification_s,
            startup_not_hidden_or_amortized_into_three_second_claim=True,baseline_memory=baseline_memory,
            measures={k:dict(root_wallclock_s=r['root']['wallclock_s'],branch_wallclock_s=r['branch']['wallclock_s']) for k,r in results.items()},
            scalar_result={k:v for k,v in reference.items() if k in ('J_h_bit_s','N_end_bits','E_h_J','DeltaE_h_J','cost_bit_s','terminal_event_count','service_observation_count','cohort_count')},
            same_physical_state_and_forecast=True,exact_equality=True,three_second_realtime_guaranteed=False))
        base=LinkRef.from_link(next(iter(optimized.engine.executor.links.values())))
        hot=(('X0_10','D2'),('X1_10','D1'))
        proposals=[Hold(),Add(*hot,SETUP),Drop(base),Replace((base,),*hot,SETUP,'BBM'),Replace((base,),*hot,SETUP,'MBB')]
        masks=[dict(action=asdict(a),accepted=optimized.validator.validate(optimized.engine.executor,a)['accepted']) for a in proposals]
        assert all(m['accepted'] for m in masks)
        roots={};domains={}
        for mode in ('ZERO','PERSIST'):
            fc=ForecastInput.from_current(view.observation,T_s=30.,H_s=6.,mode=mode)
            roots[mode]=make_sanitized_root(optimized,fc,binding=p0);roots[mode].verify_isolation()
            print('SMALL_DOMAIN_'+mode,flush=True);start=time.perf_counter()
            result=score_candidates(roots[mode],proposals,COST,cadence_s=3.)
            domains[mode]=dict(wallclock_s=time.perf_counter()-start,decision=result,
                forecast_input_sha256=fc.sha256,branch_count=len(result['branches']),branch_seconds=sum(x['effective_horizon_s'] for x in result['branches']),memory=old_cost.memory())
            w.write('small_domain_'+mode+'.json',domains[mode])
        assert roots['ZERO'].view==roots['PERSIST'].view and roots['ZERO'].prefix_sha256==roots['PERSIST'].prefix_sha256
        w.write('small_domain_audit.json',dict(status='PASS',same_sanitized_current_state=True,same_historical_prefix=True,
            candidate_masks=masks,candidate_count=5,complete_physical_catalog_legal_counts=None,
            selection_scope='FIVE_EXPLICIT_PHYSICALLY_VALID_ACTIONS_COST_CHECK_ONLY_NOT_GLOBAL_OPTIMAL',
            inherited_catalog_row_count=len(rows),hidden_future_used=False,main_pilot_runs=0))
        print('BOUNDED_FULL_CATALOG_START',flush=True)
        diagnosis=CatalogAudit(optimized,60.).run();diagnosis['registered_catalog_rows']=len(rows)
        w.write('bounded_catalog_cost.json',diagnosis)
        w.write('controlled_cost_completion.json',dict(status='MEASUREMENTS_COMPLETE_WITH_CATALOG_BOUNDARY',paired_hold_measurements=4,
            small_domain_predictions=10,main_pilot_runs=0,completed_global_epoch_count=0,
            catalog_status=diagnosis['status'],workers=1,scientific_gate_pass=False,new_binding=new_binding))
        print(diagnosis['status'],diagnosis['wallclock_s'],diagnosis['completed_validation_count'],flush=True)
        assert view==causal_view(live) and view==causal_view(optimized)
        stage_manifest(sha)
    finally:lease.__exit__(None,None,None)
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--sha',required=True);args=q.parse_args();main(args.sha)
