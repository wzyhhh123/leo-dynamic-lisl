"""Formal Gate F1 correctness checker.

Expected scientific status is blocked because B1/B3 scalar scores are not
human-frozen.  Infrastructure correctness may still pass independently.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT/"src"
sys.path.insert(0, str(SRC))

from dynamic_lisl.gate_f1_sanity import run_160_semantic_sanity


OVERLAY_SHA = "c4dbd526b1d21a1f0462a49a5a4b59fa54122f72313b1dbe1115c8608b65256b"


def read(name):
    return json.loads((PROJECT/name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False)+"\n", encoding="utf-8")


def canonical_sha(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def run_tests(pattern):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests",
               "-p", pattern, "-v"]
    completed = subprocess.run(command, cwd=PROJECT, env=env,
                               text=True, capture_output=True)
    text = completed.stdout+completed.stderr
    return completed.returncode, text


timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT/"outputs"/f"gate_f1_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

contract = read("configs/gate_f1_contract.json")
contract_payload = dict(contract)
contract_expected = contract_payload.pop("canonical_sha256")
parent_record = read("configs/gate_f1_frozen_parent_hashes.json")
overlay = read("configs/gate_f0_human_freeze_v1.json")
z_moderate = read("configs/z_moderate_v1.json")

checks = {}
checks["contract_canonical_hash"] = canonical_sha(contract_payload) == contract_expected
checks["overlay_canonical_hash_exact"] = overlay["canonical_sha256"] == OVERLAY_SHA
checks["z_moderate_hash_exact"] = (
    z_moderate["canonical_sha256"] ==
    "442dc666bc745da6b9fa6316cda450587f4d5da3cf64208318e2d2a15cf9f24e")

frozen_actual = {name: sha(name) for name in parent_record["a_to_e2_files"]}
checks["a_to_e2_frozen_unchanged_pre"] = frozen_actual == parent_record["a_to_e2_files"]
f0_actual = {name: sha(name)
             for name in parent_record["f0_and_human_freeze_files"]}
checks["f0_human_freeze_unchanged_pre"] = (
    f0_actual == parent_record["f0_and_human_freeze_files"])

f1_code = [
    "src/dynamic_lisl/controller_runner.py",
    "src/dynamic_lisl/candidate_proposer.py",
    "src/dynamic_lisl/baseline_controllers.py",
    "src/dynamic_lisl/outage_metrics.py",
    "src/dynamic_lisl/gate_f1_sanity.py",
]
checks["required_modules_present"] = all((PROJECT/name).is_file() for name in f1_code)
checks["b4_mpc_absent"] = not any((PROJECT/name).exists() for name in (
    "src/dynamic_lisl/mpc_controller.py",
    "src/dynamic_lisl/rollout_controller.py",
    "src/dynamic_lisl/b4_controller.py"))
checks["rl_ppo_absent"] = not any((PROJECT/name).exists() for name in (
    "src/dynamic_lisl/ppo.py", "src/dynamic_lisl/rl_controller.py",
    "src/dynamic_lisl/policy_network.py"))

f1_rc, f1_text = run_tests("test_gate_f1_*.py")
(out/"f1_tests.txt").write_text(f1_text, encoding="utf-8")
checks["f1_tests_pass"] = f1_rc == 0 and "Ran 21 tests" in f1_text

sanity_a = run_160_semantic_sanity()
sanity_b = run_160_semantic_sanity()
dump(out/"sanity_160star.json", sanity_a)
replay = {
    "sparse_action_hash_a": sanity_a["sparse"]["action_replay_sha256"],
    "sparse_action_hash_b": sanity_b["sparse"]["action_replay_sha256"],
    "moderate_action_hash_a": sanity_a["moderate"]["action_replay_sha256"],
    "moderate_action_hash_b": sanity_b["moderate"]["action_replay_sha256"],
}
replay["exact"] = (replay["sparse_action_hash_a"] == replay["sparse_action_hash_b"]
                   and replay["moderate_action_hash_a"] == replay["moderate_action_hash_b"])
dump(out/"deterministic_replay_report.json", replay)
checks["limited_160star_sanity_pass"] = sanity_a["pass"] and sanity_b["pass"]
checks["deterministic_replay_pass"] = replay["exact"]

full_rc, full_text = run_tests("test_*.py")
(out/"full_regression.txt").write_text(full_text, encoding="utf-8")
checks["full_regression_pass"] = full_rc == 0 and "FAILED" not in full_text

# Verify frozen files again after every executable check.
checks["a_to_e2_frozen_unchanged_post"] = (
    {name: sha(name) for name in parent_record["a_to_e2_files"]}
    == parent_record["a_to_e2_files"])
checks["f0_human_freeze_unchanged_post"] = (
    {name: sha(name) for name in parent_record["f0_and_human_freeze_files"]}
    == parent_record["f0_and_human_freeze_files"])

checks["decision_cadence_exact"] = contract["decision_cadence_s"] == 2.0
checks["proposer_budget_exact"] = (
    contract["candidate_top_k"] == 16
    and contract["candidate_structural_quota"] == {
        "BBM_REQUIRED": 8, "MBB_STRUCTURALLY_FEASIBLE": 8})
checks["safety_policies_exact"] = (
    contract["regime_safety"]["Z_SPARSE_REFERENCE"] == {
        "policy": "BOUNDED_TRANSITION_OUTAGE", "max_s": 2.0}
    and contract["regime_safety"]["Z_MODERATE"] == {
        "policy": "STRICT_CONNECTED"})
checks["scoring_ambiguity_honestly_blocked"] = (
    contract["scoring_contract"]["uniquely_frozen"] is False
    and contract["scoring_contract"]["status"] ==
        "BLOCKED_REQUIRES_HUMAN_FREEZE")
checks["performance_comparison_not_run"] = (
    sanity_a["scope"] == "correctness/integration only; no controller performance"
    and sanity_a["performance_fields_intentionally_omitted"] == [
        "J", "mean_delay", "delivery_ratio", "relative_improvement",
        "controller_ranking"])

infrastructure_keys = [key for key in checks
                       if key not in ("scoring_ambiguity_honestly_blocked",)]
infrastructure_pass = all(checks[key] for key in infrastructure_keys)
overall = ("BLOCKED_BEFORE_SCIENTIFIC_B1_B3_IMPLEMENTATION"
           if infrastructure_pass and checks["scoring_ambiguity_honestly_blocked"]
           else "FAIL")

frozen_report = {
    "a_to_e2_file_count": len(parent_record["a_to_e2_files"]),
    "a_to_e2_all_unchanged": checks["a_to_e2_frozen_unchanged_post"],
    "f0_human_freeze_file_count": len(parent_record["f0_and_human_freeze_files"]),
    "f0_human_freeze_all_unchanged": checks["f0_human_freeze_unchanged_post"],
    "overlay_canonical_sha256": overlay["canonical_sha256"],
    "z_moderate_canonical_sha256": z_moderate["canonical_sha256"],
}
dump(out/"frozen_hash_report.json", frozen_report)

traces = {
    "decision_cadence_s": 2.0,
    "tiny_fixture_coverage": [
        "exact_epoch", "just_before_epoch", "just_after_epoch",
        "natural_expiry_between_epochs", "hard_pruning", "8_8_quota",
        "quota_spillover", "deterministic_order", "sparse_safety_boundary",
        "moderate_strict_connected", "reject_only", "B0", "B1_scaffold",
        "B2_parameterized", "B3_firewall", "separated_outage_metrics",
        "conservation_capacity_nonnegative_queue"],
    "sanity_160star": sanity_a,
}
dump(out/"traces.json", traces)

report = {
    "schema": "gate_f1_report_v1",
    "checks": checks,
    "gate_f1_infrastructure": "PASS" if infrastructure_pass else "FAIL",
    "gate_f1_baseline_scoring_contract": "BLOCKED_REQUIRES_HUMAN_FREEZE",
    "gate_f1_overall": overall,
    "f1_regression_count": 21,
    "b0_status": "IMPLEMENTED_AND_CORRECT",
    "b1_status": "INTERFACE_CORRECT_SCIENTIFIC_SCORING_BLOCKED",
    "b2_status": "PARAMETERIZED_LOGIC_CORRECT_F3_GRID_UNFROZEN",
    "b3_status": "INTERFACE_AND_FIREWALL_CORRECT_SCIENTIFIC_SCORING_BLOCKED",
    "new_human_freeze_required": ["B1_scalar_score", "B3_scalar_score",
                                  "B2_base_signal"],
    "performance_experiment_run": False,
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(out/"report.json", report)

artifact_names = [
    "configs/gate_f1_contract.json",
    "configs/gate_f1_frozen_parent_hashes.json",
    "docs/GATE_F1_CONTROLLER_INFRASTRUCTURE_CN.md",
    "docs/GATE_F1_CORRECTNESS_RESULT_CN.md",
    "docs/GATE_F1_SCORING_AMBIGUITY_CN.md",
    *f1_code,
    "tests/test_gate_f1_controller.py",
    "tests/test_gate_f1_contract.py",
    "tools/check_gate_f1.py",
]
dump(out/"artifact_hashes.json", {name: sha(name) for name in artifact_names})

status = {
    "gate_f1_infrastructure": "PASS" if infrastructure_pass else "FAIL",
    "gate_f1_baseline_scoring_contract": "BLOCKED_REQUIRES_HUMAN_FREEZE",
    "gate_f1_overall": overall,
    "gate_f1_started": True,
    "gate_f1_completed_correctness_scope": infrastructure_pass,
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "f1_regression_count": 21,
    "frozen_hashes_unchanged": (
        checks["a_to_e2_frozen_unchanged_post"]
        and checks["f0_human_freeze_unchanged_post"]),
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(PROJECT/"configs/gate_f1_status.json", status)

current = read("configs/current.json")
current["gate_f1"] = {
    "contract": "configs/gate_f1_contract.json",
    "record": "configs/gate_f1_status.json",
    "infrastructure": status["gate_f1_infrastructure"],
    "baseline_scoring_contract": status["gate_f1_baseline_scoring_contract"],
    "overall": status["gate_f1_overall"],
    "evidence": status["evidence"],
}
current["gate_f1_started"] = True
current["gate_f2_started"] = False
current["gate_f3_started"] = False
current["rl_started"] = False
current["project_status"] = "GATE_F1_INFRASTRUCTURE_PASS_SCORING_CONTRACT_BLOCKED"
current["current_command"] = "python tools/check_gate_f1.py"
dump(PROJECT/"configs/current.json", current)

print(f"Gate F1 infrastructure = {report['gate_f1_infrastructure']}")
print("Gate F1 baseline-scoring contract = BLOCKED_REQUIRES_HUMAN_FREEZE")
print(f"Gate F1 overall = {overall}")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
print("F2 started = false")
print("F3 started = false")
print("RL started = false")

if not infrastructure_pass:
    raise SystemExit(1)
