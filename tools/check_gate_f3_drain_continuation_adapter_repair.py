"""Acceptance checker for the F3-only drain continuation adapter repair."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

from dynamic_lisl.f3_drain_continuation import (  # noqa: E402
    F3_CENSORED,
    F3_COMPLETE,
    F3_CONTINUE_DRAIN,
    NO_PROGRESS_CODE,
    F3DrainContinuationAdapter,
    classify_f3_termination,
    unfinished_work_bits,
)
from dynamic_lisl.production_candidate_source import DrainDecisionPolicy  # noqa: E402
from tests.test_gate_f3_drain_continuation_adapter import (  # noqa: E402
    ScriptedEngine,
    real_d2_fixture,
)
from tests.test_gate_f3_p1_evidence_persistence import (  # noqa: E402
    HISTORICAL,
    SCIENTIFIC,
)


PYTHON = Path(sys.executable)
F3_SHA = "118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6"
EXECUTION_SHA = "0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a"
OVERLAY_SHA = "ba527d3bc2c4ebca742ec21b8c390d512931d56d9c9ba68ed4eb22a7f47a7f39"
D2_SHA = "5b674ee226ac07aba136fc7c207f6abe727a4d63ad9097c1291afa6217750fd4"
THIRD_ATTEMPT = {
    "configs/gate_f3_p1_execution_attempt_20260925T081402_status.json":
        "f859ec7669615af2c8692c9f3b5231e3a6e4e431f43b2deae7a02ff62d6b7451",
    "docs/GATE_F3_P1_EXECUTION_ATTEMPT_3_RESULT_CN.md":
        "1a727d23f417d3f0ba9b951af357b75633757484bf45fe0e482972b3617202a6",
    "outputs/gate_f3_p1_execution_20260925T081402_105672Z/artifact_hashes.json":
        "48be1a4d2e01399b208eee1185335f709202adf43adbd8fe21bd4d76c6ef04aa",
}
ATTEMPT_ROOTS = (
    "outputs/gate_f3_p1_20260925T050259_813979Z",
    "outputs/gate_f3_p1_execution_20260925T055958_725913Z",
    "outputs/gate_f3_p1_execution_20260925T081402_105672Z",
)


def dump(path: Path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def digest(relative: str) -> str:
    return hashlib.sha256((PROJECT / relative).read_bytes()).hexdigest()


def canonical_hash(document) -> str:
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_canonical(relative: str, expected: str) -> bool:
    document = json.loads((PROJECT / relative).read_text(encoding="utf-8-sig"))
    recorded = document.pop("canonical_sha256")
    return recorded == expected == canonical_hash(document)


def verify_artifact_manifest(root_relative: str):
    root = PROJECT / root_relative
    manifest = json.loads((root / "artifact_hashes.json").read_text(encoding="utf-8"))
    mismatches = []
    for recorded_name, expected in manifest["files"].items():
        candidate = PROJECT / recorded_name
        if not candidate.is_file():
            candidate = root / recorded_name
        observed = hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else None
        if observed != expected:
            mismatches.append({
                "file": recorded_name,
                "expected": expected,
                "observed": observed,
            })
    return not mismatches, mismatches


def run_suite(out: Path, name: str, args: list[str]):
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(PROJECT / "src") + (
        os.pathsep + existing if existing else ""
    )
    command = [str(PYTHON), "-m", "unittest", *args]
    process = subprocess.run(
        command,
        cwd=PROJECT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    text = (
        "COMMAND: " + " ".join(command) + "\n\nSTDOUT:\n" + process.stdout
        + "\nSTDERR:\n" + process.stderr
        + f"\nEXIT_CODE: {process.returncode}\n"
    )
    (out / name).write_text(text, encoding="utf-8")
    match = re.search(r"Ran (\d+) tests?", process.stdout + process.stderr)
    return {
        "pass": process.returncode == 0,
        "exit_code": process.returncode,
        "test_count": int(match.group(1)) if match else None,
        "evidence": name,
    }


def fixture_evidence():
    engine = real_d2_fixture()
    d2 = engine.run(10.0)
    before = {
        "time_s": engine.now,
        "unfinished_bits": unfinished_work_bits(engine),
        "D2_censored": d2["metrics"]["censored"],
        "F3_classification": classify_f3_termination(
            engine.now, unfinished_work_bits(engine)
        ),
        "pending_propagation_events": len(engine.propagation_agenda),
    }
    outcome = F3DrainContinuationAdapter().advance_to_boundary(engine, 10.0)
    after = {
        "time_s": engine.now,
        "unfinished_bits": unfinished_work_bits(engine),
        "F3_classification": outcome.status,
        "continuation_iterations": outcome.continuation_iterations,
        "max_abs_conservation_error_bits": engine.max_abs_conservation,
        "max_capacity_violation_bit_s": engine.max_capacity_violation,
        "negative_queue_count": sum(value < 0.0 for value in engine.queues.bits.values()),
    }

    no_progress_code = None
    try:
        F3DrainContinuationAdapter().advance_to_boundary(
            ScriptedEngine(250.0, 0.5), 252.0
        )
    except RuntimeError as exc:
        no_progress_code = str(exc)

    policy = DrainDecisionPolicy()
    epochs = policy.possible_epochs()
    return {
        "schema": "gate_f3_drain_continuation_fixture_evidence_v1",
        "fixture_scope": "synthetic_non_P1_two_node_production_D2_path",
        "D2_internal_return": before,
        "F3_after_real_continuation": after,
        "no_progress_error": no_progress_code,
        "drain_epochs": {
            "first_at_or_after_240_s": list(epochs[120:123]),
            "last": epochs[-1],
            "contains_600": 600.0 in epochs,
        },
        "checks": {
            "D2_returned_below_1_bit_but_above_F3_threshold":
                before["D2_censored"] is False
                and 0.01 < before["unfinished_bits"] <= 1.0,
            "F3_initially_CONTINUE_DRAIN":
                before["F3_classification"] == F3_CONTINUE_DRAIN,
            "real_time_advanced":
                after["time_s"] > before["time_s"],
            "event_reached_delivery":
                before["pending_propagation_events"] > 0
                and after["unfinished_bits"] <= 0.01,
            "F3_finally_COMPLETE":
                outcome.status == F3_COMPLETE,
            "conservation_capacity_queue_pass":
                engine.max_abs_conservation
                <= 1.0 + 1e-12 * max(1.0, sum(engine.arrived.values()))
                and engine.max_capacity_violation <= 0.01
                and after["negative_queue_count"] == 0,
            "no_progress_guard_explicit": no_progress_code == NO_PROGRESS_CODE,
            "drain_epochs_240_242_through_598":
                epochs[120] == 240.0 and epochs[121] == 242.0
                and epochs[-1] == 598.0 and 600.0 not in epochs,
            "classification_edges":
                classify_f3_termination(250.0, 0.005) == F3_COMPLETE
                and classify_f3_termination(250.0, 0.5) == F3_CONTINUE_DRAIN
                and classify_f3_termination(600.0, 0.5) == F3_CENSORED,
        },
    }


def output_contains_registered_run_id(out: Path) -> bool:
    manifest = json.loads(
        (PROJECT / "configs/gate_f3_execution_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    registered = {
        row["run_id"] for row in manifest["runs"] if row["block_id"] == "P1"
    }
    for path in out.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(run_id in text for run_id in registered):
                return True
    return False


def main():
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = PROJECT / "outputs" / f"gate_f3_drain_continuation_adapter_repair_{timestamp}"
    out.mkdir(parents=True, exist_ok=False)

    immutable = {**HISTORICAL, **THIRD_ATTEMPT}
    immutable_before = {name: digest(name) for name in immutable}
    scientific_before = {name: digest(name) for name in SCIENTIFIC}
    execution_roots_before = sorted(
        path.name for path in (PROJECT / "outputs").glob("gate_f3_p1_execution_*")
        if path.is_dir()
    )

    fixture = fixture_evidence()
    dump(out / "fixture_evidence.json", fixture)
    focused = run_suite(
        out,
        "focused_test_report.txt",
        ["-v", "tests.test_gate_f3_drain_continuation_adapter"],
    )
    regression = run_suite(
        out,
        "regression_report.txt",
        ["discover", "-s", "tests", "-v"],
    )

    immutable_after = {name: digest(name) for name in immutable}
    scientific_after = {name: digest(name) for name in SCIENTIFIC}
    execution_roots_after = sorted(
        path.name for path in (PROJECT / "outputs").glob("gate_f3_p1_execution_*")
        if path.is_dir()
    )
    attempt_manifests = {}
    for root in ATTEMPT_ROOTS:
        valid, mismatches = verify_artifact_manifest(root)
        attempt_manifests[root] = {
            "pass": valid,
            "mismatches": mismatches,
        }

    traffic_contract = json.loads(
        (PROJECT / "configs/gate_d0_traffic_contract.json").read_text(
            encoding="utf-8"
        )
    )
    latest_attempt = json.loads(
        (PROJECT / "configs/gate_f3_p1_execution_attempt_20260925T081402_status.json")
        .read_text(encoding="utf-8")
    )

    checks = {
        "F3_0_canonical_unchanged": verify_canonical(
            "configs/gate_f3_experiment_human_freeze_v1.json", F3_SHA
        ),
        "F3_execution_manifest_canonical_unchanged": verify_canonical(
            "configs/gate_f3_execution_manifest_v1.json", EXECUTION_SHA
        ),
        "F3_0_1_overlay_canonical_unchanged": verify_canonical(
            "configs/gate_f3_candidate_source_drain_human_freeze_v1.json",
            OVERLAY_SHA,
        ),
        "D2_implementation_hash_unchanged":
            digest("src/dynamic_lisl/transition_service_orchestrator.py") == D2_SHA,
        "D2_state_tolerance_unchanged":
            traffic_contract["state_tolerance_bits"] == 0.01,
        "D2_conservation_tolerance_unchanged":
            traffic_contract["conservation_abs_tolerance_bits"] == 1.0,
        "D2_internal_threshold_is_1_bit":
            max(
                traffic_contract["state_tolerance_bits"],
                traffic_contract["conservation_abs_tolerance_bits"],
            ) == 1.0,
        "F3_complete_threshold_is_0_01_bit":
            F3DrainContinuationAdapter.complete_threshold_bits == 0.01,
        "F3_censor_limit_is_600_s":
            F3DrainContinuationAdapter.censor_limit_s == 600.0,
        "fixture_all_checks_pass": all(fixture["checks"].values()),
        "focused_tests_pass": focused["pass"] and focused["test_count"] == 10,
        "full_regression_pass": regression["pass"],
        "historical_key_evidence_unchanged":
            immutable_before == immutable_after == immutable,
        "historical_attempt_manifests_valid":
            all(row["pass"] for row in attempt_manifests.values()),
        "scientific_code_hashes_unchanged":
            scientific_before == scientific_after == SCIENTIFIC,
        "P1_execution_attempt_roots_unchanged":
            execution_roots_before == execution_roots_after
            and len(execution_roots_after) == 2,
        "historical_third_attempt_still_blocked":
            latest_attempt["Gate_F3_P1_execution"] == "BLOCKED"
            and latest_attempt["P1_registered_runs_executed"] == "0/12",
        "P2_not_started": latest_attempt["P2_started"] is False,
        "RL_not_started": latest_attempt["RL_started"] is False,
    }

    dump(out / "frozen_hash_report.json", {
        "schema": "gate_f3_drain_continuation_frozen_hash_report_v1",
        "canonical": {
            "F3": F3_SHA,
            "execution_manifest": EXECUTION_SHA,
            "F3_0_1_overlay": OVERLAY_SHA,
        },
        "historical_before": immutable_before,
        "historical_after": immutable_after,
        "historical_attempt_artifact_manifests": attempt_manifests,
        "unchanged": checks["historical_key_evidence_unchanged"]
            and checks["historical_attempt_manifests_valid"],
    })
    dump(out / "scientific_code_hash_report.json", {
        "schema": "gate_f3_drain_continuation_scientific_hash_report_v1",
        "before": scientific_before,
        "after": scientific_after,
        "D2_expected_sha256": D2_SHA,
        "D2_observed_sha256":
            digest("src/dynamic_lisl/transition_service_orchestrator.py"),
        "unchanged": checks["scientific_code_hashes_unchanged"]
            and checks["D2_implementation_hash_unchanged"],
    })

    # This scan is intentionally performed only after all test evidence exists.
    checks["no_registered_P1_run_id_in_repair_evidence"] = (
        not output_contains_registered_run_id(out)
    )
    checks["registered_P1_runs_executed_in_repair_is_zero"] = (
        checks["P1_execution_attempt_roots_unchanged"]
        and checks["no_registered_P1_run_id_in_repair_evidence"]
    )

    report = {
        "schema": "gate_f3_drain_continuation_adapter_repair_report_v1",
        "status": (
            "Gate F3 Drain Continuation Adapter Repair = PASS"
            if all(checks.values()) else
            "Gate F3 Drain Continuation Adapter Repair = FAIL"
        ),
        "checks": checks,
        "pass": all(checks.values()),
        "D2_internal_early_return_semantics": "UNCHANGED",
        "D2_internal_return_threshold_bits": 1.0,
        "F3_COMPLETE_threshold_bits": 0.01,
        "F3_censor_limit_s": 600.0,
        "D2_return_not_F3_completion": "ENFORCED",
        "real_drain_continuation": (
            "PASS" if fixture["checks"]["event_reached_delivery"] else "FAIL"
        ),
        "no_progress_guard": (
            "PASS" if fixture["checks"]["no_progress_guard_explicit"] else "FAIL"
        ),
        "drain_controller_cadence": "UNCHANGED",
        "frozen_scientific_semantics_unchanged":
            checks["scientific_code_hashes_unchanged"],
        "frozen_tolerances_unchanged":
            checks["D2_state_tolerance_unchanged"]
            and checks["D2_conservation_tolerance_unchanged"],
        "new_P1_execution_attempt_readiness": (
            "READY" if all(checks.values()) else "NOT_READY"
        ),
        "registered_P1_runs_executed_in_this_repair_task": 0,
        "focused_test_count": focused["test_count"],
        "full_regression_test_count": regression["test_count"],
        "P2_started": False,
        "RL_started": False,
    }
    dump(out / "report.json", report)

    artifact_files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "artifact_hashes.json":
            artifact_files[path.relative_to(out).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    dump(out / "artifact_hashes.json", {
        "schema": "gate_f3_drain_continuation_artifact_hashes_v1",
        "files": artifact_files,
    })

    if not report["pass"]:
        print(json.dumps(
            {name: value for name, value in checks.items() if not value},
            indent=2,
        ))
        raise SystemExit("GATE_F3_DRAIN_CONTINUATION_ADAPTER_REPAIR_FAIL")

    print("Gate F3 Drain Continuation Adapter Repair = PASS")
    print("D2 internal early-return semantics = UNCHANGED")
    print("D2 internal return threshold = 1.0 bit")
    print("F3 COMPLETE threshold = 0.01 bit")
    print("F3 censor limit = 600 s")
    print("D2 return != F3 completion = ENFORCED")
    print("real drain continuation = PASS")
    print("no-progress guard = PASS")
    print("drain controller cadence = UNCHANGED")
    print("frozen scientific semantics unchanged = YES")
    print("frozen tolerances unchanged = YES")
    print("new P1 execution attempt readiness = READY")
    print("registered P1 runs executed in this repair task = 0")
    print("P2 started = false")
    print("RL started = false")
    print(out.relative_to(PROJECT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
