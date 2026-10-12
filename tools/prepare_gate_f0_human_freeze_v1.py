"""Freeze the immutable Gate F0 Human Freeze v1 overlay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "configs/gate_f0_human_freeze_v1.json"
if OUT.exists():
    raise FileExistsError("REFUSE_TO_OVERWRITE_GATE_F0_HUMAN_FREEZE_V1")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


z = json.loads((PROJECT / "configs/z_moderate_v1.json").read_text(
    encoding="utf-8"))
if z["status"] != "CONSTRUCTED":
    raise RuntimeError("Z_MODERATE_NOT_CONSTRUCTED")

document = {
    "schema": "gate_f0_human_freeze_v1",
    "overlay_status": "FROZEN",
    "immutable_overlay": True,
    "parent": {
        "contract": "configs/gate_f0_controller_contract.json",
        "parent_contract_sha256": sha(
            PROJECT / "configs/gate_f0_controller_contract.json"),
        "baseline_registry": "configs/gate_f0_baseline_registry.json",
        "parent_baseline_registry_sha256": sha(
            PROJECT / "configs/gate_f0_baseline_registry.json"),
        "human_decisions": "docs/GATE_F0_HUMAN_DECISIONS_REQUIRED_CN.md",
        "parent_human_decisions_sha256": sha(
            PROJECT / "docs/GATE_F0_HUMAN_DECISIONS_REQUIRED_CN.md"),
        "parent_f0_status": "PASS_WITH_HUMAN_FREEZE_ITEMS",
        "parent_is_not_rewritten": True,
    },
    "resolved_f1_blockers": {
        "items": [1, 2, 3, 4, 5],
        "all_resolved": True,
        "flag": "F1_BLOCKING_HUMAN_ITEMS_1_TO_5_RESOLVED",
    },
    "decision_epoch": {
        "decision_cadence_s": 2.0,
        "periodic_decision_enabled": True,
        "topology_event_immediate_decision": False,
        "natural_expiry_immediate_decision": False,
        "link_up_immediate_decision": False,
        "link_down_immediate_decision": False,
        "minimum_controller_reaction_interval_s": 2.0,
        "simultaneous_periodic_event_policy":
            "single_periodic_epoch_after_existing_physical_events_settle",
        "epoch_formula": "t_k=t_0+2k_s",
        "between_epoch_physical_events_apply_immediately": True,
        "between_epoch_graph_routing_service_update_immediately": True,
        "between_epoch_controller_waits_until_next_periodic_epoch": True,
        "microstep_order": [
            "committed_propagation_events",
            "gate_b_terminal_events",
            "controller_observes_right_continuous_current_state",
            "one_action",
            "gate_c_safety_gate_b",
            "graph",
            "router",
            "service",
        ],
        "setup_target_cancel_or_rewrite_allowed": False,
    },
    "candidate_proposal": {
        "candidate_top_k": 16,
        "budget_is_preregistered_not_performance_tuned": True,
        "main_scale_exhaustive_candidate_evaluation_forbidden": True,
        "hard_pruning": [
            "gate_c_bilateral_illegal",
            "setup_cannot_finish_before_terminal_pair_window_end",
            "terminal_or_reservation_conflict",
            "target_binding_already_invalid",
            "exact_physical_noop_or_identical_binding",
            "violates_regime_frozen_connectivity_safety_policy",
        ],
        "forbidden_inputs": [
            "J", "delta_J", "future_realized_traffic",
            "reversal_status", "controller_identity", "downstream_performance",
        ],
        "structural_strata": {
            "MBB_STRUCTURALLY_FEASIBLE": 8,
            "BBM_REQUIRED": 8,
        },
        "quota_spillover": (
            "Keep every candidate in a stratum with fewer than 8, then "
            "deterministically give unused slots to the other stratum; "
            "total at most 16."
        ),
        "within_stratum_ranking": [
            "usable_lifetime_s_descending",
            "plane_gap_ascending",
            "old_edge_lexicographic",
            "old_terminal_ids_lexicographic",
            "new_edge_lexicographic",
            "new_terminal_ids_lexicographic",
            "proposal_id_lexicographic",
        ],
        "ranking_uses_queue_load_or_value": False,
        "shared_proposal_set_controllers": ["B1", "B2", "B3", "B4"],
        "B0_candidate_budget_not_used_by_design": True,
        "B5_tiny_fixture_exact_oracle_exempt_from_k": True,
    },
    "forecast": {
        "forecast_class": "SHORT_HORIZON_FORECAST",
        "traffic_forecast": "CURRENT_RATE_PERSISTENCE",
        "forecast_horizon_s": 10.0,
        "forecast_update_period_s": 2.0,
        "formula": "lambda_hat_f(t+tau)=lambda_f(t),0<=tau<=10s",
        "may_read_unrealized_immutable_trace_segments": False,
        "predictable_geometry_allowed": [
            "SGP4_Gate_C_deterministic_geometry",
            "current_known_terminal_pair_windows",
            "natural_expiry",
            "Gate_B_deterministic_transition_dynamics",
        ],
        "geometry_is_not_traffic_oracle": True,
        "shared_across_short_horizon_controllers": True,
        "development_horizon_not_claimed_optimal": True,
        "horizon_change_before_performance_forbidden": True,
    },
    "z_moderate": {
        "selected_design": "ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE",
        "construction_epoch_s": 0.0,
        "asset": "configs/z_moderate_v1.json",
        "asset_file_sha256": sha(PROJECT / "configs/z_moderate_v1.json"),
        "asset_canonical_sha256": z["canonical_sha256"],
        "construction_status": z["status"],
        "fallback_design_allowed": False,
        "infeasible_status":
            "Z_MODERATE_CONSTRUCTION_INFEASIBLE_AT_REGISTERED_EPOCH",
        "traffic_agnostic": True,
        "result_blind": True,
        "minimum_added_bindings": z["minimality_certificate"][
            "minimum_added_bindings"],
        "selected_addition": z["selected_addition"],
        "structural_audit": z["structural_audit"],
    },
    "connectivity_safety": {
        "Z_SPARSE_REFERENCE": {
            "policy": "BOUNDED_TRANSITION_OUTAGE",
            "T_max_transition_outage_s": 2.0,
            "applies_only_to_controller_initiated_transition_period": True,
            "equality_is_accepted": True,
            "post_expiry_no_route_in_transition_budget": False,
            "post_expiry_must_enter_rollout_objective_and_reporting": True,
            "fixture_interpretation":
                "aligned with 2 s simplified setup; not commercial hardware guarantee",
        },
        "Z_MODERATE": {
            "policy": "STRICT_CONNECTED",
            "profiled_graph": "G_admit",
            "must_hold_for_entire_controller_initiated_transition": True,
            "safety_is_reject_only": True,
            "automatic_mbb_conversion_forbidden": True,
            "terminal_substitution_forbidden": True,
            "second_best_action_substitution_forbidden": True,
        },
    },
    "additive_metric_requirement_before_f1_validation": {
        "required": [
            "transition_period_outage_s",
            "transition_period_no_route_by_commodity_s",
            "post_expiry_no_route_s",
            "post_expiry_no_route_by_commodity_s",
        ],
        "forced_outage_duration_role": "diagnostic_only",
        "controller_implementation_authorized_by_overlay": False,
    },
    "explicit_non_decisions": {
        "status": "REQUIRES_HUMAN_FREEZE_BEFORE_F3",
        "items": [
            "B2_minimum_hold_grid",
            "B2_improvement_threshold_grid",
            "F3_controller_evaluation_cross_product",
            "mixed_complete_censored_controller_ranking",
            "stochastic_seed_policy",
        ],
        "B2_may_be_parameterized_in_f1": True,
        "B2_performance_based_parameter_selection_allowed": False,
    },
    "readiness": {
        "gate_f1_readiness": "READY",
        "gate_f1_started": False,
        "gate_f2_started": False,
        "gate_f3_started": False,
        "rl_started": False,
    },
    "forbidden": [
        "implement_B0", "implement_B1", "implement_B2", "implement_B3",
        "implement_B4_MPC", "implement_B5_oracle",
        "implement_matching_controller", "implement_RL_PPO",
        "run_controller_comparison", "run_J_based_tuning",
        "tune_K", "tune_horizon", "tune_topology_density",
        "fallback_to_another_Z_MODERATE_design",
        "modify_E0_E1_E2_manifests", "modify_parent_F0_contract",
    ],
}
document["canonical_sha256"] = hashlib.sha256(
    canonical(document).encode("utf-8")
).hexdigest()
OUT.write_text(
    json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(json.dumps({
    "status": document["overlay_status"],
    "canonical_sha256": document["canonical_sha256"],
    "gate_f1_readiness": document["readiness"]["gate_f1_readiness"],
}, indent=2))
