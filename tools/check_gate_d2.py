"""Formal Gate D2 acceptance; stops before Gate E/F."""
from __future__ import annotations
import hashlib, io, json, platform, sys, time, unittest
from pathlib import Path

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project/"src")); sys.path.insert(0, str(project/"tests"))
from dynamic_lisl.common import dump, new_output, read_json, sha
from dynamic_lisl.gate_d2_fixtures import (SMALL_FIXTURE_BUILDERS,
    fixture_h_clone_base, fixture_h_switch_action, load_160_pilot)

class MachineResult(unittest.TextTestResult):
    def __init__(self,*a,**k): super().__init__(*a,**k); self.cases=[]
    def addSuccess(self,t): super().addSuccess(t); self.cases.append({"test":t.id(),"status":"PASS"})
    def addFailure(self,t,e): super().addFailure(t,e); self.cases.append({"test":t.id(),"status":"FAIL","detail":self._exc_info_to_string(e,t)})
    def addError(self,t,e): super().addError(t,e); self.cases.append({"test":t.id(),"status":"ERROR","detail":self._exc_info_to_string(e,t)})

def run_tests(pattern,name,verbosity=2):
    suite=unittest.defaultTestLoader.discover(str(project/"tests"),pattern=pattern)
    stream=io.StringIO(); result=unittest.TextTestRunner(stream=stream,verbosity=verbosity,resultclass=MachineResult).run(suite)
    text=stream.getvalue(); (out/name).write_text(text,encoding="utf-8"); print(text,end="",flush=True); return result

def normalized(result):
    document=dict(result); document["metrics"]=dict(result["metrics"]); document["metrics"].pop("runtime",None)
    return json.dumps(document,sort_keys=True,separators=(",",":"),allow_nan=False)

def analytical(expected,observed):
    absolute=abs(float(observed)-float(expected))
    return {"analytical_expected":expected,"simulated_observed":observed,"absolute_error":absolute,"relative_error":absolute/max(1.0,abs(float(expected)))}

def compact_160(result):
    times={0.0,1.0,3.0,12.0,result["metrics"]["evaluation_end_s"]}; checkpoints=[]
    for row in result["timeline"]:
        if any(abs(row["time_s"]-value)<=1e-9 for value in times):
            if not checkpoints or row!=checkpoints[-1]: checkpoints.append(row)
    source_changes=[row for row in result["route_changes"] if row["old_route"] and row["node"]==row["old_route"][0]]
    return {"metrics":result["metrics"],"action_results":result["action_results"],
            "terminal_event_sequence":result["terminal_event_sequence"],"graph_event_sequence":result["graph_event_sequence"],
            "route_state_events":result["route_state_events"],"source_route_changes":source_changes,
            "queue_trajectory_checkpoints":checkpoints,"transition_episodes":result["transition_episodes"],
            "arrived_by_commodity":result["arrived_by_commodity"],"delivered_by_commodity":result["delivered_by_commodity"]}

def conservation_entry(result,abs_tol=1.0,rel_tol=1e-12):
    m=result["metrics"]; limit=abs_tol+rel_tol*max(1.0,m["arrived_bits"])
    passed=(m["max_abs_conservation_error_bits"]<=limit and m["negative_queue_count"]==0 and m["max_capacity_violation_bit_s"]<=0.01)
    return {"max_abs_error_bits":m["max_abs_conservation_error_bits"],"allowed_error_bits":limit,
            "negative_queue_count":m["negative_queue_count"],"max_capacity_violation_bit_s":m["max_capacity_violation_bit_s"],"pass":passed}

def frozen_audit():
    expected=read_json(project/"configs/gate_d2_frozen_baseline_hashes.json")["files"]
    current={name:sha(project/name) for name in sorted(expected)}; unchanged={name:current[name]==expected[name] for name in sorted(expected)}
    return {"expected":expected,"current":current,"unchanged":unchanged,"all_unchanged":all(unchanged.values())}

if not __debug__: raise RuntimeError("Gate D2 acceptance requires assertions")
out=new_output("gate_d2"); dump(out/"status.json",{"gate_d2":"RUNNING","gate_e_started":False,"gate_f_started":False}); started=time.time()
print("D2_STAGE UNIT_TESTS",flush=True); d2_tests=run_tests("test_gate_d2.py","d2_unittest.txt")
print("D2_STAGE FULL_REGRESSION",flush=True); full_regression=run_tests("test_*.py","full_regression.txt",1)
test_report={"d2":{"tests":d2_tests.testsRun,"successful":d2_tests.wasSuccessful(),"cases":d2_tests.cases},
             "gate_a_to_d_full_regression":{"tests":full_regression.testsRun,"successful":full_regression.wasSuccessful(),"cases":full_regression.cases}}
dump(out/"tests_report.json",test_report)

