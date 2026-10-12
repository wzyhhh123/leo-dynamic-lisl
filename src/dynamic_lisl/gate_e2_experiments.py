"""Frozen Gate E2 paired natural-geometry experiment implementation."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .commodity import Commodity
from .common import PROJECT, read_json
from .common_router import DeterministicShortestPropagationDelayRouter
from .gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .gate_d_scenarios import Sgp4EdgeDelayProvider, normalized_profile
from .load_aware_router import DeterministicLoadAwareRouter
from .mechanism_validation import (
    PairedCounterfactualHarness, reversal_classification, third_party_effect,
)
from .operational_policy import OperationalPolicy
from .sgp4_model import Sgp4Model
from .terminal_executor import Connect, TerminalExecutor
from .terminal_pair_intervals import TerminalPairCatalog
from .traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from .transition_service_orchestrator import (
    ScriptedProposal, TransitionAwareNetworkServiceEngine,
)


ROUTER_PRIMARY="shortest_propagation"
ROUTER_ROBUSTNESS="current_state_load_aware"
REQUIRED_BRANCHES=("HOLD","IDEAL_SWITCH","REAL_SWITCH")
SETUP_S=2.0
RETARGET_A_S=1.0
RETARGET_B_S=1.0
ACQUISITION_S=1.0
ARRIVAL_DURATION_S=12.0
DRAIN_MARGIN_S=59.0


def canonical_line(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False)+"\n"


def canonical_sha256(value):
    return hashlib.sha256(canonical_line(value).encode("utf-8")).hexdigest()


class E2TransitionEngine(TransitionAwareNetworkServiceEngine):
    """D2 engine with the frozen current-state load-aware adapter."""
    def _recompute_routes(self,reason):
        if isinstance(self.router,DeterministicLoadAwareRouter):
            edge_rates=defaultdict(float)
            for (edge,_commodity),value in self.service_rates.items():
                edge_rates[tuple(edge)]+=value
            utilization={edge:value/self.capacity_bit_s
                         for edge,value in edge_rates.items()}
            node_queue=defaultdict(float)
            for (node,_commodity),value in self.queues.bits.items():
                node_queue[node]+=value
            self.router.update_current_state(
                self.now,utilization,node_queue,self.trace.rate_at(self.now))
        super()._recompute_routes(reason)


class E2Sgp4EdgeDelayProvider(Sgp4EdgeDelayProvider):
    """Cloneable delay adapter; immutable SGP4 Satrec objects are shared."""
    def __deepcopy__(self,memo):
        cloned=type(self)(self.model,self.nodes)
        cloned.cache=dict(self.cache)
        memo[id(self)]=cloned
        return cloned


class GateE2Assets:
    def __init__(self):
        self.contract=read_json(PROJECT/"configs/gate_d0_traffic_contract.json")
        self.reference=read_json(PROJECT/self.contract["reference_topology"])
        self.selected_doc=read_json(PROJECT/"configs/gate_e2_selected_scenarios.json")
        self.execution=read_json(PROJECT/"configs/gate_e2_execution_points.json")
        self.selected={row["scenario_id"]:row
                       for row in self.selected_doc["selection"]["selected"]}
        self.fixed=tuple(tuple(edge) for edge in self.reference["fixed_edges"])
        self.nodes=tuple(sorted({node for edge in self.fixed for node in edge}))
        self.bindings=tuple(self.reference["bindings"])
        records=[json.loads(line) for line in (
            PROJECT/"outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl"
        ).read_text(encoding="utf-8").splitlines()]
        planes={node:int(node.split("_")[0][1:]) for node in self.nodes}
        self.catalog=TerminalPairCatalog.from_records(records,planes)
        self.physical=TerminalPairPhysicalFeasibility(self.catalog)
        od=read_json(PROJECT/"configs/gate_d0_od_manifest_16.json")
        self.commodity_rows=tuple(od["commodities"])
        self.commodities=tuple(Commodity.from_dict(row) for row in self.commodity_rows)
        current=read_json(PROJECT/"configs/current.json")
        d1=PROJECT/current["gate_d1"]["evidence"]
        self.alpha_star=float(read_json(d1/"load_normalization_report.json")
                              ["alpha_star_bit_s"])
        self.model=Sgp4Model.load(PROJECT/"data/raw/sgp4_x720")
        self.binding_by_edge={
            tuple(sorted((row["a"][0],row["b"][0]))):
                (tuple(row["a"]),tuple(row["b"])) for row in self.bindings}

    def trace(self,t0_s,rho):
        ids=tuple(sorted(row["commodity_id"] for row in self.commodity_rows))
        zeros={key:0.0 for key in ids}
        segments=[]
        if t0_s>0:
            segments.append(TrafficSegment(0.0,float(t0_s),zeros,
                                           "PRE_DECISION_ZERO"))
        for phase in self.contract["phases"]:
            profile=normalized_profile(
                ids,self.contract["profile_weights"][phase["label"]])
            rates={key:float(rho)*self.alpha_star*profile[key] for key in ids}
            segments.append(TrafficSegment(
                float(t0_s)+float(phase["start_s"]),
                float(t0_s)+float(phase["end_s"]),rates,phase["label"]))
        return PiecewiseConstantTrafficTrace(ids,segments)

    def executor(self):
        executor=TerminalExecutor(self.nodes)
        for binding in self.bindings:
            executor.submit((Connect(tuple(binding["a"]),tuple(binding["b"]),
                                     float(binding["end_s"]),0.0,0.0,0.0),))
        return executor

    def router(self,router_id):
        if router_id==ROUTER_PRIMARY:
            return DeterministicShortestPropagationDelayRouter()
        if router_id==ROUTER_ROBUSTNESS:
            return DeterministicLoadAwareRouter()
        raise ValueError("UNKNOWN_GATE_E2_ROUTER")

    def action(self,scenario):
        old_pair=self.binding_by_edge[tuple(scenario["old_edge"])]
        proposal={
          "a":tuple(scenario["terminal_ids"][0]),
          "b":tuple(scenario["terminal_ids"][1]),
          "retarget_a":RETARGET_A_S,"retarget_b":RETARGET_B_S,
          "acquisition":ACQUISITION_S}
        if scenario["transition_type"]=="MBB":
            proposal["release_after"]=(old_pair,)
        policy=(OperationalPolicy("BOUNDED_OUTAGE",SETUP_S+1e-7)
                if scenario["scenario_class"]=="E-A_BBM_NO_ROUTE" else
                OperationalPolicy("STRICT_CONNECTED"))
        return ScriptedProposal(
            float(scenario["t0_s"]),"E2_REAL_SWITCH",proposal,self.physical,
            policy,float(scenario["t0_s"])+SETUP_S+1e-7,None)

    def engine(self,scenario,rho,router_id):
        t0=float(scenario["t0_s"])
        engine=E2TransitionEngine(
            self.nodes,self.fixed,self.contract["link_capacity_bit_s_per_direction"],
            self.commodities,self.trace(t0,rho),
            E2Sgp4EdgeDelayProvider(self.model,self.nodes),self.executor(),(),
            self.router(router_id),
            conservation_abs_tolerance_bits=self.contract["conservation_abs_tolerance_bits"],
            conservation_relative_tolerance=self.contract["conservation_relative_tolerance"],
            state_tolerance_bits=self.contract["state_tolerance_bits"])
        # One explicit geometry refresh at the actual decision epoch.  Further
        # topology events recompute routes at their own absolute timestamps.
        engine.geometry_refresh_s=1e9
        engine.next_refresh=t0
        return engine


def physical_execution_key(scenario,rho,router_id):
    payload=[scenario["t0_s"],scenario["old_edge"],scenario["new_edge"],
             scenario["terminal_ids"],scenario["transition_type"],
             float(rho),router_id]
    return hashlib.sha256(json.dumps(
        payload,sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode("utf-8")).hexdigest()


def unique_execution_plan(assets):
    groups={}
    for logical in assets.execution["logical_points"]:
        scenario=assets.selected[logical["scenario_id"]]
        key=physical_execution_key(scenario,logical["rho"],logical["router"])
        if key!=logical["physical_execution_key"]:
            raise AssertionError("EXECUTION_POINT_PHYSICAL_KEY_MISMATCH")
        groups.setdefault(key,[]).append(logical)
    return [{"physical_execution_key":key,
             "representative":sorted(rows,key=lambda x:x["logical_point_id"])[0],
             "logical_points":sorted(rows,key=lambda x:x["logical_point_id"])}
            for key,rows in sorted(groups.items())]


def _branch_summary(branch,t0_s,capacity):
    result=branch["result"];metrics=result["metrics"]
    duration=max(0.0,float(metrics["evaluation_end_s"])-float(t0_s))
    utilization={}
    if duration>0:
        edge_bits=defaultdict(float)
        for key,value in result["transmitted_by_edge_commodity"].items():
            edge_name,_commodity=key.rsplit("|",1)
            edge_bits[edge_name]+=value
        utilization={key:value/(capacity*duration)
                     for key,value in sorted(edge_bits.items())}
    return {
      "status":branch["status"],"J_bit_s":branch["J_bit_s"],
      "J_by_commodity_bit_s":branch["J_by_commodity_bit_s"],
      "mean_bit_delay_s":metrics["mean_bit_delay_s"],
      "peak_queue_bits":metrics["max_queue_bits"],
      "transition_backlog_bits":metrics["backlog_added_during_transition_bits"],
      "peak_transition_backlog_bits":metrics["peak_transition_backlog_bits"],
      "no_route_duration_s":metrics["no_route_duration_s"],
      "no_route_duration_by_commodity_s":metrics["no_route_duration_by_commodity_s"],
      "temporary_partition_duration_s":metrics["partition_duration_s"],
      "affected_commodities":sorted(key for key,value in
          metrics["no_route_duration_by_commodity_s"].items() if value>0),
      "route_change_count":metrics["route_change_count"],
      "residual_backlog_bits":metrics["residual_backlog_bits"],
      "delivered_bits":metrics["delivered_bits"],
      "arrived_bits":metrics["arrived_bits"],
      "backlog_clearance_time_s":metrics["backlog_clearance_time_s"],
      "censored":metrics["censored"],
      "max_abs_conservation_error_bits":metrics["max_abs_conservation_error_bits"],
      "negative_queue_count":metrics["negative_queue_count"],
      "max_capacity_violation_bit_s":metrics["max_capacity_violation_bit_s"],
      "switch_count":metrics["switch_count"],"BBM_count":metrics["BBM_count"],
      "MBB_count":metrics["MBB_count"],
      "relative_link_utilization":utilization,
      "pre_action_state_hash":branch["pre_action_state_hash"],
      "future_trace_hash":branch["future_trace_hash"],
      "network_signature":branch["network_signature"],
      "action_accepted":(None if branch["action_result"] is None else
                           branch["action_result"]["accepted"]),
      "physical_reason":(None if branch["action_result"] is None else
                           branch["action_result"].get("physical_reason")),
      "policy_reason":(None if branch["action_result"] is None else
                         branch["action_result"].get("policy_reason"))}


def evaluate_physical_point(assets,logical):
    scenario=assets.selected[logical["scenario_id"]]
    t0=float(scenario["t0_s"]);rho=float(logical["rho"])
    router_id=logical["router"]
    engine=assets.engine(scenario,rho,router_id)
    action=assets.action(scenario)
    drain_limit=t0+DRAIN_MARGIN_S
    harness=PairedCounterfactualHarness(engine,t0,action,drain_limit)
    paired=harness.run()
    branches={name:_branch_summary(
        paired["branches"][name],t0,assets.contract["link_capacity_bit_s_per_direction"])
        for name in REQUIRED_BRANCHES}
    any_censored=any(branches[name]["censored"] for name in REQUIRED_BRANCHES)
    all_executed=all(branches[name]["status"] in
                     ("EXECUTED","CENSORED_AT_DRAIN_LIMIT")
                     for name in REQUIRED_BRANCHES)
    if any_censored:
        reversal={"classification":"NOT_EVALUABLE_CENSORED",
                  "r_ideal":None,"r_real":None}
    elif not all_executed:
        reversal={"classification":"NOT_EVALUABLE_INFEASIBLE",
                  "r_ideal":None,"r_real":None}
    else:
        reversal=reversal_classification(
            branches["HOLD"]["J_bit_s"],branches["IDEAL_SWITCH"]["J_bit_s"],
            branches["REAL_SWITCH"]["J_bit_s"])
    return {
      "physical_execution_key":logical["physical_execution_key"],
      "representative_scenario_id":logical["scenario_id"],
      "t0_s":t0,"old_edge":scenario["old_edge"],"new_edge":scenario["new_edge"],
      "terminal_ids":scenario["terminal_ids"],
      "transition_type":scenario["transition_type"],"rho":rho,
      "setup_s":SETUP_S,"router":router_id,
      "remaining_lifetime_s":scenario["remaining_lifetime_s"],
      "usable_lifetime_s":scenario["remaining_lifetime_s"]-SETUP_S,
      "arrival_horizon_s":t0+ARRIVAL_DURATION_S,"drain_limit_s":drain_limit,
      "branches":branches,
      "delta_J_ideal_bit_s":branches["IDEAL_SWITCH"]["J_bit_s"]-branches["HOLD"]["J_bit_s"],
      "delta_J_real_bit_s":branches["REAL_SWITCH"]["J_bit_s"]-branches["HOLD"]["J_bit_s"],
      "r_ideal":reversal["r_ideal"],"r_real":reversal["r_real"],
      "reversal_status":reversal["classification"],
      "censor_status":"CENSORED_AT_DRAIN_LIMIT" if any_censored else "COMPLETE",
      "paired_identity":{
        "pre_action_state_hashes_equal":paired["all_pre_action_state_hashes_equal"],
        "future_trace_hashes_equal":paired["all_future_trace_hashes_equal"],
        "same_target_real_ideal":paired["same_target_real_ideal"]}}


def _actual_shared_utilization(branch,focus):
    focus=set(focus);by_edge=defaultdict(lambda:{"focus":0.0,"third":0.0})
    # Relative utilization is already aggregated, while commodity attribution
    # is available through J only.  Report shared structural edge utilization
    # for edges present in the frozen candidate sample at logical mapping time.
    return by_edge


def logical_result(physical,logical,scenario):
    branches=physical["branches"]
    focus=scenario["focus_commodities"]
    real=third_party_effect(
        branches["HOLD"]["J_by_commodity_bit_s"],
        branches["REAL_SWITCH"]["J_by_commodity_bit_s"],focus)
    ideal=third_party_effect(
        branches["HOLD"]["J_by_commodity_bit_s"],
        branches["IDEAL_SWITCH"]["J_by_commodity_bit_s"],focus)
    shared_utilization={}
    for edge in scenario.get("shared_edges",()):
        forward=edge[0]+"->"+edge[1];reverse=edge[1]+"->"+edge[0]
        shared_utilization[edge[0]+"--"+edge[1]]={
            branch:{
              "forward":branches[branch]["relative_link_utilization"].get(forward,0.0),
              "reverse":branches[branch]["relative_link_utilization"].get(reverse,0.0)}
            for branch in REQUIRED_BRANCHES}
    real_branch=branches["REAL_SWITCH"]
    return {
      "logical_point_id":logical["logical_point_id"],
      "physical_execution_key":physical["physical_execution_key"],
      "scenario_id":scenario["scenario_id"],
      "scenario_class":scenario["scenario_class"],
      "kappa2_bin":scenario["kappa2_bin"],"kappa2":scenario["kappa2"],
      "t0_s":physical["t0_s"],"old_edge":physical["old_edge"],
      "new_edge":physical["new_edge"],"terminal_ids":physical["terminal_ids"],
      "transition_type":physical["transition_type"],
      "remaining_lifetime_s":physical["remaining_lifetime_s"],
      "usable_lifetime_s":physical["usable_lifetime_s"],
      "rho":physical["rho"],"setup_s":physical["setup_s"],
      "router":physical["router"],
      "J_hold":branches["HOLD"]["J_bit_s"],
      "J_ideal":branches["IDEAL_SWITCH"]["J_bit_s"],
      "J_real":branches["REAL_SWITCH"]["J_bit_s"],
      "delta_J_ideal":physical["delta_J_ideal_bit_s"],
      "delta_J_real":physical["delta_J_real_bit_s"],
      "r_ideal":physical["r_ideal"],"r_real":physical["r_real"],
      "reversal_status":physical["reversal_status"],
      "mean_bit_delay_hold":branches["HOLD"]["mean_bit_delay_s"],
      "mean_bit_delay_ideal":branches["IDEAL_SWITCH"]["mean_bit_delay_s"],
      "mean_bit_delay_real":branches["REAL_SWITCH"]["mean_bit_delay_s"],
      "peak_queue":real_branch["peak_queue_bits"],
      "transition_backlog":real_branch["transition_backlog_bits"],
      "no_route_duration":real_branch["no_route_duration_s"],
      "route_change_count":real_branch["route_change_count"],
      "residual_backlog":real_branch["residual_backlog_bits"],
      "censor_status":physical["censor_status"],
      "focus_delta_J":real["delta_J_focus_bit_s"],
      "third_party_delta_J":real["delta_J_third_bit_s"],
      "focus_delta_J_ideal":ideal["delta_J_focus_bit_s"],
      "third_party_delta_J_ideal":ideal["delta_J_third_bit_s"],
      "focus_third_effect_evaluable":physical["censor_status"]=="COMPLETE",
      "temporary_partition_duration":real_branch["temporary_partition_duration_s"],
      "affected_commodities":real_branch["affected_commodities"],
      "backlog_accumulated_during_setup":real_branch["transition_backlog_bits"],
      "backlog_clearance_time":real_branch["backlog_clearance_time_s"],
      "MBB_continuity":(physical["transition_type"]=="MBB" and
                         real_branch["no_route_duration_s"]==0.0),
      "forced_outage_duration":real_branch["no_route_duration_s"],
      "setup_opportunity_cost_J":physical["delta_J_real_bit_s"]-physical["delta_J_ideal_bit_s"],
      "shared_link_utilization":shared_utilization,
      "focus_improves_while_third_party_degrades":(
          real["delta_J_focus_bit_s"]<0 and real["delta_J_third_bit_s"]>0
          if physical["censor_status"]=="COMPLETE" else None),
      "branches":branches,"paired_identity":physical["paired_identity"]}


def run_all_unique(assets,progress=None):
    plan=unique_execution_plan(assets);physical_results={};logical_rows=[]
    reuse=[]
    for index,group in enumerate(plan,1):
        representative=group["representative"]
        result=evaluate_physical_point(assets,representative)
        physical_results[group["physical_execution_key"]]=result
        mapped=[]
        for logical in group["logical_points"]:
            scenario=assets.selected[logical["scenario_id"]]
            logical_rows.append(logical_result(result,logical,scenario))
            mapped.append(logical["logical_point_id"])
        reuse.append({
          "physical_execution_key":group["physical_execution_key"],
          "representative_logical_point_id":representative["logical_point_id"],
          "mapped_logical_point_ids":mapped,
          "executed_once":True})
        if progress:progress(index,len(plan),representative)
    logical_rows.sort(key=lambda row:row["logical_point_id"])
    physical_rows=[physical_results[key] for key in sorted(physical_results)]
    return {"physical_results":physical_rows,"logical_results":logical_rows,
            "execution_reuse_map":reuse,
            "canonical_sha256":canonical_sha256({
                "physical_results":physical_rows,"logical_results":logical_rows,
                "execution_reuse_map":reuse})}


def integrity_summary(run):
    failures=defaultdict(int)
    for physical in run["physical_results"]:
        branches=physical["branches"]
        failures["paired_identity"]+=int(not all(physical["paired_identity"].values()))
        for branch in branches.values():
            failures["work_conservation"]+=int(branch["max_abs_conservation_error_bits"]>1.0)
            failures["nonnegative_queue"]+=int(branch["negative_queue_count"]!=0)
            failures["capacity"]+=int(branch["max_capacity_violation_bit_s"]>0.01)
            failures["gate_c_action"]+=int(
                branch["action_accepted"] is False)
    return dict(failures)
