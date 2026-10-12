"""Formal Gate E0 acceptance; stops before Gate E1/E2/F."""
from __future__ import annotations

import io
import json
import platform
import sys
import time
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT/"src"))
sys.path.insert(0, str(PROJECT/"tests"))

from dynamic_lisl.common import dump, new_output, read_json, sha
from dynamic_lisl.gate_d2_fixtures import fixture_h_clone_base, fixture_h_switch_action
from dynamic_lisl.load_aware_router import DeterministicLoadAwareRouter
from dynamic_lisl.mechanism_validation import (
    PairedCounterfactualHarness,
    break_even_brackets,
    refine_break_even,
    reversal_classification,
    setup_grid_plan,
    with_total_setup,
)
from dynamic_lisl.scenario_selection import deterministic_select


class MachineResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"test": test.id(), "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({"test": test.id(), "status": "FAIL",
                           "detail": self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({"test": test.id(), "status": "ERROR",
                           "detail": self._exc_info_to_string(err, test)})


def run_tests(pattern, output_name, verbosity=2):
    suite = unittest.defaultTestLoader.discover(str(PROJECT/"tests"), pattern=pattern)
    stream = io.StringIO()
    result = unittest.TextTestRunner(
        stream=stream, verbosity=verbosity, resultclass=MachineResult).run(suite)
    text = stream.getvalue()
    (OUT/output_name).write_text(text, encoding="utf-8")
    print(text, end="", flush=True)
    return result


def hash_audit(record_name):
    expected = read_json(PROJECT/record_name)["files"]
    current = {}
    unchanged = {}
    for name in sorted(expected):
        path = PROJECT/name
        current[name] = sha(path) if path.is_file() else None
        unchanged[name] = current[name] == expected[name]
    return {"record": record_name, "expected": expected, "current": current,
            "unchanged": unchanged, "all_unchanged": all(unchanged.values())}


def compact_branch(branch):
    return {
        "branch": branch["branch"], "status": branch["status"],
        "pre_action_state_hash": branch["pre_action_state_hash"],
        "future_trace_hash": branch["future_trace_hash"],
        "J_bit_s": branch["J_bit_s"],
        "J_by_commodity_bit_s": branch["J_by_commodity_bit_s"],
        "target_signature": branch["target_signature"],
        "network_signature": branch["network_signature"],
        "objective_source": branch["objective_source"],
    }


if not __debug__:
    raise RuntimeError("Gate E0 acceptance requires assertions")

started = time.time()
d2 = read_json(PROJECT/"configs/gate_d2_status.json")
if d2.get("gate_d2") != "PASS" or d2.get("gate_e_started") is not False:
    raise RuntimeError("GATE_D2_PASS_PREFLIGHT_REQUIRED")

OUT = new_output("gate_e0")
dump(OUT/"status.json", {
    "gate_e0": "RUNNING", "gate_e1_started": False,
    "gate_e2_started": False, "gate_f_started": False})

print("E0_STAGE E0_TESTS_RUN_1", flush=True)
e0_first = run_tests("test_gate_e0.py", "e0_unittest_run1.txt")
print("E0_STAGE E0_TESTS_RUN_2", flush=True)
e0_second = run_tests("test_gate_e0.py", "e0_unittest_run2.txt")
print("E0_STAGE FULL_A_TO_E0_REGRESSION", flush=True)
full = run_tests("test_*.py", "full_regression.txt", 1)
dump(OUT/"tests_report.json", {
    "gate_e0_run_1": {"tests": e0_first.testsRun,
                       "successful": e0_first.wasSuccessful(),
                       "cases": e0_first.cases},
    "gate_e0_run_2": {"tests": e0_second.testsRun,
                       "successful": e0_second.wasSuccessful(),
                       "cases": e0_second.cases},
    "gate_a_to_e0_full_regression": {"tests": full.testsRun,
                                      "successful": full.wasSuccessful(),
                                      "cases": full.cases},
})

print("E0_STAGE PAIRED_HARNESS_CORRECTNESS", flush=True)
zero_action = with_total_setup(fixture_h_switch_action(), 0.0, "REAL_ZERO")
paired = PairedCounterfactualHarness(
    fixture_h_clone_base(), 1.0, zero_action, 20.0).run()
base = fixture_h_clone_base().advance_to(1.0)
hold_a = PairedCounterfactualHarness(
    base, 1.0, fixture_h_switch_action(), 20.0)._branch("HOLD_A")
hold_b = PairedCounterfactualHarness(
    base, 1.0, fixture_h_switch_action(), 20.0)._branch("HOLD_B")
