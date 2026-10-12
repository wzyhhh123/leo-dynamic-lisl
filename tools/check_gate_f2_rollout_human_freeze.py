"""Validate Gate F2-0 Rollout/MPC Human Freeze v1 without implementing B4."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
CONTRACT = "configs/gate_f2_rollout_human_freeze_v1.json"


def read(name: str):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


def sha(name: str) -> str:
    return hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()


def canonical_sha(value) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True,
                   ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


contract = read(CONTRACT)
payload = dict(contract)
expected_canonical = payload.pop("canonical_sha256")
checks: dict[str, bool] = {}

checks["schema_exact"] = contract.get("schema") == "gate_f2_rollout_human_freeze_v1"
checks["immutable_frozen_overlay"] = (
    contract.get("immutable_overlay") is True
    and contract.get("overlay_status") == "FROZEN"
    and contract.get("gate") == "F2-0"
)
checks["canonical_sha256_correct"] = canonical_sha(payload) == expected_canonical

parent_expected = contract["parent_hashes"]
parent_pre = {
    group: {name: sha(name) for name in records}
    for group, records in parent_expected.items()
}
checks["all_declared_parent_hashes_unchanged_pre"] = parent_pre == parent_expected

a_to_e2 = read("configs/gate_f0_frozen_a_to_e2_hashes.json")
a_to_e2_pre = {name: sha(name) for name in a_to_e2["files"]}
checks["all_a_to_e2_frozen_hashes_unchanged_pre"] = (
    a_to_e2_pre == a_to_e2["files"]
)

closure = read("configs/gate_f1_closure_status.json")
scientific = read("configs/gate_f1_scientific_implementation_status.json")
scoring_v2 = read("configs/gate_f1_scoring_human_freeze_v2_status.json")
checks["gate_f1_parent_state_ready"] = all((
    closure.get("gate_f1_infrastructure") == "PASS",
    closure.get("gate_f1_scoring_contract_v2") == "PASS",
    closure.get("gate_f1_overall") == "PASS",
    closure.get("gate_f1_closure") == "YES",
    closure.get("F2_readiness") == "READY",
    scientific.get("B0_scientific_implementation") == "PASS",
    scientific.get("B1_scientific_implementation") == "PASS",
    scientific.get("B2_parameterized_implementation") == "PASS",
    scientific.get("B3_scientific_implementation") == "PASS",
    scoring_v2.get("gate_f1_scoring_human_freeze_v2") == "PASS",
))

inputs = contract["frozen_inputs"]
checks["frozen_F2_inputs_exact"] = all((
    inputs["decision_cadence_s"] == 2.0,
    inputs["candidate_top_k"] == 16,
    inputs["maximum_normal_branch_count"] == 17,
    inputs["candidate_strata_slots"] == {
        "MBB_STRUCTURALLY_FEASIBLE": 8,
        "BBM_REQUIRED": 8,
    },
    inputs["information_class"] == "SHORT_HORIZON_FORECAST",
    inputs["traffic_forecast"] == "CURRENT_RATE_PERSISTENCE",
    inputs["forecast_horizon_s"] == 10.0,
    inputs["forecast_update_period_s"] == 2.0,
    inputs["forecast_formula"]
        == "lambda_hat_f(t+tau)=lambda_f(t), 0<=tau<=10s",
    inputs["realized_future_trace_access"] is False,
))
checks["deterministic_future_physics_exact"] = set(
    inputs["allowed_deterministic_future_physics"]
) == {
    "SGP4_Gate_C_geometry",
    "known_candidate_windows",
    "natural_expiry",
    "deterministic_Gate_B_transition_events",
}

branches = contract["branch_set"]
checks["branch_set_unique_and_bounded"] = all((
    branches["hold_branch"] == "A0=HOLD",
    branches["evaluate_every_proposal"] is True,
    branches["additional_candidate_generation_inside_B4"] is False,
    branches["rollout_score_pruning_or_reranking_before_evaluation"] is False,
    branches["maximum_normal_branch_count"] == 17,
    branches["same_canonical_state_required"] is True,
    branches["state_time_convention"] == "RIGHT_CONTINUOUS_AT_DECISION_EPOCH",
))

clone = contract["clone_contract"]
required_clone_fields = {
    "terminal_state", "reservations", "pending_Gate_B_events",
    "G_active", "G_admit", "queues_Q", "in_flight_I",
    "arrival_rate_events", "cumulative_arrived_and_delivered_for_conservation",
    "common_router_configuration", "current_physical_time",
    "Gate_C_geometry_state", "current_candidate_windows",
    "all_deterministic_physical_event_state",
}
checks["same_state_clone_semantics_complete"] = all((
    set(clone["exact_clone_fields"]) == required_clone_fields,
    clone["live_engine_mutation"] is False,
    clone["shared_mutable_objects_between_branches"] is False,
    clone["branch_order_may_affect_scores"] is False,
    clone["future_required_tests"] == [
        "clone_isolation", "branch_order_invariance"],
))

root = contract["root_action_mpc"]
required_evolution = {
    "committed_propagation_events", "Gate_B_terminal_events", "DRAINING",
    "LINK_DOWN", "RETARGETING", "ACQUIRING", "LINK_UP",
    "natural_link_expiry", "deterministic_Gate_C_geometry_and_window_evolution",
    "physical_event_driven_G_active_and_G_admit_changes", "common_routing",
    "service_allocation", "Q_I_D_evolution",
}
checks["root_action_only_semantics_exact"] = all((
    root["semantics"] == "ROOT_ACTION_ONLY_RECEDING_HORIZON",
    root["voluntary_controller_actions_after_root_inside_horizon"] is False,
    root["internal_epochs_s"] == [2.0, 4.0, 6.0, 8.0, 10.0],
    root["internal_epoch_controller_action"] == "HOLD",
    set(root["physical_and_network_evolution_continues"]) == required_evolution,
    root["recursive_B4_calls"] is False,
    root["B1_B2_B3_future_rollout_policy"] is False,
    root["exponential_action_tree"] is False,
))

forecast = contract["forecast_contract"]
checks["current_rate_persistence_no_future_leakage"] = all((
    forecast["branch_start_observation"] == "lambda_f(t) only",
    forecast["branch_local_source"] is True,
    forecast["constant_over_full_horizon"] is True,
    forecast["same_forecast_all_branches"] is True,
    forecast["live_realized_future_segments_consumed"] is False,
    forecast["next_real_epoch_may_observe_new_current_lambda"] is True,
))

objective = contract["objective"]
checks["exact_horizon_objective_frozen"] = all((
    objective["formula"] == "sum_f integral_t^(t+H) N_f^a(tau) d tau",
    objective["horizon_s"] == 10.0,
    objective["unfinished_work"]
        == "N_f=A_f-D_f=sum_i Q_i^f+sum_e I_e^f",
    objective["optimization_direction"] == "MINIMIZE",
    objective["real_network_dynamics_rollout"] is True,
))
checks["no_artificial_objective_terms"] = set(
    objective["forbidden_additions"]
) == {
    "V_v2_terminal_penalty", "topology_score", "setup_penalty",
    "switch_count_penalty", "outage_penalty",
    "artificial_hysteresis_penalty", "learned_value_function",
    "alpha_beta_gamma_weighted_objective",
}

horizon = contract["horizon_boundary"]
checks["horizon_boundary_exact"] = all((
    horizon["end"] == "t+10s",
    horizon["drain_beyond_horizon"] is False,
    horizon["terminal_residual_backlog_penalty"] is False,
    horizon["V_v2_at_horizon"] is False,
    horizon["residual_backlog_role"] == "DIAGNOSTIC_ONLY",
    horizon["finite_horizon_truncation_intentional"] is True,
))

invalidity = contract["branch_invalidity"]
checks["invalid_branch_semantics_exact"] = all((
    invalidity["hold_always_evaluated"] is True,
    invalidity["invalid_score"] == "+infinity",
    invalidity["exact_rejection_reason_required"] is True,
    invalidity["invalid_after_common_proposer"]
        == "PROPOSER_EXECUTOR_CONSISTENCY_DIAGNOSTIC",
    set(invalidity["not_invalid_reasons"]) == {
        "later_natural_expiry", "temporary_route_disappearance",
        "backlog_growth", "delivery_reduction",
        "physically_valid_no_route_interval",
    },
))

selection = contract["selection"]
checks["selection_and_ties_exact"] = selection == {
    "rule": "minimum J_H",
    "hold_vs_replace_exact_tie": "HOLD",
    "replace_vs_replace_exact_tie": "FROZEN_PROPOSER_CANONICAL_ORDER",
    "random_tie_breaking": False,
    "deadband": False,
}

routers = contract["router_fairness"]
checks["common_router_fairness_exact"] = all((
    routers["same_router_for_all_branches"] is True,
    routers["same_router_for_B0_through_B4_in_comparison"] is True,
    routers["primary"] == "DeterministicShortestPropagationDelayRouter",
    routers["robustness"] == "DeterministicCurrentStateLoadAwareRouter",
))

safety = contract["regime_safety"]
checks["regime_safety_exact"] = all((
    safety["Z_SPARSE_REFERENCE"]["policy"]
        == "BOUNDED_TRANSITION_OUTAGE",
    safety["Z_SPARSE_REFERENCE"]["Tmax_s"] == 2.0,
    safety["Z_SPARSE_REFERENCE"]["scope"]
        == "CONTROLLER_INDUCED_TRANSITION_OUTAGE_ONLY",
    safety["Z_MODERATE"]["policy"] == "STRICT_CONNECTED",
    safety["Z_MODERATE"]["graph"] == "G_admit",
    safety["Z_MODERATE"]["scope"]
        == "ENTIRE_CONTROLLER_INDUCED_TRANSITION",
    safety["safety_is_reject_only"] is True,
    safety["candidate_substitution"] is False,
    safety["natural_post_expiry_no_route_is_transition_outage"] is False,
))

live = contract["live_execution"]
checks["live_state_non_mutation_and_receding_horizon"] = all((
    live["returned_action"]
        == "HOLD or REPLACE(old binding,new concrete terminal pair)",
    live["selected_action_execution"]
        == "Same real Gate B/C path used by all controllers.",
    live["hypothetical_states_discarded"] is True,
    live["hypothetical_state_may_replace_live_engine"] is False,
    live["recompute_each_real_epoch"] is True,
))

interpretation = contract["interpretation"]
checks["B3_B4_interpretation_exact"] = all((
    interpretation["B3"] == "setup-aware current-state greedy controller",
    "explicit short-horizon network-dynamics rollout"
        in interpretation["scientific_difference"],
    interpretation["globally_optimal_claim"] is False,
    interpretation["H_10s_optimal_claim"] is False,
))

boundary = contract["implementation_boundary"]
scope = contract["scope_guard"]
gate_f1_contract = read("configs/gate_f1_contract.json")
forbidden_implementation_paths = (
    "src/dynamic_lisl/rollout_controller.py",
    "src/dynamic_lisl/mpc_controller.py",
    "src/dynamic_lisl/b4_controller.py",
    "tests/test_gate_f2_rollout.py",
    "configs/gate_f2_status.json",
    "configs/gate_f3_status.json",
)
checks["freeze_does_not_authorize_implementation_or_performance"] = all((
    boundary["B4_implementation_authorized"] is False,
    boundary["B4_performance_ranking_authorized"] is False,
    boundary["F3_experiment_grid_authorized"] is False,
    boundary["B2_grid_selection_authorized"] is False,
    boundary["main_scale_sweep_authorized"] is False,
    boundary["RL_PPO_authorized"] is False,
    boundary["B5_main_scale_oracle_authorized"] is False,
    scope["controller_performance_run"] is False,
    scope["B4_implemented"] is False,
))
checks["B4_still_not_implemented"] = all((
    gate_f1_contract["controllers"]["B4"] == "NOT_IMPLEMENTED",
    not any((PROJECT / name).exists() for name in forbidden_implementation_paths),
))
checks["later_gates_and_RL_not_started"] = all((
    scope["F2_started"] is False,
    scope["F3_started"] is False,
    scope["RL_started"] is False,
    closure.get("gate_f2_started") is False,
    closure.get("gate_f3_started") is False,
    closure.get("rl_started") is False,
))

parent_post = {
    group: {name: sha(name) for name in records}
    for group, records in parent_expected.items()
}
a_to_e2_post = {name: sha(name) for name in a_to_e2["files"]}
checks["all_declared_parent_hashes_unchanged_post"] = parent_post == parent_expected
checks["all_a_to_e2_frozen_hashes_unchanged_post"] = (
    a_to_e2_post == a_to_e2["files"]
)

passed = all(checks.values())
timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT / "outputs" / f"gate_f2_rollout_human_freeze_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

statement = (
    "Gate F2 Rollout Human Freeze v1 = PASS" if passed
    else "Gate F2 Rollout Human Freeze v1 = FAIL"
)
report = {
    "schema": "gate_f2_rollout_human_freeze_v1_report",
    "statement": statement,
    "checks": checks,
    "canonical_sha256": expected_canonical,
    "B4_rollout_contract": "FROZEN" if passed else "NOT_FROZEN",
    "B4_implementation_readiness": "READY" if passed else "NOT_READY",
    "B4_implemented": False,
    "controller_performance_run": False,
    "F2_started": False,
    "F3_started": False,
    "RL_started": False,
}
dump(out / "report.json", report)
dump(out / "frozen_hash_report.json", {
    "schema": "gate_f2_rollout_human_freeze_parent_hash_report_v1",
    "parent_expected": parent_expected,
    "parent_actual_pre": parent_pre,
    "parent_actual_post": parent_post,
    "all_declared_parents_unchanged": parent_post == parent_expected,
    "a_to_e2_registry_file_sha256": sha(
        "configs/gate_f0_frozen_a_to_e2_hashes.json"),
    "a_to_e2_file_count": len(a_to_e2["files"]),
    "a_to_e2_all_unchanged_pre": a_to_e2_pre == a_to_e2["files"],
    "a_to_e2_all_unchanged_post": a_to_e2_post == a_to_e2["files"],
    "contract_canonical_sha256": expected_canonical,
    "contract_file_sha256": sha(CONTRACT),
})

status = {
    "schema": "gate_f2_rollout_human_freeze_status_v1",
    "statement": statement,
    "gate_f2_rollout_human_freeze_v1": "PASS" if passed else "FAIL",
    "B4_rollout_contract": "FROZEN" if passed else "NOT_FROZEN",
    "B4_implementation_readiness": "READY" if passed else "NOT_READY",
    "B4_implemented": False,
    "controller_performance_run": False,
    "canonical_sha256": expected_canonical,
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "F2_started": False,
    "F3_started": False,
    "RL_started": False,
}
dump(PROJECT / "configs/gate_f2_rollout_human_freeze_status.json", status)

artifact_names = (
    "docs/GATE_F2_ROLLOUT_HUMAN_FREEZE_V1_CN.md",
    CONTRACT,
    "configs/gate_f2_rollout_human_freeze_status.json",
    "tools/check_gate_f2_rollout_human_freeze.py",
)
dump(out / "artifact_hashes.json", {
    name: sha(name) for name in artifact_names
})

print(statement)
print("B4 rollout contract = " + ("FROZEN" if passed else "NOT_FROZEN"))
print("B4 implementation readiness = " + ("READY" if passed else "NOT_READY"))
print("F2 started = false")
print("F3 started = false")
print("RL started = false")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
if not passed:
    print("FAILED_CHECKS=" + ",".join(name for name, ok in checks.items() if not ok))
    raise SystemExit(1)

