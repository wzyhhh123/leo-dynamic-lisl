"""Frozen small-network Gate E1 builders and point evaluator."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
import math

from .commodity import Commodity
from .common_router import DeterministicShortestPropagationDelayRouter
from .gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .load_aware_router import DeterministicLoadAwareRouter
from .mechanism_validation import (
    PairedCounterfactualHarness, break_even_brackets,
    reversal_classification, target_signature, third_party_effect,
)
from .operational_policy import OperationalPolicy
from .terminal_executor import Connect, TerminalExecutor
from .terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from .traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from .transition_service_orchestrator import (
    ScriptedProposal, TransitionAwareNetworkServiceEngine,
)


GBIT = 1e9
ROUTER_PRIMARY = "shortest_propagation_delay"
ROUTER_ROBUSTNESS = "current_load_aware"
REQUIRED_BRANCHES = ("HOLD", "REAL_SWITCH", "IDEAL_SWITCH")


class ConstantEdgeDelay:
    def __init__(self, edge_delay_s):
        self.edge_delay_s = {
            tuple(sorted(edge.split("--"))): float(value)
            for edge, value in edge_delay_s.items()}

    def __call__(self, edge, time_s):
        key = tuple(sorted(tuple(edge)))
        if key not in self.edge_delay_s:
            raise KeyError("UNREGISTERED_E1_EDGE:"+"--".join(key))
        return self.edge_delay_s[key]


class E1TransitionEngine(TransitionAwareNetworkServiceEngine):
    """D2 engine adapter that supplies only current state to load-aware routing."""

    def _recompute_routes(self, reason):
        if isinstance(self.router, DeterministicLoadAwareRouter):
            edge_rates = defaultdict(float)
            for (edge, _commodity), value in self.service_rates.items():
                edge_rates[tuple(edge)] += value
            utilization = {
                edge: value/self.capacity_bit_s for edge, value in edge_rates.items()}
            node_queue = defaultdict(float)
            for (node, _commodity), value in self.queues.bits.items():
                node_queue[node] += value
            offered = self.trace.rate_at(self.now)
            self.router.update_current_state(
                self.now, utilization, node_queue, offered)
        super()._recompute_routes(reason)


def frozen_templates():
    """Return fresh copies of the four preregistered structural templates."""
    base_action = {
        "retarget_a_s": 0.4, "retarget_b_s": 0.7,
        "acquisition_s": 0.3, "tau0_s": 1.0,
    }
    templates = {
        "E-A_BBM_NO_ROUTE": {
            "scenario_class": "E-A_BBM_NO_ROUTE",
            "nodes": ["A", "B", "C", "D"],
            "fixed_edges": [["A", "B"], ["C", "D"]],
            "dynamic_terminals_per_node": ["D1", "D2"],
            "old_dynamic_pair": [["B", "D1"], ["C", "D1"]],
            "target_dynamic_pair": [["B", "D1"], ["D", "D1"]],
            "release_after": [],
            "capacity_bit_s_per_direction": GBIT,
            "edge_delay_s": {
                "A--B": 0.02, "B--C": 0.01,
                "C--D": 0.02, "B--D": 0.005,
            },
            "commodities": [
                {"commodity_id": "focus", "source": "A", "destination": "D",
                 "weight": 1.0, "reference_shape": 1.0}],
            "reference_alpha_factor": 1.0,
            "focus_commodities": ["focus"], "third_party_commodities": [],
            "base_transition": base_action,
            "policy": {"mode": "BOUNDED_OUTAGE", "max_outage_s": 16.0},
            "structural_reason": "occupied B:D1 is broken before retarget; fixed graph has no A-to-D path until target LINK_UP",
        },
        "E-B_BBM_CONNECTED_REROUTE": {
            "scenario_class": "E-B_BBM_CONNECTED_REROUTE",
            "nodes": ["A", "B", "C", "D", "E"],
            "fixed_edges": [["A", "B"], ["B", "E"], ["E", "D"], ["C", "D"]],
            "dynamic_terminals_per_node": ["D1", "D2"],
            "old_dynamic_pair": [["A", "D1"], ["C", "D1"]],
            "target_dynamic_pair": [["A", "D1"], ["D", "D1"]],
            "release_after": [],
            "capacity_bit_s_per_direction": GBIT,
            "edge_delay_s": {
                "A--B": 0.04, "B--E": 0.04, "D--E": 0.04,
                "C--D": 0.005, "A--C": 0.005, "A--D": 0.004,
            },
            "commodities": [
                {"commodity_id": "focus", "source": "A", "destination": "D",
                 "weight": 1.0, "reference_shape": 1.0}],
            "reference_alpha_factor": 1.0,
            "focus_commodities": ["focus"], "third_party_commodities": [],
            "base_transition": base_action,
            "policy": {"mode": "STRICT_CONNECTED", "max_outage_s": None},
            "structural_reason": "occupied A:D1 uses BBM while fixed A-B-E-D remains an admitted alternate path",
        },
        "E-C_GENUINE_MBB": {
            "scenario_class": "E-C_GENUINE_MBB",
            "nodes": ["A", "B", "C", "D"],
            "fixed_edges": [["A", "B"], ["B", "C"], ["C", "D"]],
            "dynamic_terminals_per_node": ["D1", "D2"],
            "old_dynamic_pair": [["A", "D1"], ["C", "D1"]],
            "target_dynamic_pair": [["A", "D2"], ["D", "D2"]],
            "release_after": [[["A", "D1"], ["C", "D1"]]],
            "capacity_bit_s_per_direction": GBIT,
            "edge_delay_s": {
                "A--B": 0.03, "B--C": 0.03, "C--D": 0.008,
                "A--C": 0.008, "A--D": 0.004,
            },
            "commodities": [
                {"commodity_id": "focus", "source": "A", "destination": "D",
                 "weight": 1.0, "reference_shape": 1.0}],
            "reference_alpha_factor": 1.0,
            "focus_commodities": ["focus"], "third_party_commodities": [],
            "base_transition": base_action,
            "policy": {"mode": "STRICT_CONNECTED", "max_outage_s": None},
            "structural_reason": "A:D2 and D:D2 are truly idle; target LINK_UP precedes release of old A:D1-C:D1",
        },
        "E-D_SHARED_CONGESTION_EXTERNALITY": {
            "scenario_class": "E-D_SHARED_CONGESTION_EXTERNALITY",
            "nodes": ["A", "B", "C", "D", "E"],
            "fixed_edges": [["A", "B"], ["B", "E"], ["E", "D"], ["C", "D"]],
            "dynamic_terminals_per_node": ["D1", "D2"],
            "old_dynamic_pair": [["B", "D1"], ["C", "D1"]],
            "target_dynamic_pair": [["A", "D2"], ["D", "D2"]],
            "release_after": [[["B", "D1"], ["C", "D1"]]],
            "capacity_bit_s_per_direction": GBIT,
            "edge_delay_s": {
                "A--B": 0.01, "B--E": 0.02, "D--E": 0.02,
                "C--D": 0.01, "B--C": 0.01, "A--D": 0.004,
            },
            "commodities": [
                {"commodity_id": "focus", "source": "A", "destination": "D",
                 "weight": 1.0, "reference_shape": 3.0/13.0},
                {"commodity_id": "third", "source": "B", "destination": "D",
                 "weight": 1.0, "reference_shape": 5.0/13.0},
                {"commodity_id": "background", "source": "E", "destination": "D",
                 "weight": 1.0, "reference_shape": 5.0/13.0},
            ],
            "reference_alpha_factor": 1.3,
            "focus_commodities": ["focus"],
            "third_party_commodities": ["background", "third"],
            "shared_capacity_edge_after_switch": ["E", "D"],
            "base_transition": base_action,
            "policy": {"mode": "STRICT_CONNECTED", "max_outage_s": None},
            "structural_reason": "focus gains direct A-D while third reroutes from B-C-D to B-E-D and shares capacity-limited E-D with background",
        },
    }
    return deepcopy(templates)


def scale_setup(base_transition, tau_setup_s):
    tau = float(tau_setup_s)
    if not math.isfinite(tau) or tau < 0:
        raise ValueError("INVALID_E1_SETUP")
    tau0 = float(base_transition["tau0_s"])
    computed = max(float(base_transition["retarget_a_s"]),
                   float(base_transition["retarget_b_s"])) + float(
                       base_transition["acquisition_s"])
    if abs(computed-tau0) > 1e-12 or tau0 <= 0:
        raise ValueError("INVALID_BASE_TRANSITION_TAU0")
    scale = tau/tau0
    result = {
        "retarget_a": scale*float(base_transition["retarget_a_s"]),
        "retarget_b": scale*float(base_transition["retarget_b_s"]),
        "acquisition": scale*float(base_transition["acquisition_s"]),
        "scale": scale,
    }
    result["effective_tau_setup_s"] = max(
        result["retarget_a"], result["retarget_b"]) + result["acquisition"]
    if abs(result["effective_tau_setup_s"]-tau) > 1e-10:
        raise AssertionError("E1_SETUP_MAPPING_ERROR")
    return result


def common_drain_limit_s(t_demand_s):
    value = float(t_demand_s)
    if value <= 0:
        raise ValueError("POSITIVE_DEMAND_TIMESCALE_REQUIRED")
    return value + max(60.0, 2.0*value)


def _catalog(template, target_end_s):
    a, b = template["target_dynamic_pair"]
    if tuple(a) > tuple(b):
        a, b = b, a
    row = TerminalPairWindow(
        sat_a=a[0], terminal_a=a[1], sat_b=b[0], terminal_b=b[1],
        start_s=0.0, end_s=float(target_end_s), parent_start_s=0.0,
        parent_end_s=float(target_end_s), plane_gap=1, distance_km=1000.0)
    planes = {node: index for index, node in enumerate(template["nodes"])}
    return TerminalPairCatalog((row,), planes)


def _activate_old(executor, template, old_end_s):
    a, b = template["old_dynamic_pair"]
    executor.submit((Connect(tuple(a), tuple(b), float(old_end_s),
                             0.0, 0.0, 0.0),))


def build_action(template, tau_setup_s, target_end_s, action_time_s=0.0,
                 action_id="E1_REAL_SWITCH"):
    mapped = scale_setup(template["base_transition"], tau_setup_s)
    a, b = template["target_dynamic_pair"]
    proposal = {
        "a": tuple(a), "b": tuple(b),
        "retarget_a": mapped["retarget_a"],
        "retarget_b": mapped["retarget_b"],
        "acquisition": mapped["acquisition"],
    }
    release = template.get("release_after", ())
    if release:
        proposal["release_after"] = tuple(
            (tuple(pair[0]), tuple(pair[1])) for pair in release)
    physical = TerminalPairPhysicalFeasibility(_catalog(template, target_end_s))
    policy_row = template["policy"]
    policy = OperationalPolicy(policy_row["mode"], policy_row["max_outage_s"])
    horizon = float(action_time_s)+float(tau_setup_s)+1e-7
    return ScriptedProposal(
        float(action_time_s), str(action_id), proposal, physical, policy,
        horizon, None)


def build_base_engine(template, rho, t_demand_s, target_end_s, router_id,
                      drain_limit_s):
    commodities = tuple(Commodity(
        row["commodity_id"], row["source"], row["destination"], row["weight"])
        for row in template["commodities"])
    alpha = (float(template["capacity_bit_s_per_direction"])
             * float(template["reference_alpha_factor"]))
    rates = {row["commodity_id"]: float(rho)*alpha*float(row["reference_shape"])
             for row in template["commodities"]}
    trace = PiecewiseConstantTrafficTrace(
        tuple(sorted(rates)),
        (TrafficSegment(0.0, float(t_demand_s), rates, "E1_ACTIVE_PROFILE"),))
    executor = TerminalExecutor(template["nodes"])
    _activate_old(executor, template, max(float(drain_limit_s),
                                          float(target_end_s))+100.0)
    if router_id == ROUTER_PRIMARY:
        router = DeterministicShortestPropagationDelayRouter()
    elif router_id == ROUTER_ROBUSTNESS:
        router = DeterministicLoadAwareRouter()
    else:
        raise ValueError("UNKNOWN_E1_ROUTER")
    return E1TransitionEngine(
        template["nodes"], template["fixed_edges"],
        template["capacity_bit_s_per_direction"], commodities, trace,
        ConstantEdgeDelay(template["edge_delay_s"]), executor, (), router,
        conservation_abs_tolerance_bits=1.0,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=0.01,
    )


def _branch_summary(branch):
    result = branch["result"]
    metrics = result["metrics"]
    action_result = branch["action_result"]
    return {
        "status": branch["status"],
        "J_bit_s": branch["J_bit_s"],
        "J_by_commodity_bit_s": branch["J_by_commodity_bit_s"],
        "mean_bit_delay_s": metrics["mean_bit_delay_s"],
        "peak_queue_bits": metrics["max_queue_bits"],
        "transition_backlog_bits": metrics["backlog_added_during_transition_bits"],
        "peak_transition_backlog_bits": metrics["peak_transition_backlog_bits"],
        "no_route_duration_s": metrics["no_route_duration_s"],
        "route_change_count": metrics["route_change_count"],
        "delivered_bits": metrics["delivered_bits"],
        "residual_backlog_bits": metrics["residual_backlog_bits"],
        "censored": metrics["censored"],
        "max_abs_conservation_error_bits": metrics["max_abs_conservation_error_bits"],
        "negative_queue_count": metrics["negative_queue_count"],
        "max_capacity_violation_bit_s": metrics["max_capacity_violation_bit_s"],
        "action_accepted": None if action_result is None else action_result["accepted"],
        "physical_reason": None if action_result is None else action_result["physical_reason"],
        "policy_reason": None if action_result is None else action_result["policy_reason"],
        "target_signature": branch["target_signature"],
        "pre_action_state_hash": branch["pre_action_state_hash"],
        "future_trace_hash": branch["future_trace_hash"],
        "network_signature": branch["network_signature"],
    }


def evaluate_point(point, templates=None, include_delayed=False):
    templates = frozen_templates() if templates is None else templates
    template = templates[point["template_id"]]
    drain_limit = float(point["drain_limit_s"])
    base = build_base_engine(
        template, point["rho"], point["T_demand_s"],
        point["L_remain_s"], point["router_id"], drain_limit)
    action = build_action(
        template, point["tau_setup_s"], point["L_remain_s"], 0.0,
        point["experiment_id"]+"_REAL")
    harness = PairedCounterfactualHarness(base, 0.0, action, drain_limit)
    ratios = tuple(point.get("delay_switch_ratios", ())) if include_delayed else ()
    paired = harness.run()
    # Gate C policy_horizon_s is absolute, so delay action and horizon together.
    # This E1 adapter leaves the frozen E0 generic harness unchanged.
    for ratio in ratios:
        delayed_time = float(ratio)*float(point["T_demand_s"])
        delayed_action = replace(
            action, time_s=delayed_time,
            action_id=f"DELAYED_SWITCH_{float(ratio):g}",
            policy_horizon_s=(delayed_time+float(point["tau_setup_s"])+1e-7),
            expected_accept=None)
        paired["branches"][delayed_action.action_id] = harness._branch(
            delayed_action.action_id, delayed_action)
    branches = {name: _branch_summary(branch)
                for name, branch in paired["branches"].items()}
    required_censored = any(branches[name]["censored"] for name in REQUIRED_BRANCHES)
    required_executed = all(branches[name]["status"] == "EXECUTED"
                            for name in REQUIRED_BRANCHES)
    if required_censored:
        reversal_status = "NOT_EVALUABLE_CENSORED"
        reversal = {"r_ideal": None, "r_real": None}
        break_even_use = False
    elif not required_executed:
        reversal_status = "NOT_EVALUABLE_INFEASIBLE"
        reversal = {"r_ideal": None, "r_real": None}
        break_even_use = False
    else:
        reversal = reversal_classification(
            branches["HOLD"]["J_bit_s"], branches["IDEAL_SWITCH"]["J_bit_s"],
            branches["REAL_SWITCH"]["J_bit_s"])
        reversal_status = reversal["classification"]
        break_even_use = True
    focus = template["focus_commodities"]
    real_effect = third_party_effect(
        branches["HOLD"]["J_by_commodity_bit_s"],
        branches["REAL_SWITCH"]["J_by_commodity_bit_s"], focus)
    ideal_effect = third_party_effect(
        branches["HOLD"]["J_by_commodity_bit_s"],
        branches["IDEAL_SWITCH"]["J_by_commodity_bit_s"], focus)
    result = {
        "experiment_id": point["experiment_id"], "study": point["study"],
        "template_id": point["template_id"], "router_id": point["router_id"],
        "rho": point["rho"], "tau_setup_s": point["tau_setup_s"],
        "kappa1": point.get("kappa1"), "kappa2": point.get("kappa2"),
        "T_demand_s": point["T_demand_s"], "L_remain_s": point["L_remain_s"],
        "drain_limit_s": drain_limit,
        "branches": branches,
        "delta_J_ideal_bit_s": branches["IDEAL_SWITCH"]["J_bit_s"]-branches["HOLD"]["J_bit_s"],
        "delta_J_real_bit_s": branches["REAL_SWITCH"]["J_bit_s"]-branches["HOLD"]["J_bit_s"],
        "r_ideal": reversal["r_ideal"], "r_real": reversal["r_real"],
        "reversal_status": reversal_status, "break_even_use": break_even_use,
        "focus_delta_J_real_bit_s": real_effect["delta_J_focus_bit_s"],
        "third_party_delta_J_real_bit_s": real_effect["delta_J_third_bit_s"],
        "focus_delta_J_ideal_bit_s": ideal_effect["delta_J_focus_bit_s"],
        "third_party_delta_J_ideal_bit_s": ideal_effect["delta_J_third_bit_s"],
        "paired_identity": {
            "pre_action_state_hashes_equal": paired["all_pre_action_state_hashes_equal"],
            "future_trace_hashes_equal": paired["all_future_trace_hashes_equal"],
            "same_target_real_ideal": paired["same_target_real_ideal"],
        },
    }
    if ratios:
        result["delayed_branches"] = {
            name: branches[name] for name in sorted(branches)
            if name.startswith("DELAYED_SWITCH_")}
    return result


def validate_point_physics(point, templates=None):
    """Pre-run structural legality only; no network objective is evaluated."""
    templates = frozen_templates() if templates is None else templates
    template = templates[point["template_id"]]
    drain = float(point["drain_limit_s"])
    engine = build_base_engine(
        template, point["rho"], point["T_demand_s"], point["L_remain_s"],
        point["router_id"], drain)
    action = build_action(template, point["tau_setup_s"], point["L_remain_s"])
    physical = action.physical_layer.evaluate(engine.executor, **action.proposal)
    if not physical["accepted"]:
        return {"legal": False, "reason": physical["reason"]}
    ready = max(action.proposal["retarget_a"], action.proposal["retarget_b"])+action.proposal["acquisition"]
    return {"legal": ready < point["L_remain_s"], "reason": None,
            "ready_s": ready, "visibility_end_s": point["L_remain_s"]}


def break_even_summary(samples):
    eligible = [{"tau_setup_s": row["tau_setup_s"],
                 "delta_J_bit_s": row["delta_J_real_bit_s"],
                 "status": "EXECUTED"}
                for row in samples if row["break_even_use"]]
    return break_even_brackets(eligible)
