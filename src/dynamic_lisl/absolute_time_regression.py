"""Synthetic global-time-translation regression spanning Gate C/B/D2/E0."""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math

from .commodity import Commodity
from .common_router import DeterministicShortestPropagationDelayRouter
from .gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .gate_e1_experiments import ConstantEdgeDelay, E1TransitionEngine, frozen_templates
from .mechanism_validation import (
    PairedCounterfactualHarness, reversal_classification, with_total_setup,
)
from .operational_policy import OperationalPolicy
from .terminal_executor import Connect, TerminalExecutor
from .terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from .transition_profiler import profile_transition
from .transition_service_orchestrator import ScriptedProposal


FRAME_ID = "PRE_E2_SYNTHETIC_ABSOLUTE_TIME_V1"
SHIFTS_S = (0.0, 7.25, 100.0)
BASE_DECISION_TIME_S = 5.0
DELAY_OFFSET_S = 2.5
SETUP_S = 2.0
WINDOW_START_OFFSET_S = 1.0
WINDOW_END_OFFSET_S = 10.0
TRAFFIC_END_OFFSET_S = 10.0
DRAIN_END_OFFSET_S = 70.0


@dataclass(frozen=True)
class AbsoluteTrafficSegment:
    start_s: float
    end_s: float
    rates_bit_s: dict
    label: str


