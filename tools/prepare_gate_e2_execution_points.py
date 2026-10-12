"""Freeze Gate E2 execution points before any paired branch is run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
OUT=PROJECT/"configs/gate_e2_execution_points.json"
HASHES=PROJECT/"configs/gate_e2_execution_points_hashes.json"
if OUT.exists() or HASHES.exists():
    raise FileExistsError("REFUSE_TO_OVERWRITE_GATE_E2_EXECUTION_POINTS")

RHO=[0.2,0.5,0.8,1.0,1.2]
ROUTERS=["shortest_propagation","current_state_load_aware"]
BRANCHES=["HOLD","IDEAL_SWITCH","REAL_SWITCH"]

def read(path):return json.loads(path.read_text(encoding="utf-8-sig"))
def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def physical_key(row,rho,router):
    payload=[row["t0_s"],row["old_edge"],row["new_edge"],
             row["terminal_ids"],row["transition_type"],rho,router]
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()

pre=read(PROJECT/"configs/pre_e2_absolute_time_status.json")
status=read(PROJECT/"configs/gate_e2_status.json")
selected_doc=read(PROJECT/"configs/gate_e2_selected_scenarios.json")
if pre.get("pre_e2_absolute_time_regression")!="PASS":
    raise RuntimeError("PRE_E2_PASS_REQUIRED")
if not status.get("candidate_selection_frozen"):
    raise RuntimeError("E2_SELECTION_FREEZE_REQUIRED")
selected=selected_doc["selection"]["selected"]
logical=[];groups={}
for row in selected:
    for rho in RHO:
        for router in ROUTERS:
            key=physical_key(row,rho,router)
            point={
              "logical_point_id":f'{row["scenario_id"]}|rho={rho:g}|router={router}',
              "scenario_id":row["scenario_id"],
              "scenario_class":row["scenario_class"],
              "kappa2_bin":row["kappa2_bin"],
              "rho":rho,"setup_s":2.0,"router":router,
              "physical_execution_key":key}
            logical.append(point)
            groups.setdefault(key,[]).append(point["logical_point_id"])
document={
 "schema":"gate_e2_execution_points_v1",
 "status":"FROZEN_BEFORE_PAIRED_BRANCH_EXECUTION",
 "rho":RHO,"setup_s":[2.0],"routers":ROUTERS,"branches":BRANCHES,
 "setup_semantics":{
   "model":"Gate C simplified nominal audit fixture",
   "parallel_endpoint_retarget_s":1.0,"acquisition_s":1.0,
   "total_ready_delay_s":2.0,"commercial_hardware_measurement":False},
 "natural_kappa2_setup_s":2.0,"candidate_reselection":False,
 "selected_manifest":"configs/gate_e2_selected_scenarios.json",
 "selected_manifest_sha256":sha(PROJECT/"configs/gate_e2_selected_scenarios.json"),
 "logical_selected_entries":len(selected),
 "logical_paired_points":len(logical),
 "unique_physical_execution_points":len(groups),
 "logical_points":logical,
 "physical_reuse_groups":[
   {"physical_execution_key":key,"logical_point_ids":groups[key]}
   for key in sorted(groups)],
 "no_eligible_strata":selected_doc["selection"]["availability"],
 "created_result_blind":True,"paired_branches_executed_before_freeze":False}
document["canonical_sha256"]=hashlib.sha256(
    canonical(document).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(document,indent=2,sort_keys=True,
                          ensure_ascii=False)+"\n",encoding="utf-8")
hash_record={
 "schema":"gate_e2_execution_points_hashes_v1",
 "frozen_before_paired_branch_execution":True,
 "files":{
   "configs/gate_e2_execution_points.json":sha(OUT),
   "configs/gate_e2_selected_scenarios.json":sha(PROJECT/"configs/gate_e2_selected_scenarios.json"),
   "configs/gate_e2_candidate_inventory.json":sha(PROJECT/"configs/gate_e2_candidate_inventory.json"),
   "configs/gate_e0_sweep_manifest.json":sha(PROJECT/"configs/gate_e0_sweep_manifest.json"),
   "configs/gate_e0_scenario_selection_manifest.json":sha(PROJECT/"configs/gate_e0_scenario_selection_manifest.json")}}
HASHES.write_text(json.dumps(hash_record,indent=2,sort_keys=True,
                             ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"status":"FROZEN","logical_paired_points":len(logical),
                  "unique_physical_execution_points":len(groups),
                  "canonical_sha256":document["canonical_sha256"]},indent=2))
