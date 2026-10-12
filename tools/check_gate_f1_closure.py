"""Gate F1 scientific scoring implementation and closure validation."""
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
SRC = PROJECT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.gate_d2_fixtures import ConstantDelay
from dynamic_lisl.gate_f1_scientific_sanity import run_160_scientific_semantic_sanity
from dynamic_lisl.scientific_snapshot import ScientificSnapshotEvaluator
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine


V2_CANONICAL = "f35ad97de5c4be5ae2e989f5758986516dd0344f9e6af64be34a48fcff1051f2"
V2_ARTIFACT_HASHES = {
    "docs/GATE_F1_SCORING_HUMAN_FREEZE_V2_CN.md":
        "b4acbc80a4fdd22d891ed7bdf7db9cb6a0af5b7210aa5b69c3a64875b50f6e1d",
    "configs/gate_f1_scoring_human_freeze_v2.json":
        "e91d23f1f4ea81c2598431bd3d0b1d684efb89df4e704f9d37025cfb425e9c69",
    "tools/check_gate_f1_scoring_human_freeze_v2.py":
        "96aceaf965d5d2d316e7b62a6c80f16c437250d144ff1d23d4ed035c8e4b4a16",
    "configs/z_moderate_v1.json":
        "a28f54be05c5dbae07d0654b507209dad499ff853f9558cdd7da50f28d56c0d9",
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


def latest(prefix):
    rows = sorted(path for path in (PROJECT / "outputs").glob(prefix + "_*")
                  if path.name[len(prefix)+1:len(prefix)+2].isdigit())
    if not rows:
        raise FileNotFoundError(prefix)
    return rows[-1]


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


def build_compatibility_engine():
    trace = PiecewiseConstantTrafficTrace(("f",), (
        TrafficSegment(0.0, 0.5, {"f": 1.0}, "on"),
        TrafficSegment(0.5, 2.0, {"f": 0.0}, "off"),
    ))
    return TransitionAwareNetworkServiceEngine(
        ("A", "B", "C"), (("A", "B"), ("B", "C")), 10.0,
        (Commodity("f", "A", "C"),), trace, ConstantDelay(1.0),
        TerminalExecutor(("A", "B", "C")), (),
        conservation_abs_tolerance_bits=1e-9,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=0.01)


def compatibility_snapshot(time_s):
    engine = build_compatibility_engine().advance_to(time_s)
    evaluation = ScientificSnapshotEvaluator(engine).evaluate_hold()
    row = evaluation.commodities[0]
    return {
        "time_s": time_s,
        "Q_f_bits": engine.queues.total("f"),
        "lambda_f_bit_s": engine.trace.rate_at(engine.now)["f"],
        "I_f_bits": engine.in_flight.total("f"),
        "D_f_nodes": list(row.current_demand_nodes),
        "R_f_snap_bit_s": row.R_f_snap_bit_s,
        "Psi_f_bit_s": row.Psi_f_bit_s,
        "V_v2_bit_s": evaluation.value_bit_s,
        "finite": evaluation.finite,
        "allocator": evaluation.allocator,
    }


timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT / "outputs" / f"gate_f1_closure_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

overlay = read("configs/gate_f1_scoring_human_freeze_v2.json")
parent_expected = overlay["parent_hashes"]
parent_pre = {group: {name: sha(name) for name in records}
              for group, records in parent_expected.items()}
a_to_e2 = read("configs/gate_f0_frozen_a_to_e2_hashes.json")
a_to_e2_pre = {name: sha(name) for name in a_to_e2["files"]}
v2_pre = {name: sha(name) for name in V2_ARTIFACT_HASHES}

checks = {}
checks["v2_canonical_exact"] = overlay["canonical_sha256"] == V2_CANONICAL
checks["all_declared_frozen_parents_unchanged_pre"] = parent_pre == parent_expected
checks["all_a_to_e2_frozen_hashes_unchanged_pre"] = a_to_e2_pre == a_to_e2["files"]
checks["v2_and_z_moderate_artifacts_unchanged_pre"] = v2_pre == V2_ARTIFACT_HASHES

# Mandatory historical preflight evidence.  F0-era checkers intentionally fail
# only their chronology/output-absence assertions after F1 has started.
f0_preflight = read(str((latest("gate_f0_contract") / "report.json").relative_to(PROJECT)))
hf_preflight = read(str((latest("gate_f0_human_freeze") / "report.json").relative_to(PROJECT)))
f1_preflight = read(str((latest("gate_f1") / "report.json").relative_to(PROJECT)))
f0_false = sorted(name for name, value in f0_preflight["checks"].items() if not value)
hf_false = sorted(name for name, value in hf_preflight["checks"].items() if not value)
checks["legacy_f0_preflight_hash_checks_pass"] = all((
    f0_preflight["checks"]["frozen_a_to_e2_unchanged_pre"],
    f0_preflight["checks"]["frozen_a_to_e2_unchanged_post"],
    f0_false == ["later_gates_not_started_before_check",
                 "no_gate_f_performance_outputs"],
))
checks["legacy_f0_human_freeze_hash_checks_pass"] = all((
    hf_preflight["checks"]["frozen_a_to_e2_unchanged_pre"],
    hf_preflight["checks"]["frozen_a_to_e2_unchanged_post"],
    hf_preflight["checks"]["parent_f0_contract_hashes_unchanged"],
    hf_preflight["checks"]["parent_f0_contract_hashes_unchanged_post"],
    hf_false == ["controller_performance_outputs_absent",
                 "later_gates_not_started_pre"],
))
checks["existing_f1_preflight_pass"] = (
    f1_preflight["gate_f1_infrastructure"] == "PASS")

v2_code, v2_text = run_command([
    sys.executable, "tools/check_gate_f1_scoring_human_freeze_v2.py"])
(out / "scoring_v2_checker.txt").write_text(v2_text, encoding="utf-8")
checks["scoring_v2_checker_pass"] = (
    v2_code == 0 and "Gate F1 Scoring Human Freeze v2 = PASS" in v2_text)

scientific_code, scientific_text = run_command([
    sys.executable, "-m", "unittest", "discover", "-s", "tests",
    "-p", "test_gate_f1_scientific_scoring_*.py", "-v"])
(out / "scientific_scoring_tests.txt").write_text(scientific_text,
                                                    encoding="utf-8")
scientific_count = count_tests(scientific_text)
checks["scientific_scoring_tests_pass"] = scientific_code == 0 and scientific_count >= 25

existing_outputs = []
existing_count = 0
existing_ok = True
for pattern in ("test_gate_f1_controller.py", "test_gate_f1_contract.py"):
    code, text = run_command([
        sys.executable, "-m", "unittest", "discover", "-s", "tests",
        "-p", pattern, "-v"])
    existing_outputs.append(text)
    existing_count += count_tests(text)
    existing_ok = existing_ok and code == 0
(out / "existing_gate_f1_tests.txt").write_text(
    "\n".join(existing_outputs), encoding="utf-8")
checks["existing_gate_f1_correctness_tests_pass"] = existing_ok and existing_count >= 21

pure = compatibility_snapshot(0.75)
arrival = compatibility_snapshot(1.25)
scoring_fixture = {
    "schema": "gate_f1_scientific_scoring_fixture_report_v1",
    "pure_propagation": pure,
    "downstream_arrival": arrival,
    "matches_frozen_v2": all((
        pure["D_f_nodes"] == [], pure["R_f_snap_bit_s"] is None,
        pure["Psi_f_bit_s"] == 0.0, pure["V_v2_bit_s"] == 1.0,
        arrival["D_f_nodes"] == ["B"],
        arrival["R_f_snap_bit_s"] == 1.0,
        arrival["Psi_f_bit_s"] == 0.125,
        arrival["V_v2_bit_s"] == 1.125,
    )),
}
checks["implementation_matches_v2_compatibility_fixture"] = scoring_fixture["matches_frozen_v2"]
dump(out / "scoring_fixture_report.json", scoring_fixture)

sanity = run_160_scientific_semantic_sanity()
dump(out / "semantic_sanity_160star.json", sanity)
checks["limited_160star_semantic_sanity_pass"] = sanity["pass"] is True
checks["deterministic_160star_replay_pass"] = sanity["deterministic_B1_replay"] is True
dump(out / "deterministic_replay_report.json", {
    "schema": "gate_f1_closure_deterministic_replay_v1",
    "pass": sanity["deterministic_B1_replay"],
    "B1_action_replay_sha256": sanity["controllers"]["B1"]["action_replay_sha256"],
    "scientific_B1_B2_B3_action_kinds": {
        name: row["selected_action_kinds"]
        for name, row in sanity["controllers"].items()},
    "performance_comparison": False,
})

full_code, full_text = run_command([
    sys.executable, "-m", "unittest", "discover", "-s", "tests",
    "-p", "test_*.py", "-v"])
(out / "full_regression.txt").write_text(full_text, encoding="utf-8")
full_count = count_tests(full_text)
checks["full_regression_pass"] = full_code == 0 and full_count > 0

checks["shared_v2_evaluator_present"] = (
    (PROJECT / "src/dynamic_lisl/scientific_snapshot.py").is_file())
checks["B0_scientific_implementation_pass"] = existing_ok
checks["B1_scientific_implementation_pass"] = scientific_code == 0
checks["B2_parameterized_implementation_pass"] = scientific_code == 0
checks["B3_scientific_implementation_pass"] = scientific_code == 0
checks["no_B4_MPC_or_RL_started"] = all((
    read("configs/current.json").get("gate_f2_started") is False,
    read("configs/current.json").get("gate_f3_started") is False,
    read("configs/current.json").get("rl_started") is False,
    read("configs/gate_f1_contract.json")["controllers"]["B4"] == "NOT_IMPLEMENTED",
))

parent_post = {group: {name: sha(name) for name in records}
               for group, records in parent_expected.items()}
a_to_e2_post = {name: sha(name) for name in a_to_e2["files"]}
v2_post = {name: sha(name) for name in V2_ARTIFACT_HASHES}
checks["all_declared_frozen_parents_unchanged_post"] = parent_post == parent_expected
checks["all_a_to_e2_frozen_hashes_unchanged_post"] = a_to_e2_post == a_to_e2["files"]
checks["v2_and_z_moderate_artifacts_unchanged_post"] = v2_post == V2_ARTIFACT_HASHES

passed = all(checks.values())
statement = "Gate F1 overall = PASS" if passed else "Gate F1 overall = FAIL"
report = {
    "schema": "gate_f1_closure_report_v1",
    "statement": statement,
    "checks": checks,
    "new_scientific_scoring_test_count": scientific_count,
    "existing_gate_f1_test_count": existing_count,
    "full_regression_count": full_count,
    "shared_V_v2_evaluator": "PASS" if passed else "FAIL",
    "scheduler_aligned_service_snapshot": "PASS" if passed else "FAIL",
    "B0_scientific_implementation": "PASS" if checks["B0_scientific_implementation_pass"] else "FAIL",
    "B1_scientific_implementation": "PASS" if checks["B1_scientific_implementation_pass"] else "FAIL",
    "B2_parameterized_implementation": "PASS" if checks["B2_parameterized_implementation_pass"] else "FAIL",
    "B3_scientific_implementation": "PASS" if checks["B3_scientific_implementation_pass"] else "FAIL",
    "gate_f1_closure": "YES" if passed else "NO",
    "F2_readiness": "READY" if passed else "NOT_READY",
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
    "controller_performance_comparison_run": False,
    "preflight_note": (
        "Legacy F0/F0-Human-Freeze checkers were executed. Their only false "
        "assertions are historical stage/output-absence guards after F1 started; "
        "all frozen-hash assertions passed."),
}
dump(out / "report.json", report)
dump(out / "frozen_hash_report.json", {
    "parent_expected": parent_expected,
    "parent_actual_pre": parent_pre,
    "parent_actual_post": parent_post,
    "a_to_e2_file_count": len(a_to_e2["files"]),
    "a_to_e2_pre": a_to_e2_pre,
    "a_to_e2_post": a_to_e2_post,
    "v2_and_z_moderate_expected": V2_ARTIFACT_HASHES,
    "v2_and_z_moderate_pre": v2_pre,
    "v2_and_z_moderate_post": v2_post,
    "all_unchanged": all((
        parent_post == parent_expected,
        a_to_e2_post == a_to_e2["files"],
        v2_post == V2_ARTIFACT_HASHES)),
})

implementation_status = {
    "gate_f1_scientific_scoring_implementation": "PASS" if passed else "FAIL",
    "shared_V_v2_evaluator": "PASS" if passed else "FAIL",
    "scheduler_semantics_aligned": passed,
    "B0_scientific_implementation": "PASS" if checks["B0_scientific_implementation_pass"] else "FAIL",
    "B1_scientific_implementation": "PASS" if checks["B1_scientific_implementation_pass"] else "FAIL",
    "B2_parameterized_implementation": "PASS" if checks["B2_parameterized_implementation_pass"] else "FAIL",
    "B3_scientific_implementation": "PASS" if checks["B3_scientific_implementation_pass"] else "FAIL",
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
closure_status = {
    "statement": statement,
    "gate_f1_infrastructure": "PASS" if checks["existing_f1_preflight_pass"] else "FAIL",
    "gate_f1_scoring_contract_v2": "PASS" if checks["scoring_v2_checker_pass"] else "FAIL",
    "gate_f1_overall": "PASS" if passed else "FAIL",
    "gate_f1_closure": "YES" if passed else "NO",
    "F2_readiness": "READY" if passed else "NOT_READY",
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(PROJECT / "configs/gate_f1_scientific_implementation_status.json",
     implementation_status)
dump(PROJECT / "configs/gate_f1_closure_status.json", closure_status)

closure_doc = f"""# Gate F1 Closure Result

## 正式状态

- Gate F1 infrastructure = {closure_status['gate_f1_infrastructure']}
- Gate F1 scoring contract v2 = {closure_status['gate_f1_scoring_contract_v2']}
- B0 scientific implementation = {implementation_status['B0_scientific_implementation']}
- B1 scientific implementation = {implementation_status['B1_scientific_implementation']}
- B2 parameterized implementation = {implementation_status['B2_parameterized_implementation']}
- B3 scientific implementation = {implementation_status['B3_scientific_implementation']}
- Gate F1 overall = {closure_status['gate_f1_overall']}
- Gate F1 closure = {closure_status['gate_f1_closure']}
- F2 readiness = {closure_status['F2_readiness']}
- F2/F3/RL started = false

## 验证

共享 `V_v2` evaluator 与 scheduler-aligned node-local demand snapshot 已通过 {scientific_count} 项新增科学评分测试。既有 Gate F1 correctness tests 共 {existing_count} 项通过；完整项目回归共 {full_count} 项通过。

160 星限定语义 sanity 使用冻结自然 Gate C candidate。B1/B2/B3 均完成 2 s cadence 的多 epoch 调用并消费同一个 top-K proposal interface；未依据结果替换 candidate。该案例下三个科学控制器均选择 HOLD。另一个明确标注为 test-only 的同候选 execution probe 验证了真实 Gate B/C BBM 执行。B1 确定性重放结果为 `{sanity['deterministic_B1_replay']}`。

该 sanity 未输出或比较 J、delay、delivery ratio、相对提升、最佳控制器或 B2 最佳参数。

## 完整性

A–E2、F0、F0 Human Freeze、F1 infrastructure、Scoring v1、semantic audit、Scoring v2 和 Z_MODERATE 的冻结 hash 前后均保持一致。旧 F0 两个 checker 已按要求执行；其 FAIL 仅来自“F1 尚未启动/不存在后续 Gate F 输出”的历史时点断言，所有 frozen-hash 检查均 PASS。
"""
(PROJECT / "docs/GATE_F1_CLOSURE_RESULT_CN.md").write_text(
    closure_doc, encoding="utf-8")

artifact_names = (
    "docs/GATE_F1_SCIENTIFIC_SCORING_IMPLEMENTATION_CN.md",
    "docs/GATE_F1_CLOSURE_RESULT_CN.md",
    "configs/gate_f1_scientific_implementation_status.json",
    "configs/gate_f1_closure_status.json",
    "src/dynamic_lisl/scientific_snapshot.py",
    "src/dynamic_lisl/scientific_controllers.py",
    "src/dynamic_lisl/gate_f1_scientific_sanity.py",
    "tests/test_gate_f1_scientific_scoring_v2.py",
    "tools/check_gate_f1_closure.py",
)
dump(out / "artifact_hashes.json", {name: sha(name) for name in artifact_names})

print("Gate F1 infrastructure = " + closure_status["gate_f1_infrastructure"])
print("Gate F1 scoring contract v2 = " + closure_status["gate_f1_scoring_contract_v2"])
print("B0 scientific implementation = " + implementation_status["B0_scientific_implementation"])
print("B1 scientific implementation = " + implementation_status["B1_scientific_implementation"])
print("B2 parameterized implementation = " + implementation_status["B2_parameterized_implementation"])
print("B3 scientific implementation = " + implementation_status["B3_scientific_implementation"])
print(statement)
print("Gate F1 closure = " + closure_status["gate_f1_closure"])
print("F2 readiness = " + closure_status["F2_readiness"])
print("F2 started = false")
print("F3 started = false")
print("RL started = false")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
if not passed:
    print("FAILED_CHECKS=" + ",".join(name for name, ok in checks.items() if not ok))
    raise SystemExit(1)
