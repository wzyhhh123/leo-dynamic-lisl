"""Limited 160-star natural-geometry Gate F2 B4 semantic sanity."""
from __future__ import annotations

from .candidate_proposer import CandidateSpec, FrozenTerminalPairProposer
from .controller_runner import MultiEpochControllerRunner
from .gate_e2_experiments import GateE2Assets
from .rollout_controller import RootActionRolloutMPCController


def _scenario(assets):
    return next(row for row in assets.selected.values()
                if row["scenario_class"] == "E-A_BBM_NO_ROUTE"
                and row["kappa2_bin"] == "low")


def _execute_once():
    assets = GateE2Assets()
    scenario = _scenario(assets)
    engine = assets.engine(scenario, 0.2, "shortest_propagation")
    scripted = assets.action(scenario)
    old_pair = assets.binding_by_edge[tuple(scenario["old_edge"])]
    spec = CandidateSpec(
        "F2-B4-160-NATURAL", scripted.proposal, old_pair)
    controller = RootActionRolloutMPCController(
        engine, assets.physical, assets.fixed, "Z_SPARSE_REFERENCE")
    source = controller.candidate_source(lambda _state, _context: (spec,))
    t0 = float(scenario["t0_s"])
    runner = MultiEpochControllerRunner(
        engine, assets.physical, assets.fixed, "Z_SPARSE_REFERENCE",
        source, controller, t0_s=t0, decision_end_s=t0)
    run = runner.run(t0+59.0)
    decision = controller.last_decision
    action = run["controller_actions"][0]
    metrics = run["engine_result"]["metrics"]
    summary = {
        "schema": "gate_f2_160star_b4_semantic_sanity_v1",
        "scope": "limited deterministic correctness only; no controller performance comparison",
        "scenario_id": scenario["scenario_id"],
        "scenario_is_frozen_natural_gate_c_case": True,
        "decision_epoch_s": t0,
        "candidate_top_k": FrozenTerminalPairProposer.top_k,
        "proposal_set_sha256": action["proposal_set_sha256"],
        "branch_count": decision["branch_count"],
        "branch_count_within_limit": decision["branch_count"] <= 17,
        "same_start_state_all_branches": decision["same_start_state_all_branches"],
        "same_forecast_all_branches": decision["same_forecast_all_branches"],
        "forecast_sha256": decision["forecast_sha256"],
        "selected_action": action["selected_action"]["kind"],
        "selected_proposal_id": action["selected_proposal_id"],
        "selected_action_accepted_or_hold": (
            action["selected_action"]["kind"] == "HOLD" or action["accepted"]),
        "real_gate_b_c_transition_type": action["resulting_gate_b_transition_type"],
        "live_engine_not_mutated_during_scoring": not decision["live_engine_mutated"],
        "root_action_only": decision["root_action_only"],
        "multi_step_future_controller_actions":
            decision["multi_step_future_controller_actions"],
        "deterministic_decision_sha256": decision["decision_sha256"],
        "action_replay_sha256": run["action_replay_sha256"],
        "work_conservation_pass": metrics["max_abs_conservation_error_bits"] <= 1.0,
        "nonnegative_queue_pass": metrics["negative_queue_count"] == 0,
        "capacity_pass": metrics["max_capacity_violation_bit_s"] <= 0.01,
        "performance_fields_intentionally_omitted": [
            "J_comparison", "mean_delay_comparison", "delivery_ratio_comparison",
            "relative_improvement", "best_controller", "controller_ranking",
        ],
    }
    summary["pass"] = all((
        summary["branch_count_within_limit"],
        summary["same_start_state_all_branches"],
        summary["same_forecast_all_branches"],
        summary["selected_action_accepted_or_hold"],
        summary["live_engine_not_mutated_during_scoring"],
        summary["root_action_only"],
        summary["multi_step_future_controller_actions"] is False,
        summary["work_conservation_pass"],
        summary["nonnegative_queue_pass"],
        summary["capacity_pass"],
    ))
    return summary


def run_160_b4_semantic_sanity():
    first = _execute_once()
    second = _execute_once()
    deterministic = all((
        first["deterministic_decision_sha256"]
            == second["deterministic_decision_sha256"],
        first["action_replay_sha256"] == second["action_replay_sha256"],
        first["selected_action"] == second["selected_action"],
        first["selected_proposal_id"] == second["selected_proposal_id"],
    ))
    first["deterministic_replay_pass"] = deterministic
    first["pass"] = first["pass"] and deterministic
    return first

