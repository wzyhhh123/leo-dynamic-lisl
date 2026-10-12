"""Engineering-only Phase 2B-2 Phase-2B-1-reference-vs-same-destination-reuse checker."""
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


class InstrumentedRouter(DeterministicShortestPropagationDelayRouter):
    def __init__(self, reuse):
        super().__init__(use_adjacency_reuse=True,
                         use_same_destination_reuse=reuse)
        self.routes_calls=0
        self.path_search_count=0
        self.path_search_wall_s=0.0
        self.adjacency_build_count=0
        self.adjacency_build_wall_s=0.0
        self.route_tables=[]
        self.route_times=[]

    def _build_adjacency(self, edges):
        started=time.perf_counter()
        value=super()._build_adjacency(edges)
        self.adjacency_build_wall_s+=time.perf_counter()-started
        self.adjacency_build_count+=1
        return value

    def _path_with_adjacency(self,*args,**kwargs):
        started=time.perf_counter()
        value=super()._path_with_adjacency(*args,**kwargs)
        self.path_search_wall_s+=time.perf_counter()-started
        self.path_search_count+=1
        return value

    def routes_to_destinations(self,*args,**kwargs):
        self.routes_calls+=1
        value=super().routes_to_destinations(*args,**kwargs)
        self.route_tables.append(value)
        self.route_times.append(float(kwargs.get(
            'time_s',args[4] if len(args)>4 else 0.0)))
        return value


class CapturingProposer:
    def __init__(self):
        self.inner=FrozenTerminalPairProposer()
        self.results=[]
        self.raw_candidate_ids=[]

    def propose(self,*args,**kwargs):
        candidates=tuple(args[1] if len(args)>1 else kwargs['candidates'])
        self.raw_candidate_ids.append(tuple(
            row.proposal_id for row in candidates))
        call_args=list(args)
        if len(call_args)>1:
            call_args[1]=candidates
        else:
            kwargs=dict(kwargs);kwargs['candidates']=candidates
        result=self.inner.propose(*call_args,**kwargs)
        self.results.append(result)
        return result


class CapturingEvaluator(ScientificSnapshotEvaluator):
    def __init__(self,engine):
        super().__init__(engine,use_edge_delay_memoization=True)
        self.results=[]

    def evaluate_edges(self,edges):
        value=super().evaluate_edges(edges)
        self.results.append(value)
        return value


def canonical_hash(value):
    return hashlib.sha256(json.dumps(
        value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
        allow_nan=False).encode('utf-8')).hexdigest()


def normalized_action(row):
    return {key:value for key,value in row.items()
            if key not in ('controller_decision_runtime_s',
                           'action_canonical_sha256')}


def route_table_document(tables):
    return [[
        [node,commodity,list(route) if route is not None else None]
        for (node,commodity),route in table.items()
    ] for table in tables]


def route_cost_document(tables,times,provider):
    result=[]
    for table,time_s in zip(tables,times):
        rows=[]
        for key,route in table.items():
            cost=(None if route is None else sum(
                float(provider(edge,time_s))
                for edge in zip(route,route[1:])))
            rows.append([key[0],key[1],cost])
        result.append(rows)
    return result


def public_proposal_set(value):
    return {key:item for key,item in value.items()
            if key!='candidate_specs'}


