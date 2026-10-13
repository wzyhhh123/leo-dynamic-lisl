"""PILOT_ONLY isolated exact-nominal event clock over unchanged D2 service.

Original global classes/functions are never patched. Only explicit construction
of these subclasses selects the new numeric event timing semantics.
"""
import heapq,math,hashlib,json
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
from copy import deepcopy
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine
from dynamic_lisl.transition_profiler import profile_transition
from runtime.n1b_observer import ObservedD2Engine

@dataclass(frozen=True)
class VariantBinding:
    manifest_path: str
    sha256: str
    def verify(self):
        p=Path(self.manifest_path)
        assert hashlib.sha256(p.read_bytes()).hexdigest()==self.sha256,'P0F_MANIFEST_DRIFT'
        doc=json.loads(p.read_text(encoding='utf-8'))
        for r in doc['files']:
            q=Path(r['path']);data=q.read_bytes()
            assert len(data)==r['byte_count'] and hashlib.sha256(data).hexdigest()==r['sha256'],'P0F_DEPENDENCY_DRIFT:'+str(q)
        return {'status':'PASS','semantic_version':'P0F_EXACT_NOMINAL_V1'}

class ExactEventClock:
    def __init__(self,*args,variant_binding,**kwargs):
        variant_binding.verify()
        self.variant_binding=variant_binding
        super().__init__(*args,**kwargs)
    def _settle_propagation_rate_events(self):
        deltas = defaultdict(float)
        while (self.propagation_agenda
               and self.propagation_agenda[0].time_s <= self.now):
            event = heapq.heappop(self.propagation_agenda)
            deltas[(event.edge, event.commodity_id)] += event.delta_rate_bit_s
        for key, delta in deltas.items():
            self.in_flight.arrival_rates[key] += delta
            value = self.in_flight.arrival_rates[key]
            tolerance = max(1e-6, abs(delta)*1e-12)
            if abs(value) <= tolerance:
                self.in_flight.arrival_rates[key] = 0.0
            elif value < 0.0:
                raise AssertionError("NEGATIVE_DELAYED_RATE")
        self._finalize_quiescent_propagation(deltas)

    def _next_time(self, drain_limit_s, queue_derivative):
        candidates = [drain_limit_s]
        while (self.boundary_index < len(self.boundaries)
               and self.boundaries[self.boundary_index] <= self.now):
            self.boundary_index += 1
        if self.boundary_index < len(self.boundaries):
            candidates.append(self.boundaries[self.boundary_index])
        if self.propagation_agenda:
            candidates.append(self.propagation_agenda[0].time_s)
        if self.executor.events:
            candidates.append(self.executor.events[0][0])
        if self.action_index < len(self.actions):
            candidates.append(self.actions[self.action_index].time_s)
        if self.next_refresh is not None:
            candidates.append(self.next_refresh)
        for (node, commodity_id), derivative in queue_derivative.items():
            backlog = self.queues.get(node, commodity_id)
            if backlog > self.state_tol and derivative < -1e-15:
                candidates.append(self.now+backlog/(-derivative))
        future = [value for value in candidates if value > self.now]
        if not future:
            raise RuntimeError("NO_FORWARD_EVENT")
        return min(future)

    def advance_to(self, until_s):
        until_s = float(until_s)
        if until_s < self.now or not math.isfinite(until_s):
            raise ValueError("INVALID_ADVANCE_TARGET")
        events = 0
        while self.now < until_s:
            events += 1
            if events > 1000000:
                raise RuntimeError("EVENT_LIMIT_EXCEEDED")
            prior = self.now
            self._step(until_s)
            if not prior < self.now <= until_s:
                raise RuntimeError("P0F_NON_FORWARD_OR_OVERSHOOT")
        self.settle_current_time()
        return self

    def settle_current_time(self):
        """Process all real events at the current timestamp without advancing time."""
        is_refresh = False
        if self.next_refresh is not None and self.next_refresh <= self.now:
            is_refresh = True
            while self.next_refresh <= self.now:
                prior_refresh = self.next_refresh
                self.next_refresh += self.geometry_refresh_s
                if self.next_refresh <= prior_refresh:
                    raise RuntimeError("P0F_UNREPRESENTABLE_REFRESH_INCREMENT")
        self._microstep(force_refresh=is_refresh)
        return self

    def _step(self, limit_s):
        is_refresh = False
        if self.next_refresh is not None and self.next_refresh <= self.now:
            is_refresh = True
            while self.next_refresh <= self.now:
                prior_refresh = self.next_refresh
                self.next_refresh += self.geometry_refresh_s
                if self.next_refresh <= prior_refresh:
                    raise RuntimeError("P0F_UNREPRESENTABLE_REFRESH_INCREMENT")
        external, inputs = self._microstep(force_refresh=is_refresh)
        queue_derivative, delivery_rates = self._derivatives(inputs)
        next_time = self._next_time(limit_s, queue_derivative)
        self._integrate(next_time, external, inputs,
                        queue_derivative, delivery_rates)

    def _microstep(self, force_refresh=False):
        self._settle_propagation_rate_events()
        due_terminal = bool(self.executor.events and self.executor.events[0][0] <= self.now)
        due_action = bool(self.action_index < len(self.actions)
                          and self.actions[self.action_index].time_s <= self.now)
        old_graph = self.graph
        log_start = len(self.executor.log)
        if due_terminal or due_action:
            self._record("BEFORE_TOPOLOGY_MICROSTEP")
        self.executor.advance(self.now)
        self._apply_due_actions()
        new_logs = [{"time": item["time"], "event": item["event"],
                     "details": deepcopy(item["details"])} 
                    for item in self.executor.log[log_start:]]
        self.terminal_log_cursor = len(self.executor.log)
        self.terminal_event_sequence.extend(new_logs)
        self.graph = self._active_admit_snapshot()
        graph_changed = (old_graph["active_edges"] != self.graph["active_edges"]
                         or old_graph["admit_edges"] != self.graph["admit_edges"])
        if new_logs or graph_changed:
            self.graph_event_sequence.append({
                "time_s": self.now,
                "terminal_events": [item["event"] for item in new_logs],
                "active_edges": self.graph["active_edges"],
                "admit_edges": self.graph["admit_edges"],
                "active_components": self.graph["active_components"],
                "admit_components": self.graph["admit_components"],
            })
        if old_graph["admit_edges"] != self.graph["admit_edges"] or force_refresh:
            reason = "TOPOLOGY_ADMIT_CHANGE" if not force_refresh else "GEOMETRY_REFRESH"
            self._recompute_routes(reason)
        self._update_transition_episode_state()
        if due_terminal or due_action:
            self._record("AFTER_TOPOLOGY_MICROSTEP")

        external = self.trace.rate_at(self.now)
        inputs = self._inputs(external)
        new_service = self._allocate_service(inputs)
        self._schedule_service_segments(new_service, force_refresh=force_refresh)
        return external, inputs

    def _apply_due_actions(self):
        while (self.action_index < len(self.actions)
               and self.actions[self.action_index].time_s <= self.now):
            action = self.actions[self.action_index]
            self.action_index += 1
            physical = action.physical_layer.evaluate(self.executor, **action.proposal)
            result = {
                "time_s": self.now, "action_id": action.action_id,
                "proposal": action.proposal, "physical_reason": physical.get("reason"),
                "accepted": False, "policy_reason": None,
            }
            if physical["accepted"]:
                profile = profile_transition(
                    self.executor, [physical["command"]], self.fixed_edges,
                    action.policy_horizon_s)
                decision = action.policy.apply(profile)
                result["policy_reason"] = decision["reason"]
                result["profile_classification"] = profile.get("classification")
                if decision["accepted"]:
                    mode = self._proposal_mode(physical["command"])
                    self.executor.submit([physical["command"]])
                    result["accepted"] = True
                    result["transition_mode"] = mode
                    self.switch_count += 1
                    self.BBM_count += int(mode == "BBM")
                    self.MBB_count += int(mode == "MBB")
            if (action.expected_accept is not None
                    and result["accepted"] != action.expected_accept):
                raise AssertionError(
                    f"SCRIPTED_ACTION_ACCEPTANCE_MISMATCH {action.action_id}")
            self.action_results.append(result)

class ExactObservedD2Engine(ExactEventClock,ObservedD2Engine):
    pass

class ExactBareD2Engine(ExactEventClock,TransitionAwareNetworkServiceEngine):
    pass
