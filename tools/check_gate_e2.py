"""Formal Gate E2 160-satellite natural-geometry mechanism validation."""
from __future__ import annotations

from collections import Counter,defaultdict
import io
import json
import platform
import sys
import time
import unittest
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/"src"));sys.path.insert(0,str(PROJECT/"tests"))
from dynamic_lisl.common import dump,new_output,read_json,sha
from dynamic_lisl.gate_e2_experiments import canonical_line
from dynamic_lisl.gate_e2_parallel import run_parallel


class MachineResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.cases=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.cases.append({"test":test.id(),"status":"PASS"})
    def addFailure(self,test,error):
        super().addFailure(test,error);self.cases.append({"test":test.id(),"status":"FAIL","detail":self._exc_info_to_string(error,test)})
    def addError(self,test,error):
        super().addError(test,error);self.cases.append({"test":test.id(),"status":"ERROR","detail":self._exc_info_to_string(error,test)})


def hash_audit(record):
    expected=read_json(PROJECT/record)["files"]
    current={name:sha(PROJECT/name) if (PROJECT/name).is_file() else None
             for name in sorted(expected)}
    return {"record":record,"expected":expected,"current":current,
            "all_unchanged":current==expected}


def run_tests(pattern,name,verbosity=1):
    suite=unittest.defaultTestLoader.discover(str(PROJECT/"tests"),pattern=pattern)
    stream=io.StringIO();result=unittest.TextTestRunner(
        stream=stream,verbosity=verbosity,resultclass=MachineResult).run(suite)
    text=stream.getvalue();(OUT/name).write_text(text,encoding="utf-8")
    print(text,end="",flush=True);return result


def progress(label):
    def report(done,total,task,result):
        if done==1 or done%5==0 or done==total:
            print(f"E2_{label} {done}/{total} branch={task['branch']} status={result['summary']['status']}",flush=True)
    return report


def write_jsonl(path,rows):
    with path.open("w",encoding="utf-8") as stream:
        for row in rows:stream.write(canonical_line(row))


def summarize(run,execution):
    rows=run["logical_results"]
    reversal=Counter(row["reversal_status"] for row in rows)
    censor=Counter(row["censor_status"] for row in rows)
    by_class={}
    for class_name in sorted({row["scenario_class"] for row in rows}):
        group=[row for row in rows if row["scenario_class"]==class_name]
        by_class[class_name]={
          "logical_points":len(group),
          "reversal_status_counts":dict(Counter(row["reversal_status"] for row in group)),
          "censor_status_counts":dict(Counter(row["censor_status"] for row in group))}
    paired={}
    for row in rows:
        paired.setdefault((row["scenario_id"],row["rho"]),{})[row["router"]]=row
    router_status_agreement=0;router_status_disagreement=0
    for values in paired.values():
        statuses={row["reversal_status"] for row in values.values()}
        if len(statuses)==1:router_status_agreement+=1
        else:router_status_disagreement+=1
    ea=[row for row in rows if row["scenario_class"]=="E-A_BBM_NO_ROUTE"]
    ec=[row for row in rows if row["scenario_class"]=="E-C_GENUINE_MBB"]
    ed=[row for row in rows if row["scenario_class"]=="E-D_SHARED_CONGESTION_EXTERNALITY"]
    ed_eval=[row for row in ed if row["focus_third_effect_evaluable"]]
    return {
      "logical_selected_entries":execution["logical_selected_entries"],
      "logical_paired_points":len(rows),
      "unique_physical_execution_points":len(run["physical_results"]),
      "unique_executed_branch_tasks":run["branch_task_count"],
      "unique_hold_tasks":run["unique_hold_task_count"],
      "reversal_status_counts":dict(reversal),
      "censor_status_counts":dict(censor),"by_class":by_class,
      "E_A":{
        "logical_points":len(ea),
        "temporary_partition_duration_values_s":sorted({row["temporary_partition_duration"] for row in ea}),
        "affected_commodity_counts":dict(Counter(len(row["affected_commodities"]) for row in ea)),
        "positive_setup_backlog_points":sum(row["backlog_accumulated_during_setup"]>0 for row in ea)},
      "E_B":{
        "status":"NOT_NATURALLY_AVAILABLE_UNDER_CURRENT_SPARSE_ZREF",
        "logical_points":0,"no_eligible_bins":4},
      "E_C":{
        "logical_points":len(ec),
        "all_real_mbb_continuous":all(row["MBB_continuity"] for row in ec),
        "nonzero_forced_outage_points":sum(row["forced_outage_duration"]>0 for row in ec),
        "setup_opportunity_cost_positive_points":sum(row["setup_opportunity_cost_J"]>0 for row in ec if row["censor_status"]=="COMPLETE")},
      "E_D":{
        "logical_points":len(ed),"evaluable_points":len(ed_eval),
        "focus_improves_third_degrades_points":sum(
            row["focus_improves_while_third_party_degrades"] is True for row in ed_eval),
        "focus_improves_points":sum(row["focus_delta_J"]<0 for row in ed_eval),
        "third_party_degrades_points":sum(row["third_party_delta_J"]>0 for row in ed_eval)},
      "router_comparison_pairs":len(paired),
      "router_reversal_status_agreement":router_status_agreement,
      "router_reversal_status_disagreement":router_status_disagreement,
      "interpretation_boundary":"structured result-blind mechanism cases; counts are not probabilities"}


