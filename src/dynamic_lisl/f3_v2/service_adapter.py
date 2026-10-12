"""Batch due-action hook; all propagation/service integration remains Gate D2."""
from __future__ import annotations

from dataclasses import dataclass
import math

from ..transition_service_orchestrator import TransitionAwareNetworkServiceEngine
from .batch_executor import AtomicBatchExecutor
from .joint_action import JointAction, canonical_sha256


@dataclass(frozen=True)
class ScriptedBatchProposal:
    time_s: float
    action_id: str
    action: JointAction
    validator: object
    expected_accept: bool | None = None


class BatchNetworkServiceEngine(TransitionAwareNetworkServiceEngine):
    def __init__(self, *args, absolute_time_frame_id, **kwargs):
        self.absolute_time_frame_id = absolute_time_frame_id
        self.batch_results = []
        self.batch_count = 0
        actions = kwargs.get("scripted_actions", ())
        if len({a.time_s for a in actions}) != len(actions):
            raise ValueError("MULTIPLE_CONTROLLER_BATCHES_AT_SAME_EPOCH")
        if any(not isinstance(a, ScriptedBatchProposal) for a in actions):
            raise TypeError("ONLY_SCRIPTED_BATCH_PROPOSALS_ALLOWED")
        super().__init__(*args, **kwargs)

    def decision_root_state(self):
        # Scheduling bookkeeping is not physical root state; all causal service
        # and terminal state is retained. This explicit schema is used by v2 only.
        state = super().canonical_state()
        state.pop("future_action_ids")
        state.pop("scripted_action_cursor")
        # Internal full-state clone hashes still retain these in canonical_state.
        # The controller action root exposes current rates, not future realization
        # bytes or the trace's phase cursor, and remains unchanged by an exactly
        # current-rate-equivalent branch-local persistence forecast.
        state.pop("future_trace_sha256")
        state.pop("traffic_cursor")
        state.update({"absolute_time_frame_id": self.absolute_time_frame_id,
                      "current_offered_rates_bit_s": self.trace.rate_at(self.now),
                      "objective_by_commodity": dict(sorted(self.objective_by_commodity.items())),
                      "objective_compensation": dict(sorted(self.objective_compensation.items())),
                      "arrived_compensation": dict(sorted(self.arrived_compensation.items())),
                      "delivered_compensation": dict(sorted(self.delivered_compensation.items())),
                      "service_rates": sorted((edge, f, v) for (edge, f), v in self.service_rates.items()),
                      "service_delays": sorted((edge, f, v) for (edge, f), v in self.service_delays.items()),
                      "sequence": self.sequence, "next_refresh": self.next_refresh,
                      "G_active": self.graph["active_edges"], "G_admit": self.graph["admit_edges"]})
        return state

    def decision_root_sha256(self):
        return canonical_sha256(self.decision_root_state())

    def canonical_state(self):
        return {**super().canonical_state(), "v2": {
            "decision_root_state": self.decision_root_state(), "batch_results": self.batch_results,
            "batch_count": self.batch_count,
            # Full equivalence must also cover state which drives later audit
            # metrics or routing. It is not added to the controller-visible root.
            "audit_state": self.audit_state(),
            "scheduled_batches": [a.action.to_dict() for a in self.actions[self.action_index:]]}}

    def audit_state(self):
        fields=('queue_area','max_queue','max_capacity_violation','max_abs_conservation',
                'max_relative_conservation','conservation_samples','terminal_log_cursor',
                'route_changes','route_state_events','action_results','terminal_event_sequence',
                'graph_event_sequence','timeline','BBM_count','MBB_count','switch_count',
                'outage_duration_s','partition_duration_s','partition_node_time_s',
                'backlog_added_during_transition_bits','peak_transition_backlog_bits',
                'transition_episodes','_transition_open','_pending_clearance','_last_transition_active',
                'propagation_closure_events')
        state={key:getattr(self,key) for key in fields}
        state['transmitted']=sorted(self.transmitted.items())
        state['transmitted_by_commodity']=sorted(self.transmitted_by_commodity.items())
        state['no_route_duration_by_commodity']=sorted(self.no_route_duration_by_commodity.items())
        state['next_hop']=sorted(self.next_hop.items())
        state['terminal_log']=self.executor.log
        # Public primitive configuration plus a separately normalized current
        # snapshot. Never serialize process identities or mutable delay caches.
        state['router_parameters']={k:v for k,v in vars(self.router).items() if k!='snapshot'}
        snapshot=getattr(self.router,'snapshot',None)
        state['router_snapshot']=None if snapshot is None else {
            'time_s':snapshot.time_s,'edge_utilization':sorted(snapshot.edge_utilization.items()),
            'node_queue_bits':sorted(snapshot.node_queue_bits.items()),
            'offered_rate_bit_s':sorted(snapshot.offered_rate_bit_s.items())}
        state['service_config']={'capacity_bit_s':self.capacity_bit_s,'abs_tol':self.abs_tol,
            'rel_tol':self.rel_tol,'state_tol':self.state_tol,'geometry_refresh_s':self.geometry_refresh_s,
            'nodes':self.nodes,'fixed_edges':self.fixed_edges}
        return state

    def schedule_action(self, action):
        if not isinstance(action, ScriptedBatchProposal):
            raise TypeError("SCRIPTED_BATCH_PROPOSAL_REQUIRED")
        if action.time_s != action.action.decision_time_s:
            raise ValueError("BATCH_ACTION_TIME_MISMATCH")
        if any(a.time_s == action.time_s for a in self.actions):
            raise ValueError("MULTIPLE_CONTROLLER_BATCHES_AT_SAME_EPOCH")
        return super().schedule_action(action)

    def _apply_due_actions(self):
        while (self.action_index < len(self.actions)
               and self.actions[self.action_index].time_s <= self.now + 1e-12):
            scheduled = self.actions[self.action_index]
            root = self.decision_root_sha256()
            plan = scheduled.validator.evaluate(self.executor, scheduled.action,
                                                 decision_root_sha256=root)
            row = {"time_s": self.now, "action_id": scheduled.action_id,
                   "accepted": plan.accepted, "reason": plan.reason,
                   "validation": plan.to_dict(), "validation_sha256": plan.seal_sha256,
                   "decision_root_sha256": root}
            if plan.accepted:
                row["commit"] = AtomicBatchExecutor(scheduled.validator).commit(
                    self.executor, plan, decision_root_sha256=root)
                self.batch_count += int(bool(scheduled.action.members))
                self.switch_count += len(scheduled.action.members)
                self.BBM_count += sum(r["transition_mode"] == "BBM" for r in plan.member_results)
                self.MBB_count += sum(r["transition_mode"] == "MBB" for r in plan.member_results)
            self.action_index += 1
            self.batch_results.append(row)
            self.action_results.append(row)
            if scheduled.expected_accept is not None and plan.accepted != scheduled.expected_accept:
                raise AssertionError("SCRIPTED_BATCH_ACCEPTANCE_MISMATCH")