print("D2_STAGE SMALL_FIXTURES",flush=True); small={key:builder().run(30.0) for key,builder in SMALL_FIXTURE_BUILDERS.items()}
base=fixture_h_clone_base().advance_to(1.0); hold=base.clone(); switch=base.clone(); clone_hash_equal=hold.canonical_state_sha256()==switch.canonical_state_sha256()
switch.schedule_action(fixture_h_switch_action(1.0)); hold_result=hold.run(20.0); switch_result=switch.run(20.0)
h_report={"pre_branch_state_hash_equal":clone_hash_equal,
          "initial_simulation_time_equal":base.now==base.executor.now,
          "future_trace_hash_equal":hold_result["metrics"]["trace_sha256"]==switch_result["metrics"]["trace_sha256"],
          "arrived_bits_equal":hold_result["metrics"]["arrived_bits"]==switch_result["metrics"]["arrived_bits"],
          "hold_switch_counts":[hold_result["metrics"]["switch_count"],switch_result["metrics"]["switch_count"]],
          "claim_scope":"state clone sanity only; no HOLD/SWITCH performance claim"}
h_report["pass"]=all((h_report["pre_branch_state_hash_equal"],h_report["initial_simulation_time_equal"],h_report["future_trace_hash_equal"],h_report["arrived_bits_equal"],h_report["hold_switch_counts"]==[0,1]))
a=small["D2-A"]["metrics"]
analytical_report={"D2-A":{"outage_duration_s":analytical(2.0,a["outage_duration_s"]),"backlog_added_bits":analytical(16e9,a["backlog_added_during_transition_bits"]),"peak_backlog_bits":analytical(16e9,a["peak_transition_backlog_bits"]),"clearance_time_s":analytical(8.0,a["backlog_clearance_time_s"])},"D2-B":{"forced_outage_duration_s":analytical(0.0,small["D2-B"]["metrics"]["outage_duration_s"])}}
dump(out/"analytical_comparison.json",analytical_report)
ra=SMALL_FIXTURE_BUILDERS["D2-A"]().run(30.0); rb=SMALL_FIXTURE_BUILDERS["D2-A"]().run(30.0); ca=normalized(ra); cb=normalized(rb)
replay={"fixture":"D2-A","same_future_trace_hash":ra["metrics"]["trace_sha256"]==rb["metrics"]["trace_sha256"],"canonical_identical_excluding_runtime":ca==cb,"canonical_sha256":hashlib.sha256(ca.encode()).hexdigest(),"covered":["Gate B event sequence","active/admit graph sequence","route changes","queue trajectory","in-flight accounting","delivered bits","conservation","J","mean delay","transition metrics"]}
replay["pass"]=replay["same_future_trace_hash"] and replay["canonical_identical_excluding_runtime"]; dump(out/"deterministic_replay_report.json",replay)

print("D2_STAGE PILOT_160_BRIDGE",flush=True); engine,limit=load_160_pilot("bridge_temporary_partition"); bridge=engine.run(limit)
print("D2_STAGE PILOT_160_MBB",flush=True); engine,limit=load_160_pilot("connected_mbb_reroute"); mbb=engine.run(limit)
fixture_results={"small":small,"D2-H":{"report":h_report,"hold_metrics":hold_result["metrics"],"switch_metrics":switch_result["metrics"]},"pilot_160":{"bridge_temporary_partition":compact_160(bridge),"connected_mbb_reroute":compact_160(mbb)}}
dump(out/"fixture_results.json",fixture_results)
all_results={**small,"160_bridge":bridge,"160_mbb":mbb}; conservation={key:conservation_entry(value) for key,value in all_results.items()}
conservation_report={"identity":"A_f = D_f + sum_i Q_i^f + sum_e I_e^f","frozen_abs_tolerance_bits":1.0,"frozen_relative_tolerance":1e-12,"capacity_tolerance_bit_s":0.01,"cases":conservation,"pass":all(row["pass"] for row in conservation.values())}; dump(out/"conservation_report.json",conservation_report)
metric_names=("BBM_count","MBB_count","route_change_count","no_route_duration_s","outage_duration_s","partition_duration_s","partition_node_time_s","backlog_added_during_transition_bits","peak_transition_backlog_bits","backlog_clearance_time_s","max_queue_bits","delivered_bits","residual_backlog_bits","J_bit_s","mean_bit_delay_s")
dump(out/"transition_metrics.json",{key:{name:value["metrics"].get(name) for name in metric_names} for key,value in all_results.items()})
frozen=frozen_audit(); dump(out/"frozen_input_hash_report.json",frozen)

def has_state(result,commodity,state,old=None):
    return any(row["commodity_id"]==commodity and row["new_state"]==state and (old is None or row["old_state"]==old) for row in result["route_state_events"])
