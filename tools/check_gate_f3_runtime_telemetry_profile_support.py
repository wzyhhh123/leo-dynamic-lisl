"""Acceptance checker for F3 passive telemetry and profile support."""
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
PYTHON = Path(sys.executable)
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT))

from dynamic_lisl.gate_f3_p1_execution import canonical_hash  # noqa: E402
from tests.test_gate_f3_p1_evidence_persistence import SCIENTIFIC  # noqa: E402


F3_SHA = "118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6"
EXECUTION_SHA = "0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a"
OVERLAY_SHA = "ba527d3bc2c4ebca742ec21b8c390d512931d56d9c9ba68ed4eb22a7f47a7f39"
F3_PROGRESS_SHA = "0d00fa44e92de973704e1d4f5641ce80229e06f5fce8c8da7d80431a0a3f17ac"
ABORTED_ROOT = PROJECT / "outputs/gate_f3_p1_execution_20260925T090650_595069Z"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(root):
    return {path.relative_to(root).as_posix(): digest(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def canonical_valid(relative, expected):
    document = json.loads((PROJECT / relative).read_text(encoding="utf-8-sig"))
    observed = document.pop("canonical_sha256")
    return observed == expected == canonical_hash(document)


def run_suite(out, filename, args):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT / "src") + (
        os.pathsep + environment["PYTHONPATH"]
        if environment.get("PYTHONPATH") else "")
    command = [str(PYTHON), "-m", "unittest", *args]
    process = subprocess.run(command, cwd=PROJECT, capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             env=environment)
    content = ("COMMAND: " + " ".join(command) + "\n\nSTDOUT:\n"
               + process.stdout + "\nSTDERR:\n" + process.stderr
               + f"\nEXIT_CODE: {process.returncode}\n")
    (out / filename).write_text(content, encoding="utf-8")
    match = re.search(r"Ran (\d+) tests?", process.stdout + process.stderr)
    return {"pass": process.returncode == 0,
            "count": int(match.group(1)) if match else None,
            "exit_code": process.returncode}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = PROJECT / "outputs" / f"gate_f3_runtime_telemetry_profile_support_{stamp}"
    out.mkdir(parents=True, exist_ok=False)

    roots_before = sorted(path.name for path in (PROJECT / "outputs").glob(
        "gate_f3_p1_execution_*") if path.is_dir())
    historical_before = tree_hashes(ABORTED_ROOT)
    scientific_before = {name: digest(PROJECT / name) for name in SCIENTIFIC}

    focused = run_suite(out, "focused_test_report.txt",
                        ["-v", "tests.test_gate_f3_runtime_telemetry"])
    regression = run_suite(out, "regression_report.txt",
                           ["discover", "-s", "tests", "-v"])

    roots_after = sorted(path.name for path in (PROJECT / "outputs").glob(
        "gate_f3_p1_execution_*") if path.is_dir())
    historical_after = tree_hashes(ABORTED_ROOT)
    scientific_after = {name: digest(PROJECT / name) for name in SCIENTIFIC}
    abort_text = (ABORTED_ROOT / "RUNTIME_ABORT_RECORD.txt").read_text(
        encoding="utf-8")
    profile_source = (PROJECT / "tools/profile_gate_f3_b1_runtime.py").read_text(
        encoding="utf-8")
    progress_source = (PROJECT / "src/dynamic_lisl/f3_progress.py").read_text(
        encoding="utf-8")
    runner_source = (PROJECT / "tools/run_gate_f3_p1_execution.py").read_text(
        encoding="utf-8")
    latest_status = json.loads((PROJECT /
        "configs/gate_f3_p1_execution_attempt_20260925T081402_status.json")
        .read_text(encoding="utf-8"))

    checks = {
        "focused_equivalence_tests_pass": focused["pass"] and focused["count"] == 5,
        "full_regression_pass": regression["pass"],
        "F3_contract_unchanged": canonical_valid(
            "configs/gate_f3_experiment_human_freeze_v1.json", F3_SHA),
        "execution_manifest_unchanged": canonical_valid(
            "configs/gate_f3_execution_manifest_v1.json", EXECUTION_SHA),
        "candidate_drain_overlay_unchanged": canonical_valid(
            "configs/gate_f3_candidate_source_drain_human_freeze_v1.json",
            OVERLAY_SHA),
        "scientific_modules_unchanged":
            scientific_before == scientific_after == SCIENTIFIC,
        "aborted_attempt_tree_unchanged": historical_before == historical_after,
        "abort_record_preserved":
            "status = ABORTED_FOR_RUNTIME_ENGINEERING" in abort_text
            and "B1_scientific_outcome = NOT_AVAILABLE" in abort_text,
        "no_new_registered_P1_attempt": roots_before == roots_after,
        "profile_marked_engineering_only":
            "ENGINEERING_PROFILE_ONLY" in profile_source
            and "PROFILE_RUN_ID" in profile_source
            and "cProfile.Profile" in profile_source,
        "profile_does_not_use_registered_run_id":
            "PROFILE_MUST_NOT_USE_REGISTERED_P1_RUN_ID" in profile_source,
        "profile_progress_modes_frozen":
            '"--progress"' in profile_source
            and '"--no-progress"' in profile_source
            and "set_defaults(telemetry_enabled=True)" in profile_source
            and '"telemetry_enabled": bool(args.telemetry_enabled)' in profile_source,
        "profile_no_progress_passes_none":
            "if not telemetry_enabled:\n        return None" in profile_source,
        "f3_progress_implementation_unchanged":
            digest(PROJECT / "src/dynamic_lisl/f3_progress.py") == F3_PROGRESS_SHA,
        "progress_has_start_and_end":
            "EPOCH_START" in progress_source and "EPOCH_END" in progress_source,
        "progress_latest_atomic_replace":
            "os.replace" in progress_source and "progress_latest.json" in progress_source,
        "runner_progress_is_optional":
            "--progress-dir" in runner_source and "--disable-progress" in runner_source,
        "progress_excluded_from_science_attempt_root":
            "PROGRESS_DIR_MUST_BE_OUTSIDE_SCIENTIFIC_ATTEMPT_ROOT" in runner_source,
        "P2_not_started": latest_status["P2_started"] is False,
        "RL_not_started": latest_status["RL_started"] is False,
    }
    report = {
        "schema": "gate_f3_runtime_telemetry_profile_support_report_v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "pass": all(checks.values()),
        "checks": checks,
        "focused_test_count": focused["count"],
        "full_regression_test_count": regression["count"],
        "registered_P1_runs_executed_in_this_task": 0,
        "long_profile_executed": False,
        "P2_started": False,
        "RL_started": False,
        "historical_abort_record_sha256": digest(
            ABORTED_ROOT / "RUNTIME_ABORT_RECORD.txt"),
    }
    dump(out / "historical_evidence_hash_report.json", {
        "before": historical_before, "after": historical_after,
        "unchanged": historical_before == historical_after})
    dump(out / "scientific_hash_report.json", {
        "before": scientific_before, "after": scientific_after,
        "unchanged": scientific_before == scientific_after})
    dump(out / "report.json", report)
    dump(out / "artifact_hashes.json", {
        path.relative_to(out).as_posix(): digest(path)
        for path in sorted(out.rglob("*")) if path.is_file()
        and path.name != "artifact_hashes.json"})
    if not report["pass"]:
        print(json.dumps({k: v for k, v in checks.items() if not v}, indent=2))
        raise SystemExit("GATE_F3_RUNTIME_TELEMETRY_PROFILE_SUPPORT_FAIL")
    print("Gate F3 runtime telemetry/profile support = PASS")
    print(f"focused tests = {focused['count']} PASS")
    print(f"full regression = {regression['count']} PASS")
    print("registered P1 runs executed = 0")
    print("long profile executed = false")
    print(out.relative_to(PROJECT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

