"""Gate F1 scientific B1/B3 controllers using the shared frozen V_v2."""
from __future__ import annotations

import math

from .baseline_controllers import ControllerAction
from .scientific_snapshot import ScientificSnapshotEvaluator


FORBIDDEN_FUTURE_FIELDS = frozenset({
    "future_trace", "future_trace_sha256", "future_action_ids",
    "realized_future_traffic", "final_J", "forecast",
})


def _json_number(value):
    value = float(value)
    if math.isinf(value):
        return "Infinity" if value > 0.0 else "-Infinity"
    if math.isnan(value):
        raise ValueError("SCIENTIFIC_SCORE_NAN")
    return value


class _ScientificControllerBase:
    information_class = "CURRENT_STATE_ONLY"
    evaluator_class = ScientificSnapshotEvaluator
    requires_scientific_snapshot = True

    def __init__(self, engine):
        self.engine = engine
        self.evaluator = self.evaluator_class(engine)

    def _assert_information_firewall(self, current_state, context):
        leaked = FORBIDDEN_FUTURE_FIELDS & (set(current_state) | set(context))
        if leaked:
            raise AssertionError("SCIENTIFIC_CURRENT_STATE_FIREWALL_VIOLATION")
        if abs(float(current_state["time_s"])-float(self.engine.now)) > 1e-12:
            raise AssertionError("SCIENTIFIC_SCORING_STATE_TIME_MISMATCH")

    def _values(self, current_state, proposal_set, context):
        self._assert_information_firewall(current_state, context)
        hold, candidates = self.evaluator.evaluate_proposal_set(proposal_set)
        return hold, candidates

    def on_action_result(self, record):
        return None


class IgnoreSetupDynamicController(_ScientificControllerBase):
    """B1: minimize V_v2 on instantaneous ideal target topologies."""

    controller_id = "B1_IGNORE_SETUP_DYNAMIC"

    def observe(self, current_state, proposal_set, context):
        hold, candidates = self._values(current_state, proposal_set, context)
        if hold.total_unfinished_bits <= 0.0:
            return ControllerAction("HOLD", decision_metadata=(
                ("reason", "ZERO_TOTAL_UNFINISHED_WORK"),
                ("scientific_score", "V_v2")))
        best_id = None
        best_value = hold.value_bit_s
        for proposal_id, evaluation in candidates:  # frozen proposer order
            if evaluation.value_bit_s < best_value:
                best_id = proposal_id
                best_value = evaluation.value_bit_s
        improvement = hold.value_bit_s-best_value
        metadata = (
            ("decision_assumed_setup_s", 0.0),
            ("scientific_score", "V_v2"),
            ("V_hold_bit_s", _json_number(hold.value_bit_s)),
            ("V_selected_bit_s", _json_number(best_value)),
            ("improvement", _json_number(improvement)),
            ("multi_step_rollout", False),
        )
        return (ControllerAction("REPLACE", best_id, metadata)
                if best_id is not None else ControllerAction("HOLD",
                                                               decision_metadata=metadata))


class SetupAwareGreedyController(_ScientificControllerBase):
    """B3: maximize positive DeltaV times usable/remaining lifetime."""

    controller_id = "B3_SETUP_AWARE_GREEDY"

    def observe(self, current_state, proposal_set, context):
        hold, candidates = self._values(current_state, proposal_set, context)
        if hold.total_unfinished_bits <= 0.0:
            return ControllerAction("HOLD", decision_metadata=(
                ("reason", "ZERO_TOTAL_UNFINISHED_WORK"),
                ("scientific_score", "V_v2")))
        records = {row["proposal_id"]: row for row in proposal_set["proposals"]}
        best_id = None
        best_score = 0.0
        best_delta = None
        best_eta = None
        for proposal_id, evaluation in candidates:  # frozen proposer order
            delta = hold.value_bit_s-evaluation.value_bit_s
            if delta <= 0.0:
                continue
            record = records[proposal_id]
            remaining = float(record["remaining_lifetime_s"])
            usable = float(record["usable_lifetime_s"])
            if remaining <= 0.0 or usable <= 0.0:
                continue
            eta = usable/remaining
            score = delta*eta
            if score > best_score:
                best_id, best_score = proposal_id, score
                best_delta, best_eta = delta, eta
        if best_id is None:
            return ControllerAction("HOLD", decision_metadata=(
                ("scientific_score", "V_v2"),
                ("reason", "NO_POSITIVE_SETUP_AWARE_SCORE"),
                ("multi_step_rollout", False)))
        return ControllerAction("REPLACE", best_id, (
            ("scientific_score", "V_v2"),
            ("improvement", _json_number(best_delta)),
            ("eta", _json_number(best_eta)),
            ("S_c", _json_number(best_score)),
            ("uses_actual_setup_metadata", True),
            ("multi_step_rollout", False),
        ))
