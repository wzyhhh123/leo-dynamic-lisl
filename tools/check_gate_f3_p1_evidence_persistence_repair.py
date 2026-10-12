"""Gate F3-1a evidence-persistence repair acceptance checker."""
from __future__ import annotations

from copy import deepcopy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT/"src"))

from tests.test_gate_f3_p1_evidence_persistence import (  # noqa: E402
    HISTORICAL, SCIENTIFIC, fixture,
)
from tools.run_gate_f3_p1_execution import (  # noqa: E402
    P1InvariantFailure, artifact_hashes, canonical_hash, dump,
    persist_run_evidence,
)


PYTHON = Path(sys.executable)
F3_SHA = "118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6"
EXECUTION_SHA = "0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a"
OVERLAY_SHA = "ba527d3bc2c4ebca742ec21b8c390d512931d56d9c9ba68ed4eb22a7f47a7f39"


def read(relative):
    return json.loads((PROJECT/relative).read_text(encoding="utf-8-sig"))


def digest(relative):
    return hashlib.sha256((PROJECT/relative).read_bytes()).hexdigest()


def verify_canonical(relative, expected):
    document = read(relative)
    observed = document.pop("canonical_sha256")
    return observed == expected == canonical_hash(document)


def run_regression(output):
    command = [str(PYTHON), "-m", "unittest", "discover", "-s", "tests", "-v"]
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(PROJECT/"src")+(
        os.pathsep+existing if existing else "")
    process = subprocess.run(command, cwd=PROJECT, capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             env=environment)
    content = ("COMMAND: "+" ".join(command)+"\n\nSTDOUT:\n"
               +process.stdout+"\nSTDERR:\n"+process.stderr
               +f"\nEXIT_CODE: {process.returncode}\n")
    output.write_text(content, encoding="utf-8")
    return process.returncode == 0, process.returncode