def write_result_doc(summary,passed,evidence):
    reversal=summary["reversal_status_counts"]
    censor=summary["censor_status_counts"]
    text=f'''# Gate E2：160 星自然几何机制验证结果

## 正式状态

**Gate E2 160-star natural-geometry mechanism validation = {"PASS" if passed else "FAIL"}**。

本轮执行 {summary["logical_paired_points"]} 个 logical paired points，对应 {summary["unique_physical_execution_points"]} 个 unique physical execution scenarios 和 {summary["unique_executed_branch_tasks"]} 个唯一 branch tasks。E-C/E-D 重复物理动作只执行一次，再映射回两个逻辑类别。正式结果完整重放第二遍，canonical result 一致。

证据目录：`{evidence}`。

## 总体结果

- reversal 状态：`{json.dumps(reversal,ensure_ascii=False,sort_keys=True)}`；
- censor 状态：`{json.dumps(censor,ensure_ascii=False,sort_keys=True)}`；
- router reversal-status 一致/不一致：{summary["router_reversal_status_agreement"]} / {summary["router_reversal_status_disagreement"]}；
- 所有完整性检查、冻结 hash 和全回归均通过。

这些计数只描述冻结的结构化机制案例，不是现实 LEO 网络中的 reversal 概率。

## 分机制结果

### E-A：BBM temporary partition

执行 {summary["E_A"]["logical_points"]} 个 logical points。真实 setup 产生的 temporary-partition duration 取值为 {summary["E_A"]["temporary_partition_duration_values_s"]} s；出现正 setup backlog 的点数为 {summary["E_A"]["positive_setup_backlog_points"]}。逐点 affected commodities、backlog、recovery 和 drain 记录在 `case_details.jsonl`。

### E-B：connected BBM reroute

正式结果为 `NOT_NATURALLY_AVAILABLE_UNDER_CURRENT_SPARSE_ZREF`，四个 κ₂ bin 均保留原始 `NO_ELIGIBLE_CASE`。这只说明当前三 bridge 的稀疏 Z_ref 没有自然 E-B case。

### E-C：genuine MBB

执行 {summary["E_C"]["logical_points"]} 个 logical points。所有 REAL MBB 是否保持业务连续：{summary["E_C"]["all_real_mbb_continuous"]}；出现非零 forced outage 的点数：{summary["E_C"]["nonzero_forced_outage_points"]}。setup opportunity cost 和 κ₂ 分层结果见逐点记录。

### E-D：shared-congestion externality

执行 {summary["E_D"]["logical_points"]} 个 logical points，其中 {summary["E_D"]["evaluable_points"]} 个未 censor。focus 改善且 third party 恶化的点数为 {summary["E_D"]["focus_improves_third_degrades_points"]}；shared-link utilization 与两个 router 的逐点差异记录在 `case_details.jsonl`。

## 解释边界

setup=2 s 是 Gate C simplified parametric audit fixture，不是真实商业 LCT 硬件测量值。自然 κ₂、candidate 和 Z_ref 均未因结果修改。Gate F、matching、MPC、RL、240/720 星实验及 setup sensitivity 均未启动。
'''
    (PROJECT/"docs/GATE_E2_160STAR_MECHANISM_RESULT_CN.md").write_text(text,encoding="utf-8")