class AbsolutePiecewiseTrafficTrace:
    """External fluid trace whose absolute timestamps need not start at zero."""

    schema = "pre_e2_absolute_piecewise_fluid_trace_v1"

    def __init__(self, commodity_ids, segments, frame_id=FRAME_ID):
        self.commodity_ids = tuple(commodity_ids)
        self.segments = tuple(segments)
        self.absolute_time_frame_id = str(frame_id)
        if not self.commodity_ids or not self.segments:
            raise ValueError("EMPTY_ABSOLUTE_TRAFFIC_TRACE")
        previous = None
        for segment in self.segments:
            if (not math.isfinite(segment.start_s)
                    or not math.isfinite(segment.end_s)
                    or segment.end_s <= segment.start_s):
                raise ValueError("INVALID_ABSOLUTE_TRAFFIC_SEGMENT")
            if previous is not None and segment.start_s != previous:
                raise ValueError("NONCONTIGUOUS_ABSOLUTE_TRAFFIC_SEGMENTS")
            if set(segment.rates_bit_s) != set(self.commodity_ids):
                raise ValueError("ABSOLUTE_TRAFFIC_COMMODITY_MISMATCH")
            previous = segment.end_s
        self.arrival_horizon_s = self.segments[-1].end_s

    def rate_at(self, time_s):
        time_s = float(time_s)
        if time_s < 0:
            raise ValueError("NEGATIVE_TRACE_TIME")
        for segment in self.segments:
            if segment.start_s <= time_s < segment.end_s:
                return dict(segment.rates_bit_s)
        return {key: 0.0 for key in self.commodity_ids}

    def boundaries_after(self, time_s):
        values = {segment.start_s for segment in self.segments
                  if segment.start_s > time_s}
        values.update(segment.end_s for segment in self.segments
                      if segment.end_s > time_s)
        return tuple(sorted(values))

    def to_dict(self):
        return {
            "schema": self.schema,
            "absolute_time_frame_id": self.absolute_time_frame_id,
            "commodity_ids": list(self.commodity_ids),
            "arrival_horizon_s": self.arrival_horizon_s,
            "segments": [{
                "start_s": row.start_s, "end_s": row.end_s,
                "rates_bit_s": {key: row.rates_bit_s[key]
                                for key in sorted(row.rates_bit_s)},
                "label": row.label,
            } for row in self.segments],
        }

    def sha256(self):
        payload = json.dumps(self.to_dict(), sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def relative_sha256(self, shift_s):
        document = self.to_dict()
        document.pop("arrival_horizon_s")
        for row in document["segments"]:
            row["start_s"] = _round(row["start_s"]-shift_s)
            row["end_s"] = _round(row["end_s"]-shift_s)
        document["relative_arrival_horizon_s"] = _round(
            self.arrival_horizon_s-shift_s)
        payload = json.dumps(document, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AbsoluteTimeContract:
    absolute_time_frame_id: str
    decision_time_s: float
    action_time_s: float
    profiler_horizon_s: float
    window_start_s: float
    window_end_s: float
    arrival_horizon_s: float
    drain_horizon_s: float
    setup_s: float
    delayed_action_offset_s: float
    traffic_frame_id: str
    window_frame_id: str
    action_frame_id: str
    profiler_frame_id: str

    def validate(self):
        frames = {self.absolute_time_frame_id, self.traffic_frame_id,
                  self.window_frame_id, self.action_frame_id,
                  self.profiler_frame_id}
        if len(frames) != 1:
            raise ValueError("ABSOLUTE_TIME_FRAME_ID_MISMATCH")
        if abs((self.action_time_s-self.decision_time_s)
               - self.delayed_action_offset_s) > 1e-12:
            raise ValueError("DELAYED_ACTION_OFFSET_MISMATCH")
        if not self.window_start_s <= self.action_time_s < self.window_end_s:
            raise ValueError("ACTION_OUTSIDE_ABSOLUTE_TERMINAL_WINDOW")
        if self.profiler_horizon_s <= self.action_time_s:
            raise ValueError(
                "ABSOLUTE_TIME_FRAME_MISMATCH_STALE_PROFILER_HORIZON")
        expected = self.action_time_s+self.setup_s+1e-7
        if abs(self.profiler_horizon_s-expected) > 1e-10:
            raise ValueError("PROFILER_HORIZON_NOT_TRANSLATED_WITH_ACTION")
        if not self.arrival_horizon_s < self.drain_horizon_s:
            raise ValueError("DRAIN_HORIZON_NOT_AFTER_ARRIVAL_HORIZON")
        return True


def _round(value):
    return round(float(value), 10)


def _work(value):
    """Canonicalize below the frozen 0.01-bit state tolerance."""
    value = float(value)
    if abs(value) < 1e-3:
        return 0.0
    return round(value, 3)


ABSOLUTE_TIME_KEYS = {
    "time", "time_s", "start", "end", "start_s", "end_s", "ready",
    "predicted_ready", "drain_end", "visibility_end", "retarget_start",
    "retarget_end", "acquisition_end", "active_link_start",
    "terminal_free_time", "expires_at",
}


def _work_map(values):
    result = {key: _work(value) for key, value in values.items()}
    return {key: value for key, value in result.items() if value != 0.0}


def _normalize_payload(value, shift_s, key=None):
    if isinstance(value, dict):
        result = {name: _normalize_payload(item, shift_s, name)
                  for name, item in value.items()}
        return {name: item for name, item in result.items()
                if not (isinstance(item, float) and item == 0.0
                        and name not in ABSOLUTE_TIME_KEYS)}
    if isinstance(value, (list, tuple)):
        return [_normalize_payload(item, shift_s, key) for item in value]
    if isinstance(value, float):
        if key in ABSOLUTE_TIME_KEYS:
            return _round(value-shift_s)
        if key and ("bit" in key or "queue" in key or "work" in key
                    or "delivered" in key or "arrived" in key
                    or "transmitted" in key or "conservation" in key):
            return _work(value)
        if abs(value) < 1e-12:
            return 0.0
        return round(value, 10)
    return value


def _traffic(decision_time_s, shift_s):
    rates1 = {"focus": 0.6e9}
    rates2 = {"focus": 0.8e9}
    return AbsolutePiecewiseTrafficTrace(
        ("focus",), (
            AbsoluteTrafficSegment(decision_time_s, decision_time_s+4.0,
                                   rates1, "PHASE_1"),
            AbsoluteTrafficSegment(decision_time_s+4.0,
                                   decision_time_s+TRAFFIC_END_OFFSET_S,
                                   rates2, "PHASE_2"),
        ))


def _target_catalog(template, window_start_s, window_end_s):
    a, b = template["target_dynamic_pair"]
    if tuple(a) > tuple(b):
        a, b = b, a
    window = TerminalPairWindow(
        sat_a=a[0], terminal_a=a[1], sat_b=b[0], terminal_b=b[1],
        start_s=window_start_s, end_s=window_end_s,
        parent_start_s=window_start_s, parent_end_s=window_end_s,
        plane_gap=1, distance_km=1000.0)
    planes = {node: index for index, node in enumerate(template["nodes"])}
    return TerminalPairCatalog((window,), planes)


def build_translated_fixture(shift_s, stale_profiler=False,
                             action_after_window=False):
    shift_s = float(shift_s)
    template = frozen_templates()["E-B_BBM_CONNECTED_REROUTE"]
    decision = BASE_DECISION_TIME_S+shift_s
    action_time = decision+DELAY_OFFSET_S
    window_start = decision+WINDOW_START_OFFSET_S
    window_end = decision+WINDOW_END_OFFSET_S
    if action_after_window:
        action_time = window_end+0.5
    profiler_horizon = action_time+SETUP_S+1e-7
    if stale_profiler:
        profiler_horizon = (BASE_DECISION_TIME_S+DELAY_OFFSET_S
                            + SETUP_S+1e-7)
    arrival_horizon = decision+TRAFFIC_END_OFFSET_S
    drain_horizon = decision+DRAIN_END_OFFSET_S
    trace = _traffic(decision, shift_s)
    contract = AbsoluteTimeContract(
        FRAME_ID, decision, action_time, profiler_horizon,
        window_start, window_end, arrival_horizon, drain_horizon,
        SETUP_S, action_time-decision,
        trace.absolute_time_frame_id, FRAME_ID, FRAME_ID, FRAME_ID)
    if not action_after_window:
        contract.validate()

    executor = TerminalExecutor(template["nodes"])
    old_a, old_b = template["old_dynamic_pair"]
    executor.submit((Connect(tuple(old_a), tuple(old_b), drain_horizon+100.0,
                             0.0, 0.0, 0.0),))
    commodities = (Commodity("focus", "A", "D"),)
    engine = E1TransitionEngine(
        template["nodes"], template["fixed_edges"],
        template["capacity_bit_s_per_direction"], commodities, trace,
        ConstantEdgeDelay(template["edge_delay_s"]), executor, (),
        DeterministicShortestPropagationDelayRouter(),
        conservation_abs_tolerance_bits=1.0,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=0.01)
    mapped = {"retarget_a": 0.8, "retarget_b": 1.4,
              "acquisition": 0.6}
    target_a, target_b = template["target_dynamic_pair"]
    action = ScriptedProposal(
        action_time, "ABS_REAL", {
            "a": tuple(target_a), "b": tuple(target_b), **mapped,
        }, TerminalPairPhysicalFeasibility(
            _target_catalog(template, window_start, window_end)),
        OperationalPolicy("STRICT_CONNECTED"), profiler_horizon, None)
    return {
        "shift_s": shift_s, "template": template, "engine": engine,
        "action": action, "contract": contract, "trace": trace,
        "decision_time_s": decision, "action_time_s": action_time,
        "window_start_s": window_start, "window_end_s": window_end,
        "drain_horizon_s": drain_horizon,
    }


def _gate_c_at_execution(fixture):
    contract = fixture["contract"]
    contract.validate()
    engine = fixture["engine"].clone().advance_to(contract.action_time_s)
    if abs(engine.now-engine.executor.now) > 1e-12:
        raise AssertionError("ABSOLUTE_GATE_C_CLOCK_MISMATCH")
    physical = fixture["action"].physical_layer.evaluate(
        engine.executor, **fixture["action"].proposal)
    if not physical["accepted"]:
        return {"accepted": False, "reason": physical["reason"],
                "profile": None}
    profile = profile_transition(
        engine.executor, (physical["command"],), engine.fixed_edges,
        fixture["action"].policy_horizon_s)
    decision = fixture["action"].policy.apply(profile)
    return {"accepted": decision["accepted"], "reason": decision["reason"],
            "profile": profile, "physical": physical}


def _normalize_timeline(rows, shift_s, decision_time_s):
    result = []
    for row in rows:
        if row["time_s"] < decision_time_s-1e-9:
            continue
        item = _normalize_payload(dict(row), shift_s)
        result.append(item)
    return result


def _normalize_events(rows, shift_s, decision_time_s, time_key):
    result = []
    for row in rows:
        if row[time_key] < decision_time_s-1e-9:
            continue
        item = _normalize_payload(dict(row), shift_s)
        result.append(item)
    return result


def _relative_branch(branch, shift_s, decision_time_s):
    result = branch["result"]
    metrics = result["metrics"]
    selected_metrics = {
        key: metrics[key] for key in (
            "censored", "mean_bit_delay_s", "J_bit_s", "arrived_bits",
            "delivered_bits", "residual_backlog_bits", "max_queue_bits",
            "route_change_count", "switch_count", "BBM_count", "MBB_count",
            "no_route_duration_s", "outage_duration_s",
            "backlog_added_during_transition_bits",
            "peak_transition_backlog_bits", "max_abs_conservation_error_bits",
            "max_capacity_violation_bit_s", "negative_queue_count")}
    return {
        "status": branch["status"], "J_bit_s": _work(branch["J_bit_s"]),
        "J_by_commodity_bit_s": {key: _work(value)
                                 for key, value in branch["J_by_commodity_bit_s"].items()},
        "metrics": _normalize_payload(selected_metrics, 0.0),
        "timeline": _normalize_timeline(
            result["timeline"], shift_s, decision_time_s),
        "terminal_events": _normalize_events(
            result["terminal_event_sequence"], shift_s, decision_time_s, "time"),
        "graph_events": _normalize_events(
            result["graph_event_sequence"], shift_s, decision_time_s, "time_s"),
        "route_state_events": _normalize_events(
            result["route_state_events"], shift_s, decision_time_s, "time_s"),
        "route_changes": _normalize_events(
            result["route_changes"], shift_s, decision_time_s, "time_s"),
        "queues": _work_map(result["queues"]),
        "in_flight": _work_map(result["in_flight"]),
        "arrived": {key: _work(value) for key, value in result["arrived_by_commodity"].items()},
        "delivered": {key: _work(value) for key, value in result["delivered_by_commodity"].items()},
        "transmitted": {key: _work(value) for key, value in result["transmitted_by_edge_commodity"].items()},
    }


def run_translated_replay(shift_s):
    fixture = build_translated_fixture(shift_s)
    contract = fixture["contract"]
    gate_c = _gate_c_at_execution(fixture)
    if not gate_c["accepted"]:
        raise AssertionError("REGISTERED_ABSOLUTE_FIXTURE_GATE_C_REJECTED")
    harness = PairedCounterfactualHarness(
        fixture["engine"], contract.decision_time_s, fixture["action"],
        contract.drain_horizon_s)
    hold = harness._branch("HOLD")
    real = harness._branch("REAL_SWITCH", fixture["action"])
    ideal_action = with_total_setup(
        fixture["action"], 0.0, "IDEAL_SWITCH", contract.action_time_s, None)
    ideal_action = replace(
        ideal_action, policy_horizon_s=contract.action_time_s+1e-7)
    ideal = harness._branch("IDEAL_SWITCH", ideal_action)
    branches = {"HOLD": hold, "REAL_SWITCH": real, "IDEAL_SWITCH": ideal}
    classification = reversal_classification(
        hold["J_bit_s"], ideal["J_bit_s"], real["J_bit_s"])
    ready = contract.action_time_s+contract.setup_s
    relative = {
        "absolute_time_frame_id": contract.absolute_time_frame_id,
        "decision_time_minus_shift_s": _round(contract.decision_time_s-shift_s),
        "action_time_minus_shift_s": _round(contract.action_time_s-shift_s),
        "action_offset_s": _round(contract.action_time_s-contract.decision_time_s),
        "ready_offset_from_action_s": _round(ready-contract.action_time_s),
        "L_remain_s": _round(contract.window_end_s-contract.action_time_s),
        "L_usable_s": _round(contract.window_end_s-ready),
        "window_relative_s": [_round(contract.window_start_s-shift_s),
                              _round(contract.window_end_s-shift_s)],
        "profiler_horizon_minus_shift_s": _round(
            contract.profiler_horizon_s-shift_s),
        "gate_c": {
            "accepted": gate_c["accepted"], "reason": gate_c["reason"],
            "classification": gate_c["profile"]["classification"],
            "partition_occurs": gate_c["profile"]["partition_occurs"],
            "outage_duration": gate_c["profile"]["outage_duration"],
        },
        "transition_mode": real["action_result"]["transition_mode"],
        "reversal": _normalize_payload(classification, 0.0),
        "relative_traffic_trace_hash": fixture["trace"].relative_sha256(shift_s),
        "branches": {name: _relative_branch(branch, shift_s,
                                               contract.decision_time_s)
                     for name, branch in branches.items()},
    }
    payload = json.dumps(relative, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False)
    return {
        "shift_s": shift_s, "contract": contract.__dict__,
        "raw_traffic_trace_hash": fixture["trace"].sha256(),
        "relative_traffic_trace_hash": fixture["trace"].relative_sha256(shift_s),
        "relative": relative,
        "relative_time_canonical_hash": hashlib.sha256(
            payload.encode("utf-8")).hexdigest(),
    }


def run_out_of_window_negative(shift_s):
    fixture = build_translated_fixture(shift_s, action_after_window=True)
    contract = fixture["contract"]
    engine = fixture["engine"].clone().advance_to(contract.decision_time_s)
    harness = PairedCounterfactualHarness(
        engine, contract.decision_time_s, fixture["action"],
        contract.drain_horizon_s)
    branch = harness._branch("DELAYED_OUT_OF_WINDOW", fixture["action"])
    return {
        "status": branch["status"],
        "physical_reason": branch["action_result"]["physical_reason"],
        "target_signature": branch["target_signature"],
        "replacement_candidate_used": False,
    }


def stale_horizon_negative_control(shift_s=100.0):
    try:
        fixture = build_translated_fixture(shift_s, stale_profiler=True)
        fixture["contract"].validate()
    except ValueError as error:
        return {"caught": True, "error": str(error)}
    return {"caught": False, "error": None}
