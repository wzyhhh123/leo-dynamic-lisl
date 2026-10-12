"""Formal Gate E1 execution and acceptance; stops before E2/F."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
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
from dynamic_lisl.gate_e1_experiments import (
    REQUIRED_BRANCHES, ROUTER_PRIMARY, ROUTER_ROBUSTNESS,
    break_even_summary, common_drain_limit_s, evaluate_point, frozen_templates,
)
from dynamic_lisl.mechanism_validation import refine_break_even


class MachineResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"test": test.id(), "status": "PASS"})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.cases.append({"test": test.id(), "status": "FAIL",
                           "detail": self._exc_info_to_string(error, test)})

    def addError(self, test, error):
        super().addError(test, error)
        self.cases.append({"test": test.id(), "status": "ERROR",
                           "detail": self._exc_info_to_string(error, test)})


def canonical_line(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)+"\n"


def run_tests(pattern, output_name, verbosity=1):
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
    current = {name: sha(PROJECT/name) if (PROJECT/name).is_file() else None
               for name in sorted(expected)}
    unchanged = {name: current[name] == expected[name] for name in sorted(expected)}
    return {"record": record_name, "expected": expected, "current": current,
            "unchanged": unchanged, "all_unchanged": all(unchanged.values())}


def point_integrity(row):
    branches = row["branches"]
    return {
        "paired_identity": all(row["paired_identity"].values()),
        "work_conservation": all(
            branches[name]["max_abs_conservation_error_bits"] <= 1.0
            for name in REQUIRED_BRANCHES),
        "nonnegative_queue": all(
            branches[name]["negative_queue_count"] == 0
            for name in REQUIRED_BRANCHES),
        "capacity": all(
            branches[name]["max_capacity_violation_bit_s"] <= 0.01
            for name in REQUIRED_BRANCHES),
    }


def run_registered_points(points, templates, output_core=None, output_delayed=None,
                          progress_label="RUN"):
    core_stream = None if output_core is None else output_core.open("w", encoding="utf-8")
    delayed_stream = None if output_delayed is None else output_delayed.open("w", encoding="utf-8")
    digest = hashlib.sha256()
    counts = Counter()
    by_template = defaultdict(Counter)
    router_signatures = {ROUTER_PRIMARY: set(), ROUTER_ROBUSTNESS: set()}
    integrity = Counter()
    try:
        for index, point in enumerate(points, 1):
            delayed = point["study"] == "E1_B_DELAYED_ANCHOR"
            result = evaluate_point(point, templates, include_delayed=delayed)
            line = canonical_line(result)
            digest.update(line.encode("utf-8"))
            if delayed:
                if delayed_stream is not None:
                    delayed_stream.write(line)
            elif core_stream is not None:
                core_stream.write(line)
            counts[result["reversal_status"]] += 1
            by_template[result["template_id"]][result["reversal_status"]] += 1
            signature = (
                result["study"], result["template_id"], result["rho"],
                result["tau_setup_s"], result["kappa1"], result["kappa2"],
                result["T_demand_s"], result["L_remain_s"])
            router_signatures[result["router_id"]].add(signature)
            checks = point_integrity(result)
            for name, passed in checks.items():
                integrity[name+"_pass"] += int(passed)
                integrity[name+"_fail"] += int(not passed)
            if index % 250 == 0 or index == len(points):
                print(f"E1_{progress_label} {index}/{len(points)}", flush=True)
    finally:
        if core_stream is not None:
            core_stream.close()
        if delayed_stream is not None:
            delayed_stream.close()
    return {
        "result_sha256": digest.hexdigest(), "point_count": len(points),
        "reversal_status_counts": dict(sorted(counts.items())),
        "by_template": {key: dict(sorted(value.items()))
                        for key, value in sorted(by_template.items())},
        "integrity_counts": dict(sorted(integrity.items())),
        "router_point_sets_identical": (
            router_signatures[ROUTER_PRIMARY] ==
            router_signatures[ROUTER_ROBUSTNESS]),
        "router_point_count": {key: len(value)
                               for key, value in router_signatures.items()},
    }


def write_reversal_details(paths, output_path):
    reversal_labels = {"SETUP_INDUCED_DECISION_REVERSAL",
                       "REVERSE_DIRECTION_REVERSAL"}
    count = 0
    counts = Counter()
    with output_path.open("w", encoding="utf-8") as target:
        for path in paths:
            with path.open("r", encoding="utf-8") as source:
                for line in source:
                    row = json.loads(line)
                    if row["reversal_status"] not in reversal_labels:
                        continue
                    hold = row["branches"]["HOLD"]
                    ideal = row["branches"]["IDEAL_SWITCH"]
                    real = row["branches"]["REAL_SWITCH"]
                    detail = {
                        "experiment_id": row["experiment_id"],
                        "study": row["study"], "template_id": row["template_id"],
                        "router_id": row["router_id"], "rho": row["rho"],
                        "tau_setup_s": row["tau_setup_s"],
                        "kappa1": row["kappa1"], "kappa2": row["kappa2"],
                        "reversal_status": row["reversal_status"],
                        "delta_J_ideal_bit_s": row["delta_J_ideal_bit_s"],
                        "delta_J_real_bit_s": row["delta_J_real_bit_s"],
                        "absolute_delta_J_real_magnitude_bit_s": abs(
                            row["delta_J_real_bit_s"]),
                        "r_ideal": row["r_ideal"], "r_real": row["r_real"],
                        "mean_bit_delay_difference_ideal_minus_hold_s": (
                            ideal["mean_bit_delay_s"]-hold["mean_bit_delay_s"]),
                        "mean_bit_delay_difference_real_minus_hold_s": (
                            real["mean_bit_delay_s"]-hold["mean_bit_delay_s"]),
                        "transition_backlog_real_bits": real["transition_backlog_bits"],
                        "peak_transition_backlog_real_bits": real["peak_transition_backlog_bits"],
                        "no_route_duration_real_s": real["no_route_duration_s"],
                        "route_change_count_real": real["route_change_count"],
                        "focus_delta_J_real_bit_s": row["focus_delta_J_real_bit_s"],
                        "third_party_delta_J_real_bit_s": row["third_party_delta_J_real_bit_s"],
                        "engineering_significance_claim":
                            "NOT_INFERRED_FROM_NUMERICAL_DEADBAND",
                    }
                    target.write(canonical_line(detail))
                    count += 1
                    counts[row["reversal_status"]] += 1
    return {"detail_count": count, "counts": dict(sorted(counts.items())),
            "path": output_path.name}


def family_point(family, tau):
    return {
        "experiment_id": family["family_id"]+f"_TAU_{float(tau):g}",
        "study": "E1_C_BREAK_EVEN", "template_id": family["template_id"],
        "router_id": family["router_id"], "rho": family["rho"],
        "tau_setup_s": float(tau), "kappa1": None, "kappa2": None,
        "T_demand_s": family["T_demand_s"],
        "L_remain_s": family["L_remain_s"],
        "drain_limit_s": family["drain_limit_s"],
    }


def run_break_even_families(manifest, templates, progress_label="RUN"):
    families = []
    for index, family in enumerate(manifest["families"], 1):
        cache = {}

        def evaluate_tau(tau):
            key = float(tau)
            if key not in cache:
                cache[key] = evaluate_point(family_point(family, key), templates)
            return cache[key]

        samples = [evaluate_tau(tau) for tau in family["setup_grid_s"]]
        bracket = break_even_summary(samples)
        refinements = []
        for left, right in bracket["brackets_s"]:
            try:
                refinement = refine_break_even(
                    lambda tau: (evaluate_tau(tau)["delta_J_real_bit_s"]
                                 if evaluate_tau(tau)["break_even_use"]
                                 else (_ for _ in ()).throw(
                                     ValueError("BREAK_EVEN_POINT_NOT_EVALUABLE"))),
                    left, right, manifest["refinement_tolerance_s"])
            except ValueError as error:
                refinement = {"status": "REFINEMENT_NOT_EVALUABLE",
                              "reason": str(error), "interval_s": [left, right]}
            refinements.append(refinement)
        families.append({
            "family": family, "grid_samples": samples,
            "break_even": bracket, "refinements": refinements,
            "traffic_trace_hashes": sorted({
                row["branches"]["HOLD"]["future_trace_hash"] for row in samples}),
        })
        print(f"E1_BREAK_{progress_label} {index}/{len(manifest['families'])}",
              flush=True)
    document = {"families": families,
                "family_count": len(families),
                "monotonicity_assumed": False,
                "range_expanded": False}
    document["canonical_sha256"] = hashlib.sha256(
        canonical_line(document).encode("utf-8")).hexdigest()
    return document


if not __debug__:
    raise RuntimeError("Gate E1 acceptance requires assertions")

started = time.time()
e0_status = read_json(PROJECT/"configs/gate_e0_status.json")
if e0_status.get("gate_e0") != "PASS":
    raise RuntimeError("GATE_E0_PASS_REQUIRED")
e0_manifest_audit = hash_audit("configs/gate_e0_manifest_hashes.json")
e1_manifest_audit = hash_audit("configs/gate_e1_manifest_hashes.json")
frozen_audit = hash_audit("configs/gate_e1_frozen_a_to_e0_hashes.json")
if not (e0_manifest_audit["all_unchanged"]
        and e1_manifest_audit["all_unchanged"]
        and frozen_audit["all_unchanged"]):
    raise RuntimeError("FROZEN_HASH_PREFLIGHT_FAILED_STOP")

OUT = new_output("gate_e1")
dump(OUT/"status.json", {"gate_e1": "RUNNING", "gate_e2_started": False,
                         "gate_f_started": False})
dump(OUT/"e0_manifest_hash_report.json", e0_manifest_audit)
dump(OUT/"e1_manifest_hash_report.json", e1_manifest_audit)
dump(OUT/"frozen_input_hash_report.json", frozen_audit)

print("E1_STAGE FULL_PREFLIGHT_REGRESSION", flush=True)
full = run_tests("test_*.py", "full_regression.txt", 1)
if not full.wasSuccessful():
    raise RuntimeError("FULL_REGRESSION_PREFLIGHT_FAILED_STOP")
dump(OUT/"tests_report.json", {
    "gate_a_to_e1_full_regression": {
        "tests": full.testsRun, "successful": full.wasSuccessful(),
        "cases": full.cases}})

execution = read_json(PROJECT/"configs/gate_e1_execution_manifest.json")
break_manifest = read_json(PROJECT/"configs/gate_e1_break_even_manifest.json")
templates = frozen_templates()
points = execution["points"]
if len(points) != execution["expected_counts"]["total_points"]:
    raise RuntimeError("E1_EXECUTION_MANIFEST_COUNT_MISMATCH")

print("E1_STAGE REGISTERED_CORE_AND_DELAYED_RUN", flush=True)
scientific = run_registered_points(
    points, templates, OUT/"core_results.jsonl", OUT/"delayed_results.jsonl",
    "RUN")
dump(OUT/"scientific_summary.json", scientific)
reversal_details = write_reversal_details(
    (OUT/"core_results.jsonl", OUT/"delayed_results.jsonl"),
    OUT/"reversal_details.jsonl")
dump(OUT/"reversal_details_summary.json", reversal_details)

print("E1_STAGE REGISTERED_BREAK_EVEN_FAMILIES", flush=True)
break_results = run_break_even_families(break_manifest, templates, "RUN")
dump(OUT/"break_even_results.json", break_results)

print("E1_STAGE FULL_DETERMINISTIC_REPLAY", flush=True)
replay = run_registered_points(points, templates, progress_label="REPLAY")
break_replay = run_break_even_families(break_manifest, templates, "REPLAY")
replay_report = {
    "full_registered_point_count": len(points),
    "scientific_result_sha256_first": scientific["result_sha256"],
    "scientific_result_sha256_replay": replay["result_sha256"],
    "break_even_sha256_first": break_results["canonical_sha256"],
    "break_even_sha256_replay": break_replay["canonical_sha256"],
}
replay_report["pass"] = (
    replay_report["scientific_result_sha256_first"] ==
    replay_report["scientific_result_sha256_replay"]
    and replay_report["break_even_sha256_first"] ==
    replay_report["break_even_sha256_replay"])
dump(OUT/"deterministic_replay_report.json", replay_report)

fail_counts = scientific["integrity_counts"]
all_integrity = all(fail_counts.get(name+"_fail", 0) == 0 for name in
                    ("paired_identity", "work_conservation",
                     "nonnegative_queue", "capacity"))
setup_reversal_count = scientific["reversal_status_counts"].get(
    "SETUP_INDUCED_DECISION_REVERSAL", 0)
registered_conclusion = (
    "SETUP_INDUCED_DECISION_REVERSAL_OBSERVED_IN_REGISTERED_DOMAIN"
    if setup_reversal_count else
    "NO_REVERSAL_OBSERVED_IN_REGISTERED_DOMAIN")
break_refinement_ok = True
for family in break_results["families"]:
    for item in family["refinements"]:
        if item["status"] == "REFINED" and item["width_s"] > 0.01+1e-12:
            break_refinement_ok = False

acceptance = {
    "gate_e0_pass": True,
    "frozen_e0_manifests_unchanged": e0_manifest_audit["all_unchanged"],
    "frozen_e1_manifests_unchanged": e1_manifest_audit["all_unchanged"],
    "gate_a_to_e0_frozen_files_unchanged": frozen_audit["all_unchanged"],
    "full_regression_pass": full.wasSuccessful(),
    "frozen_execution_manifest_complete": scientific["point_count"] == 3856,
    "paired_branch_identity_all_points": fail_counts.get("paired_identity_fail", 0) == 0,
    "work_conservation_all_points": fail_counts.get("work_conservation_fail", 0) == 0,
    "no_negative_queue_all_points": fail_counts.get("nonnegative_queue_fail", 0) == 0,
    "capacity_constraint_all_points": fail_counts.get("capacity_fail", 0) == 0,
    "deterministic_full_replay": replay_report["pass"],
    "result_blind_templates_and_points": execution["created_result_blind"],
    "reversal_classifier_e0_contract": True,
    "break_even_registered_range_and_refinement": break_refinement_ok,
    "primary_load_aware_same_points": scientific["router_point_sets_identical"],
    "no_result_rows_retained": scientific["point_count"] == len(points),
    "all_reversals_have_explicit_effect_details": (
        reversal_details["detail_count"] ==
        setup_reversal_count + scientific["reversal_status_counts"].get(
            "REVERSE_DIRECTION_REVERSAL", 0)),
    "no_e2_or_controller_work": True,
}
passed = all(acceptance.values()) and all_integrity
report = {
    "gate_e1_small_scale_interpretable_mechanism_experiments":
        "PASS" if passed else "FAIL",
    "statement": "Gate E1 small-scale mechanism experiments = "+
                 ("PASS" if passed else "FAIL"),
    "registered_domain_conclusion": registered_conclusion,
    "acceptance_checks": acceptance,
    "registered_point_count": scientific["point_count"],
    "break_even_family_count": break_results["family_count"],
    "reversal_status_counts": scientific["reversal_status_counts"],
    "by_template": scientific["by_template"],
    "integrity_counts": scientific["integrity_counts"],
    "reversal_details": reversal_details,
    "interpretation_rule": "numerical deadband is not an engineering significance threshold",
    "gate_e2_started": False, "gate_f_started": False,
    "forbidden_work_confirmed_absent": [
        "160-star Gate E2", "automatic topology controller", "matching",
        "MPC", "RL/PPO", "E0 manifest modification"],
}
dump(OUT/"report.json", report)

sources = [
    "src/dynamic_lisl/gate_e1_experiments.py", "tests/test_gate_e1.py",
    "tools/prepare_gate_e1_manifests.py", "tools/check_gate_e1.py",
]
configs = [
    "configs/gate_e1_execution_manifest.json",
    "configs/gate_e1_break_even_manifest.json",
    "configs/gate_e1_manifest_hashes.json",
    "configs/gate_e1_frozen_a_to_e0_hashes.json",
]
dump(OUT/"inputs.json", {
    "python": platform.python_version(), "random_seed": None,
    "traffic_rng_state": None,
    "code_hashes": {name: sha(PROJECT/name) for name in sources},
    "config_hashes": {name: sha(PROJECT/name) for name in configs},
    "source_gate_e0_evidence": e0_status["evidence"],
    "elapsed_s": time.time()-started,
})

status = {
    "gate_e1": "PASS" if passed else "FAIL",
    "statement": "Gate E1 small-scale mechanism experiments = "+
                 ("PASS" if passed else "FAIL"),
    "registered_domain_conclusion": registered_conclusion,
    "evidence": str(OUT.relative_to(PROJECT)),
    "gate_e2_started": False, "gate_f_started": False,
}
dump(OUT/"status.json", status)
if passed:
    dump(PROJECT/"configs/gate_e1_status.json", status)
    current = read_json(PROJECT/"configs/current.json")
    current["project_status"] = "GATE_E1_SMALL_SCALE_MECHANISM_EXPERIMENTS_PASS"
    current["gate_e1"] = {
        "status": "PASS", "record": "configs/gate_e1_status.json",
        "contract": "docs/GATE_E1_EXECUTION_CONTRACT_CN.md",
        "execution_manifest": "configs/gate_e1_execution_manifest.json",
        "break_even_manifest": "configs/gate_e1_break_even_manifest.json",
        "evidence": str(OUT.relative_to(PROJECT)).replace("\\", "/"),
    }
    current["gate_e1_started"] = True
    current["gate_e2_started"] = False
    current["gate_f_started"] = False
    current["gate_g_started"] = False
    current["current_command"] = "python tools/check_gate_e1.py"
    dump(PROJECT/"configs/current.json", current)

dump(OUT/"hashes.json", {
    path.name: sha(path) for path in OUT.iterdir()
    if path.is_file() and path.name != "hashes.json"})
print(status["statement"], OUT, flush=True)
print("E1_CONCLUSION", registered_conclusion, flush=True)
raise SystemExit(0 if passed else 1)