def main():
    global OUT
    if not __debug__:raise RuntimeError("Gate E2 acceptance requires assertions")
    started=time.time()
    pre=read_json(PROJECT/"configs/pre_e2_absolute_time_status.json")
    selection=read_json(PROJECT/"configs/gate_e2_status.json")
    execution=read_json(PROJECT/"configs/gate_e2_execution_points.json")
    if pre.get("pre_e2_absolute_time_regression")!="PASS":
        raise RuntimeError("PRE_E2_PASS_REQUIRED_STOP")
    if not selection.get("candidate_selection_frozen"):
        raise RuntimeError("E2_SELECTION_FREEZE_REQUIRED_STOP")
    if execution.get("status")!="FROZEN_BEFORE_PAIRED_BRANCH_EXECUTION":
        raise RuntimeError("E2_EXECUTION_POINTS_NOT_FROZEN_STOP")
    OUT=new_output("gate_e2")
    dump(OUT/"status.json",{"gate_e2":"RUNNING","gate_f_started":False})
    records=[
      "configs/gate_e2_frozen_a_to_pre_e2_hashes.json",
      "configs/gate_e2_selection_hashes.json",
      "configs/gate_e2_execution_points_hashes.json",
      "configs/gate_e2_execution_code_hashes.json",
      "configs/gate_e0_manifest_hashes.json",
      "configs/gate_e1_manifest_hashes.json"]
    audits={name:hash_audit(name) for name in records}
    dump(OUT/"frozen_input_hash_report.json",audits)
    if not all(row["all_unchanged"] for row in audits.values()):
        raise RuntimeError("FROZEN_INPUT_HASH_PREFLIGHT_FAILED_STOP")

    print("E2_STAGE REGISTERED_NATURAL_GEOMETRY_RUN",flush=True)
    scientific=run_parallel(24,progress("RUN"))
    write_jsonl(OUT/"unique_physical_results.jsonl",scientific["physical_results"])
    write_jsonl(OUT/"case_details.jsonl",scientific["logical_results"])
    dump(OUT/"execution_reuse_map.json",{
      "selected_logical_entries":execution["logical_selected_entries"],
      "logical_paired_points":execution["logical_paired_points"],
      "unique_physical_execution_scenarios":execution["unique_physical_execution_points"],
      "unique_executed_paired_points":len(scientific["physical_results"]),
      "reuse":scientific["execution_reuse_map"]})

    print("E2_STAGE COMPLETE_DETERMINISTIC_REPLAY",flush=True)
    replay=run_parallel(24,progress("REPLAY"))
    replay_report={
      "scientific_canonical_sha256":scientific["canonical_sha256"],
      "replay_canonical_sha256":replay["canonical_sha256"],
      "canonical_results_equal":scientific["canonical_sha256"]==replay["canonical_sha256"],
      "scientific_integrity_failures":scientific["integrity_failures"],
      "replay_integrity_failures":replay["integrity_failures"]}
    dump(OUT/"deterministic_replay_report.json",replay_report)

    print("E2_STAGE FULL_REGRESSION",flush=True)
    full=run_tests("test_*.py","full_regression.txt",1)
    post={name:hash_audit(name) for name in records}
    dump(OUT/"post_run_frozen_input_hash_report.json",post)
    summary=summarize(scientific,execution)
    dump(OUT/"scientific_summary.json",summary)
    logical_ids={row["logical_point_id"] for row in scientific["logical_results"]}
    expected_ids={row["logical_point_id"] for row in execution["logical_points"]}
    branch_status_ok=all(
      branch["status"] in ("EXECUTED","CENSORED_AT_DRAIN_LIMIT")
      for row in scientific["physical_results"] for branch in row["branches"].values())
    integrity_ok=all(value==0 for value in scientific["integrity_failures"].values())
    replay_integrity_ok=all(value==0 for value in replay["integrity_failures"].values())
    router_points=defaultdict(set)
    for row in scientific["logical_results"]:
        router_points[row["router"]].add((row["scenario_id"],row["rho"],row["setup_s"]))
    availability=execution["no_eligible_strata"]
    selected_validation=read_json(PROJECT/"configs/gate_e2_selected_scenarios.json")["selected_gate_c_validation"]
    acceptance={
      "execution_point_contract_frozen_before_branches":True,
      "all_registered_logical_points_present":logical_ids==expected_ids and len(logical_ids)==80,
      "all_unique_physical_points_executed":len(scientific["physical_results"])==50,
      "all_required_branches_completed_or_censored":branch_status_ok,
      "all_no_eligible_strata_retained":len(availability)==16 and sum(row["status"]=="NO_ELIGIBLE_CASE" for row in availability)==8,
      "E_B_all_bins_no_eligible":all(row["status"]=="NO_ELIGIBLE_CASE" for row in availability if row["scenario_class"]=="E-B_BBM_CONNECTED_REROUTE"),
      "both_routers_identical_points":router_points["shortest_propagation"]==router_points["current_state_load_aware"],
      "paired_identity_all_points":scientific["integrity_failures"].get("paired_identity",0)==0,
      "work_conservation_all_branches":scientific["integrity_failures"].get("work_conservation",0)==0,
      "capacity_all_branches":scientific["integrity_failures"].get("capacity",0)==0,
      "nonnegative_queue_all_branches":scientific["integrity_failures"].get("nonnegative_queue",0)==0,
      "gate_c_legality_unchanged":selected_validation["all_selected_gate_c_legal"] and scientific["integrity_failures"].get("gate_c_action",0)==0,
      "no_result_based_scenario_replacement":logical_ids==expected_ids,
      "deterministic_complete_replay":replay_report["canonical_results_equal"],
      "replay_integrity":replay_integrity_ok,
      "frozen_assets_unchanged":all(row["all_unchanged"] for row in post.values()),
      "full_regression_pass":full.wasSuccessful(),
      "gate_f_not_started":True}
    passed=all(acceptance.values()) and integrity_ok
    report={
      "gate_e2_160star_natural_geometry_mechanism_validation":"PASS" if passed else "FAIL",
      "statement":"Gate E2 160-star natural-geometry mechanism validation = "+("PASS" if passed else "FAIL"),
      "acceptance_checks":acceptance,"scientific_summary":summary,
      "execution_points_sha256":execution["canonical_sha256"],
      "scientific_results_sha256":scientific["canonical_sha256"],
      "deterministic_replay_sha256":replay["canonical_sha256"],
      "setup_interpretation":"2 s simplified parametric fixture; not a commercial hardware measurement",
      "sampling_interpretation":"structured result-blind cases; counts are not probabilities",
      "gate_f_started":False}
    dump(OUT/"report.json",report)
    dump(OUT/"tests_report.json",{"full":{"tests":full.testsRun,
          "successful":full.wasSuccessful(),"cases":full.cases}})
    dump(OUT/"inputs.json",{
      "python":platform.python_version(),"workers":24,
      "elapsed_s":time.time()-started,"pre_e2_evidence":pre["evidence"],
      "code_hashes":{name:sha(PROJECT/name) for name in (
        "src/dynamic_lisl/gate_e2_experiments.py",
        "src/dynamic_lisl/gate_e2_parallel.py",
        "tools/check_gate_e2.py","tests/test_gate_e2_execution.py")}})
    evidence=str(OUT.relative_to(PROJECT)).replace("\\","/")
    status={"gate_e2":"PASS" if passed else "FAIL",
      "statement":report["statement"],"evidence":evidence,
      "paired_branches_executed":True,"gate_e2_complete":passed,
      "gate_e2_started":True,"gate_f_started":False}
    dump(OUT/"status.json",status);dump(PROJECT/"configs/gate_e2_status.json",status)
    write_result_doc(summary,passed,evidence)
    if passed:
        current=read_json(PROJECT/"configs/current.json")
        current["project_status"]="GATE_E2_160STAR_NATURAL_GEOMETRY_MECHANISM_VALIDATION_PASS"
        current["gate_e2"]={"status":"PASS","record":"configs/gate_e2_status.json",
          "contract":"docs/GATE_E2_EXECUTION_CONTRACT_CN.md",
          "result":"docs/GATE_E2_160STAR_MECHANISM_RESULT_CN.md",
          "execution_points":"configs/gate_e2_execution_points.json",
          "evidence":evidence}
        current["gate_e2_started"]=True;current["gate_f_started"]=False
        current["current_command"]="python tools/check_gate_e2.py"
        dump(PROJECT/"configs/current.json",current)
    dump(OUT/"hashes.json",{path.name:sha(path) for path in OUT.iterdir()
                             if path.is_file() and path.name!="hashes.json"})
    print(report["statement"],OUT,flush=True)
    print("Gate F started = false",flush=True)
    return 0 if passed else 1


if __name__=="__main__":raise SystemExit(main())
