"""Formal Pre-E2 absolute-time/delayed-action regression and hard stop gate."""
from __future__ import annotations

import io
import platform
import sys
import time
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "tests"))

from dynamic_lisl.absolute_time_regression import (
    SHIFTS_S, run_out_of_window_negative, run_translated_replay,
    stale_horizon_negative_control,
)
from dynamic_lisl.common import dump, new_output, read_json, sha


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


def hash_audit(record_name):
    expected = read_json(PROJECT / record_name)["files"]
    current = {name: sha(PROJECT / name) if (PROJECT / name).is_file() else None
               for name in sorted(expected)}
    unchanged = {name: current[name] == expected[name] for name in sorted(expected)}
    return {"record": record_name, "expected": expected, "current": current,
            "unchanged": unchanged, "all_unchanged": all(unchanged.values())}


def run_tests(pattern, output_name, verbosity=1):
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT / "tests"), pattern=pattern)
    stream = io.StringIO()
    result = unittest.TextTestRunner(
        stream=stream, verbosity=verbosity, resultclass=MachineResult).run(suite)
    text = stream.getvalue()
    (OUT / output_name).write_text(text, encoding="utf-8")
    print(text, end="", flush=True)
    return result


def compact_replay(row):
    relative = row["relative"]
    return {
        "shift_s": row["shift_s"], "contract": row["contract"],
        "raw_traffic_trace_hash": row["raw_traffic_trace_hash"],
        "relative_traffic_trace_hash": row["relative_traffic_trace_hash"],
        "relative_time_canonical_hash": row["relative_time_canonical_hash"],
        "relative_quantities": {key: relative[key] for key in (
            "action_offset_s", "ready_offset_from_action_s",
            "L_remain_s", "L_usable_s", "window_relative_s")},
        "gate_c": relative["gate_c"],
        "transition_mode": relative["transition_mode"],
        "reversal": relative["reversal"],
        "branch_metrics": {name: branch["metrics"]
                           for name, branch in relative["branches"].items()},
    }


