"""Gate E0 paired-counterfactual and break-even harness definitions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math


REVERSAL_DEADBAND = 1e-9


def target_signature(action):
    proposal = action.proposal
    endpoints = tuple(sorted((tuple(proposal["a"]), tuple(proposal["b"]))))
    releases = tuple(sorted(tuple(sorted((tuple(a), tuple(b))))
                            for a, b in proposal.get("release_after", ())))
    return {"endpoints": endpoints, "release_after": releases}


def with_total_setup(action, setup_s, action_id=None, time_s=None,
                     expected_accept=None):
    setup_s = float(setup_s)
    if not math.isfinite(setup_s) or setup_s < 0:
        raise ValueError("INVALID_SETUP_DURATION")
    proposal = deepcopy(action.proposal)
    if any(key in proposal for key in (
            "setup_cost_weight", "switch_penalty", "outage_penalty")):
        raise ValueError("HIDDEN_OBJECTIVE_PENALTY_FORBIDDEN")
    proposal["retarget_a"] = setup_s
    proposal["retarget_b"] = setup_s
    proposal["acquisition"] = 0.0
    return replace(action, proposal=proposal,
                   action_id=action_id or action.action_id,
                   time_s=action.time_s if time_s is None else float(time_s),
                   expected_accept=expected_accept)


def reversal_classification(j_hold, j_ideal, j_real, epsilon=REVERSAL_DEADBAND):
    values = tuple(float(x) for x in (j_hold, j_ideal, j_real))
    if any(not math.isfinite(x) for x in values):
        raise ValueError("NONFINITE_COUNTERFACTUAL_OBJECTIVE")
    if j_hold <= 0:
        return {"classification": "UNDEFINED_ZERO_HOLD_OBJECTIVE",
                "r_ideal": None, "r_real": None, "epsilon_r": epsilon}
    r_ideal = (j_ideal-j_hold)/j_hold
    r_real = (j_real-j_hold)/j_hold
    if abs(r_ideal) <= epsilon or abs(r_real) <= epsilon:
        label = "NUMERICALLY_TIED"
    elif r_ideal < -epsilon and r_real > epsilon:
        label = "SETUP_INDUCED_DECISION_REVERSAL"
    elif r_ideal > epsilon and r_real < -epsilon:
        label = "REVERSE_DIRECTION_REVERSAL"
    else:
        label = "NO_REVERSAL"
    return {"classification": label, "r_ideal": r_ideal, "r_real": r_real,
            "epsilon_r": epsilon}


def third_party_effect(objective_hold, objective_switch, focus_commodities):
    focus = set(focus_commodities)
    if set(objective_hold) != set(objective_switch):
        raise ValueError("COMMODITY_OBJECTIVE_SET_MISMATCH")
    delta = {key: objective_switch[key]-objective_hold[key]
             for key in sorted(objective_hold)}
    return {
        "delta_J_by_commodity_bit_s": delta,
        "delta_J_focus_bit_s": sum(value for key, value in delta.items() if key in focus),
        "delta_J_third_bit_s": sum(value for key, value in delta.items() if key not in focus),
        "focus_commodities": sorted(focus),
        "third_party_commodities": sorted(set(delta)-focus),
    }


def _canonical_network_signature(result):
    metrics = dict(result["metrics"]); metrics.pop("runtime", None)
    document = {
        "metrics": metrics, "timeline": result["timeline"],
        "queues": result["queues"], "in_flight": result["in_flight"],
        "arrived": result["arrived_by_commodity"],
        "delivered": result["delivered_by_commodity"],
        "transmitted": result["transmitted_by_edge_commodity"],
        "routes": result["routes"], "route_changes": result["route_changes"],
        "route_state_events": result["route_state_events"],
        "graph_event_sequence": result["graph_event_sequence"],
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PairedCounterfactualHarness:
    """Clone one state and vary only the registered reconfiguration action."""

    def __init__(self, base_engine, decision_time_s, real_action, drain_limit_s,
                 numerical_deadband=REVERSAL_DEADBAND):
        self.base = base_engine.clone().advance_to(float(decision_time_s))
        self.decision_time_s = float(decision_time_s)
        if self.base.now != self.base.executor.now:
            raise AssertionError("CROSS_LAYER_CLOCK_NOT_SETTLED")
        self.real_action = replace(real_action, time_s=self.decision_time_s,
                                   expected_accept=None)
        self.drain_limit_s = float(drain_limit_s)
        self.deadband = float(numerical_deadband)
        self.initial_state_hash = self.base.canonical_state_sha256()
        self.prefix_objective = dict(self.base.objective_by_commodity)

    def _branch(self, name, action=None):
        engine = self.base.clone()
        pre_hash = engine.canonical_state_sha256()
        if action is not None:
            engine.schedule_action(action)
        result = engine.run(self.drain_limit_s)
        action_result = (next((x for x in result["action_results"]
                              if action is not None and x["action_id"] == action.action_id), None))
        if action is None:
            status = "EXECUTED"
        elif action_result and action_result["accepted"]:
            status = "EXECUTED"
        else:
            reason = None if action_result is None else (
                action_result.get("physical_reason") or action_result.get("policy_reason"))
            status = ("INFEASIBLE_SETUP_EXCEEDS_WINDOW" if reason == "INSUFFICIENT_LIFETIME"
                      else "INFEASIBLE_AT_EXECUTION_TIME")
        if status == "EXECUTED" and result["metrics"]["censored"]:
            status = "CENSORED_AT_DRAIN_LIMIT"
        by_commodity = {
            key: engine.objective_by_commodity[key]-self.prefix_objective.get(key, 0.0)
            for key in sorted(engine.by_id)}
        return {"branch": name, "status": status, "pre_action_state_hash": pre_hash,
                "future_trace_hash": result["metrics"]["trace_sha256"],
                "J_bit_s": sum(by_commodity.values()),
                "J_by_commodity_bit_s": by_commodity,
                "target_signature": None if action is None else target_signature(action),
                "network_signature": _canonical_network_signature(result),
                "action_result": action_result, "result": result,
                "objective_source": "unfinished-work area from network dynamics only"}

    def run(self, delayed_ratios=(), demand_timescale_s=None, include_mbb_alias=False):
        hold = self._branch("HOLD")
        real = self._branch("REAL_SWITCH", self.real_action)
        ideal_action = with_total_setup(
            self.real_action, 0.0, "IDEAL_SWITCH", self.decision_time_s, None)
        ideal = self._branch("IDEAL_SWITCH", ideal_action)
        if real["target_signature"] != ideal["target_signature"]:
            raise AssertionError("REAL_AND_IDEAL_TARGET_MISMATCH")
        branches = {"HOLD": hold, "REAL_SWITCH": real, "IDEAL_SWITCH": ideal}
        if delayed_ratios:
            if demand_timescale_s is None or demand_timescale_s <= 0:
                raise ValueError("POSITIVE_DEMAND_TIMESCALE_REQUIRED")
            for ratio in delayed_ratios:
                ratio = float(ratio)
                if ratio not in (0.0, 0.25, 0.5):
                    raise ValueError("UNREGISTERED_DELAY_RATIO")
                action = replace(self.real_action,
                                 time_s=self.decision_time_s+ratio*demand_timescale_s,
                                 action_id=f"DELAYED_SWITCH_{ratio:g}",
                                 expected_accept=None)
                branches[action.action_id] = self._branch(action.action_id, action)
        if include_mbb_alias:
            if not self.real_action.proposal.get("release_after"):
                raise ValueError("MBB_ALIAS_REQUIRES_GENUINE_RELEASE_AFTER")
            mbb_action = replace(self.real_action, action_id="MBB_SWITCH")
            branches["MBB_SWITCH"] = self._branch("MBB_SWITCH", mbb_action)
        metrics = {
            "delta_J_real_bit_s": real["J_bit_s"]-hold["J_bit_s"],
            "delta_J_ideal_bit_s": ideal["J_bit_s"]-hold["J_bit_s"],
        }
        metrics.update(reversal_classification(
            hold["J_bit_s"], ideal["J_bit_s"], real["J_bit_s"], self.deadband))
        metrics["relative_effect_real"] = metrics["r_real"]
        metrics["relative_effect_ideal"] = metrics["r_ideal"]
        return {"initial_state_hash": self.initial_state_hash,
                "all_pre_action_state_hashes_equal": all(
                    x["pre_action_state_hash"] == self.initial_state_hash
                    for x in branches.values()),
                "all_future_trace_hashes_equal": len({
                    x["future_trace_hash"] for x in branches.values()}) == 1,
                "same_target_real_ideal": real["target_signature"] == ideal["target_signature"],
                "branches": branches, "metrics": metrics,
                "hidden_penalty_fields": []}


def setup_grid_plan(setup_grid_s):
    values = tuple(float(x) for x in setup_grid_s)
    if values != tuple(sorted(set(values))) or any(x < 0 for x in values):
        raise ValueError("SETUP_GRID_MUST_BE_UNIQUE_SORTED_NONNEGATIVE")
    return [{"tau_setup_s": value, "status": "PLANNED_NOT_EXECUTED"}
            for value in values]


def break_even_brackets(samples):
    valid = sorted((float(x["tau_setup_s"]), float(x["delta_J_bit_s"]))
                   for x in samples if x.get("status", "EXECUTED") == "EXECUTED")
    brackets = []
    exact = []
    for tau, delta in valid:
        if delta == 0.0:
            exact.append(tau)
    for (a, fa), (b, fb) in zip(valid[:-1], valid[1:]):
        if fa*fb < 0:
            brackets.append([a, b])
    if len(brackets) > 1:
        status = "MULTIPLE_BREAK_EVEN_INTERVALS"
    elif brackets or exact:
        status = "BREAK_EVEN_BRACKETED"
    else:
        status = "NO_BREAK_EVEN_IN_SCANNED_RANGE"
    return {"status": status, "brackets_s": brackets,
            "exact_grid_crossings_s": exact}


def refine_break_even(evaluate_delta, left_s, right_s, tolerance_s=0.01,
                      max_iterations=100):
    left, right = float(left_s), float(right_s)
    tolerance = float(tolerance_s)
    f_left, f_right = float(evaluate_delta(left)), float(evaluate_delta(right))
    if not left < right or tolerance <= 0 or f_left*f_right >= 0:
        raise ValueError("VALID_SIGN_CHANGING_BRACKET_REQUIRED")
    history = [(left, f_left), (right, f_right)]
    for _ in range(max_iterations):
        if right-left <= tolerance:
            break
        middle = (left+right)/2.0; f_middle = float(evaluate_delta(middle))
        history.append((middle, f_middle))
        if f_middle == 0.0:
            left = right = middle; break
        if f_left*f_middle < 0:
            right, f_right = middle, f_middle
        else:
            left, f_left = middle, f_middle
    return {"status": "REFINED", "interval_s": [left, right],
            "width_s": right-left, "tolerance_s": tolerance,
            "history": [{"tau_setup_s": x, "delta_J_bit_s": y}
                        for x, y in history]}


class SetupSweepFramework:
    """Execution framework; E0 only validates it and does not run the full grid."""

    def __init__(self, base_engine, decision_time_s, action_template, drain_limit_s):
        self.base_engine = base_engine
        self.decision_time_s = float(decision_time_s)
        self.action_template = action_template
        self.drain_limit_s = float(drain_limit_s)

    def execute_registered_grid(self, setup_grid_s):
        rows = []
        for tau in setup_grid_s:
            action = with_total_setup(
                self.action_template, tau, f"REAL_SWITCH_TAU_{float(tau):g}",
                self.decision_time_s, None)
            paired = PairedCounterfactualHarness(
                self.base_engine, self.decision_time_s, action,
                self.drain_limit_s).run()
            real = paired["branches"]["REAL_SWITCH"]
            rows.append({"tau_setup_s": float(tau), "status": real["status"],
                         "delta_J_bit_s": paired["metrics"]["delta_J_real_bit_s"]
                         if real["status"] == "EXECUTED" else None})
        return {"samples": rows, "break_even": break_even_brackets(rows)}

