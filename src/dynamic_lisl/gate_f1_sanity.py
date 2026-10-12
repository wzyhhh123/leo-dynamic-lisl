"""Predeclared 160-satellite Gate F1 semantic sanity integrations.

These runs check orchestration and invariants only.  They intentionally omit J,
delay, delivery, and all cross-controller performance comparisons.
"""
from __future__ import annotations

from .baseline_controllers import IgnoreSetupDynamicScaffold, StaticHoldController
from .candidate_proposer import CandidateSpec
from .common import PROJECT, read_json
from .controller_runner import MultiEpochControllerRunner
from .gate_e2_experiments import E2Sgp4EdgeDelayProvider, GateE2Assets
from .terminal_executor import Connect, TerminalExecutor
from .transition_service_orchestrator import TransitionAwareNetworkServiceEngine


def _moderate_engine(assets):
    topology = read_json(PROJECT/"configs/z_moderate_v1.json")
    executor = TerminalExecutor(assets.nodes)
    for binding in topology["bindings"]:
        executor.submit((Connect(tuple(binding["a"]), tuple(binding["b"]),
                                 float(binding["end_s"]), 0.0, 0.0, 0.0),))
    return TransitionAwareNetworkServiceEngine(
        assets.nodes, assets.fixed,
        assets.contract["link_capacity_bit_s_per_direction"],
        assets.commodities, assets.trace(0.0, 0.2),
        E2Sgp4EdgeDelayProvider(assets.model, assets.nodes), executor, (),
        assets.router("shortest_propagation"),
        conservation_abs_tolerance_bits=
            assets.contract["conservation_abs_tolerance_bits"],
        conservation_relative_tolerance=
            assets.contract["conservation_relative_tolerance"],
        state_tolerance_bits=assets.contract["state_tolerance_bits"])


def _sparse_switch_engine(assets):
    engine = assets.engine(next(row for row in assets.selected.values()
                                if row["scenario_class"] == "E-A_BBM_NO_ROUTE"),
                           0.2, "shortest_propagation")
    scenario = next(row for row in assets.selected.values()
                    if row["scenario_class"] == "E-A_BBM_NO_ROUTE")
    scripted = assets.action(scenario)
    old_pair = assets.binding_by_edge[tuple(scenario["old_edge"])]
    spec = CandidateSpec("F1-160-SPARSE-BBM", scripted.proposal, old_pair)
    controller = IgnoreSetupDynamicScaffold(
        lambda state, proposal_set, context: {
            "HOLD": 0.0,
            **{row["proposal_id"]: 1.0 for row in proposal_set["proposals"]}},
        test_only=True)
    runner = MultiEpochControllerRunner(
        engine, assets.physical, assets.fixed, "Z_SPARSE_REFERENCE",
        lambda state, context: (spec,), controller,
        t0_s=float(scenario["t0_s"]),
        decision_end_s=float(scenario["t0_s"])+4.0)
    return runner, scenario


def _summary(run, expected_switches):
    metrics = run["engine_result"]["metrics"]
    return {
        "callbacks": run["decision_callback_times_s"],
        "callback_count": len(run["decision_callback_times_s"]),
        "switch_count": metrics["switch_count"],
        "expected_switch_count": expected_switches,
        "work_conservation_pass": metrics["max_abs_conservation_error_bits"] <= 1.0,
        "nonnegative_queue_pass": metrics["negative_queue_count"] == 0,
        "capacity_pass": metrics["max_capacity_violation_bit_s"] <= 0.01,
        "action_replay_sha256": run["action_replay_sha256"],
        "outage_fields_present": all(key in run["separated_outage_metrics"] for key in (
            "transition_period_outage_s",
            "transition_period_no_route_by_commodity_s",
            "post_expiry_no_route_s",
            "post_expiry_no_route_by_commodity_s")),
    }


def run_160_semantic_sanity():
    assets = GateE2Assets()
    sparse_runner, scenario = _sparse_switch_engine(assets)
    sparse = sparse_runner.run(float(scenario["t0_s"])+59.0)

    moderate_engine = _moderate_engine(assets)
    def forbidden_source(_state, _context):
        raise AssertionError("B0_MUST_NOT_INVOKE_CANDIDATE_PROPOSER")
    moderate = MultiEpochControllerRunner(
        moderate_engine, assets.physical, assets.fixed, "Z_MODERATE",
        forbidden_source, StaticHoldController(),
        decision_end_s=4.0).run(59.0)

    report = {
        "schema": "gate_f1_160star_semantic_sanity_v1",
        "scope": "correctness/integration only; no controller performance",
        "sparse": _summary(sparse, 1),
        "moderate": _summary(moderate, 0),
        "proposer_natural_gate_c_candidate_executed":
            sparse["engine_result"]["metrics"]["switch_count"] == 1,
        "both_regimes_executed": True,
        "performance_fields_intentionally_omitted": [
            "J", "mean_delay", "delivery_ratio", "relative_improvement",
            "controller_ranking"],
    }
    report["pass"] = all((
        report["proposer_natural_gate_c_candidate_executed"],
        report["sparse"]["work_conservation_pass"],
        report["sparse"]["nonnegative_queue_pass"],
        report["sparse"]["capacity_pass"],
        report["sparse"]["outage_fields_present"],
        report["moderate"]["work_conservation_pass"],
        report["moderate"]["nonnegative_queue_pass"],
        report["moderate"]["capacity_pass"],
        report["moderate"]["outage_fields_present"],
        report["sparse"]["switch_count"] == 1,
        report["moderate"]["switch_count"] == 0,
    ))
    return report