def main():
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = PROJECT/"outputs"/f"gate_f3_p1_evidence_persistence_repair_{timestamp}"
    out.mkdir(parents=True, exist_ok=False)

    frozen_before = {name: digest(name) for name in HISTORICAL}
    scientific_before = {name: digest(name) for name in SCIENTIFIC}

    # Persist a deliberate two-check failure using a nonregistered unit fixture.
    row, run, final, invariant = fixture()
    invariant = deepcopy(invariant)
    invariant["invariants"]["work_conservation"]["pass"] = False
    invariant["invariants"]["work_conservation"]["observed_value"] = 1.25
    invariant["invariants"]["capacity"]["pass"] = False
    invariant["invariants"]["capacity"]["observed_value"] = 0.02
    fixture_dir = out/"fixture_failure_evidence"
    fixture_dir.mkdir()
    caught = None
    try:
        persist_run_evidence(fixture_dir, row, run, final, invariant, True)
    except P1InvariantFailure as exc:
        caught = str(exc)

    regression_pass, regression_exit = run_regression(out/"regression_report.txt")
    frozen_after = {name: digest(name) for name in HISTORICAL}
    scientific_after = {name: digest(name) for name in SCIENTIFIC}
    failure = read(str((fixture_dir/"failure_summary.json").relative_to(PROJECT)))
    detailed = read(str((fixture_dir/"invariant_report.json").relative_to(PROJECT)))
    manifest = read("configs/gate_f3_execution_manifest_v1.json")
    registered_ids = {item["run_id"] for item in manifest["runs"]
                      if item["block_id"] == "P1"}
    repair_text = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                            for path in out.rglob("*") if path.is_file())
    prior_attempt_roots = list((PROJECT/"outputs").glob("gate_f3_p1_execution_*"))

    checks = {
        "F3_canonical_unchanged": verify_canonical(
            "configs/gate_f3_experiment_human_freeze_v1.json", F3_SHA),
        "execution_manifest_canonical_unchanged": verify_canonical(
            "configs/gate_f3_execution_manifest_v1.json", EXECUTION_SHA),
        "F3_0_1_overlay_canonical_unchanged": verify_canonical(
            "configs/gate_f3_candidate_source_drain_human_freeze_v1.json",
            OVERLAY_SHA),
        "historical_failed_attempts_unchanged":
            frozen_before == frozen_after == HISTORICAL,
        "scientific_code_hashes_unchanged":
            scientific_before == scientific_after == SCIENTIFIC,
        "forced_failure_report_persisted":
            (fixture_dir/"invariant_report.json").is_file(),
        "forced_failure_summary_persisted":
            (fixture_dir/"failure_summary.json").is_file(),
        "all_forced_failures_preserved": failure["failed_invariant_names"]
            == ["work_conservation", "capacity"],
        "specific_aggregate_error": caught is not None
            and "failed_checks=work_conservation,capacity" in caught,
        "aggregate_after_initial_persistence":
            detailed["aggregate_evaluated_after_initial_evidence_persistence"] is True,
        "raw_value_and_tolerance_preserved":
            detailed["invariants"]["work_conservation"]["observed_value"] == 1.25
            and detailed["invariants"]["work_conservation"]["tolerance"]
                == 0.0010000001
            and detailed["invariants"]["capacity"]["observed_value"] == 0.02
            and detailed["invariants"]["capacity"]["tolerance"] == 0.01,
        "final_state_evidence_persisted":
            (fixture_dir/"final_state_evidence.json").is_file(),
        "artifact_hashes_persisted":
            (fixture_dir/"artifact_hashes.json").is_file(),
        "no_registered_P1_id_used": not any(key in repair_text
                                             for key in registered_ids),
        "historical_attempt_count_unchanged": len(prior_attempt_roots) == 1,
        "historical_failed_count_still_one":
            read("configs/gate_f3_p1_execution_status.json")["P1_FAILED_count"] == 1,
        "no_P2_or_RL_started":
            not read("configs/gate_f3_p1_execution_status.json")["P2_started"]
            and not read("configs/gate_f3_p1_execution_status.json")["RL_started"],
        "full_regression_pass": regression_pass,
    }

    dump(out/"frozen_hash_report.json", {
        "schema": "gate_f3_p1_evidence_repair_frozen_hash_report_v1",
        "before": frozen_before, "after": frozen_after,
        "unchanged": frozen_before == frozen_after,
        "canonical": {"F3": F3_SHA, "execution": EXECUTION_SHA,
                      "overlay": OVERLAY_SHA},
    })
    dump(out/"scientific_code_hash_report.json", {
        "schema": "gate_f3_p1_evidence_repair_scientific_hash_report_v1",
        "before": scientific_before, "after": scientific_after,
        "unchanged": scientific_before == scientific_after,
    })
    report = {
        "schema": "gate_f3_p1_evidence_persistence_repair_report_v1",
        "checks": checks, "pass": all(checks.values()),
        "failure_evidence_write_ordering": "PASS" if all((
            checks["forced_failure_report_persisted"],
            checks["forced_failure_summary_persisted"],
            checks["aggregate_after_initial_persistence"])) else "FAIL",
        "individual_invariant_persistence": "PASS" if checks[
            "all_forced_failures_preserved"] else "FAIL",
        "aggregate_assertion_after_evidence_persistence": "PASS" if checks[
            "aggregate_after_initial_persistence"] else "FAIL",
        "frozen_scientific_semantics_unchanged": scientific_before == scientific_after,
        "frozen_tolerances_unchanged": checks["raw_value_and_tolerance_preserved"],
        "historical_failed_P1_attempt_preserved": frozen_before == frozen_after,
        "new_P1_execution_attempt_readiness": (
            "READY" if all(checks.values()) else "NOT_READY"),
        "registered_P1_runs_executed_in_repair": 0,
        "regression_exit_code": regression_exit,
        "P2_started": False, "RL_started": False,
    }
    dump(out/"report.json", report)
    dump(out/"artifact_hashes.json", {
        "schema": "gate_f3_p1_evidence_repair_artifact_hashes_v1",
        "files": artifact_hashes(out, exclude={"artifact_hashes.json"}),
    })
    if not report["pass"]:
        print(json.dumps({key: value for key, value in checks.items() if not value},
                         indent=2))
        raise SystemExit("GATE_F3_P1_EVIDENCE_PERSISTENCE_REPAIR_FAIL")
    print("Gate F3 P1 Evidence Persistence Repair = PASS")
    print("failure-evidence write ordering = PASS")
    print("individual invariant persistence = PASS")
    print("aggregate assertion occurs after evidence persistence = PASS")
    print("frozen scientific semantics unchanged = YES")
    print("frozen tolerances unchanged = YES")
    print("historical failed P1 attempt preserved = YES")
    print("new P1 execution attempt readiness = READY")
    print("registered P1 runs executed in this repair task = 0")
    print("P2 started = false")
    print("RL started = false")
    print(str(out.relative_to(PROJECT)).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
