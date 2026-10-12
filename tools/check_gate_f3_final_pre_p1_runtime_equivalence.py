"""Final pre-P1 multi-epoch runtime equivalence gate (no cProfile)."""
from __future__ import annotations

from copy import deepcopy
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT/'src'),str(PROJECT)]

from dynamic_lisl.candidate_proposer import FrozenTerminalPairProposer
from dynamic_lisl.common import read_json
from dynamic_lisl.common_router import DeterministicShortestPropagationDelayRouter
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor
from dynamic_lisl.scientific_snapshot import ScientificSnapshotEvaluator
from dynamic_lisl.transition_profiler import profile_transition_legacy_reference

EPOCHS=(0.0,2.0,4.0,6.0,8.0,10.0)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(
        value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
        allow_nan=False).encode('utf-8')).hexdigest()


def sum_numeric(value):
    """Sum numeric leaves in a deterministic snapshot without assumptions."""
    if isinstance(value,dict):
        return sum(sum_numeric(item) for item in value.values())
    if isinstance(value,(list,tuple)):
        return sum(sum_numeric(item) for item in value)
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        return float(value)
    return 0.0


def normalized_action(row):
    return {key:value for key,value in row.items()
            if key not in ('controller_decision_runtime_s',
                           'action_canonical_sha256')}


def public_proposal_set(value):
    return {key:item for key,item in value.items()
            if key!='candidate_specs'}


class CapturingSource:
    def __init__(self,inner):
        self.inner=inner;self.specs=[]
    def __call__(self,*args,**kwargs):
        value=tuple(self.inner(*args,**kwargs));self.specs.append(value)
        return value


class CapturingProposer:
    def __init__(self,inner):
        self.inner=inner;self.results=[]
    def propose(self,*args,**kwargs):
        value=self.inner.propose(*args,**kwargs);self.results.append(value)
        return value


class CapturingEvaluator(ScientificSnapshotEvaluator):
    def __init__(self,engine,memoized):
        super().__init__(engine,use_edge_delay_memoization=memoized)
        self.results=[]
    def evaluate_proposal_set(self,proposal_set):
        value=super().evaluate_proposal_set(proposal_set)
        self.results.append(value)
        return value


class CapturingRouter(DeterministicShortestPropagationDelayRouter):
    def __init__(self,optimized):
        super().__init__(use_adjacency_reuse=optimized,
                         use_same_destination_reuse=optimized)
        self.records=[]
    def routes_to_destinations(self,*args,**kwargs):
        value=super().routes_to_destinations(*args,**kwargs)
        time_s=float(kwargs.get('time_s',args[4] if len(args)>4 else 0.0))
        provider=(kwargs.get('propagation_delay_s')
                  if 'propagation_delay_s' in kwargs else args[3])
        self.records.append((time_s,value,provider))
        return value


def network_state(engine):
    return {
        'canonical_state_sha256':engine.canonical_state_sha256(),
        'G_active_G_admit':deepcopy(engine.graph),
        'queues':engine.queues.snapshot(),
        'in_flight':engine.in_flight.snapshot(),
        'arrived':dict(sorted(engine.arrived.items())),
        'delivered':dict(sorted(engine.delivered.items())),
        'terminal':engine.executor.snapshot(),
        'terminal_event_sequence':deepcopy(engine.terminal_event_sequence),
        'graph_event_sequence':deepcopy(engine.graph_event_sequence),
        'action_results':deepcopy(engine.action_results),
    }


def route_record_document(record):
    time_s,routes,provider=record
    rows=[];costs=[]
    for (node,commodity),route in routes.items():
        route_list=list(route) if route is not None else None
        rows.append([node,commodity,route_list])
        cost=(None if route is None else sum(
            float(provider(edge,time_s)) for edge in zip(route,route[1:])))
        costs.append([node,commodity,cost])
    return {
        'time_s':time_s,'entry_count':len(rows),
        'route_table_sha256':canonical_hash(rows),
        'route_cost_sha256':canonical_hash(costs),
        'none_count':sum(row[2] is None for row in rows),
    }


def snapshot_document(value):
    hold,candidates=value
    return {'hold':hold.to_dict(),'candidates':[
        {'proposal_id':proposal_id,'evaluation':evaluation.to_dict()}
        for proposal_id,evaluation in candidates]}


