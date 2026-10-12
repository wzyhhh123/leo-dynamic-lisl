"""Validate and record the result-blind Gate E2 selection freeze; no branches."""
from __future__ import annotations

import io
import json
import sys
import time
import unittest
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/"src"))
sys.path.insert(0,str(PROJECT/"tests"))
from dynamic_lisl.common import dump,new_output,read_json,sha
from dynamic_lisl.gate_e2_enumeration import canonical_sha256
from dynamic_lisl.scenario_selection import (
    deterministic_select,validate_result_blind_candidate)


class MachineResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.cases=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.cases.append({"test":test.id(),"status":"PASS"})
    def addFailure(self,test,error):
        super().addFailure(test,error);self.cases.append({"test":test.id(),"status":"FAIL","detail":self._exc_info_to_string(error,test)})
    def addError(self,test,error):
        super().addError(test,error);self.cases.append({"test":test.id(),"status":"ERROR","detail":self._exc_info_to_string(error,test)})


def audit(record):
    expected=read_json(PROJECT/record)["files"]
    current={name:sha(PROJECT/name) if (PROJECT/name).is_file() else None
             for name in sorted(expected)}
    return {"record":record,"expected":expected,"current":current,
            "all_unchanged":current==expected}


def tests(pattern,name,verbosity=1):
    suite=unittest.defaultTestLoader.discover(str(PROJECT/"tests"),pattern=pattern)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=verbosity,
                                   resultclass=MachineResult).run(suite)
    text=stream.getvalue();(OUT/name).write_text(text,encoding="utf-8")
    print(text,end="",flush=True);return result


if not __debug__:raise RuntimeError("Gate E2 selection check requires assertions")
started=time.time()
pre=read_json(PROJECT/"configs/pre_e2_absolute_time_status.json")
if pre.get("pre_e2_absolute_time_regression")!="PASS":
    raise RuntimeError("PRE_E2_PASS_REQUIRED_STOP")
OUT=new_output("gate_e2_selection")
audits={
 "a_to_pre_e2":audit("configs/gate_e2_frozen_a_to_pre_e2_hashes.json"),
 "selection":audit("configs/gate_e2_selection_hashes.json"),
 "e0_manifest":audit("configs/gate_e0_manifest_hashes.json"),
 "e1_manifest":audit("configs/gate_e1_manifest_hashes.json")}
dump(OUT/"frozen_input_hash_report.json",audits)
if not all(row["all_unchanged"] for row in audits.values()):
    raise RuntimeError("FROZEN_INPUT_CHANGED_STOP")

inventory=read_json(PROJECT/"configs/gate_e2_candidate_inventory.json")
selected=read_json(PROJECT/"configs/gate_e2_selected_scenarios.json")
inv_payload=dict(inventory);inv_hash=inv_payload.pop("canonical_sha256")
sel_payload=dict(selected);sel_hash=sel_payload.pop("canonical_sha256")
reselected=deterministic_select(inventory["candidates"],1)
schema_ok=all(validate_result_blind_candidate(row)
              for row in inventory["candidates"])
source_ok=all(sha(PROJECT/name)==expected
              for name,expected in inventory["source_hashes"].items())

print("E2_SELECTION_STAGE SPECIALIZED_TESTS",flush=True)
special=tests("test_gate_e2_enumeration.py","selection_tests.txt",2)
print("E2_SELECTION_STAGE FULL_REGRESSION",flush=True)
full=tests("test_*.py","full_regression.txt",1)
post={name:audit(row["record"]) for name,row in audits.items()}
dump(OUT/"post_run_frozen_input_hash_report.json",post)