bridge_no=any(row["new_state"]=="NO_ROUTE_TEMPORARY" for row in bridge["route_state_events"]); bridge_rec=any(row["old_state"]=="NO_ROUTE_TEMPORARY" and row["new_state"]=="ROUTED" for row in bridge["route_state_events"])
small_checks={
 "bbm_analytical_outage_and_backlog":abs(a["outage_duration_s"]-2)<=1e-9 and abs(a["backlog_added_during_transition_bits"]-16e9)<=1 and abs(a["backlog_clearance_time_s"]-8)<=1e-9,
 "genuine_mbb_no_forced_outage":small["D2-B"]["metrics"]["MBB_count"]==1 and small["D2-B"]["metrics"]["outage_duration_s"]==0,
 "false_mbb_gate_c_rejection":not small["D2-C"]["action_results"][0]["accepted"] and small["D2-C"]["action_results"][0]["physical_reason"]=="FOR_FAIL_BILATERAL",
 "draining_active_admit_split":any(("B","C") in row["active_edges"] and ("B","C") not in row["admit_edges"] for row in small["D2-D"]["graph_event_sequence"]),
 "temporary_partition_wait_and_recovery":has_state(small["D2-E"],"affected","NO_ROUTE_TEMPORARY") and has_state(small["D2-E"],"affected","ROUTED","NO_ROUTE_TEMPORARY") and "unaffected" not in small["D2-E"]["metrics"]["no_route_duration_by_commodity_s"],
 "alternate_path_deterministic_reroute":any(row["node"]=="A" and row["commodity_id"]=="target" and row["new_route"]==["A","B","D"] for row in small["D2-F"]["route_changes"]),
 "natural_expiry_propagates":any(row["event"]=="LINK_DOWN" and row["details"].get("reason")=="LINK_EXPIRE" for row in small["D2-G"]["terminal_event_sequence"]),"same_state_branching":h_report["pass"]}
pilot_checks={"bridge_action_gate_c_legal":bridge["action_results"][0]["accepted"],"bridge_partition_no_route_recovery":bridge_no and bridge_rec and bridge["metrics"]["partition_duration_s"]==2.0,"bridge_queue_accumulation_and_drain":bridge["metrics"]["backlog_added_during_transition_bits"]>0 and not bridge["metrics"]["censored"],"mbb_action_gate_c_legal":mbb["action_results"][0]["accepted"],"mbb_connected_without_forced_outage":all(len(row["admit_components"])==1 for row in mbb["graph_event_sequence"]) and mbb["metrics"]["outage_duration_s"]==0,"mbb_causes_route_change":mbb["metrics"]["route_change_count"]>0,"same_frozen_traffic_trace":bridge["metrics"]["trace_sha256"]==mbb["metrics"]["trace_sha256"]}
acceptance={**small_checks,**pilot_checks,"all_topology_events_work_conservation":conservation_report["pass"],"deterministic_replay":replay["pass"],"frozen_A_B_C_D0_D1_unchanged":frozen["all_unchanged"],"d2_unit_tests":d2_tests.wasSuccessful(),"gate_A_to_D_full_regression":full_regression.wasSuccessful()}; passed=all(acceptance.values())
report={"gate_d2_transition_aware_network_service_integration":"PASS" if passed else "FAIL","acceptance_checks":acceptance,"scope":"integration/correctness only; deterministic scripted fixtures","causal_chain":"scripted terminal proposal -> Gate C -> Gate B events -> G_active/G_admit -> CommonRouter -> service -> Q/I/D","gate_e_started":False,"gate_f_started":False,"forbidden_work_confirmed_absent":["automatic HOLD/SWITCH policy","topology scoring","matching/b-matching","greedy/hysteresis","MPC","RL/PPO","decision-reversal search","parameter sweep","720-satellite experiment"]}; dump(out/"report.json",report)
sources=["src/dynamic_lisl/transition_service_orchestrator.py","src/dynamic_lisl/gate_d2_fixtures.py","tests/test_gate_d2.py","tools/check_gate_d2.py"]; configs=["configs/gate_d2_fixture_manifest.json","configs/gate_d2_frozen_baseline_hashes.json"]
dump(out/"inputs.json",{"python":platform.python_version(),"random_seed":None,"traffic_rng_state":None,"code_hashes":{n:sha(project/n) for n in sources},"config_hashes":{n:sha(project/n) for n in configs},"elapsed_s":time.time()-started})
status={"gate_d2":"PASS" if passed else "FAIL","statement":"Gate D2 transition-aware network-service integration = "+("PASS" if passed else "FAIL"),"evidence":str(out.relative_to(project)),"gate_e_started":False,"gate_f_started":False}; dump(out/"status.json",status)
if passed:
    dump(project/"configs/gate_d2_status.json",status); current=read_json(project/"configs/current.json"); current["project_status"]="GATE_D2_TRANSITION_AWARE_NETWORK_SERVICE_INTEGRATION_PASS"; current["gate_d2"]={"status":"PASS","record":"configs/gate_d2_status.json","evidence":str(out.relative_to(project)).replace("\\","/"),"result":"docs/GATE_D2_TRANSITION_SERVICE_RESULT_CN.md"}; current.pop("gate_d2_to_g",None); current["gate_e_started"]=False; current["gate_f_started"]=False; current["gate_g_started"]=False; current["current_command"]="python tools/check_gate_d2.py"; dump(project/"configs/current.json",current)
dump(out/"hashes.json",{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!="hashes.json"}); print(status["statement"],out,flush=True); raise SystemExit(0 if passed else 1)