@dataclass(frozen=True)
class DecisionSchedule:
    cadence_s: float
    arrival_end_s: float
    simulation_end_s: float
    nominal_rollout_horizon_s: float
    complete_threshold_bits: float
    clip_horizon_at_end: bool

    def __post_init__(self):
        values = (self.cadence_s, self.simulation_end_s, self.nominal_rollout_horizon_s,
                  self.complete_threshold_bits)
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("INVALID_EXPLICIT_SCHEDULE")
        if not 0 <= self.arrival_end_s < self.simulation_end_s:
            raise ValueError("INVALID_ARRIVAL_DRAIN_HORIZON")

    def epochs(self):
        k = 0
        while k * self.cadence_s < self.simulation_end_s:
            yield k * self.cadence_s
            k += 1

    def horizon_at(self, time_s):
        if not 0 <= time_s < self.simulation_end_s:
            raise ValueError("NO_DECISION_AT_OR_AFTER_END")
        if self.clip_horizon_at_end:
            return min(self.nominal_rollout_horizon_s, self.simulation_end_s - time_s)
        if time_s + self.nominal_rollout_horizon_s > self.simulation_end_s:
            raise ValueError("INSUFFICIENT_ROLLOUT_COVERAGE")
        return self.nominal_rollout_horizon_s