def main():
    global OUT
    if not __debug__:
        raise RuntimeError("Pre-E2 acceptance requires assertions")
    started = time.time()
    e1_status = read_json(PROJECT / "configs/gate_e1_status.json")
    if e1_status.get("gate_e1") != "PASS":
        raise RuntimeError("GATE_E1_PASS_REQUIRED_STOP")
    OUT = new_output("pre_e2_absolute_time")
    dump(OUT / "status.json", {
        "pre_e2_absolute_time_regression": "RUNNING",
        "gate_e2_started": False, "gate_f_started": False})
    audits = {
        "e0_manifests": hash_audit("configs/gate_e0_manifest_hashes.json"),
        "e1_manifests": hash_audit("configs/gate_e1_manifest_hashes.json"),
        "a_to_e1_evidence": hash_audit(
            "configs/pre_e2_frozen_a_to_e1_hashes.json"),
    }
    dump(OUT / "frozen_input_hash_report.json", audits)
    if not all(row["all_unchanged"] for row in audits.values()):
        raise RuntimeError("PRE_E2_FROZEN_HASH_PREFLIGHT_FAILED_STOP")

    print("PRE_E2_STAGE SPECIALIZED_REGRESSION", flush=True)
    specialized = run_tests("test_pre_e2_absolute_time.py",
                            "specialized_regression.txt", 2)
    print("PRE_E2_STAGE TRANSLATED_FULL_STACK_REPLAY", flush=True)
    replays = [run_translated_replay(shift) for shift in SHIFTS_S]
    repeat = [run_translated_replay(shift) for shift in SHIFTS_S]
    stale = stale_horizon_negative_control(100.0)
    out_of_window = [run_out_of_window_negative(shift) for shift in SHIFTS_S]
    relative_hashes = [row["relative_time_canonical_hash"] for row in replays]
    relative_traffic_hashes = [row["relative_traffic_trace_hash"]
                               for row in replays]
    raw_traffic_hashes = [row["raw_traffic_trace_hash"] for row in replays]
    deterministic = {
        "first_relative_hashes": relative_hashes,
        "replay_relative_hashes": [row["relative_time_canonical_hash"]
                                   for row in repeat],
        "pass": all(first["relative"] == second["relative"]
                    for first, second in zip(replays, repeat)),
    }
    dump(OUT / "translated_replays.json", {
        "replays": [compact_replay(row) for row in replays],
        "stale_horizon_negative_control": stale,
        "out_of_window_negative_controls": out_of_window})
    dump(OUT / "deterministic_replay_report.json", deterministic)
    dump(OUT / "relative_hash_report.json", {
        "relative_time_canonical_hashes": relative_hashes,
        "relative_traffic_trace_hashes": relative_traffic_hashes,
        "raw_traffic_trace_hashes": raw_traffic_hashes,
        "relative_time_all_equal": len(set(relative_hashes)) == 1,
        "relative_traffic_all_equal": len(set(relative_traffic_hashes)) == 1,
        "raw_traffic_all_distinct": len(set(raw_traffic_hashes)) == len(SHIFTS_S),
    })

    print("PRE_E2_STAGE FULL_GATE_A_TO_E1_REGRESSION", flush=True)
    full = run_tests("test_*.py", "full_regression.txt", 1)
    post_audits = {name: hash_audit(row["record"])
                   for name, row in audits.items()}
    dump(OUT / "post_run_frozen_input_hash_report.json", post_audits)
    e1_report = read_json(PROJECT / e1_status["evidence"] / "report.json")
    reference = replays[0]["relative"]
    branch_invariants = []
    for row in replays:
        for name, branch in row["relative"]["branches"].items():
            metrics = branch["metrics"]
            branch_invariants.append({
                "shift_s": row["shift_s"], "branch": name,
                "work_conservation": metrics.get(
                    "max_abs_conservation_error_bits", 0.0) <= 1.0,
                "nonnegative_queue": metrics.get("negative_queue_count", 0) == 0,
                "capacity": metrics.get(
                    "max_capacity_violation_bit_s", 0.0) <= 0.01,
            })
    acceptance = build_acceptance(
        replays, reference, relative_hashes, relative_traffic_hashes,
        raw_traffic_hashes, stale, out_of_window, deterministic,
        specialized, full, audits, post_audits, e1_report, branch_invariants)
    passed = all(acceptance.values())
    write_results(started, e1_status, replays, acceptance, branch_invariants,
                  relative_hashes, relative_traffic_hashes, specialized, full,
                  passed)
    return 0 if passed else 1


def build_acceptance(replays, reference, relative_hashes,
                     relative_traffic_hashes, raw_traffic_hashes, stale,
                     out_of_window, deterministic, specialized, full, audits,
                     post_audits, e1_report, branch_invariants):
    return {
        "gate_e1_formal_pass": e1_report.get(
            "gate_e1_small_scale_interpretable_mechanism_experiments") == "PASS",
        "specialized_regression_pass": specialized.wasSuccessful(),
        "full_gate_a_to_e1_regression_pass": full.wasSuccessful(),
        "relative_gate_c_result_identical": all(
            row["relative"]["gate_c"] == reference["gate_c"] for row in replays),
        "delayed_execution_legality_identical": all(
            row["relative"]["transition_mode"] == reference["transition_mode"]
            for row in replays),
        "relative_L_remain_and_L_usable_identical": all(
            (row["relative"]["L_remain_s"], row["relative"]["L_usable_s"])
            == (reference["L_remain_s"], reference["L_usable_s"])
            for row in replays),
        "normalized_event_and_network_trajectory_identical":
            len(set(relative_hashes)) == 1,
        "relative_traffic_trace_identical":
            len(set(relative_traffic_hashes)) == 1,
        "absolute_traffic_trace_actually_translated":
            len(set(raw_traffic_hashes)) == len(SHIFTS_S),
        "J_delay_reversal_censor_identical": all(
            row["relative"]["reversal"] == reference["reversal"] and
            {name: (branch["J_bit_s"], branch["metrics"]["mean_bit_delay_s"],
                    branch["metrics"]["censored"])
             for name, branch in row["relative"]["branches"].items()}
            == {name: (branch["J_bit_s"], branch["metrics"]["mean_bit_delay_s"],
                       branch["metrics"]["censored"])
                for name, branch in reference["branches"].items()}
            for row in replays),
        "work_conservation_all_branches": all(
            row["work_conservation"] for row in branch_invariants),
        "no_negative_queue_all_branches": all(
            row["nonnegative_queue"] for row in branch_invariants),
        "capacity_constraint_all_branches": all(
            row["capacity"] for row in branch_invariants),
        "stale_profiler_negative_control_caught": stale == {
            "caught": True,
            "error": "ABSOLUTE_TIME_FRAME_MISMATCH_STALE_PROFILER_HORIZON"},
        "execution_time_infeasibility_no_replacement": all(
            row["status"] == "INFEASIBLE_AT_EXECUTION_TIME"
            and not row["replacement_candidate_used"] for row in out_of_window),
        "deterministic_repeated_replay": deterministic["pass"],
        "frozen_inputs_unchanged_before_and_after": (
            all(row["all_unchanged"] for row in audits.values())
            and all(row["all_unchanged"] for row in post_audits.values())),
    }


