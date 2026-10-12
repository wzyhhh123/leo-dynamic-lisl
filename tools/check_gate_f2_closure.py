"""Gate F2 B4 implementation, correctness, and closure validation."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "src"
TESTS = PROJECT / "tests"
for path in (SRC, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_f2_sanity import run_160_b4_semantic_sanity
from dynamic_lisl.rollout_controller import RootActionRolloutMPCController


F2_CANONICAL = "ca82a1e49f6bdbe56a4c9f2fb79299eac0174844e0bdc6608ea3cb4f12f90b2a"
F2_ZERO_ASSETS = {
    "docs/GATE_F2_ROLLOUT_HUMAN_FREEZE_V1_CN.md":
        "205ff6cc999dc83241926c68aacff11be759a5e463c8ef8d11cfd30b8d95043c",
    "configs/gate_f2_rollout_human_freeze_v1.json":
        "7276c0fbfedcfc6f35fd6ee316338c7f089fcaf1c47e81d3425f42f15b3b01df",
    "configs/gate_f2_rollout_human_freeze_status.json":
        "c87f7bc40980637971829fadb22d12d547fc4c721ee434ed57100ab804443742",
    "tools/check_gate_f2_rollout_human_freeze.py":
        "95e6cdb2f5f9a76d78c64f7fff717a414153de20c2cfdb5787a805c8285a3cc7",
    "outputs/gate_f2_rollout_human_freeze_20260925T031740_835531Z/report.json":
        "cd9bab95f88efedabd8429580c3638d1b5681e3cc53183a7fe297795567b5718",
    "outputs/gate_f2_rollout_human_freeze_20260925T031740_835531Z/frozen_hash_report.json":
        "d72618acb7b20732189ec1d82bd6cb7c4cf11f243de7d8fb0163010ea5f9c15e",
    "outputs/gate_f2_rollout_human_freeze_20260925T031740_835531Z/artifact_hashes.json":
        "9f2b34db1163ddc9762fda06dc3e9ce257ab9426e157ce867bf635d898d065ec",
}


def read(name):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def run_command(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    completed = subprocess.run(
        args, cwd=PROJECT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace")
    return completed.returncode, completed.stdout


def count_tests(text):
    match = re.search(r"Ran (\d+) tests?", text)
    return int(match.group(1)) if match else 0


def load_test_helpers():
    path = TESTS / "test_gate_f2_rollout.py"
    spec = importlib.util.spec_from_file_location("gate_f2_test_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = read("configs/gate_f2_rollout_human_freeze_v1.json")
closure = read("configs/gate_f1_closure_status.json")
zero_report = read(
    "outputs/gate_f2_rollout_human_freeze_20260925T031740_835531Z/report.json")
parent_expected = contract["parent_hashes"]
parent_pre = {group: {name: sha(name) for name in records}
              for group, records in parent_expected.items()}
zero_pre = {name: sha(name) for name in F2_ZERO_ASSETS}
a_to_e2 = read("configs/gate_f0_frozen_a_to_e2_hashes.json")
a_to_e2_pre = {name: sha(name) for name in a_to_e2["files"]}

checks = {}
checks["gate_f1_closure_preflight_pass"] = all((
    closure["gate_f1_overall"] == "PASS",
    closure["gate_f1_closure"] == "YES",
    closure["F2_readiness"] == "READY",
))
checks["f2_0_preimplementation_evidence_pass"] = (
    zero_report["statement"] == "Gate F2 Rollout Human Freeze v1 = PASS")
checks["f2_0_canonical_exact"] = contract["canonical_sha256"] == F2_CANONICAL
checks["f2_0_assets_unchanged_pre"] = zero_pre == F2_ZERO_ASSETS
checks["declared_parent_hashes_unchanged_pre"] = parent_pre == parent_expected
checks["a_to_e2_148_hashes_unchanged_pre"] = (
    len(a_to_e2["files"]) == 148 and a_to_e2_pre == a_to_e2["files"])

required_implementation = (
    "src/dynamic_lisl/forecast.py",
    "src/dynamic_lisl/rollout_evaluator.py",
    "src/dynamic_lisl/rollout_controller.py",
    "src/dynamic_lisl/gate_f2_sanity.py",
    "tests/test_gate_f2_rollout.py",
    "docs/GATE_F2_B4_IMPLEMENTATION_CN.md",
)
checks["one_canonical_B4_implementation_exists"] = all(
    (PROJECT / name).is_file() for name in required_implementation)
checks["frozen_contract_not_modified_for_implementation"] = (
    zero_pre == F2_ZERO_ASSETS)

timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT / "outputs" / f"gate_f2_closure_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

new_code, new_text = run_command([
    sys.executable, "-m", "unittest", "discover", "-s", "tests",
    "-p", "test_gate_f2_rollout.py", "-v"])
(out / "new_f2_tests.txt").write_text(new_text, encoding="utf-8")
new_count = count_tests(new_text)
checks["new_F2_correctness_tests_pass"] = new_code == 0 and new_count >= 25

relevant_outputs = []
relevant_count = 0
relevant_ok = True
for pattern in (
        "test_gate_b.py", "test_gate_c.py", "test_gate_c_simplified.py",
        "test_gate_d1.py", "test_gate_d2.py", "test_gate_f1_contract.py",
        "test_gate_f1_controller.py", "test_gate_f1_scientific_scoring_v2.py"):
    code, text = run_command([
        sys.executable, "-m", "unittest", "discover", "-s", "tests",
        "-p", pattern, "-v"])
    relevant_outputs.append(f"===== {pattern} =====\n{text}")
    relevant_count += count_tests(text)
    relevant_ok = relevant_ok and code == 0
(out / "relevant_regression.txt").write_text(
    "\n".join(relevant_outputs), encoding="utf-8")
checks["relevant_B_C_D1_D2_F1_regression_pass"] = relevant_ok

helpers = load_test_helpers()
engine, _, spec1, _, controller = helpers.bbm_environment()
spec2 = helpers.CandidateSpec("BBM-ALT", {
    "a": ("B", "D1"), "b": ("A", "D2"),
    "retarget_a": 2.0, "retarget_b": 2.0, "acquisition": 0.0,
}, (("B", "D1"), ("C", "D1")))
physical2 = helpers.TerminalPairPhysicalFeasibility(helpers._catalog(
    engine.nodes, [helpers._window("B", "D1", "D", "D1"),
                   helpers._window("A", "D2", "B", "D1")]))
proposed = helpers.FrozenTerminalPairProposer().propose(
    engine.executor, (spec1, spec2), physical2, engine.fixed_edges,
    "Z_SPARSE_REFERENCE")
controller = RootActionRolloutMPCController(
    engine, physical2, engine.fixed_edges, "Z_SPARSE_REFERENCE")
controller.bind_candidate_specs((spec1, spec2), engine.now)
state = controller_visible_state(engine)
ids = [row["proposal_id"] for row in proposed["proposals"]]
forward = controller.evaluate_root_actions(
    state, helpers.public(proposed), {}, ids)
reverse = controller.evaluate_root_actions(
    state, helpers.public(proposed), {}, ids[::-1])
forward_scores = {x["branch_id"]: x["J_H_bit_s"] for x in forward["branches"]}
reverse_scores = {x["branch_id"]: x["J_H_bit_s"] for x in reverse["branches"]}
branch_order = {
    "schema": "gate_f2_branch_order_report_v1",
    "forward_order": ids,
    "reverse_order": ids[::-1],
    "forward_scores": forward_scores,
    "reverse_scores": reverse_scores,
    "same_scores_by_proposal": forward_scores == reverse_scores,
    "same_selected_action": (
        forward["selected_action"], forward["selected_proposal_id"])
        == (reverse["selected_action"], reverse["selected_proposal_id"]),
}
branch_order["pass"] = all((branch_order["same_scores_by_proposal"],
                            branch_order["same_selected_action"]))
dump(out / "branch_order_report.json", branch_order)
checks["clone_isolation_pass"] = all(
    not row["invariants"]["live_engine_mutated"]
    for row in forward["branches"] if row["valid"])
checks["branch_order_invariance_pass"] = branch_order["pass"]

def traffic_trace(future):
    return helpers.PiecewiseConstantTrafficTrace(("f",), (
        helpers.TrafficSegment(0.0, 1.0, {"f": 2*helpers.GBIT}, "current"),
        helpers.TrafficSegment(1.0, 30.0, {"f": future}, "future"),
    ))

firewall_rows = []
for future in (0.0, 9*helpers.GBIT):
    e, _, _, p, c = helpers.bbm_environment(trace=traffic_trace(future))
    firewall_rows.append(c.evaluate_root_actions(
        controller_visible_state(e), helpers.public(p), {}))
forecast_firewall = {
    "schema": "gate_f2_forecast_firewall_report_v1",
    "realized_future_rates_bit_s": [0.0, 9*helpers.GBIT],
    "observed_current_lambda_bit_s": firewall_rows[0]["current_lambda_bit_s"],
    "forecast_hashes": [row["forecast_sha256"] for row in firewall_rows],
    "hold_J_H_bit_s": [row["HOLD_J_H_bit_s"] for row in firewall_rows],
    "same_forecast_hash": (firewall_rows[0]["forecast_sha256"]
                           == firewall_rows[1]["forecast_sha256"]),
    "same_rollout_score": (firewall_rows[0]["HOLD_J_H_bit_s"]
                           == firewall_rows[1]["HOLD_J_H_bit_s"]),
    "realized_future_trace_access": False,
}
forecast_firewall["pass"] = all((
    forecast_firewall["same_forecast_hash"],
    forecast_firewall["same_rollout_score"],
    forecast_firewall["observed_current_lambda_bit_s"] == {"f": 2*helpers.GBIT},
))
dump(out / "forecast_firewall_report.json", forecast_firewall)
checks["forecast_firewall_pass"] = forecast_firewall["pass"]

e, _, _, p, c = helpers.bbm_environment()
s = controller_visible_state(e)
replay1 = c.evaluate_root_actions(s, helpers.public(p), {})
replay2 = c.evaluate_root_actions(s, helpers.public(p), {})
deterministic = {
    "schema": "gate_f2_deterministic_replay_report_v1",
    "first_decision_sha256": replay1["decision_sha256"],
    "second_decision_sha256": replay2["decision_sha256"],
    "same": replay1["decision_sha256"] == replay2["decision_sha256"],
}
deterministic["pass"] = deterministic["same"]
dump(out / "deterministic_replay_report.json", deterministic)
checks["deterministic_replay_pass"] = deterministic["pass"]

e, _, _, p, c = helpers.bbm_environment(
    rate=10*helpers.GBIT, setup=2.0, decision_time=1.0)
s = controller_visible_state(e)
b1 = helpers.IgnoreSetupDynamicController(e).observe(s, helpers.public(p), {})
b4 = c.observe(s, helpers.public(p), {})
fixture_report = {
    "schema": "gate_f2_rollout_fixture_report_v1",
    "new_test_count": new_count,
    "exact_J_H_source": "engine objective delta J(t+10)-J(t)",
    "historical_J_cancelled": True,
    "post_horizon_drain": False,
    "terminal_penalty": False,
    "mechanism_separation_fixture": {
        "status": "CORRECTNESS_ONLY_NOT_PERFORMANCE",
        "B1_action": b1.kind,
        "B4_action": b4.kind,
        "expected": "B1_REPLACE_B4_HOLD",
        "pass": b1.kind == "REPLACE" and b4.kind == "HOLD",
    },
    "root_action_only": True,
    "recursive_B4": False,
}
fixture_report["pass"] = all((
    checks["new_F2_correctness_tests_pass"],
    fixture_report["mechanism_separation_fixture"]["pass"],
))
dump(out / "rollout_fixture_report.json", fixture_report)
checks["mechanism_separation_fixture_pass"] = fixture_report["pass"]

sanity = run_160_b4_semantic_sanity()
dump(out / "semantic_sanity_160star.json", sanity)
checks["limited_160star_semantic_sanity_pass"] = sanity["pass"]

full_code, full_text = run_command([
    sys.executable, "-m", "unittest", "discover", "-s", "tests",
    "-p", "test_*.py", "-v"])
(out / "full_regression.txt").write_text(full_text, encoding="utf-8")
full_count = count_tests(full_text)
checks["full_regression_pass"] = full_code == 0 and full_count > 0

implementation_text = (PROJECT / "src/dynamic_lisl/rollout_controller.py").read_text(
    encoding="utf-8")
evaluator_text = (PROJECT / "src/dynamic_lisl/rollout_evaluator.py").read_text(
    encoding="utf-8")
checks["root_action_only_implementation_present"] = all((
    "ROOT_ACTION" in implementation_text,
    "multi_step_future_controller_actions = False" in implementation_text,
    "recursive" not in implementation_text.lower(),
))
checks["exact_objective_delta_implementation_present"] = all((
    "final-start" in evaluator_text,
    "objective_by_commodity" in evaluator_text,
    "advance_to(end)" in evaluator_text,
))
checks["no_artificial_terminal_cost"] = not any(token in evaluator_text for token in (
    "V_v2", "terminal_penalty", "switch_penalty", "setup_penalty"))
checks["no_performance_tuning_or_F3_RL"] = all((
    not (PROJECT / "configs/gate_f3_status.json").exists(),
    not (PROJECT / "configs/gate_f3_closure_status.json").exists(),
    not any((PROJECT / "outputs").glob("gate_f3_performance_*")),
    not any((PROJECT / "outputs").glob("gate_f2_performance_*")),
))

parent_post = {group: {name: sha(name) for name in records}
               for group, records in parent_expected.items()}
zero_post = {name: sha(name) for name in F2_ZERO_ASSETS}
a_to_e2_post = {name: sha(name) for name in a_to_e2["files"]}
checks["declared_parent_hashes_unchanged_post"] = parent_post == parent_expected
checks["f2_0_assets_unchanged_post"] = zero_post == F2_ZERO_ASSETS
checks["a_to_e2_148_hashes_unchanged_post"] = a_to_e2_post == a_to_e2["files"]

passed = all(checks.values())
statement = "Gate F2 overall = PASS" if passed else "Gate F2 overall = FAIL"
report = {
    "schema": "gate_f2_closure_report_v1",
    "checks": checks,
    "gate_f2_rollout_contract": "PASS" if passed else "FAIL",
    "B4_implementation": "PASS" if passed else "FAIL",
    "B4_correctness_fixtures": "PASS" if checks["new_F2_correctness_tests_pass"] else "FAIL",
    "clone_isolation": "PASS" if checks["clone_isolation_pass"] else "FAIL",
    "branch_order_invariance": "PASS" if checks["branch_order_invariance_pass"] else "FAIL",
    "forecast_firewall": "PASS" if checks["forecast_firewall_pass"] else "FAIL",
    "root_action_only_semantics": "PASS" if checks["root_action_only_implementation_present"] else "FAIL",
    "J_H_horizon_objective": "PASS" if checks["exact_objective_delta_implementation_present"] else "FAIL",
    "deterministic_replay": "PASS" if checks["deterministic_replay_pass"] else "FAIL",
    "statement": statement,
    "gate_f2_closure": "YES" if passed else "NO",
    "F3_readiness": "READY" if passed else "NOT_READY",
    "F3_started": False,
    "RL_started": False,
    "new_F2_test_count": new_count,
    "relevant_regression_count": relevant_count,
    "full_regression_count": full_count,
    "full_regression_status": "PASS" if checks["full_regression_pass"] else "FAIL",
    "limited_160star_semantic_sanity": "PASS" if sanity["pass"] else "FAIL",
    "natural_B4_selected_action": sanity["selected_action"],
    "natural_action_interpretation": "SEMANTIC_SANITY_ONLY_NOT_PERFORMANCE",
    "frozen_parent_hash_status": "UNCHANGED" if all((
        checks["declared_parent_hashes_unchanged_post"],
        checks["f2_0_assets_unchanged_post"],
        checks["a_to_e2_148_hashes_unchanged_post"])) else "CHANGED",
    "f2_0_canonical_sha256": F2_CANONICAL,
    "controller_performance_comparison_run": False,
}
dump(out / "report.json", report)
dump(out / "frozen_hash_report.json", {
    "parent_expected": parent_expected,
    "parent_actual_pre": parent_pre,
    "parent_actual_post": parent_post,
    "f2_0_expected": F2_ZERO_ASSETS,
    "f2_0_pre": zero_pre,
    "f2_0_post": zero_post,
    "a_to_e2_file_count": len(a_to_e2["files"]),
    "a_to_e2_pre": a_to_e2_pre,
    "a_to_e2_post": a_to_e2_post,
    "all_unchanged": all((parent_post == parent_expected,
                           zero_post == F2_ZERO_ASSETS,
                           a_to_e2_post == a_to_e2["files"])),
    "f2_0_canonical_sha256": F2_CANONICAL,
})

implementation_status = {
    "schema": "gate_f2_implementation_status_v1",
    "B4_implementation": "PASS" if passed else "FAIL",
    "B4_correctness_fixtures": "PASS" if checks["new_F2_correctness_tests_pass"] else "FAIL",
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "controller_performance_comparison_run": False,
    "F3_started": False,
    "RL_started": False,
}
closure_status = {
    "schema": "gate_f2_closure_status_v1",
    "statement": statement,
    "gate_f2_overall": "PASS" if passed else "FAIL",
    "gate_f2_closure": "YES" if passed else "NO",
    "F3_readiness": "READY" if passed else "NOT_READY",
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "F3_started": False,
    "RL_started": False,
}
dump(PROJECT / "configs/gate_f2_implementation_status.json", implementation_status)
dump(PROJECT / "configs/gate_f2_closure_status.json", closure_status)

closure_doc = f"""# Gate F2 Closure Result

