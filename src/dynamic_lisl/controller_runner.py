"""Thin Gate F1 multi-epoch controller adapter over the frozen D2 engine."""
from __future__ import annotations

import hashlib
import json

from .baseline_controllers import ControllerAction
from .candidate_proposer import (FrozenTerminalPairProposer, RegimeSafetyAdapter,
                                 canonical_sha256)
from .outage_metrics import derive_separated_outage_metrics
from .transition_service_orchestrator import ScriptedProposal


def _jsonable_map(values, key_formatter):
    return {key_formatter(key): value for key, value in sorted(values.items())
            if value != 0.0}


def controller_visible_state(engine):
    """Right-continuous current state with all future realization fields removed."""
    external = engine.trace.rate_at(engine.now)
    document = {
        "schema": "gate_f1_controller_visible_state_v1",
        "time_s": engine.now,
        "G_active": [list(edge) for edge in engine.graph["active_edges"]],
        "G_admit": [list(edge) for edge in engine.graph["admit_edges"]],
        "active_components": [list(row) for row in engine.graph["active_components"]],
        "admit_components": [list(row) for row in engine.graph["admit_components"]],
        "terminal": engine.executor.snapshot(),
        "queues": engine.queues.snapshot(),
        "in_flight": engine.in_flight.snapshot(),
        "current_offered_rates_bit_s": dict(sorted(external.items())),
        "current_service_rates_bit_s": _jsonable_map(
            engine.service_rates,
            lambda key: key[0][0]+"->"+key[0][1]+"|"+key[1]),
        "routes": {node+"|"+key: (list(route) if route else None)
                   for (node, key), route in sorted(engine.routes.items())},
    }
    document["current_state_sha256"] = canonical_sha256(document)
    return document


class MultiEpochControllerRunner:
    """Call one controller at common 2-s epochs; physics remains event-driven."""

    def __init__(self, engine, physical_layer, fixed_edges, regime,
                 candidate_source, controller, *, t0_s=0.0,
                 decision_end_s=8.0, cadence_s=2.0, proposer=None):
        self.engine = engine
        self.physical_layer = physical_layer
        self.fixed_edges = tuple(fixed_edges)
        self.regime = str(regime)
        self.candidate_source = candidate_source
        self.controller = controller
        self.t0_s = float(t0_s)
        self.decision_end_s = float(decision_end_s)
        self.cadence_s = float(cadence_s)
        if self.cadence_s != 2.0:
            raise ValueError("GATE_F1_DECISION_CADENCE_MUST_BE_2_SECONDS")
        if self.t0_s < self.engine.now or self.decision_end_s < self.t0_s:
            raise ValueError("INVALID_DECISION_HORIZON")
        self.proposer = proposer or FrozenTerminalPairProposer()
        self.action_records = []
        self.callback_times = []

    def _epochs(self):
        value = self.t0_s
        while value <= self.decision_end_s+1e-12:
            yield value
            value += self.cadence_s

    def _record_action(self, epoch, state, proposal_set, action):
        if not isinstance(action, ControllerAction):
            raise TypeError("CONTROLLER_MUST_RETURN_CONTROLLER_ACTION")
        proposals = {row["proposal_id"]: row
                     for row in proposal_set["proposals"]}
        if action.kind == "REPLACE" and action.proposal_id not in proposals:
            raise ValueError("CONTROLLER_SELECTED_OUTSIDE_COMMON_PROPOSAL_SET")
        record = {
            "controller_id": self.controller.controller_id,
            "decision_epoch_s": epoch,
            "current_state_sha256": state["current_state_sha256"],
            "proposal_set_sha256": proposal_set["proposal_set_sha256"],
            "selected_action": action.to_dict(),
            "selected_proposal_id": action.proposal_id,
            "accepted": action.kind == "HOLD",
            "rejection_status": None,
            "rejection_reason": None,
            "resulting_gate_b_transition_type": None,
        }
        action_payload = {key: value for key, value in record.items()
                          if key != "action_canonical_sha256"}
        record["action_canonical_sha256"] = canonical_sha256(action_payload)
        return record

    def run(self, drain_limit_s):
        for index, epoch in enumerate(self._epochs()):
            self.engine.advance_to(epoch)
            if abs(self.engine.now-epoch) > 1e-12:
                raise AssertionError("DECISION_EPOCH_NOT_EXACT")
            self.callback_times.append(epoch)
            state = controller_visible_state(self.engine)
            if getattr(self.controller, "candidate_budget_not_used_by_design", False):
                empty = {
                    "schema": "gate_f1_proposal_set_v1", "time_s": epoch,
                    "regime": self.regime, "candidate_top_k": 16,
                    "quota": {"MBB_STRUCTURALLY_FEASIBLE": 8,
                              "BBM_REQUIRED": 8}, "proposals": [],
                }
                proposal_set = {
                    **empty, "proposal_set_sha256": canonical_sha256(empty),
                    "pruned": [], "candidate_specs": {},
                }
            else:
                candidates = tuple(self.candidate_source(state, {
                    "epoch_index": index, "regime": self.regime,
                    "terminal_executor": self.engine.executor,
                }))
                proposal_set = self.proposer.propose(
                    self.engine.executor, candidates, self.physical_layer,
                    self.fixed_edges, self.regime)
            public_set = {key: value for key, value in proposal_set.items()
                          if key != "candidate_specs"}
            action = self.controller.observe(state, public_set, {
                "regime": self.regime, "epoch_index": index,
                "information_class": getattr(self.controller, "information_class", None),
            })
            record = self._record_action(epoch, state, proposal_set, action)
            if action.kind == "REPLACE":
                spec = proposal_set["candidate_specs"][action.proposal_id]
                safety = RegimeSafetyAdapter(self.regime)
                scheduled = ScriptedProposal(
                    epoch, f"F1-{index:04d}-{action.proposal_id}", spec.proposal,
                    self.physical_layer, safety.policy,
                    max(epoch+1e-7,
                        next(row["ready_time_s"] for row in proposal_set["proposals"]
                             if row["proposal_id"] == action.proposal_id)+1e-7),
                    None)
                before = len(self.engine.action_results)
                self.engine.schedule_action(scheduled)
                self.engine.settle_current_time()
                if len(self.engine.action_results) != before+1:
                    raise AssertionError("CONTROLLER_ACTION_NOT_EXECUTED_AT_EPOCH")
                result = self.engine.action_results[-1]
                record["accepted"] = bool(result["accepted"])
                if not result["accepted"]:
                    record["rejection_status"] = "REJECTED"
                    record["rejection_reason"] = (result.get("policy_reason")
                                                   or result.get("physical_reason"))
                record["resulting_gate_b_transition_type"] = result.get("transition_mode")
            action_payload = {key: value for key, value in record.items()
                              if key != "action_canonical_sha256"}
            record["action_canonical_sha256"] = canonical_sha256(action_payload)
            self.controller.on_action_result(record)
            self.action_records.append(record)
        result = self.engine.run(float(drain_limit_s))
        separated = derive_separated_outage_metrics(result)
        normalized_actions = json.dumps(self.action_records, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False)
        return {
            "engine_result": result,
            "controller_actions": self.action_records,
            "decision_callback_times_s": self.callback_times,
            "decision_cadence_s": self.cadence_s,
            "separated_outage_metrics": separated,
            "action_replay_sha256": hashlib.sha256(
                normalized_actions.encode("utf-8")).hexdigest(),
            "candidate_budget_not_used_by_design": bool(getattr(
                self.controller, "candidate_budget_not_used_by_design", False)),
        }