def write_results(started, e1_status, replays, acceptance, branch_invariants,
                  relative_hashes, relative_traffic_hashes, specialized, full,
                  passed):
    formal = ("PRE_E2_ABSOLUTE_TIME_REGRESSION_PASS" if passed else
              "PRE_E2_ABSOLUTE_TIME_REGRESSION_FAIL")
    report = {
        "formal_status": formal, "stop_condition": not passed,
        "scope": "synthetic/parametric absolute-time coordinate consistency",
        "not_an_orbital_invariance_test": True,
        "shifts_s": list(SHIFTS_S), "acceptance_checks": acceptance,
        "branch_invariants": branch_invariants,
        "relative_time_canonical_hash": relative_hashes[0]
            if len(set(relative_hashes)) == 1 else None,
        "relative_traffic_trace_hash": relative_traffic_hashes[0]
            if len(set(relative_traffic_hashes)) == 1 else None,
        "gate_e2_started": False, "gate_f_started": False,
    }
    dump(OUT / "report.json", report)
    dump(OUT / "tests_report.json", {
        "specialized": {"tests": specialized.testsRun,
                        "successful": specialized.wasSuccessful(),
                        "cases": specialized.cases},
        "full": {"tests": full.testsRun, "successful": full.wasSuccessful(),
                 "cases": full.cases}})
    dump(OUT / "inputs.json", {
        "python": platform.python_version(), "elapsed_s": time.time() - started,
        "code_hashes": {name: sha(PROJECT / name) for name in (
            "src/dynamic_lisl/absolute_time_regression.py",
            "tests/test_pre_e2_absolute_time.py",
            "tools/check_pre_e2_absolute_time.py")},
        "frozen_baseline": "configs/pre_e2_frozen_a_to_e1_hashes.json",
        "source_gate_e1_evidence": e1_status["evidence"],
    })
    status = {
        "pre_e2_absolute_time_regression": "PASS" if passed else "FAIL",
        "formal_status": formal, "stop_condition": not passed,
        "evidence": str(OUT.relative_to(PROJECT)).replace("\\", "/"),
        "gate_e2_started": False, "gate_f_started": False,
    }
    dump(OUT / "status.json", status)
    dump(PROJECT / "configs/pre_e2_absolute_time_status.json", status)
    if passed:
        current = read_json(PROJECT / "configs/current.json")
        current["project_status"] = formal
        current["pre_e2_absolute_time_regression"] = {
            "status": "PASS",
            "record": "configs/pre_e2_absolute_time_status.json",
            "contract": "docs/PRE_E2_ABSOLUTE_TIME_REGRESSION_CN.md",
            "evidence": status["evidence"],
        }
        current["gate_e2_started"] = False
        current["gate_f_started"] = False
        current["current_command"] = "python tools/check_pre_e2_absolute_time.py"
        dump(PROJECT / "configs/current.json", current)
    dump(OUT / "hashes.json", {
        path.name: sha(path) for path in OUT.iterdir()
        if path.is_file() and path.name != "hashes.json"})
    print(formal, OUT, flush=True)
    if not passed:
        print("STOP CONDITION: Gate E2 must not start.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