## 正式状态

- Gate F2 rollout contract = {report['gate_f2_rollout_contract']}
- B4 implementation = {report['B4_implementation']}
- B4 correctness fixtures = {report['B4_correctness_fixtures']}
- clone isolation = {report['clone_isolation']}
- branch-order invariance = {report['branch_order_invariance']}
- forecast firewall = {report['forecast_firewall']}
- root-action-only semantics = {report['root_action_only_semantics']}
- J_H horizon objective = {report['J_H_horizon_objective']}
- deterministic replay = {report['deterministic_replay']}
- Gate F2 overall = {closure_status['gate_f2_overall']}
- Gate F2 closure = {closure_status['gate_f2_closure']}
- F3 readiness = {closure_status['F3_readiness']}
- F3/RL started = false

## 验证证据

新增 F2 correctness tests 共 {new_count} 项；相关 Gate B/C/D1/D2/F1 回归共 {relevant_count} 项；完整项目回归共 {full_count} 项。限定 160 星自然几何 sanity 为 {report['limited_160star_semantic_sanity']}，自然案例选择 `{sanity['selected_action']}`，该结果只用于语义验证，不构成控制器性能结论。

F2-0 canonical SHA-256 保持 `{F2_CANONICAL}`。148 个 A–E2 文件以及 F0、F1、Scoring v2、F2-0、Z_MODERATE 父资产哈希前后保持不变。

