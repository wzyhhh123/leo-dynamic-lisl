"""Validate Gate F1 Scoring Human Freeze v2 without running controllers."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.gate_d2_fixtures import ConstantDelay
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine


OVERLAY = "configs/gate_f1_scoring_human_freeze_v2.json"


def read(name):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()


def canonical_sha(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def build_fixture():
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
        state_tolerance_bits=0.01,
    )


def fixture_snapshot(time_s):
    engine = build_fixture().advance_to(time_s)
    external = engine.trace.rate_at(engine.now)
    inputs = engine._inputs(external)
    # This calls the existing D2 demand builder and existing shared allocator.
    rates = engine._allocate_service(inputs)
    demand_nodes = []
    for node, commodity_id in sorted(
            {key for key, value in engine.queues.bits.items() if value > 1e-12}
            | {key for key, value in inputs.items() if value > 1e-15}):
        commodity = engine.by_id[commodity_id]
        if node == commodity.destination:
            continue
        edge = engine.next_hop[(node, commodity_id)]
        if edge is None:
            continue
        backlog = engine.queues.get(node, commodity_id)
        demand = math.inf if backlog > engine.state_tol else inputs[(node, commodity_id)]
        if demand > 1e-15:
            demand_nodes.append(node)

    route = engine.routes[("A", "f")]
    propagation_cost = sum(float(engine.delay((a, b), engine.now))
                           for a, b in zip(route, route[1:]))
    n_f = engine.arrived["f"] - engine.delivered["f"]
    allocations = [rate for (edge, commodity_id), rate in sorted(rates.items())
                   if commodity_id == "f" and edge[0] in demand_nodes]
    if demand_nodes:
        r_snap = min(allocations) if allocations else 0.0
        psi = n_f * n_f / (2.0 * r_snap) if r_snap > 0.0 else math.inf
    else:
        r_snap = None
        psi = 0.0
    value = n_f * propagation_cost + psi
    return {
        "time_s": engine.now,
        "Q_f_bits": engine.queues.total("f"),
        "lambda_f_bit_s": external["f"],
        "I_f_bits": engine.in_flight.total("f"),
        "N_f_bits": n_f,
        "route": list(route) if route else None,
        "current_inputs_bit_s": {
            node + "|" + key: value
            for (node, key), value in sorted(inputs.items()) if value > 0.0
        },
        "D_f_nodes": demand_nodes,
        "service_rates_bit_s": {
            edge[0] + "->" + edge[1] + "|" + key: value
            for (edge, key), value in sorted(rates.items()) if value > 0.0
        },
        "R_f_snap_bit_s": r_snap,
        "Psi_f_bit_s": psi,
        "C_f_prop_s": propagation_cost,
        "V_v2_bit_s": value,
        "finite_value": math.isfinite(value),
    }


overlay = read(OVERLAY)
payload = dict(overlay)
expected_overlay_sha = payload.pop("canonical_sha256")
checks = {}
checks["schema_exact"] = overlay.get("schema") == "gate_f1_scoring_human_freeze_v2"
checks["immutable_frozen_overlay"] = (
    overlay.get("immutable_overlay") is True
    and overlay.get("overlay_status") == "FROZEN")
checks["canonical_sha256_correct"] = canonical_sha(payload) == expected_overlay_sha

parent_expected = overlay["parent_hashes"]
parent_pre = {group: {name: sha(name) for name in records}
              for group, records in parent_expected.items()}
checks["all_declared_parent_hashes_unchanged"] = parent_pre == parent_expected
checks["v1_canonical_sha_referenced"] = (
    overlay["versioning"]["parent_v1_canonical_sha256"]
    == "afb031e5da8e988aadd081c83b2d2910a01bf87226c07f2938d2e6d541ca3955")

a_to_e2 = read("configs/gate_f0_frozen_a_to_e2_hashes.json")
a_to_e2_actual = {name: sha(name) for name in a_to_e2["files"]}
checks["all_a_to_e2_frozen_hashes_unchanged"] = a_to_e2_actual == a_to_e2["files"]

supersedes = overlay["versioning"]["supersedes_only"]
checks["supersession_scope_exact"] = supersedes == [
    "v1 F_active(t)", "v1 n_e(G,t)", "v1 r_e_f(G,t)=C_e/n_e(G,t)",
    "v1 R_f service-participation semantics"]

scheduler = overlay["scheduler_consistent_snapshot"]
checks["node_local_scheduler_semantics_frozen"] = (
    scheduler["global_active_commodity_set"] is False
    and scheduler["aggregate_I_f_is_service_demand_indicator"] is False
    and scheduler["allocator"]
        == "dynamic_lisl.service_scheduler.equal_weight_fair_share"
    and scheduler["allocator_reimplementation_forbidden"] is True)
numerical = overlay["numerical_semantics"]
checks["existing_numerical_tolerances_reused"] = (
    numerical["queue_key_scan_tolerance_bits"] == 1e-12
    and numerical["queue_backlog_tolerance_source"] == "engine.state_tolerance_bits"
    and numerical["gate_d0_state_tolerance_bits"] == 0.01
    and numerical["input_tolerance_bit_s"] == 1e-15
    and numerical["new_threshold_introduced"] is False)

definitions = overlay["definitions"]
checks["unfinished_work_preserved"] = (
    definitions["unfinished_work"]["formula"]
    == "A_f(t) - D_f(t) = sum_i Q_i^f(t) + sum_e I_e^f(t)")
checks["propagation_cost_preserved"] = (
    definitions["propagation_cost"]["formula"]
    == "sum_{e in P_f(G,t)} d_e(t)/c")
checks["node_local_current_demand_set"] = (
    definitions["commodity_current_demand_nodes"]
    ["node_local_not_global_commodity_active_set"] is True)
checks["scheduler_service_proxy_exact"] = (
    definitions["current_service_bottleneck_snapshot"]["formula"]
    == "min_{i in D_f(G,t)} mu_i_f(G,t)")
checks["inflight_only_edge_rule_exact"] = (
    definitions["service_area_term"]["when_current_demand_empty"] == "0"
    and overlay["edge_rules"]["route_exists_but_current_demand_empty"]
        == "Psi_f=0 and do not invent R_f_snap")
checks["v2_value_exact"] = definitions["snapshot_value"] == {
    "symbol": "V_v2(G,t)",
    "formula": "sum_{f:N_f(t)>0} [N_f(t)*C_f_prop(G,t) + Psi_f(G,t)]",
    "optimization_direction": "MINIMIZE",
}

b1, b2, b3 = overlay["B1"], overlay["B2"], overlay["B3"]
checks["B1_preserved"] = (
    b1["selection"] == "argmin over HOLD and all candidates"
    and b1["candidate_decision_setup_s"] == 0.0
    and b1["real_replace_execution"] == "REAL_GATE_B_C_SETUP")
checks["B2_preserved"] = b2["base_signal_formula"] == "V_H - V_c"
checks["B3_preserved"] = (
    b3["economic_reject_rule"] == "DeltaV_c <= 0"
    and b3["lifetime_fraction_formula"] == "L_usable,c / L_remaining,c"
    and b3["score_formula"] == "DeltaV_c * eta_c"
    and b3["selection"] == "candidate with maximum positive S_c; otherwise HOLD")

gap_first = fixture_snapshot(0.75)
arrival_first = fixture_snapshot(1.25)
gap_second = fixture_snapshot(0.75)
arrival_second = fixture_snapshot(1.25)
checks["pure_propagation_fixture"] = all((
    gap_first["Q_f_bits"] == 0.0,
    gap_first["lambda_f_bit_s"] == 0.0,
    gap_first["I_f_bits"] > 0.0,
    gap_first["D_f_nodes"] == [],
    gap_first["R_f_snap_bit_s"] is None,
    gap_first["Psi_f_bit_s"] == 0.0,
    gap_first["finite_value"] is True,
))
checks["downstream_arrival_fixture"] = all((
    arrival_first["Q_f_bits"] == 0.0,
    arrival_first["lambda_f_bit_s"] == 0.0,
    arrival_first["I_f_bits"] > 0.0,
    arrival_first["current_inputs_bit_s"] == {"B|f": 1.0},
    arrival_first["D_f_nodes"] == ["B"],
    arrival_first["service_rates_bit_s"] == {"B->C|f": 1.0},
    arrival_first["R_f_snap_bit_s"] == 1.0,
    arrival_first["finite_value"] is True,
))
checks["no_division_by_zero"] = (
    gap_first["Psi_f_bit_s"] == 0.0
    and arrival_first["R_f_snap_bit_s"] > 0.0)
checks["deterministic_fixture_replay"] = (
    gap_first == gap_second and arrival_first == arrival_second)
checks["no_global_F_active_required"] = (
    "active_commodities" not in definitions
    and scheduler["global_active_commodity_set"] is False)

semantics = overlay["evaluation_semantics"]
checks["current_state_proxy_not_rollout"] = all((
    semantics["information_class"] == "CURRENT_STATE_ONLY",
    semantics["analytic_snapshot_only"] is True,
    semantics["advance_simulation_time"] is False,
    semantics["multi_step_rollout"] is False,
    semantics["final_J"] is False,
    semantics["aggregate_unfinished_work_proxy"] is True,
))

scope = overlay["scope_guard"]
current = read("configs/current.json")
f1_status = read("configs/gate_f1_status.json")
checks["scientific_implementation_unmodified"] = (
    scope["modify_B1_B2_B3_scientific_implementation"] is False
    and parent_pre["gate_f1_implementation"]
        == parent_expected["gate_f1_implementation"])
checks["controller_performance_not_run"] = scope["controller_performance_run"] is False
checks["later_gates_not_started"] = all((
    scope["gate_f2_started"] is False,
    scope["gate_f3_started"] is False,
    scope["rl_started"] is False,
    current.get("gate_f2_started") is False,
    current.get("gate_f3_started") is False,
    current.get("rl_started") is False,
    f1_status.get("gate_f2_started") is False,
    f1_status.get("gate_f3_started") is False,
    f1_status.get("rl_started") is False,
))
checks["no_f2_f3_status_assets"] = not any((PROJECT / name).exists() for name in (
    "configs/gate_f2_status.json", "configs/gate_f3_status.json"))

parent_post = {group: {name: sha(name) for name in records}
               for group, records in parent_expected.items()}
checks["all_parent_hashes_unchanged_post"] = parent_post == parent_expected
checks["all_a_to_e2_hashes_unchanged_post"] = (
    {name: sha(name) for name in a_to_e2["files"]} == a_to_e2["files"])

passed = all(checks.values())
timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT / "outputs" / f"gate_f1_scoring_human_freeze_v2_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

dump(out / "compatibility_fixture.json", {
    "schema": "gate_f1_scoring_v2_compatibility_fixture_v1",
    "pure_propagation_gap": gap_first,
    "downstream_arrival_stream": arrival_first,
    "deterministic_replay": checks["deterministic_fixture_replay"],
    "existing_D2_allocator_path_used": True,
    "global_F_active_used": False,
    "performance_experiment": False,
})
dump(out / "formula_audit.json", {
    "schema": "gate_f1_scoring_formula_audit_v2",
    "checks": checks,
    "superseded_v1_definitions": supersedes,
    "preserved_baseline_ladder": overlay["versioning"]["preserves"],
    "proxy_interpretation": overlay["evaluation_semantics"],
})
dump(out / "frozen_hash_report.json", {
    "parent_expected": parent_expected,
    "parent_actual_pre": parent_pre,
    "parent_actual_post": parent_post,
    "a_to_e2_file_count": len(a_to_e2["files"]),
    "a_to_e2_all_unchanged": checks["all_a_to_e2_hashes_unchanged_post"],
    "all_declared_parents_unchanged": parent_post == parent_expected,
    "overlay_canonical_sha256": expected_overlay_sha,
    "overlay_file_sha256": sha(OVERLAY),
})

statement = ("Gate F1 Scoring Human Freeze v2 = PASS" if passed
             else "Gate F1 Scoring Human Freeze v2 = FAIL")
report = {
    "schema": "gate_f1_scoring_human_freeze_v2_report",
    "statement": statement,
    "checks": checks,
    "overlay_canonical_sha256": expected_overlay_sha,
    "scheduler_semantics_aligned": passed,
    "inflight_only_edge_case_resolved": passed,
    "B1_B2_B3_scientific_implementation_readiness": "READY" if passed else "NOT_READY",
    "B1_B2_B3_scientific_implementation_modified": False,
    "controller_performance_run": False,
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(out / "report.json", report)
dump(out / "artifact_hashes.json", {
    name: sha(name) for name in (
        "docs/GATE_F1_SCORING_HUMAN_FREEZE_V2_CN.md",
        OVERLAY,
        "tools/check_gate_f1_scoring_human_freeze_v2.py",
    )
})

status = {
    "gate_f1_scoring_human_freeze_v2": "PASS" if passed else "FAIL",
    "statement": statement,
    "overlay": OVERLAY,
    "overlay_canonical_sha256": expected_overlay_sha,
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "scheduler_semantics_aligned": passed,
    "inflight_only_edge_case_resolved": passed,
    "B1_B2_B3_scientific_implementation_readiness": "READY" if passed else "NOT_READY",
    "B1_B2_B3_scientific_implementation_modified": False,
    "controller_performance_run": False,
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(PROJECT / "configs/gate_f1_scoring_human_freeze_v2_status.json", status)

print(statement)
print(f"scheduler_semantics_aligned = {str(passed).lower()}")
print(f"inflight_only_edge_case_resolved = {str(passed).lower()}")
print("B1_B2_B3_scientific_implementation_readiness = "
      + ("READY" if passed else "NOT_READY"))
print("F2 started = false")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
if not passed:
    failed = [name for name, ok in checks.items() if not ok]
    print("FAILED_CHECKS=" + ",".join(failed))
    raise SystemExit(1)