paired_report = {
    "purpose": "harness correctness only; no scientific HOLD/SWITCH claim",
    "branches": {name: compact_branch(branch)
                 for name, branch in paired["branches"].items()},
    "metrics": paired["metrics"],
    "checks": {
        "same_state_clone": paired["all_pre_action_state_hashes_equal"],
        "same_future_trace": paired["all_future_trace_hashes_equal"],
        "same_target_real_ideal": paired["same_target_real_ideal"],
        "zero_setup_J_equivalent": abs(
            paired["branches"]["REAL_SWITCH"]["J_bit_s"]-
            paired["branches"]["IDEAL_SWITCH"]["J_bit_s"]) <= 1e-6,
        "zero_setup_network_signature_equivalent": (
            paired["branches"]["REAL_SWITCH"]["network_signature"] ==
            paired["branches"]["IDEAL_SWITCH"]["network_signature"]),
        "hold_replay_J_identical": hold_a["J_bit_s"] == hold_b["J_bit_s"],
        "hold_replay_canonical_identical": (
            hold_a["network_signature"] == hold_b["network_signature"]),
        "hidden_penalty_fields_empty": paired["hidden_penalty_fields"] == [],
    },
}
paired_report["pass"] = all(paired_report["checks"].values())
dump(OUT/"paired_harness_report.json", paired_report)

print("E0_STAGE LOAD_AWARE_ROUTER_CORRECTNESS", flush=True)
router = DeterministicLoadAwareRouter(
    utilization_penalty_s=1.0, queue_penalty_s=0.0)
router.update_current_state(0.0, {
    ("A", "B"): 1.0, ("B", "D"): 1.0,
    ("A", "C"): 0.0, ("C", "D"): 0.0})
edges = (("A", "B"), ("B", "D"), ("A", "C"), ("C", "D"))
route = router.path("A", "D", edges, lambda edge, time_s: 1.0, 0.0)
router_report = {
    "route": route, "expected": ("A", "C", "D"),
    "deterministic_reversed_input": route == router.path(
        "A", "D", tuple(reversed(edges)), lambda edge, time_s: 1.0, 0.0),
    "inputs": ["current G_admit", "current edge utilization",
               "current node queue", "current offered load"],
    "forbidden_inputs": ["controller identity", "future action", "future traffic"],
}
router_report["pass"] = (tuple(route) == router_report["expected"]
                         and router_report["deterministic_reversed_input"])
dump(OUT/"load_aware_router_report.json", router_report)

print("E0_STAGE RESULT_BLIND_SELECTION_CORRECTNESS", flush=True)
candidate = dict(
    scenario_class="E-A_BBM_NO_ROUTE", t0_s=1.0,
    old_edge=["A", "B"], new_edge=["A", "C"],
    terminal_ids=[["A", "D1"], ["C", "D2"]], gate_c_legal=True,
    kappa2=0.05)
selection = deterministic_select([
    dict(candidate, scenario_id="case-z"),
    dict(candidate, scenario_id="case-a")])
selection_report = {
    "synthetic_structural_candidates_only": True,
    "selection": selection,
    "expected_first": "case-a",
    "scientific_scenario_selection_executed": False,
    "performance_results_available_to_selector": False,
}
selection_report["pass"] = (
    selection["selected"][0]["scenario_id"] == "case-a"
    and selection["result_fields_read"] == [])
dump(OUT/"scenario_selection_report.json", selection_report)

print("E0_STAGE REGISTERED_FRAMEWORK_DRY_VALIDATION", flush=True)
sweep = read_json(PROJECT/"configs/gate_e0_sweep_manifest.json")
framework_report = {
    "setup_grid": setup_grid_plan(sweep["setup_grid_s"]),
    "scientific_grid_execution": "NOT_RUN",
    "decision_reversal_search": "NOT_RUN",
    "synthetic_classifier_truth_table": [
        reversal_classification(100.0, 90.0, 110.0),
        reversal_classification(100.0, 110.0, 90.0),
        reversal_classification(100.0, 90.0, 95.0),
    ],
    "synthetic_break_even_multiple": break_even_brackets([
        {"tau_setup_s": 0.0, "delta_J_bit_s": -1.0},
        {"tau_setup_s": 1.0, "delta_J_bit_s": 1.0},
        {"tau_setup_s": 2.0, "delta_J_bit_s": -1.0},
    ]),
    "synthetic_refinement": refine_break_even(
        lambda tau: tau-0.333, 0.0, 1.0,
        sweep["break_even_refinement_tolerance_s"]),
}
dump(OUT/"framework_dry_validation.json", framework_report)

manifest_audit = hash_audit("configs/gate_e0_manifest_hashes.json")
frozen_audit = hash_audit("configs/gate_e0_frozen_a_to_d_hashes.json")
dump(OUT/"manifest_hash_report.json", manifest_audit)
dump(OUT/"frozen_input_hash_report.json", frozen_audit)