class BatchCadenceAdapter:
    """Engineering controller callback contract, not a performance runner.

    Physics advances using D2; callback receives a settled current root, returns
    HOLD or exactly one complete batch. No decision at the drain cutoff.
    """
    def __init__(self, engine, schedule, validator):
        if engine.now != 0:
            raise ValueError("ADAPTER_REQUIRES_INITIAL_ENGINE")
        if engine.trace.arrival_horizon_s != schedule.arrival_end_s:
            raise ValueError("TRAFFIC_SCHEDULE_HORIZON_MISMATCH")
        self.engine, self.schedule, self.validator = engine, schedule, validator
        self.checkpoints = []

    def _advance_with_completion(self, target):
        while self.engine.now < target-1e-13:
            self.engine._step(target)
            if (self.engine.now >= self.schedule.arrival_end_s and
                    self.engine.queues.total()+self.engine.in_flight.total() <= self.schedule.complete_threshold_bits):
                self.engine.settle_current_time()
                if self.engine.queues.total()+self.engine.in_flight.total() <= self.schedule.complete_threshold_bits:
                    return True
        self.engine.settle_current_time()
        return (self.engine.now >= self.schedule.arrival_end_s and
                self.engine.queues.total()+self.engine.in_flight.total() <= self.schedule.complete_threshold_bits)

    def run(self, callback):
        for t in self.schedule.epochs():
            pre = self.engine.canonical_state_sha256()
            complete = self._advance_with_completion(t)
            root = self.engine.decision_root_sha256()
            remaining = self.engine.queues.total() + self.engine.in_flight.total()
            if complete:
                break
            canonical_root = self.engine.canonical_state_sha256()
            action = callback(self.engine, root, self.schedule.horizon_at(t))
            post_observe = self.engine.canonical_state_sha256()
            if canonical_root != post_observe:
                raise AssertionError("CONTROLLER_CHANGED_LIVE_ENGINE")
            if action.decision_root_sha256 != root:
                raise ValueError("CONTROLLER_ROOT_MISMATCH")
            self.engine.schedule_action(ScriptedBatchProposal(t, action.batch_id, action, self.validator, True))
            self.engine.settle_current_time()
            self.checkpoints.append({"time_s": t, "H_pre_call": pre,
                                     "H_decision_root": canonical_root, "H_post_observe": post_observe,
                                     "H_post_decision": self.engine.canonical_state_sha256(),
                                     "action": action.to_dict()})
        if self.engine.now < self.schedule.simulation_end_s:
            # Real drain with D2 advance, not D2's different early-return threshold.
            # On early COMPLETE stop at the actual settled completion time.
            if not (self.engine.now >= self.schedule.arrival_end_s and
                    self.engine.queues.total()+self.engine.in_flight.total() <= self.schedule.complete_threshold_bits):
                self._advance_with_completion(self.schedule.simulation_end_s)
        residual = self.engine.queues.total()+self.engine.in_flight.total()
        return {"status": "COMPLETE" if residual <= self.schedule.complete_threshold_bits else "CENSORED_AT_DRAIN_LIMIT",
                "residual_backlog_bits": residual, "checkpoints": self.checkpoints,
                "final_state": self.engine.canonical_state(),
                "engineering_only": True, "scientific_frozen": False}