acceptance={
 "pre_e2_absolute_time_pass":True,
 "a_to_pre_e2_frozen_unchanged":audits["a_to_pre_e2"]["all_unchanged"],
 "selection_frozen_unchanged":audits["selection"]["all_unchanged"],
 "e0_e1_manifests_unchanged":audits["e0_manifest"]["all_unchanged"] and audits["e1_manifest"]["all_unchanged"],
 "candidate_inventory_canonical_hash":canonical_sha256(inv_payload)==inv_hash,
 "selected_manifest_canonical_hash":canonical_sha256(sel_payload)==sel_hash,
 "source_160_assets_unchanged":source_ok,
 "result_blind_candidate_schema":schema_ok and inventory["result_fields_read"]==[],
 "frozen_selector_exact_replay":reselected==selected["selection"],
 "all_16_strata_retained":len(selected["selection"]["availability"])==16,
 "selected_gate_c_validation_pass":selected["selected_gate_c_validation"]["all_selected_gate_c_legal"],
 "selected_transition_class_validation_pass":selected["selected_gate_c_validation"]["all_transition_classes_match"],
 "selected_before_branch_execution":not selected["paired_branches_executed"],
 "specialized_tests_pass":special.wasSuccessful(),
 "full_regression_pass":full.wasSuccessful(),
 "frozen_inputs_unchanged_after_tests":all(row["all_unchanged"] for row in post.values()),
 "no_performance_branch_executed":True,
 "gate_f_not_started":True}
passed=all(acceptance.values())
formal=("GATE_E2_CANDIDATE_SELECTION_FROZEN_AWAITING_EXECUTION_CONTRACT"
        if passed else "GATE_E2_SELECTION_VALIDATION_FAIL_STOP")
report={
 "formal_status":formal,"selection_validation_pass":passed,
 "gate_e2_complete":False,"paired_branch_count":0,
 "execution_ambiguity_stop":passed,
 "candidate_count":inventory["candidate_count"],
 "selected_count":len(selected["selection"]["selected"]),
 "no_eligible_strata_count":sum(row["status"]=="NO_ELIGIBLE_CASE"
                                 for row in selected["selection"]["availability"]),
 "counts_by_class":inventory["counts_by_class"],
 "acceptance_checks":acceptance,
 "inventory_sha256":inv_hash,"selected_sha256":sel_hash,
 "gate_e2_started":True,"gate_f_started":False}
dump(OUT/"report.json",report)
dump(OUT/"deterministic_replay_report.json",{
 "selector_replay_equal":reselected==selected["selection"],
 "specialized_test_replay_pass":special.wasSuccessful()})
dump(OUT/"tests_report.json",{
 "specialized":{"tests":special.testsRun,"successful":special.wasSuccessful(),"cases":special.cases},
 "full":{"tests":full.testsRun,"successful":full.wasSuccessful(),"cases":full.cases}})
status={
 "gate_e2":"AWAITING_EXECUTION_CONTRACT" if passed else "FAIL",
 "formal_status":formal,"candidate_selection_frozen":passed,
 "paired_branches_executed":False,"gate_e2_complete":False,
 "evidence":str(OUT.relative_to(PROJECT)).replace("\\","/"),
 "gate_e2_started":True,"gate_f_started":False}
dump(OUT/"status.json",status);dump(PROJECT/"configs/gate_e2_status.json",status)
if passed:
    current=read_json(PROJECT/"configs/current.json")
    current["project_status"]=formal
    current["gate_e2"]={"status":"AWAITING_EXECUTION_CONTRACT",
      "record":"configs/gate_e2_status.json",
      "contract":"docs/GATE_E2_EXECUTION_CONTRACT_CN.md",
      "selected_scenarios":"configs/gate_e2_selected_scenarios.json",
      "ambiguity_report":"docs/GATE_E2_EXECUTION_AMBIGUITY_CN.md",
      "evidence":status["evidence"]}
    current["gate_e2_started"]=True;current["gate_f_started"]=False
    current["current_command"]="python tools/check_gate_e2_selection.py"
    dump(PROJECT/"configs/current.json",current)
dump(OUT/"inputs.json",{"elapsed_s":time.time()-started,
 "pre_e2_evidence":pre["evidence"],
 "code_hashes":{name:sha(PROJECT/name) for name in (
  "src/dynamic_lisl/gate_e2_enumeration.py",
  "tools/prepare_gate_e2_enumeration.py",
  "tools/check_gate_e2_selection.py",
  "tests/test_gate_e2_enumeration.py")}})
dump(OUT/"hashes.json",{path.name:sha(path) for path in OUT.iterdir()
                         if path.is_file() and path.name!="hashes.json"})
print(formal,OUT,flush=True)
if passed:print("STOP: paired execution points remain ambiguous; Gate E2 is not PASS.",flush=True)
raise SystemExit(0 if passed else 1)