def epoch_scientific_document(stub,source,proposer,evaluator,router,executor):
    index=stub['index']
    specs=source.specs[index]
    proposal=proposer.results[index]
    source_report=stub['source_report']
    route_records=[route_record_document(row)
                   for row in router.records[stub['route_start']:stub['route_end']]]
    snapshots=[snapshot_document(row)
               for row in evaluator.results[
                   stub['snapshot_start']:stub['snapshot_end']]]
    return {
        'time_s':stub['time_s'],
        'candidate_proposal':{
            'raw_candidate_ids':[row.proposal_id for row in specs],
            'raw_source_report':source_report,
            'proposal_set':public_proposal_set(proposal),
        },
        'routing_snapshot':{
            'route_evaluation_count':len(route_records),
            'route_tables_and_costs':route_records,
            'scientific_snapshot_evaluations':snapshots,
        },
        'controller':normalized_action(executor.actions[index]),
        'physical_and_network_after_decision':stub['after_decision'],
        'state_chain':{
            'canonical_state_sha256_before_decision':
                stub['before_decision']['canonical_state_sha256'],
            'canonical_state_sha256_after_decision':
                stub['after_decision']['canonical_state_sha256'],
            'canonical_state_sha256_after_next_advance':
                stub['after_next_advance']['canonical_state_sha256'],
            'next_advance_target_s':stub['next_advance_target_s'],
            'prefix_end_no_future_interval':stub['prefix_end_no_future_interval'],
        },
    }


def configure_executor(assets,optimized):
    manifest=read_json(PROJECT/'configs/gate_f3_execution_manifest_v1.json')
    template=next(row for row in manifest['runs']
        if row['block_id']=='P1' and row['controller']=='B1'
        and float(row['rho'])==0.5)
    row={**template,
         'run_id':'ENGINEERING_PROFILE_ONLY-FINAL-PRE-P1-EQUIVALENCE',
         'block_id':'ENGINEERING_PROFILE_ONLY',
         'performance_status':'ENGINEERING_PROFILE_ONLY_NOT_SCIENTIFIC_RESULT'}
    executor=P1RunExecutor(assets,row,progress_recorder=None)
    router=CapturingRouter(optimized);executor.engine.router=router
    evaluator=CapturingEvaluator(executor.engine,memoized=optimized)
    executor.controller.evaluator=evaluator
    source=CapturingSource(executor.source);executor.candidate_source=source
    proposer=CapturingProposer(FrozenTerminalPairProposer(
        transition_profiler=(None if optimized
                             else profile_transition_legacy_reference)))
    if optimized:
        proposer=CapturingProposer(FrozenTerminalPairProposer())
    executor.proposer=proposer
    return executor,source,proposer,evaluator,router