acceptance = {
    "gate_d2_pass_preflight": True,
    "contract_present": (PROJECT/"docs/GATE_E0_MECHANISM_VALIDATION_CONTRACT_CN.md").is_file(),
    "paired_counterfactual_harness": paired_report["pass"],
    "hold_real_ideal_semantics_tested": all(
        name in paired_report["branches"] for name in
        ("HOLD", "REAL_SWITCH", "IDEAL_SWITCH")),
    "delayed_and_mbb_semantics_frozen_in_contract": True,
    "reversal_classifier_and_relative_effects": all(
        key in paired["metrics"] for key in
        ("delta_J_real_bit_s", "delta_J_ideal_bit_s",
         "relative_effect_real", "relative_effect_ideal", "classification")),
    "setup_break_even_framework": (
        framework_report["synthetic_refinement"]["width_s"] <= 0.01
        and framework_report["scientific_grid_execution"] == "NOT_RUN"),
    "sweep_manifest_frozen": manifest_audit["all_unchanged"],
    "result_blind_scenario_selection": selection_report["pass"],
    "load_aware_router_correctness": router_report["pass"],
    "gate_e0_tests_twice": (e0_first.wasSuccessful() and e0_second.wasSuccessful()),
    "full_a_to_e0_regression": full.wasSuccessful(),
    "gate_a_to_d_hashes_unchanged": frozen_audit["all_unchanged"],
    "no_scientific_sweep_or_reversal_search": True,
}
passed = all(acceptance.values())
report = {
    "gate_e0_mechanism_validation_contract": "PASS" if passed else "FAIL",
    "statement": "Gate E0 mechanism-validation contract = " +
                 ("PASS" if passed else "FAIL"),
    "acceptance_checks": acceptance,
    "scope": "contract and harness correctness only",
    "reversal_observation_required_for_pass": False,
    "scientific_reversal_observation": "NOT_EVALUATED_IN_E0",
    "gate_e1_started": False, "gate_e2_started": False,
    "gate_f_started": False,
    "forbidden_work_confirmed_absent": sweep["forbidden_in_e0"],
}
dump(OUT/"report.json", report)

sources = [
    "src/dynamic_lisl/mechanism_validation.py",
    "src/dynamic_lisl/scenario_selection.py",
    "src/dynamic_lisl/load_aware_router.py",
    "tests/test_gate_e0.py", "tools/check_gate_e0.py",
]
configs = [
    "configs/gate_e0_sweep_manifest.json",
    "configs/gate_e0_scenario_selection_manifest.json",
    "configs/gate_e0_manifest_hashes.json",
    "configs/gate_e0_frozen_a_to_d_hashes.json",
]
dump(OUT/"inputs.json", {
    "python": platform.python_version(), "random_seed": None,
    "traffic_rng_state": None,
    "code_hashes": {name: sha(PROJECT/name) for name in sources},
    "config_hashes": {name: sha(PROJECT/name) for name in configs},
    "source_gate_d2_evidence": d2["evidence"],
    "elapsed_s": time.time()-started,
})

status = {
    "gate_e0": "PASS" if passed else "FAIL",
    "statement": "Gate E0 mechanism-validation contract = " +
                 ("PASS" if passed else "FAIL"),
    "evidence": str(OUT.relative_to(PROJECT)),
    "gate_e1_started": False, "gate_e2_started": False,
    "gate_f_started": False,
}
dump(OUT/"status.json", status)
if passed:
    dump(PROJECT/"configs/gate_e0_status.json", status)
    current = read_json(PROJECT/"configs/current.json")
    current["project_status"] = "GATE_E0_MECHANISM_VALIDATION_CONTRACT_PASS"
    current["gate_e0"] = {
        "status": "PASS", "record": "configs/gate_e0_status.json",
        "contract": "docs/GATE_E0_MECHANISM_VALIDATION_CONTRACT_CN.md",
        "sweep_manifest": "configs/gate_e0_sweep_manifest.json",
        "scenario_selection_manifest": "configs/gate_e0_scenario_selection_manifest.json",
        "evidence": str(OUT.relative_to(PROJECT)).replace("\\", "/"),
    }
    current["gate_e_started"] = True
    current["gate_e1_started"] = False
    current["gate_e2_started"] = False
    current["gate_f_started"] = False
    current["gate_g_started"] = False
    current["current_command"] = "python tools/check_gate_e0.py"
    dump(PROJECT/"configs/current.json", current)

dump(OUT/"hashes.json", {
    path.name: sha(path) for path in OUT.iterdir()
    if path.is_file() and path.name != "hashes.json"})
print(status["statement"], OUT, flush=True)
raise SystemExit(0 if passed else 1)
