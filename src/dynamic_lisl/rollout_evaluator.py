"""Exact Gate F2 root-action branch evaluation on cloned D2 engines."""
from __future__ import annotations

from dataclasses import dataclass
import math

from .candidate_proposer import RegimeSafetyAdapter
from .forecast import attach_forecast_to_clone
from .outage_metrics import derive_separated_outage_metrics
from .transition_service_orchestrator import ScriptedProposal


@dataclass(frozen=True)
class RolloutBranchResult:
    branch_id: str
    action_kind: str
    proposal_id: str | None
    valid: bool
    J_H_bit_s: float
    rejection_reason: str | None
    proposer_executor_consistency_diagnostic: bool
    forecast_sha256: str
    start_state_sha256: str
    end_state_sha256: str | None
    residual_backlog_bits: float | None
    action_result: dict | None
    terminal_events: tuple
    separated_outage_metrics: dict
    invariant_report: dict
    objective_start_bit_s: float
    objective_end_bit_s: float | None
    horizon_end_s: float

    def public_record(self):
        return {
            "branch_id": self.branch_id,
            "action_kind": self.action_kind,
            "proposal_id": self.proposal_id,
            "valid": self.valid,
            "J_H_bit_s": (self.J_H_bit_s if math.isfinite(self.J_H_bit_s)
                          else "Infinity"),
            "rejection_reason": self.rejection_reason,
            "proposer_executor_consistency_diagnostic":
                self.proposer_executor_consistency_diagnostic,
            "forecast_sha256": self.forecast_sha256,
            "start_state_sha256": self.start_state_sha256,
            "end_state_sha256": self.end_state_sha256,
            "residual_backlog_bits": self.residual_backlog_bits,
            "invariants": self.invariant_report,
        }


class ExactRootActionRolloutEvaluator:
    """Evaluate HOLD/REPLACE using the real event-driven D2 engine clone."""

    horizon_s = 10.0

    def __init__(self, live_engine, physical_layer, fixed_edges, regime):
        self.live_engine = live_engine
        self.physical_layer = physical_layer
        self.fixed_edges = tuple(fixed_edges)
        self.regime = str(regime)
        self.safety = RegimeSafetyAdapter(self.regime)

    @staticmethod
    def _objective(engine):
        return math.fsum(engine.objective_by_commodity.values())

    @staticmethod
    def _partial_result(engine):
        return {
            "metrics": {
                "evaluation_end_s": engine.now,
                "outage_duration_s": engine.outage_duration_s,
            },
            "route_state_events": engine.route_state_events,
            "transition_episodes": engine.transition_episodes,
            "terminal_event_sequence": engine.terminal_event_sequence,
        }

    def _clone(self, forecast, root_hash=None):
        branch = self.live_engine.clone()
        start_hash = branch.canonical_state_sha256()
        expected_hash = (self.live_engine.canonical_state_sha256()
                         if root_hash is None else root_hash)
        if start_hash != expected_hash:
            raise AssertionError("B4_EXACT_CLONE_STATE_MISMATCH")
        if branch.action_index < len(branch.actions):
            raise AssertionError("B4_BRANCH_CONTAINS_FUTURE_VOLUNTARY_ACTION")
        if root_hash is None:
            # Preserve the legacy reference call pattern for direct evaluation.
            start_hash = branch.canonical_state_sha256()
        attach_forecast_to_clone(branch, forecast)
        return branch, start_hash

    def evaluate_hold(self, forecast, *, root_hash=None, forecast_hash=None):
        branch, start_hash = self._clone(forecast, root_hash)
        start = self._objective(branch)
        terminal_cursor = len(branch.terminal_event_sequence)
        end = branch.now+self.horizon_s
        branch.advance_to(end)
        final = self._objective(branch)
        return self._finish(
            branch, "HOLD", None, True, final-start, None, False,
            forecast, start_hash, start, final, terminal_cursor, None, forecast_hash,
        )

    def evaluate_candidate(self, forecast, proposal_record, candidate_spec,
                           *, root_hash=None, forecast_hash=None):
        branch, start_hash = self._clone(forecast, root_hash)
        start = self._objective(branch)
        terminal_cursor = len(branch.terminal_event_sequence)
        proposal_id = proposal_record["proposal_id"]
        action = ScriptedProposal(
            branch.now,
            f"F2-ROLLOUT-{branch.now:.9f}-{proposal_id}",
            candidate_spec.proposal,
            self.physical_layer,
            self.safety.policy,
            max(branch.now+1e-7,
                float(proposal_record["ready_time_s"])+1e-7),
            None,
        )
        before = len(branch.action_results)
        branch.schedule_action(action)
        branch.settle_current_time()
        if len(branch.action_results) != before+1:
            raise AssertionError("B4_ROOT_ACTION_NOT_EXECUTED")
        result = branch.action_results[-1]
        if not result["accepted"]:
            reason = result.get("policy_reason") or result.get("physical_reason")
            return self._finish(
                branch, "REPLACE", proposal_id, False, math.inf, reason, True,
                forecast, start_hash, start, None, terminal_cursor, result, forecast_hash,
            )
        end = branch.now+self.horizon_s
        branch.advance_to(end)
        final = self._objective(branch)
        return self._finish(
            branch, "REPLACE", proposal_id, True, final-start, None, False,
            forecast, start_hash, start, final, terminal_cursor, result, forecast_hash,
        )

    def _finish(self, branch, kind, proposal_id, valid, score, reason,
                consistency, forecast, start_hash, objective_start,
                objective_end, terminal_cursor, action_result, forecast_hash=None):
        if valid and abs(branch.now-(forecast.start_time_s+self.horizon_s)) > 1e-12:
            raise AssertionError("B4_HORIZON_CUTOFF_NOT_EXACT")
        invariants = {
            "work_conservation_pass": branch.max_abs_conservation <= (
                branch.abs_tol+branch.rel_tol*max(1.0, math.fsum(branch.arrived.values()))),
            "nonnegative_queue_pass": all(value >= -branch.state_tol
                                           for value in branch.queues.bits.values()),
            "capacity_pass": branch.max_capacity_violation <= max(
                1e-9, branch.capacity_bit_s*1e-12),
            "live_engine_mutated": False,
        }
        outage = (derive_separated_outage_metrics(self._partial_result(branch))
                  if valid else {
                      "transition_period_outage_s": 0.0,
                      "transition_period_no_route_by_commodity_s": {},
                      "post_expiry_no_route_s": 0.0,
                      "post_expiry_no_route_by_commodity_s": {},
                  })
        return RolloutBranchResult(
            branch_id="HOLD" if kind == "HOLD" else proposal_id,
            action_kind=kind,
            proposal_id=proposal_id,
            valid=valid,
            J_H_bit_s=float(score),
            rejection_reason=reason,
            proposer_executor_consistency_diagnostic=consistency,
            forecast_sha256=(forecast.sha256() if forecast_hash is None else forecast_hash),
            start_state_sha256=start_hash,
            end_state_sha256=(branch.canonical_state_sha256() if valid else None),
            residual_backlog_bits=(branch.queues.total()+branch.in_flight.total()
                                   if valid else None),
            action_result=action_result,
            terminal_events=tuple(branch.terminal_event_sequence[terminal_cursor:]),
            separated_outage_metrics=outage,
            invariant_report=invariants,
            objective_start_bit_s=float(objective_start),
            objective_end_bit_s=(None if objective_end is None
                                 else float(objective_end)),
            horizon_end_s=forecast.start_time_s+self.horizon_s,
        )