def run_branch(assets,optimized,out):
    executor,source,proposer,evaluator,router=(
        configure_executor(assets,optimized))
    label='optimized' if optimized else 'reference'
    stubs=[];wall_start=time.perf_counter()
    for index,epoch in enumerate(EPOCHS):
        advance_start=time.perf_counter()
        if executor.engine.now < epoch-1e-12:
            executor.engine.advance_to(epoch)
        executor.engine.settle_current_time()
        executor._pending_network_advance_wall_s=(
            executor._pending_network_advance_wall_s
            +time.perf_counter()-advance_start)
        before=network_state(executor.engine)
        route_start=len(router.records);snapshot_start=len(evaluator.results)
        executor._decision(epoch,index)
        after=network_state(executor.engine)
        source_report=deepcopy(source.inner.last_report)
        if index+1<len(EPOCHS):
            next_epoch=EPOCHS[index+1]
            advance_start=time.perf_counter()
            executor.engine.advance_to(next_epoch)
            executor.engine.settle_current_time()
            executor._pending_network_advance_wall_s=(
                time.perf_counter()-advance_start)
            after_next=network_state(executor.engine)
            prefix_end=False
        else:
            next_epoch=epoch
            executor.engine.advance_to(epoch)
            executor.engine.settle_current_time()
            after_next=network_state(executor.engine)
            prefix_end=True
        stub={'index':index,'time_s':epoch,
              'route_start':route_start,'route_end':len(router.records),
              'snapshot_start':snapshot_start,
              'snapshot_end':len(evaluator.results),
              'source_report':source_report,
              'before_decision':before,'after_decision':after,
              'after_next_advance':after_next,
              'next_advance_target_s':next_epoch,
              'prefix_end_no_future_interval':prefix_end}
        stubs.append(stub)
        progress={'branch':label,'epoch_index':index,'sim_time_s':epoch,
                  'wall_elapsed_s':time.perf_counter()-wall_start,
                  'timing':executor.epoch_runtime_records[-1]}
        with (out/'progress.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(progress,sort_keys=True)+'\n')
    runtime=time.perf_counter()-wall_start
    epoch_docs=[epoch_scientific_document(
        stub,source,proposer,evaluator,router,executor) for stub in stubs]
    natural=[]
    for index,doc in enumerate(epoch_docs):
        state=doc['physical_and_network_after_decision']
        terminal=state['terminal']
        natural.append({
            'time_s':doc['time_s'],
            'total_queue_bits':sum_numeric(state['queues']),
            'total_inflight_bits':sum_numeric(state['in_flight']),
            'total_delivered_bits':sum_numeric(state['delivered']),
            'terminal_active_link_count':len(terminal['links']),
            'terminal_reservation_count':len(terminal['reservations']),
            'selected_action':doc['controller']['selected_action'],
            'selected_proposal_id':doc['controller']['selected_proposal_id'],
            'proposal_set_sha256':doc['candidate_proposal'][
                'proposal_set']['proposal_set_sha256'],
        })
    return {'label':label,'epochs':epoch_docs,'natural_metrics':natural,
            'runtime_records':deepcopy(executor.epoch_runtime_records),
            'total_wall_clock_s':runtime,
            'final_state_sha256':executor.engine.canonical_state_sha256()}


def compare_epochs(reference,optimized):
    rows=[]
    for left,right in zip(reference['epochs'],optimized['epochs']):
        category={key:left[key]==right[key] for key in (
            'candidate_proposal','routing_snapshot','controller',
            'physical_and_network_after_decision','state_chain')}
        rows.append({'time_s':left['time_s'],'categories':category,
                     'exact_equal':all(category.values()),
                     'reference_epoch_sha256':canonical_hash(left),
                     'optimized_epoch_sha256':canonical_hash(right),
                     'state_chain':left['state_chain']})
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir')
    args=parser.parse_args()
    if args.output_dir:
        out=Path(args.output_dir)
        if not out.is_absolute():out=PROJECT/out
    else:
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        out=PROJECT/'outputs'/f'gate_f3_final_pre_p1_runtime_equivalence_{stamp}'
    if out.exists() and any(out.iterdir()):
        raise SystemExit('OUTPUT_DIR_MUST_BE_NEW_OR_EMPTY')
    out.mkdir(parents=True,exist_ok=True)
    assets=GateE2Assets()
    reference=run_branch(assets,False,out)
    optimized=run_branch(assets,True,out)
    comparisons=compare_epochs(reference,optimized)
    natural=optimized['natural_metrics']
    natural_keys={(row['total_queue_bits'],row['total_inflight_bits'],
                   row['total_delivered_bits'],row['terminal_active_link_count'],
                   row['terminal_reservation_count']) for row in natural}
    natural_verified=len(natural_keys)>1 and any(
        row['total_queue_bits']>0.0 or (row['total_inflight_bits'] or 0.0)>0.0
        or row['total_delivered_bits']>0.0 for row in natural[1:])
    timings=optimized['runtime_records']
    runtime_summary={'classification':'ENGINEERING_RUNTIME_EVIDENCE',
        'cprofile_enabled':False,'sim_end_s':10.0,
        'production_optimized_per_epoch':timings,
        'production_optimized_total_wall_clock_s':optimized['total_wall_clock_s'],
        'production_optimized_mean_epoch_wall_s':sum(
            row['epoch_total_wall_s'] for row in timings)/len(timings),
        'production_optimized_max_epoch_wall_s':max(
            row['epoch_total_wall_s'] for row in timings),
        'reference_total_wall_clock_s':reference['total_wall_clock_s']}
    epoch_report={'schema':'gate_f3_final_pre_p1_epoch_equivalence_v1',
        'epochs':comparisons,'reference_natural_metrics':reference['natural_metrics'],
        'optimized_natural_metrics':natural,
        'all_epoch_equivalence':len(comparisons)==6 and all(
            row['exact_equal'] for row in comparisons)}
    report={'schema':'gate_f3_final_pre_p1_runtime_equivalence_report_v1',
        'classification':'ENGINEERING_PROFILE_ONLY','sim_end_s':10.0,
        'decision_epochs_s':list(EPOCHS),'decision_epoch_count':len(comparisons),
        'cprofile_enabled':False,'natural_state_evolution_verified':natural_verified,
        'all_epoch_equivalence':epoch_report['all_epoch_equivalence'],
        'runtime_optimization_status':'STOPPED_AFTER_PHASE2B2',
        'registered_P1_executed':False,'P2_started':False,'RL_started':False,
        'phase2b3_started':False}
    report['pass']=(report['decision_epoch_count']==6 and natural_verified
                    and report['all_epoch_equivalence'])
    report['status']=('FINAL_PRE_P1_RUNTIME_EQUIVALENCE_PASS'
                      if report['pass'] else
                      'FINAL_PRE_P1_RUNTIME_EQUIVALENCE_FAIL')
    for name,value in (('report.json',report),
                       ('epoch_equivalence.json',epoch_report),
                       ('runtime_summary.json',runtime_summary)):
        (out/name).write_text(json.dumps(value,indent=2,sort_keys=True,
                                        ensure_ascii=False,allow_nan=False)+'\n',
                            encoding='utf-8')
    print(json.dumps({'status':report['status'],'output_dir':str(out),
        'decision_epoch_count':report['decision_epoch_count'],
        'all_epoch_equivalence':report['all_epoch_equivalence'],
        'natural_state_evolution_verified':natural_verified,
        'reference_wall_s':reference['total_wall_clock_s'],
        'optimized_wall_s':optimized['total_wall_clock_s']},indent=2))
    return 0 if report['pass'] else 1


if __name__=='__main__':raise SystemExit(main())

