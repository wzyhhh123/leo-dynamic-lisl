"""Limited 160-satellite Gate F1 scientific-scoring semantic sanity.

The returned report intentionally excludes J, delay, delivery, relative
improvement, and every cross-controller ranking field.
"""
from __future__ import annotations

from .baseline_controllers import ControllerAction, HysteresisMinimumHoldController
from .candidate_proposer import CandidateSpec, FrozenTerminalPairProposer
from .controller_runner import MultiEpochControllerRunner
from .gate_e2_experiments import GateE2Assets
from .scientific_controllers import (
    IgnoreSetupDynamicController, SetupAwareGreedyController,
)


def _scenario(assets):
    return next(row for row in assets.selected.values()
                if row["scenario_class"] == "E-A_BBM_NO_ROUTE"
                and row["kappa2_bin"] == "low")


def _runner(assets, controller_name):
    scenario = _scenario(assets)
    engine = assets.engine(scenario, 0.2, "shortest_propagation")
    scripted = assets.action(scenario)
    old_pair = assets.binding_by_edge[tuple(scenario["old_edge"])]
    spec = CandidateSpec("F1-SCIENTIFIC-160-NATURAL", scripted.proposal,
                         old_pair)
    if controller_name == "B1":
        controller = IgnoreSetupDynamicController(engine)
    elif controller_name == "B2":
        controller = HysteresisMinimumHoldController(
            IgnoreSetupDynamicController(engine), 2.0, 0.0)
        controller.test_parameter_status = "TEST_ONLY_NOT_FROZEN_FOR_F3"
    elif controller_name == "B3":
        controller = SetupAwareGreedyController(engine)
    else:
        raise ValueError("UNKNOWN_SCIENTIFIC_SANITY_CONTROLLER")
    runner = MultiEpochControllerRunner(
        engine, assets.physical, assets.fixed, "Z_SPARSE_REFERENCE",
        lambda _state, _context: (spec,), controller,
        t0_s=float(scenario["t0_s"]),
        decision_end_s=float(scenario["t0_s"])+4.0)
    return runner, scenario


class _NaturalGateBCExecutionProbe:
    """Interface-only probe; not a scientific or performance controller."""

    controller_id = "TEST_ONLY_NATURAL_GATE_B_C_EXECUTION_PROBE"
    information_class = "CURRENT_STATE_ONLY"

    def observe(self, current_state, proposal_set, context):
        if not proposal_set["proposals"]:
            return ControllerAction("HOLD")
        return ControllerAction(
            "REPLACE", proposal_set["proposals"][0]["proposal_id"],
            (("status", "TEST_ONLY_EXECUTION_PROBE"),))

    def on_action_result(self, record):
        return None


def _execution_probe_runner(assets):
    scenario = _scenario(assets)
    engine = assets.engine(scenario, 0.2, "shortest_propagation")
    scripted = assets.action(scenario)
    old_pair = assets.binding_by_edge[tuple(scenario["old_edge"])]
    spec = CandidateSpec("F1-160-NATURAL-EXECUTION-PROBE",
                         scripted.proposal, old_pair)
    runner = MultiEpochControllerRunner(
        engine, assets.physical, assets.fixed, "Z_SPARSE_REFERENCE",
        lambda _state, _context: (spec,), _NaturalGateBCExecutionProbe(),
        t0_s=float(scenario["t0_s"]),
        decision_end_s=float(scenario["t0_s"]))
    return runner, scenario


def _summary(name, run):
    metrics = run["engine_result"]["metrics"]
    actions = run["controller_actions"]
    return {
        "controller": name,
        "callbacks": run["decision_callback_times_s"],
        "callback_count": len(run["decision_callback_times_s"]),
        "candidate_top_k": FrozenTerminalPairProposer.top_k,
        "candidate_structural_quota": {
            "MBB_STRUCTURALLY_FEASIBLE": FrozenTerminalPairProposer.per_stratum,
            "BBM_REQUIRED": FrozenTerminalPairProposer.per_stratum,
        },
        "natural_proposal_consumed": all(
            bool(row["proposal_set_sha256"]) for row in actions),
        "selected_action_kinds": [row["selected_action"]["kind"] for row in actions],
        "accepted_real_replace_count": sum(
            row["selected_action"]["kind"] == "REPLACE" and row["accepted"]
            for row in actions),
        "real_gate_b_c_transition_types": [
            row["resulting_gate_b_transition_type"] for row in actions
            if row["resulting_gate_b_transition_type"] is not None],
        "work_conservation_pass": metrics["max_abs_conservation_error_bits"] <= 1.0,
        "nonnegative_queue_pass": metrics["negative_queue_count"] == 0,
        "capacity_pass": metrics["max_capacity_violation_bit_s"] <= 0.01,
        "action_replay_sha256": run["action_replay_sha256"],
        "outage_fields_present": all(
            key in run["separated_outage_metrics"] for key in (
                "transition_period_outage_s",
                "transition_period_no_route_by_commodity_s",
                "post_expiry_no_route_s",
                "post_expiry_no_route_by_commodity_s")),
    }


def run_160_scientific_semantic_sanity():
    assets = GateE2Assets()
    summaries = {}
    for name in ("B1", "B2", "B3"):
        runner, scenario = _runner(assets, name)
        run = runner.run(float(scenario["t0_s"])+59.0)
        summaries[name] = _summary(name, run)

    replay_runner, replay_scenario = _runner(assets, "B1")
    replay = _summary("B1_REPLAY", replay_runner.run(
        float(replay_scenario["t0_s"])+59.0))
    deterministic = (
        replay["action_replay_sha256"]
        == summaries["B1"]["action_replay_sha256"]
        and replay["selected_action_kinds"]
        == summaries["B1"]["selected_action_kinds"])
    probe_runner, probe_scenario = _execution_probe_runner(assets)
    probe = _summary("NATURAL_GATE_B_C_EXECUTION_PROBE", probe_runner.run(
        float(probe_scenario["t0_s"])+59.0))
    real_execution = probe["accepted_real_replace_count"] == 1
    report = {
        "schema": "gate_f1_160star_scientific_scoring_semantic_sanity_v1",
        "scope": "limited deterministic correctness only; no controller performance comparison",
        "scenario_id": _scenario(assets)["scenario_id"],
        "scenario_is_frozen_natural_gate_c_case": True,
        "controllers": summaries,
        "natural_gate_b_c_execution_probe": probe,
        "deterministic_B1_replay": deterministic,
        "real_gate_b_c_execution_observed": real_execution,
        "B2_test_parameters": {
            "minimum_hold_s": 2.0,
            "improvement_threshold": 0.0,
            "status": "TEST_ONLY_NOT_FROZEN_FOR_F3",
        },
        "performance_fields_intentionally_omitted": [
            "J", "mean_delay", "delivery_ratio", "relative_improvement",
            "best_controller", "controller_ranking", "best_B2_threshold"],
    }
    report["pass"] = all((
        deterministic,
        real_execution,
        all(row["callback_count"] == 3 for row in summaries.values()),
        all(row["candidate_top_k"] == 16 for row in summaries.values()),
        all(row["natural_proposal_consumed"] for row in summaries.values()),
        all(row["work_conservation_pass"] for row in summaries.values()),
        all(row["nonnegative_queue_pass"] for row in summaries.values()),
        all(row["capacity_pass"] for row in summaries.values()),
        all(row["outage_fields_present"] for row in summaries.values()),
    ))
    return report
