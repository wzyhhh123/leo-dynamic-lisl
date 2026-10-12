"""Gate F3-0.1 production candidate-source/drain-policy closure checker."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from dynamic_lisl.candidate_proposer import FrozenTerminalPairProposer, canonical_sha256
from dynamic_lisl.common import read_json
from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f1_sanity import _moderate_engine
from dynamic_lisl.production_candidate_source import (
    DrainDecisionPolicy,
    ProductionCandidateSource,
)


OVERLAY_CANONICAL = "ba527d3bc2c4ebca742ec21b8c390d512931d56d9c9ba68ed4eb22a7f47a7f39"
F3_CANONICAL = "118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6"
EXECUTION_CANONICAL = "0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a"
HISTORICAL_BLOCKER = "GATE_F3_P1_EXECUTION_BLOCKED_BY_CANDIDATE_SOURCE_NOT_FROZEN"

FROZEN_FILES = {
    "configs/gate_f3_experiment_human_freeze_v1.json":
        "655a2210206d502320695f325e0b488547971e99e0e6e75a9b2a0552523032c0",
    "configs/gate_f3_execution_manifest_v1.json":
        "f6aba631fa7f133f4cb95d63ec5f809b4345f1ad3676401de3df286697a558f9",
    "configs/hardware_gate_c_simplified_v1.json":
        "66ca6881b739aad87ccd850a89f0dcddb9bb35684f48fcdee2e0aece33fadd19",
    "configs/gate_f3_p1_status.json":
        "164bd07f8d80319b07029944db86b0cb70a4dacfef8227225d6b7ac2d6ea3ed3",
    "docs/GATE_F3_P1_RESULT_CN.md":
        "09a966f158a10849490661d6f7e03540e726e17f5abf197602e8e6a435a5af38",
    "outputs/gate_f3_p1_20260925T050259_813979Z/report.json":
        "2125233b4cf2256cd8587febb148c0d880dbbaca596d259519a4aa18f2bdace6",
    "src/dynamic_lisl/baseline_controllers.py":
        "44e920bca8fe686ea9c43ce4d9fe4c48679365a6eed0f706b43de20af74b31e8",
    "src/dynamic_lisl/scientific_controllers.py":
        "19726f56bb83c1c77073aac4618bbbe71733fdc9257b59dbf3ea905e6aaf3407",
    "src/dynamic_lisl/rollout_controller.py":
        "5d2b3d4170be148b5cbdf6808a57b9c9cbc105df487405bcef9904c292884e81",
    "src/dynamic_lisl/rollout_evaluator.py":
        "db7e6c187ff834e209a8afe8bab47ec8319fb394739f82f5162da7766bd1db8d",
    "src/dynamic_lisl/forecast.py":
        "fd9c2c56a6abc789cbb1e5d2fa5e2d8dec12a3b7be9bc568d4518602dea77a27",
    "src/dynamic_lisl/terminal_executor.py":
        "fa8a561d9ae935060a06d2c783f14f76c43e19800e7c1e361e63b18191330d01",
    "src/dynamic_lisl/gate_c_simplified_feasibility.py":
        "a194dc87ab8b6df15d15574f95a68588897f59dcd8779860e2bf652436311eac",
    "src/dynamic_lisl/transition_service_orchestrator.py":
        "5b674ee226ac07aba136fc7c207f6abe727a4d63ad9097c1291afa6217750fd4",
    "src/dynamic_lisl/controller_runner.py":
        "187658932a7935135e58e25140db9f32ef0c99c376a11bf2fc206d0198071185",
    "src/dynamic_lisl/candidate_proposer.py":
        "9bb609292fcbb273a17cc2009d62cee9c46a1a4a45ab305200b6b93b4aaf4b8a",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(relative):
    return json.loads((PROJECT / relative).read_text(encoding="utf-8-sig"))


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False,
        allow_nan=False) + "\n", encoding="utf-8")


def run_tests(pattern):
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", pattern, "-v"],
        cwd=PROJECT, env=environment, capture_output=True, text=True)
    log = completed.stdout + completed.stderr
    match = re.search(r"Ran (\d+) tests?", log)
    return {
        "pattern": pattern,
        "returncode": completed.returncode,
        "tests_run": int(match.group(1)) if match else None,
        "pass": completed.returncode == 0 and "OK" in log,
        "log": log,
    }


stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
output = PROJECT / "outputs" / f"gate_f3_candidate_source_drain_freeze_{stamp}"
output.mkdir(parents=True, exist_ok=False)

overlay = read("configs/gate_f3_candidate_source_drain_human_freeze_v1.json")
overlay_payload = dict(overlay)
recorded_overlay_hash = overlay_payload.pop("canonical_sha256")
f3 = read("configs/gate_f3_experiment_human_freeze_v1.json")
execution = read("configs/gate_f3_execution_manifest_v1.json")
historical_status = read("configs/gate_f3_p1_status.json")
p1_rows = [row for row in execution["runs"] if row["block_id"] == "P1"]

frozen_actual = {
    name: sha(PROJECT / name) for name in FROZEN_FILES
}
frozen_hash_report = {
    "schema": "gate_f3_candidate_source_drain_frozen_hash_report_v1",
    "expected": FROZEN_FILES,
    "actual": frozen_actual,
    "all_unchanged": frozen_actual == FROZEN_FILES,
    "overlay_canonical_sha256": recorded_overlay_hash,
}
dump(output / "frozen_hash_report.json", frozen_hash_report)

targeted = run_tests("test_gate_f3_candidate_source_drain.py")
dump(output / "candidate_source_fixture_report.json", {
    "schema": "gate_f3_candidate_source_fixture_report_v1",
    "test_count": targeted["tests_run"],
    "pass": targeted["pass"],
    "required_fixture_scope": [
        "same_state_replay", "controller_blind_equality", "BBM_RAW",
        "genuine_MBB_RAW", "multi_old_conflict", "no_op", "parallel_pair",
        "reservation", "draining", "release_owner", "unrelated_setup",
        "32_32_64_caps", "canonical_ids", "dedup", "distinct_old_binding",
        "final_top16_and_8_8",
    ],
    "unittest_log": targeted["log"],
})

policy = DrainDecisionPolicy()
drain_checks = {
    "t238_decision": policy.decision_due(238.0, 0.0),
    "t240_decision_with_backlog": policy.decision_due(240.0, 1.0),
    "t242_decision_with_backlog": policy.decision_due(242.0, 1.0),
    "early_complete_suppresses_next_epoch": not policy.decision_due(242.0, 0.01),
    "t598_decision_with_backlog": policy.decision_due(598.0, 1.0),
    "no_t600_decision": not policy.decision_due(600.0, 1.0),
    "last_possible_epoch_598": policy.possible_epochs()[-1] == 598.0,
    "t240_zero_arrival_assertion": policy.assert_arrival_cutoff_state(
        240.0, {f"f{i:02d}": 0.0 for i in range(16)}),
}
dump(output / "drain_decision_fixture_report.json", {
    "schema": "gate_f3_drain_decision_fixture_report_v1",
    "checks": drain_checks,
    "pass": all(drain_checks.values()),
    "arrival_horizon_s": policy.arrival_horizon_s,
    "drain_limit_s": policy.drain_limit_s,
    "cadence_s": policy.cadence_s,
})

# Correctness-only 160-star Z_MODERATE interface sanity.
assets = GateE2Assets()
engine = _moderate_engine(assets)
source = ProductionCandidateSource.from_project(assets.catalog, PROJECT)
visible = controller_visible_state(engine)
contexts = [
    {"terminal_executor": engine.executor, "regime": "Z_MODERATE",
     "controller_id": controller}
    for controller in ("B1", "B2", "B3", "B4")
]
controller_ids = []
controller_hashes = []
for context in contexts:
    specs = source(visible, context)
    controller_ids.append([spec.proposal_id for spec in specs])
    controller_hashes.append(source.last_report["source_sha256"])
source_report = deepcopy(source.last_report)
proposal_set = FrozenTerminalPairProposer().propose(
    engine.executor, specs, assets.physical, assets.fixed, "Z_MODERATE")
strata = Counter(row["stratum"] for row in proposal_set["proposals"])

probe = {"executed": False}
if proposal_set["proposals"]:
    chosen_record = next((row for row in proposal_set["proposals"]
                          if row["stratum"] == "MBB_STRUCTURALLY_FEASIBLE"),
                         proposal_set["proposals"][0])
    chosen = proposal_set["candidate_specs"][chosen_record["proposal_id"]]
    trial = deepcopy(engine.executor)
    physical = assets.physical.evaluate(trial, **chosen.proposal)
    probe = {
        "proposal_id": chosen.proposal_id,
        "gate_c_accepted": physical["accepted"],
        "release_after_present": bool(
            physical["command"].release_after) if physical["accepted"] else None,
        "executed": False,
        "link_up_observed": False,
    }
    if physical["accepted"]:
        trial.submit((physical["command"],))
        trial.advance(float(physical["geometry"]["ready_time"]))
        probe["executed"] = True
        probe["link_up_observed"] = any(
            row["event"] == "LINK_UP" for row in trial.log)

sanity_checks = {
    "raw_total_at_most_64": len(specs) <= 64,
    "raw_BBM_at_most_32": source_report["selected_counts"]["BBM_RAW"] <= 32,
    "raw_MBB_at_most_32": source_report["selected_counts"]["MBB_RAW"] <= 32,
    "final_at_most_16": len(proposal_set["proposals"]) <= 16,
    "final_quota_8_8": strata == {
        "BBM_REQUIRED": 8, "MBB_STRUCTURALLY_FEASIBLE": 8},
    "all_controller_source_ids_equal": len({tuple(row) for row in controller_ids}) == 1,
    "all_controller_source_hashes_equal": len(set(controller_hashes)) == 1,
    "gate_c_probe_accepted": probe["gate_c_accepted"],
    "gate_b_probe_link_up": probe["link_up_observed"],
}
deterministic_report = {
    "schema": "gate_f3_candidate_source_deterministic_replay_v1",
    "source_sha256_by_controller": dict(zip(
        ("B1", "B2", "B3", "B4"), controller_hashes)),
    "ordered_candidate_ids_equal": sanity_checks["all_controller_source_ids_equal"],
    "source_hash_equal": sanity_checks["all_controller_source_hashes_equal"],
    "ordered_candidate_ids": controller_ids[0],
    "pass": (sanity_checks["all_controller_source_ids_equal"]
             and sanity_checks["all_controller_source_hashes_equal"]),
}
dump(output / "deterministic_replay_report.json", deterministic_report)

sanity_report = {
    "schema": "gate_f3_candidate_source_160star_sanity_v1",
    "scope": "correctness-only; no registered run_id and no performance comparison",
    "topology": "Z_MODERATE",
    "raw_selected_counts": source_report["selected_counts"],
    "raw_uncapped_counts": source_report["uncapped_counts"],
    "raw_total": len(specs),
    "source_sha256": source_report["source_sha256"],
    "candidate_ids": controller_ids[0],
    "final_count": len(proposal_set["proposals"]),
    "final_strata": dict(sorted(strata.items())),
    "final_proposal_set_sha256": proposal_set["proposal_set_sha256"],
    "gate_b_c_execution_probe": probe,
    "checks": sanity_checks,
    "pass": all(sanity_checks.values()),
    "performance_fields_intentionally_absent": [
        "J", "mean_delay", "relative_improvement", "best_controller"],
}
dump(output / "sanity_160star.json", sanity_report)

full = run_tests("test*.py")
(output / "full_regression.log").write_text(full["log"], encoding="utf-8")

registered_run_dirs = []
for root in (PROJECT / "outputs").glob("gate_f3_p1_*/runs"):
    registered_run_dirs.extend(path for path in root.iterdir() if path.is_dir())

checks = {
    "overlay_canonical_exact": recorded_overlay_hash == OVERLAY_CANONICAL
        and canonical_sha256(overlay_payload) == OVERLAY_CANONICAL,
    "F3_canonical_unchanged": f3["canonical_sha256"] == F3_CANONICAL,
    "execution_manifest_canonical_unchanged":
        execution["canonical_sha256"] == EXECUTION_CANONICAL,
    "historical_blocker_preserved":
        historical_status["blocker_code"] == HISTORICAL_BLOCKER,
    "historical_P1_zero_of_12":
        historical_status["P1_registered_runs_executed"] == "0/12",
    "P1_manifest_still_planned": len(p1_rows) == 12 and all(
        row["performance_status"] == "PLANNED_NOT_EXECUTED" for row in p1_rows),
    "no_registered_P1_run_directory": registered_run_dirs == [],
    "frozen_scientific_and_parent_files_unchanged": frozen_hash_report["all_unchanged"],
    "candidate_fixture_tests_pass": targeted["pass"] and targeted["tests_run"] >= 19,
    "drain_fixture_pass": all(drain_checks.values()),
    "deterministic_replay_pass": deterministic_report["pass"],
    "sanity_160star_pass": sanity_report["pass"],
    "full_regression_pass": full["pass"],
    "P2_not_started": True,
    "RL_not_started": True,
}
overall = all(checks.values())
report = {
    "schema": "gate_f3_candidate_source_drain_freeze_report_v1",
    "statement": ("Gate F3 Candidate Source + Drain Human Freeze v1 = PASS"
                  if overall else
                  "Gate F3 Candidate Source + Drain Human Freeze v1 = FAIL"),
    "overlay_canonical_sha256": OVERLAY_CANONICAL,
    "checks": checks,
    "candidate_source_contract": "FROZEN" if overall else "FAIL",
    "production_candidate_source": "PASS" if overall else "FAIL",
    "candidate_source_deterministic_replay":
        "PASS" if deterministic_report["pass"] else "FAIL",
    "drain_decision_policy": "FROZEN" if all(drain_checks.values()) else "FAIL",
    "P1_execution_readiness": "READY" if overall else "BLOCKED",
    "P1_registered_runs_executed": "0/12",
    "F3_performance_started": False,
    "P2_started": False,
    "RL_started": False,
    "full_regression_tests_run": full["tests_run"],
    "output": str(output.relative_to(PROJECT)).replace("\\", "/"),
}
dump(output / "report.json", report)

status = {
    "schema": "gate_f3_candidate_source_drain_status_v1",
    "Gate_F3_Candidate_Source_Drain_Human_Freeze_v1":
        "PASS" if overall else "FAIL",
    "candidate_source_contract": "FROZEN" if overall else "FAIL",
    "production_candidate_source": "PASS" if overall else "FAIL",
    "candidate_source_deterministic_replay":
        "PASS" if deterministic_report["pass"] else "FAIL",
    "drain_decision_policy": "FROZEN" if all(drain_checks.values()) else "FAIL",
    "P1_execution_readiness": "READY" if overall else "BLOCKED",
    "P1_registered_runs_executed": "0/12",
    "F3_performance_started": False,
    "P2_started": False,
    "RL_started": False,
    "overlay_canonical_sha256": OVERLAY_CANONICAL,
    "evidence": report["output"],
}
dump(PROJECT / "configs/gate_f3_candidate_source_drain_status.json", status)

artifact_files = [path for path in output.rglob("*")
                  if path.is_file() and path.name != "artifact_hashes.json"]
dump(output / "artifact_hashes.json", {
    "schema": "gate_f3_candidate_source_drain_artifact_hashes_v1",
    "files": {
        str(path.relative_to(PROJECT)).replace("\\", "/"): sha(path)
        for path in sorted(artifact_files)
    },
})

if not overall:
    failed = [name for name, value in checks.items() if not value]
    raise SystemExit("GATE_F3_CANDIDATE_SOURCE_DRAIN_FAIL: " + ",".join(failed))

print("Gate F3 Candidate Source + Drain Human Freeze v1 = PASS")
print("candidate-source contract = FROZEN")
print("production candidate source = PASS")
print("candidate-source deterministic replay = PASS")
print("drain decision policy = FROZEN")
print("P1 execution readiness = READY")
print("P1 registered runs executed = 0/12")
print("F3 performance started = false")
print("P2 started = false")
print("RL started = false")
print("overlay canonical SHA-256 = " + OVERLAY_CANONICAL)
print(report["output"])

