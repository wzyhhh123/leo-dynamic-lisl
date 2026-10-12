"""Parallel branch executor for the frozen Gate E2 physical points."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json

from .gate_e2_experiments import (
    ARRIVAL_DURATION_S, DRAIN_MARGIN_S, REQUIRED_BRANCHES, SETUP_S,
    GateE2Assets, _branch_summary, canonical_sha256, integrity_summary,
    logical_result, unique_execution_plan,
)
from .mechanism_validation import (
    PairedCounterfactualHarness, reversal_classification, with_total_setup,
)


_WORKER_ASSETS=None


def _task_id(payload):
    return hashlib.sha256(json.dumps(
        payload,sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode("utf-8")).hexdigest()


def branch_task_plan(assets):
    tasks={};physical_plan=[]
    for group in unique_execution_plan(assets):
        logical=group["representative"]
        scenario=assets.selected[logical["scenario_id"]]
        hold_id=_task_id(["HOLD",scenario["t0_s"],logical["rho"],logical["router"]])
        real_id=_task_id([group["physical_execution_key"],"REAL_SWITCH"])
        ideal_id=_task_id([group["physical_execution_key"],"IDEAL_SWITCH"])
        tasks.setdefault(hold_id,{"task_id":hold_id,"branch":"HOLD","logical":logical})
        tasks[real_id]={"task_id":real_id,"branch":"REAL_SWITCH","logical":logical}
        tasks[ideal_id]={"task_id":ideal_id,"branch":"IDEAL_SWITCH","logical":logical}
        physical_plan.append({
          "physical_execution_key":group["physical_execution_key"],
          "representative":logical,"logical_points":group["logical_points"],
          "branch_task_ids":{"HOLD":hold_id,"REAL_SWITCH":real_id,
                             "IDEAL_SWITCH":ideal_id}})
    return [tasks[key] for key in sorted(tasks)],physical_plan


def _worker_init():
    global _WORKER_ASSETS
    _WORKER_ASSETS=GateE2Assets()


def _execute_branch(task):
    assets=_WORKER_ASSETS
    logical=task["logical"]
    scenario=assets.selected[logical["scenario_id"]]
    t0=float(scenario["t0_s"])
    engine=assets.engine(scenario,logical["rho"],logical["router"])
    action=assets.action(scenario)
    harness=PairedCounterfactualHarness(engine,t0,action,t0+DRAIN_MARGIN_S)
    if task["branch"]=="HOLD":
        raw=harness._branch("HOLD")
    elif task["branch"]=="REAL_SWITCH":
        raw=harness._branch("REAL_SWITCH",harness.real_action)
    elif task["branch"]=="IDEAL_SWITCH":
        ideal=with_total_setup(
            harness.real_action,0.0,"IDEAL_SWITCH",t0,None)
        raw=harness._branch("IDEAL_SWITCH",ideal)
    else:
        raise ValueError("UNKNOWN_GATE_E2_BRANCH_TASK")
    summary=_branch_summary(
        raw,t0,assets.contract["link_capacity_bit_s_per_direction"])
    return {"task_id":task["task_id"],"branch":task["branch"],
            "summary":summary,"target_signature":raw["target_signature"]}


def _assemble_physical(assets,item,results):
    logical=item["representative"]
    scenario=assets.selected[logical["scenario_id"]]
    branches={name:results[item["branch_task_ids"][name]]["summary"]
              for name in REQUIRED_BRANCHES}
    targets={name:results[item["branch_task_ids"][name]]["target_signature"]
             for name in ("IDEAL_SWITCH","REAL_SWITCH")}
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
    t0=float(scenario["t0_s"])
    physical={
      "physical_execution_key":item["physical_execution_key"],
      "representative_scenario_id":logical["scenario_id"],
      "t0_s":t0,"old_edge":scenario["old_edge"],"new_edge":scenario["new_edge"],
      "terminal_ids":scenario["terminal_ids"],
      "transition_type":scenario["transition_type"],"rho":float(logical["rho"]),
      "setup_s":SETUP_S,"router":logical["router"],
      "remaining_lifetime_s":scenario["remaining_lifetime_s"],
      "usable_lifetime_s":scenario["remaining_lifetime_s"]-SETUP_S,
      "arrival_horizon_s":t0+ARRIVAL_DURATION_S,"drain_limit_s":t0+DRAIN_MARGIN_S,
      "branches":branches,
      "delta_J_ideal_bit_s":branches["IDEAL_SWITCH"]["J_bit_s"]-branches["HOLD"]["J_bit_s"],
      "delta_J_real_bit_s":branches["REAL_SWITCH"]["J_bit_s"]-branches["HOLD"]["J_bit_s"],
      "r_ideal":reversal["r_ideal"],"r_real":reversal["r_real"],
      "reversal_status":reversal["classification"],
      "censor_status":"CENSORED_AT_DRAIN_LIMIT" if any_censored else "COMPLETE",
      "paired_identity":{
        "pre_action_state_hashes_equal":len({
            branches[name]["pre_action_state_hash"] for name in REQUIRED_BRANCHES})==1,
        "future_trace_hashes_equal":len({
            branches[name]["future_trace_hash"] for name in REQUIRED_BRANCHES})==1,
        "same_target_real_ideal":targets["REAL_SWITCH"]==targets["IDEAL_SWITCH"]}}
    return physical


def run_parallel(max_workers=12,progress=None):
    assets=GateE2Assets()
    tasks,plan=branch_task_plan(assets)
    completed={}
    with ProcessPoolExecutor(max_workers=max_workers,
                             initializer=_worker_init) as pool:
        futures={pool.submit(_execute_branch,task):task for task in tasks}
        for index,future in enumerate(as_completed(futures),1):
            result=future.result();completed[result["task_id"]]=result
            if progress:progress(index,len(tasks),futures[future],result)
    physical=[];logical_rows=[];reuse=[]
    for item in plan:
        row=_assemble_physical(assets,item,completed);physical.append(row)
        mapped=[]
        for logical in item["logical_points"]:
            logical_rows.append(logical_result(
                row,logical,assets.selected[logical["scenario_id"]]))
            mapped.append(logical["logical_point_id"])
        reuse.append({
          "physical_execution_key":item["physical_execution_key"],
          "representative_logical_point_id":item["representative"]["logical_point_id"],
          "mapped_logical_point_ids":mapped,"executed_once":True})
    physical.sort(key=lambda row:row["physical_execution_key"])
    logical_rows.sort(key=lambda row:row["logical_point_id"])
    reuse.sort(key=lambda row:row["physical_execution_key"])
    document={"physical_results":physical,"logical_results":logical_rows,
              "execution_reuse_map":reuse,"branch_task_count":len(tasks),
              "unique_hold_task_count":sum(task["branch"]=="HOLD" for task in tasks)}
    document["canonical_sha256"]=canonical_sha256(document)
    document["integrity_failures"]=integrity_summary(document)
    return document