def run_mode(assets,controller_id,reuse):
    manifest=read_json(PROJECT/'configs/gate_f3_execution_manifest_v1.json')
    template=next(row for row in manifest['runs']
        if row['block_id']=='P1' and row['controller']==controller_id
        and float(row['rho'])==0.5)
    row={**template,
         'run_id':f'ENGINEERING_PROFILE_ONLY-PHASE2B2-{controller_id}-'
                  +('REUSE' if reuse else 'PHASE2B1_REFERENCE'),
         'block_id':'ENGINEERING_PROFILE_ONLY',
         'performance_status':'ENGINEERING_PROFILE_ONLY_NOT_SCIENTIFIC_RESULT'}
    executor=P1RunExecutor(assets,row,progress_recorder=None)
    router=InstrumentedRouter(reuse)
    executor.engine.router=router
    evaluator=CapturingEvaluator(executor.engine)
    executor.controller.evaluator=evaluator
    proposer=CapturingProposer()
    executor.proposer=proposer
    started=time.perf_counter()
    prefix=executor.run_engineering_prefix(0.0)
    wall=time.perf_counter()-started
    proposal=proposer.results[0]
    state={
        'raw_candidate_ids':[list(row) for row in proposer.raw_candidate_ids],
        'actions':[normalized_action(row) for row in prefix['actions']],
        'proposal_set':public_proposal_set(proposal),
        'snapshot_evaluations':[row.to_dict() for row in evaluator.results],
        'route_tables':route_table_document(router.route_tables),
        'route_costs':route_cost_document(
            router.route_tables,router.route_times,executor.engine.delay),
        'terminal_event_sequence':deepcopy(
            executor.engine.terminal_event_sequence),
        'graph_event_sequence':deepcopy(executor.engine.graph_event_sequence),
        'G_active_G_admit':deepcopy(executor.engine.graph),
        'queues':executor.engine.queues.snapshot(),
        'in_flight':executor.engine.in_flight.snapshot(),
        'arrived':dict(sorted(executor.engine.arrived.items())),
        'delivered':dict(sorted(executor.engine.delivered.items())),
        'terminal_snapshot':executor.engine.executor.snapshot(),
        'canonical_live_state':executor.engine.canonical_state_sha256(),
    }
    epoch=prefix['epoch_runtime_records'][0]
    return {
        'controller':controller_id,
        'same_destination_reuse':reuse,
        'state':state,
        'state_sha256':canonical_hash(state),
        'routes_to_destinations_calls':router.routes_calls,
        'path_search_count':router.path_search_count,
        'adjacency_build_count':router.adjacency_build_count,
        'adjacency_build_wall_s':router.adjacency_build_wall_s,
        'path_search_wall_s':router.path_search_wall_s,
        'B1_or_B3_observe_wall_s':epoch['controller_observe_wall_s'],
        'total_epoch_wall_s':epoch['epoch_total_wall_s'],
        'total_prefix_wall_s':wall,
        'raw_candidates':len(proposer.raw_candidate_ids[0]),
        'final_proposals':len(proposal['proposals']),
        'proposal_set_sha256':proposal['proposal_set_sha256'],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir')
    args=parser.parse_args()
    if args.output_dir:
        out=Path(args.output_dir)
        if not out.is_absolute():out=PROJECT/out
    else:
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        out=PROJECT/'outputs'/f'gate_f3_runtime_phase2b2_{stamp}'
    if out.exists() and any(out.iterdir()):
        raise SystemExit('OUTPUT_DIR_MUST_BE_NEW_OR_EMPTY')
    out.mkdir(parents=True,exist_ok=True)
    assets=GateE2Assets()
    runs={}
    for controller in ('B1','B3'):
        runs[controller]={
            'legacy':run_mode(assets,controller,False),
            'optimized':run_mode(assets,controller,True)}
    equivalence={
        controller:runs[controller]['legacy']['state']
                   ==runs[controller]['optimized']['state']
        for controller in runs}
    old=runs['B1']['legacy'];new=runs['B1']['optimized']
    observe_improved=(new['B1_or_B3_observe_wall_s']
                      <old['B1_or_B3_observe_wall_s'])
    epoch_improved=new['total_epoch_wall_s']<old['total_epoch_wall_s']
    report={
        'schema':'gate_f3_runtime_phase2b2_report_v1',
        'classification':'ENGINEERING_PROFILE_ONLY',
        'sim_end_s':0.0,
        'registered_P1_executed':False,
        'phase2b2_implementation_started':True,
        'phase2b3_started':False,
        'P2_started':False,
        'RL_started':False,
        'final_pre_P1_runtime_equivalence_required':True,
        'final_pre_P1_runtime_equivalence_executed':False,
        'controller_equivalence':equivalence,
        'B1_performance':{
            'legacy':{k:v for k,v in old.items() if k!='state'},
            'optimized':{k:v for k,v in new.items() if k!='state'},
            'adjacency_build_reduction':old['adjacency_build_count']
                                        -new['adjacency_build_count'],
            'adjacency_build_reduction_fraction':
                1-new['adjacency_build_count']/old['adjacency_build_count'],
            'observe_speedup':old['B1_or_B3_observe_wall_s']
                              /new['B1_or_B3_observe_wall_s'],
            'epoch_speedup':old['total_epoch_wall_s']
                            /new['total_epoch_wall_s'],
        },
        'unique_destination_count':14,
        'commodity_count':16,
        'expected_legacy_path_search_count':46080,
        'expected_optimized_path_search_count':40320,
        'path_search_reduction_exactly_explained_by_destination_duplicates':(
            old['path_search_count']==46080
            and new['path_search_count']==40320),
        'adjacency_build_count_unchanged':(
            old['adjacency_build_count']==new['adjacency_build_count']),
        'B1_observe_wall_time_improved':observe_improved,
        'total_epoch_wall_time_improved':epoch_improved,
    }
    report['pass']=(
        all(equivalence.values())
        and old['path_search_count']==46080
        and new['path_search_count']==40320
        and old['adjacency_build_count']==new['adjacency_build_count'])
    report['status']=('GATE_F3_RUNTIME_PHASE2B2_PASS'
                      if report['pass'] else 'GATE_F3_RUNTIME_PHASE2B2_FAIL')
    (out/'report.json').write_text(json.dumps(
        report,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf-8')
    for controller in runs:
        for mode,value in runs[controller].items():
            (out/f'{controller.lower()}_{mode}_equivalence.json').write_text(
                json.dumps(value['state'],indent=2,sort_keys=True,
                           ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({
        'status':report['status'],'output_dir':str(out),
        'B1_equivalent':equivalence['B1'],'B3_equivalent':equivalence['B3'],
        'unique_destinations':14,
        'legacy_adjacency_builds':old['adjacency_build_count'],
        'optimized_adjacency_builds':new['adjacency_build_count'],
        'legacy_path_searches':old['path_search_count'],
        'optimized_path_searches':new['path_search_count'],
        'B1_observe_speedup':report['B1_performance']['observe_speedup'],
        'epoch_speedup':report['B1_performance']['epoch_speedup'],
    },indent=2))
    return 0 if report['pass'] else 1


if __name__=='__main__':
    raise SystemExit(main())
