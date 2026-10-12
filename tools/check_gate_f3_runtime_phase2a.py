"""Engineering-only Phase 2A legacy-vs-memoized initial-epoch checker."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time


PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT/"src"),str(PROJECT)]

from dynamic_lisl.candidate_proposer import FrozenTerminalPairProposer  # noqa:E402
from dynamic_lisl.common import read_json  # noqa:E402
from dynamic_lisl.common_router import DeterministicShortestPropagationDelayRouter  # noqa:E402
from dynamic_lisl.gate_e2_experiments import GateE2Assets  # noqa:E402
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor  # noqa:E402
from dynamic_lisl.scientific_snapshot import ScientificSnapshotEvaluator  # noqa:E402


class CountingDelay:
    def __init__(self,inner):
        self.inner=inner
        self.calls=0
        self.keys=Counter()
    def __call__(self,edge,time_s):
        self.calls+=1
        key=(tuple(edge),float(time_s))
        self.keys[key]+=1
        return self.inner(edge,time_s)


class RecordingRouter(DeterministicShortestPropagationDelayRouter):
    def __init__(self):
        super().__init__(use_adjacency_reuse=False,
                         use_same_destination_reuse=False)
        self.routes_calls=0
        self.path_calls=0
        self.route_tables=[]
        self.route_times=[]
    def path(self,*args,**kwargs):
        self.path_calls+=1
        return super().path(*args,**kwargs)
    def routes_to_destinations(self,*args,**kwargs):
        self.routes_calls+=1
        result=super().routes_to_destinations(*args,**kwargs)
        self.route_tables.append(result)
        self.route_times.append(float(kwargs.get(
            "time_s",args[4] if len(args)>4 else 0.0)))
        return result


class CapturingProposer:
    def __init__(self):
        self.inner=FrozenTerminalPairProposer()
        self.results=[]
    def propose(self,*args,**kwargs):
        result=self.inner.propose(*args,**kwargs)
        self.results.append(result)
        return result


class CapturingEvaluator(ScientificSnapshotEvaluator):
    def __init__(self,engine,memoized):
        super().__init__(engine,use_edge_delay_memoization=memoized)
        self.results=[]
        self.delay_stats=[]
    def evaluate_edges(self,edges):
        delay=self.engine.delay
        before_calls=delay.calls
        before=delay.keys.copy()
        result=super().evaluate_edges(edges)
        delta=delay.keys.copy()
        delta.subtract(before)
        delta=Counter({key:value for key,value in delta.items() if value})
        self.results.append(result)
        self.delay_stats.append({
            "provider_calls":delay.calls-before_calls,
            "unique_edge_delay_keys":len(delta),
            "max_calls_per_key":max(delta.values()) if delta else 0,
        })
        return result


def canonical_hash(value):
    return hashlib.sha256(json.dumps(
        value,sort_keys=True,separators=(",",":"),ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def normalized_action(row):
    return {key:value for key,value in row.items()
            if key not in ("controller_decision_runtime_s",
                           "action_canonical_sha256")}


def route_table_document(tables):
    return [[
        [node,commodity,list(route) if route is not None else None]
        for (node,commodity),route in sorted(table.items())
    ] for table in tables]


def route_cost_document(tables,times,provider):
    result=[]
    for table,time_s in zip(tables,times):
        rows=[]
        for key,route in sorted(table.items()):
            cost=(None if route is None else sum(
                float(provider(edge,time_s))
                for edge in zip(route,route[1:])))
            rows.append([key[0],key[1],cost])
        result.append(rows)
    return result


def public_proposal_set(value):
    return {key:item for key,item in value.items()
            if key!="candidate_specs"}


def run_mode(assets,controller_id,memoized):
    manifest=read_json(PROJECT/"configs/gate_f3_execution_manifest_v1.json")
    template=next(row for row in manifest["runs"]
        if row["block_id"]=="P1" and row["controller"]==controller_id
        and float(row["rho"])==0.5)
    row={**template,
         "run_id":f"ENGINEERING_PROFILE_ONLY-PHASE2A-{controller_id}-"
                  +("MEMO" if memoized else "LEGACY"),
         "block_id":"ENGINEERING_PROFILE_ONLY",
         "performance_status":"ENGINEERING_PROFILE_ONLY_NOT_SCIENTIFIC_RESULT"}
    executor=P1RunExecutor(assets,row,progress_recorder=None)
    counted_delay=CountingDelay(executor.engine.delay)
    router=RecordingRouter()
    executor.engine.delay=counted_delay
    executor.engine.router=router
    evaluator=CapturingEvaluator(executor.engine,memoized)
    executor.controller.evaluator=evaluator
    proposer=CapturingProposer()
    executor.proposer=proposer
    started=time.perf_counter()
    prefix=executor.run_engineering_prefix(0.0)
    wall=time.perf_counter()-started
    proposal=proposer.results[0]
    topologies=[evaluator.candidate_edges(row)
                for row in proposal["proposals"]]
    route_doc=route_table_document(router.route_tables)
    cost_doc=route_cost_document(
        router.route_tables,router.route_times,counted_delay.inner)
    state={
        "actions":[normalized_action(row) for row in prefix["actions"]],
        "proposal_set":public_proposal_set(proposal),
        "snapshot_evaluations":[row.to_dict() for row in evaluator.results],
        "route_tables":route_doc,
        "route_costs":cost_doc,
        "terminal_event_sequence":deepcopy(
            executor.engine.terminal_event_sequence),
        "graph_event_sequence":deepcopy(executor.engine.graph_event_sequence),
        "G_active_G_admit":deepcopy(executor.engine.graph),
        "queues":executor.engine.queues.snapshot(),
        "in_flight":executor.engine.in_flight.snapshot(),
        "arrived":dict(sorted(executor.engine.arrived.items())),
        "delivered":dict(sorted(executor.engine.delivered.items())),
        "terminal_snapshot":executor.engine.executor.snapshot(),
        "canonical_live_state":executor.engine.canonical_state_sha256(),
    }
    epoch=prefix["epoch_runtime_records"][0]
    return {
        "controller":controller_id,
        "memoized":memoized,
        "state":state,
        "state_sha256":canonical_hash(state),
        "routes_to_destinations_calls":router.routes_calls,
        "path_calls":router.path_calls,
        "delay_provider_calls":counted_delay.calls,
        "unique_edge_delay_keys_across_prefix":len(counted_delay.keys),
        "sum_unique_edge_delay_keys_per_topology":sum(
            row["unique_edge_delay_keys"] for row in evaluator.delay_stats),
        "max_calls_per_same_key_within_topology":max(
            row["max_calls_per_key"] for row in evaluator.delay_stats),
        "topology_evaluations":len(evaluator.results),
        "unique_satellite_topologies":len({
            json.dumps(value,separators=(",",":")) for value in topologies}),
        "final_proposals":len(topologies),
        "B1_or_B3_observe_wall_s":epoch["controller_observe_wall_s"],
        "total_epoch_wall_s":epoch["epoch_total_wall_s"],
        "total_prefix_wall_s":wall,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir")
    args=parser.parse_args()
    if args.output_dir:
        out=Path(args.output_dir)
        if not out.is_absolute():out=PROJECT/out
    else:
        stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        out=PROJECT/"outputs"/("gate_f3_runtime_phase2a_"+stamp)
    if out.exists() and any(out.iterdir()):
        raise SystemExit("OUTPUT_DIR_MUST_BE_NEW_OR_EMPTY")
    out.mkdir(parents=True,exist_ok=True)
    assets=GateE2Assets()
    runs={}
    for controller in ("B1","B3"):
        runs[controller]={
            "legacy":run_mode(assets,controller,False),
            "optimized":run_mode(assets,controller,True)}
    equivalence={
        controller:runs[controller]["legacy"]["state"]
                   ==runs[controller]["optimized"]["state"]
        for controller in runs}
    b1_old=runs["B1"]["legacy"];b1_new=runs["B1"]["optimized"]
    report={
        "schema":"gate_f3_runtime_phase2a_report_v1",
        "classification":"ENGINEERING_PROFILE_ONLY",
        "sim_end_s":0.0,
        "registered_P1_executed":False,
        "phase2b_started":False,
        "P2_started":False,
        "RL_started":False,
        "identical_topology_reuse":"NO_APPLICABLE_DUPLICATES",
        "controller_equivalence":equivalence,
        "B1_performance":{
            "legacy":{key:value for key,value in b1_old.items()
                      if key not in ("state",)},
            "optimized":{key:value for key,value in b1_new.items()
                         if key not in ("state",)},
            "observe_speedup":b1_old["B1_or_B3_observe_wall_s"]
                              /b1_new["B1_or_B3_observe_wall_s"],
            "epoch_speedup":b1_old["total_epoch_wall_s"]
                            /b1_new["total_epoch_wall_s"],
            "delay_provider_call_reduction":
                b1_old["delay_provider_calls"]-b1_new["delay_provider_calls"],
            "delay_provider_call_reduction_fraction":
                1-b1_new["delay_provider_calls"]/b1_old["delay_provider_calls"],
        },
    }
    report["pass"]=all(equivalence.values()) and (
        b1_new["delay_provider_calls"]<b1_old["delay_provider_calls"])
    report["status"]=("GATE_F3_RUNTIME_PHASE2A_PASS"
                      if report["pass"] else "GATE_F3_RUNTIME_PHASE2A_FAIL")
    (out/"report.json").write_text(json.dumps(
        report,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    for controller in runs:
        for mode in runs[controller]:
            value=runs[controller][mode]
            (out/f"{controller.lower()}_{mode}_equivalence.json").write_text(
                json.dumps(value["state"],indent=2,sort_keys=True,
                           ensure_ascii=False)+"\n")
    print(json.dumps({
        "status":report["status"],"output_dir":str(out),
        "B1_equivalent":equivalence["B1"],
        "B3_equivalent":equivalence["B3"],
        "legacy_delay_calls":b1_old["delay_provider_calls"],
        "optimized_delay_calls":b1_new["delay_provider_calls"],
        "B1_observe_speedup":report["B1_performance"]["observe_speedup"],
        "epoch_speedup":report["B1_performance"]["epoch_speedup"],
        "unique_topologies":b1_new["unique_satellite_topologies"],
    },indent=2))
    return 0 if report["pass"] else 1


if __name__=="__main__":
    raise SystemExit(main())
