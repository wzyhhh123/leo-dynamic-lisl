"""Validate Gate F1 Scoring Human Freeze v1 without running controllers."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OVERLAY = "configs/gate_f1_scoring_human_freeze_v1.json"


def read(name):
    return json.loads((PROJECT/name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False)+"\n", encoding="utf-8")


overlay = read(OVERLAY)
payload = dict(overlay)
expected_overlay_sha = payload.pop("canonical_sha256")
checks = {}
checks["schema_exact"] = overlay.get("schema") == "gate_f1_scoring_human_freeze_v1"
checks["immutable_frozen_overlay"] = (
    overlay.get("immutable_overlay") is True
    and overlay.get("overlay_status") == "FROZEN")
checks["canonical_sha256_correct"] = canonical_sha(payload) == expected_overlay_sha

parent_actual = {}
parent_expected = {}
for group, records in overlay["parent_hashes"].items():
    parent_actual[group] = {name: sha(name) for name in records}
    parent_expected[group] = records
checks["parent_f1_hashes_unchanged"] = (
    parent_actual["gate_f1"] == parent_expected["gate_f1"])
checks["parent_f1_implementation_hashes_unchanged"] = (
    parent_actual["gate_f1_implementation"]
    == parent_expected["gate_f1_implementation"])
checks["parent_f0_hashes_unchanged"] = (
    parent_actual["gate_f0"] == parent_expected["gate_f0"])
checks["parent_f0_human_freeze_hashes_unchanged"] = (
    parent_actual["gate_f0_human_freeze_v1"]
    == parent_expected["gate_f0_human_freeze_v1"])

definitions = overlay["definitions"]
checks["common_router_recomputed_for_each_topology"] = (
    overlay["common_router_rule"]["same_router_for_hold_and_all_candidates"] is True
    and "recompute paths" in overlay["common_router_rule"]["rule"])
checks["propagation_cost_exact"] = definitions["propagation_cost"] == {
    "symbol": "C_f_prop(G,t)",
    "formula": "sum_{e in P_f(G,t)} d_e(t)/c"}
checks["active_commodities_exact"] = definitions["active_commodities"] == {
    "symbol": "F_active(t)",
    "formula": "{f : sum_i Q_i^f(t) > 0 or lambda_f(t) > 0}"}
checks["directed_active_route_count_exact"] = definitions["active_route_count"] == {
    "symbol": "n_e(G,t)",
    "formula": "number of f in F_active(t) whose recomputed route P_f(G,t) uses directed edge e"}
checks["equal_weight_snapshot_rate_exact"] = (
    definitions["equal_weight_snapshot_edge_rate"]["symbol"] == "r_e_f(G,t)"
    and definitions["equal_weight_snapshot_edge_rate"]["formula"] == "C_e / n_e(G,t)"
    and definitions["equal_weight_snapshot_edge_rate"]["sharing_rule"]
        == "FROZEN_EQUAL_WEIGHT_SNAPSHOT_SHARING")
checks["path_bottleneck_exact"] = definitions["path_bottleneck_rate"] == {
    "symbol": "R_f(G,t)",
    "formula": "min_{e in P_f(G,t)} r_e_f(G,t)"}
checks["unfinished_work_exact"] = definitions["unfinished_work"] == {
    "symbol": "N_f(t)", "formula": "A_f(t) - D_f(t)"}
checks["snapshot_value_exact"] = definitions["snapshot_value"] == {
    "symbol": "V(G,t)",
    "formula": "sum_{f:N_f(t)>0} [N_f(t)*C_f_prop(G,t) + N_f(t)^2/(2*R_f(G,t))]",
    "optimization_direction": "MINIMIZE"}

semantics = overlay["evaluation_semantics"]
checks["current_state_analytic_not_rollout"] = (
    semantics["information_class"] == "CURRENT_STATE_ONLY"
    and semantics["analytic_snapshot_only"] is True
    and semantics["advance_simulation_time"] is False
    and semantics["multi_step_rollout"] is False
    and semantics["final_J"] is False
    and "constant-current-service queue-area proxy" in
        semantics["queue_area_term_interpretation"])

b1 = overlay["B1"]
checks["B1_exact"] = (
    b1["hold_value"] == "V_H = V(G_current,t)"
    and b1["candidate_value"] == "V_c = V(G_c_ideal,t)"
    and b1["candidate_decision_setup_s"] == 0.0
    and b1["zero_setup_scope"] == "DECISION_EVALUATION_ONLY"
    and b1["selection"] == "argmin over HOLD and all candidates"
    and b1["real_replace_execution"] == "REAL_GATE_B_C_SETUP"
    and b1["scalar_score_resolved"] is True)

b2 = overlay["B2"]
checks["B2_exact"] = (
    b2["base_signal_symbol"] == "DeltaV_c"
    and b2["base_signal_formula"] == "V_H - V_c"
    and b2["base_signal_resolved"] is True
    and b2["minimum_hold_grid_frozen_here"] is False
    and b2["hysteresis_grid_frozen_here"] is False)

b3 = overlay["B3"]
checks["B3_exact"] = (
    b3["economic_reject_rule"] == "DeltaV_c <= 0"
    and b3["lifetime_fraction_formula"] == "L_usable,c / L_remaining,c"
    and b3["score_formula"] == "DeltaV_c * eta_c"
    and b3["selection"] ==
        "candidate with maximum positive S_c; otherwise HOLD"
    and b3["scalar_score_resolved"] is True)

edge = overlay["edge_rules"]
checks["edge_rules_exact"] = edge == {
    "zero_total_unfinished_work": "HOLD",
    "unrouted_positive_unfinished_commodity_target_value": "+infinity",
    "nonpositive_R_f_target_value": "+infinity",
    "B3_nonpositive_remaining_or_usable_lifetime": "INELIGIBLE",
    "hold_replace_exact_tie": "HOLD",
    "replace_replace_exact_tie": "FROZEN_PROPOSER_CANONICAL_ORDER",
    "trainable_coefficients": False,
    "alpha_beta_gamma_weights": False,
    "realized_future_traffic": False,
    "performance_based_tuning": False,
}

resolution = overlay["resolution"]
checks["all_three_scores_resolved"] = resolution == {
    "B1_scalar_score_resolved": True,
    "B2_base_signal_resolved": True,
    "B3_scalar_score_resolved": True,
    "gate_f1_scientific_implementation_readiness": "READY",
}
scope = overlay["scope_guard"]
checks["scientific_implementation_not_modified"] = (
    scope["modify_B1_B2_B3_scientific_implementation"] is False
    and checks["parent_f1_implementation_hashes_unchanged"])
checks["controller_performance_not_run"] = (
    scope["controller_performance_run"] is False)

current = read("configs/current.json")
f1_status = read("configs/gate_f1_status.json")
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
checks["no_f2_f3_status_assets"] = not any((PROJECT/name).exists() for name in (
    "configs/gate_f2_status.json", "configs/gate_f3_status.json"))

# Recheck parents after all validation reads.
parent_post = {group: {name: sha(name) for name in records}
               for group, records in overlay["parent_hashes"].items()}
checks["all_parent_hashes_unchanged_post"] = parent_post == parent_expected

passed = all(checks.values())
timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT/"outputs"/f"gate_f1_scoring_human_freeze_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

formula_audit = {
    "schema": "gate_f1_scoring_formula_audit_v1",
    "checks": {key: value for key, value in checks.items()
               if key.endswith("_exact") or key in (
                   "common_router_recomputed_for_each_topology",
                   "current_state_analytic_not_rollout",
                   "all_three_scores_resolved")},
    "interpretation": semantics["queue_area_term_interpretation"],
}
dump(out/"formula_audit.json", formula_audit)
dump(out/"frozen_hash_report.json", {
    "parent_expected": parent_expected,
    "parent_actual_pre": parent_actual,
    "parent_actual_post": parent_post,
    "all_unchanged": parent_post == parent_expected,
    "overlay_canonical_sha256": expected_overlay_sha,
    "overlay_file_sha256": sha(OVERLAY),
})

statement = ("Gate F1 scoring human freeze v1 = PASS" if passed
             else "Gate F1 scoring human freeze v1 = FAIL")
report = {
    "schema": "gate_f1_scoring_human_freeze_report_v1",
    "statement": statement,
    "checks": checks,
    "overlay_canonical_sha256": expected_overlay_sha,
    "B1_scalar_score_resolved": passed,
    "B2_base_signal_resolved": passed,
    "B3_scalar_score_resolved": passed,
    "gate_f1_scientific_implementation_readiness": "READY" if passed else "NOT_READY",
    "B1_B2_B3_scientific_implementation_modified": False,
    "controller_performance_run": False,
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(out/"report.json", report)

artifact_hashes = {
    name: sha(name) for name in (
        "docs/GATE_F1_SCORING_HUMAN_FREEZE_V1_CN.md",
        OVERLAY,
        "tools/check_gate_f1_scoring_human_freeze.py",
    )}
dump(out/"artifact_hashes.json", artifact_hashes)

status = {
    "gate_f1_scoring_human_freeze_v1": "PASS" if passed else "FAIL",
    "statement": statement,
    "overlay": OVERLAY,
    "overlay_canonical_sha256": expected_overlay_sha,
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "B1_scalar_score_resolved": passed,
    "B2_base_signal_resolved": passed,
    "B3_scalar_score_resolved": passed,
    "gate_f1_scientific_implementation_readiness": "READY" if passed else "NOT_READY",
    "gate_f2_started": False,
    "gate_f3_started": False,
    "rl_started": False,
}
dump(PROJECT/"configs/gate_f1_scoring_human_freeze_status.json", status)

print(statement)
print(f"B1_scalar_score_resolved = {str(passed).lower()}")
print(f"B2_base_signal_resolved = {str(passed).lower()}")
print(f"B3_scalar_score_resolved = {str(passed).lower()}")
print("Gate F1 scientific implementation readiness = "
      + ("READY" if passed else "NOT_READY"))
print("F2 started = false")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
if not passed:
    raise SystemExit(1)