本 Gate 未运行 B0–B4 性能比较、参数优化、F3 实验或 RL/PPO。
"""
(PROJECT / "docs/GATE_F2_CLOSURE_RESULT_CN.md").write_text(
    closure_doc, encoding="utf-8")

artifact_names = (
    "src/dynamic_lisl/forecast.py",
    "src/dynamic_lisl/rollout_evaluator.py",
    "src/dynamic_lisl/rollout_controller.py",
    "src/dynamic_lisl/gate_f2_sanity.py",
    "tests/test_gate_f2_rollout.py",
    "docs/GATE_F2_B4_IMPLEMENTATION_CN.md",
    "docs/GATE_F2_CLOSURE_RESULT_CN.md",
    "configs/gate_f2_implementation_status.json",
    "configs/gate_f2_closure_status.json",
    "tools/check_gate_f2_closure.py",
)
dump(out / "artifact_hashes.json", {name: sha(name) for name in artifact_names})

print("Gate F2 rollout contract = " + report["gate_f2_rollout_contract"])
print("B4 implementation = " + report["B4_implementation"])
print("B4 correctness fixtures = " + report["B4_correctness_fixtures"])
print("clone isolation = " + report["clone_isolation"])
print("branch-order invariance = " + report["branch_order_invariance"])
print("forecast firewall = " + report["forecast_firewall"])
print("root-action-only semantics = " + report["root_action_only_semantics"])
print("J_H horizon objective = " + report["J_H_horizon_objective"])
print("deterministic replay = " + report["deterministic_replay"])
print(statement)
print("Gate F2 closure = " + closure_status["gate_f2_closure"])
print("F3 readiness = " + closure_status["F3_readiness"])
print("F3 started = false")
print("RL started = false")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
if not passed:
    print("FAILED_CHECKS=" + ",".join(name for name, ok in checks.items() if not ok))
    raise SystemExit(1)

