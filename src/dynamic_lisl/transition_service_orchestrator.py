"""Gate D2 adapter coupling Gate B/C transitions to Gate D1 service semantics.

This module does not choose topology actions.  It executes preregistered Gate-C
proposals and preserves the event-driven fluid accounting frozen in Gate D1.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import heapq
import json
import math
import time

from .common_router import DeterministicShortestPropagationDelayRouter
from .in_flight import InFlightState, RateArrivalEvent
from .operational_policy import OperationalPolicy
from .queue_state import QueueState
from .service_scheduler import equal_weight_fair_share
from .transition_profiler import graph_state, profile_transition


@dataclass(frozen=True)
class ScriptedProposal:
    """One deterministic proposal; `physical_layer` is a Gate C adapter."""

    time_s: float
    action_id: str
    proposal: dict
    physical_layer: object
    policy: OperationalPolicy
    policy_horizon_s: float
    expected_accept: bool | None = True


def _directed(undirected_edges):
    return tuple(sorted((a, b) for edge in {tuple(sorted(x)) for x in undirected_edges}
                        for a, b in (edge, edge[::-1])))


class TransitionAwareNetworkServiceEngine:
    """Event-driven D2 orchestration over one Gate B executor.

    Microstep order at t is frozen as: settle previously committed propagation
    events; process existing Gate-B events; evaluate/submit scripted Gate-C
    proposals; expose the new admit graph; recompute routes and service for
    times strictly greater than t.
    """

    def __init__(self, nodes, fixed_edges, capacity_bit_s, commodities, trace,
                 propagation_delay_s, terminal_executor, scripted_actions=(),
                 router=None, conservation_abs_tolerance_bits=1e-3,
                 conservation_relative_tolerance=1e-12,
                 state_tolerance_bits=1e-6, geometry_refresh_s=None):
        self.nodes = tuple(sorted(set(nodes)))
        if not self.nodes or set(self.nodes) != set(terminal_executor.satellite_ids):
            raise ValueError("TERMINAL_AND_NETWORK_NODE_MISMATCH")
        self.fixed_edges = tuple(sorted({tuple(sorted(x)) for x in fixed_edges}))
        if any(len(edge) != 2 or edge[0] == edge[1] for edge in self.fixed_edges):
            raise ValueError("INVALID_FIXED_EDGE")
        self.capacity_bit_s = float(capacity_bit_s)
        if not math.isfinite(self.capacity_bit_s) or self.capacity_bit_s <= 0.0:
            raise ValueError("INVALID_CAPACITY")
        self.commodities = tuple(sorted(commodities))
        self.by_id = {item.commodity_id: item for item in self.commodities}
        if set(self.by_id) != set(trace.commodity_ids):
            raise ValueError("TRACE_AND_COMMODITY_MISMATCH")
        self.trace = trace
        self.delay = propagation_delay_s
        self.executor = terminal_executor
        if abs(self.executor.now) > 1e-12:
            raise ValueError("D2_ENGINE_REQUIRES_ZERO_TIME_INITIAL_EXECUTOR")
        self.router = router or DeterministicShortestPropagationDelayRouter()
        self.actions = tuple(sorted(scripted_actions,
                                    key=lambda x: (float(x.time_s), x.action_id)))
        if len({x.action_id for x in self.actions}) != len(self.actions):
            raise ValueError("DUPLICATE_SCRIPTED_ACTION_ID")
        if any(not math.isfinite(x.time_s) or x.time_s < 0.0 for x in self.actions):
            raise ValueError("INVALID_SCRIPTED_ACTION_TIME")
        self.abs_tol = float(conservation_abs_tolerance_bits)
        self.rel_tol = float(conservation_relative_tolerance)
        self.state_tol = float(state_tolerance_bits)
        self.geometry_refresh_s = (None if geometry_refresh_s is None
                                   else float(geometry_refresh_s))
        if self.geometry_refresh_s is not None and self.geometry_refresh_s <= 0.0:
            raise ValueError("INVALID_GEOMETRY_REFRESH")

        self.now = 0.0
        self.queues = QueueState()
        self.in_flight = InFlightState()
        self.arrived = defaultdict(float)
        self.arrived_compensation = defaultdict(float)
        self.delivered = defaultdict(float)
        self.delivered_compensation = defaultdict(float)
        self.objective_by_commodity = defaultdict(float)
        self.objective_compensation = defaultdict(float)
        self.transmitted = defaultdict(float)
        self.transmitted_by_commodity = defaultdict(float)
        self.queue_area = 0.0
        self.max_queue = 0.0
        self.max_capacity_violation = 0.0
        self.max_abs_conservation = 0.0
        self.max_relative_conservation = 0.0
        self.conservation_samples = 0

        self.service_rates = {}
        self.service_delays = {}
        self.propagation_agenda = []
        self.propagation_closure_events = []
        self.sequence = 0
        self.boundaries = list(self.trace.boundaries_after(0.0))
        self.boundary_index = 0
        self.action_index = 0
        self.next_refresh = self.geometry_refresh_s
        self.terminal_log_cursor = len(self.executor.log)

        self.routes = {}
        self.next_hop = {}
        self.route_changes = []
        self.route_state_events = []
        self.action_results = []
        self.terminal_event_sequence = []
        self.graph_event_sequence = []
        self.timeline = []

        self.BBM_count = 0
        self.MBB_count = 0
        self.switch_count = 0
        self.outage_duration_s = 0.0
        self.no_route_duration_by_commodity = defaultdict(float)
        self.partition_duration_s = 0.0
        self.partition_node_time_s = 0.0
        self.backlog_added_during_transition_bits = 0.0
        self.peak_transition_backlog_bits = 0.0
        self.transition_episodes = []
        self._transition_open = None
        self._pending_clearance = []
        self._last_transition_active = self._transition_active()

        self.graph = graph_state(self.executor, self.fixed_edges)
        self._recompute_routes("INITIAL")
        self._record("INITIAL")

    @staticmethod
    def _compensated_add(values, compensations, key, increment):
        adjusted = increment-compensations[key]
        total = values[key]+adjusted
        compensations[key] = (total-values[key])-adjusted
        values[key] = total

    def _transition_active(self):
        return bool(self.executor.reservations) or any(
            terminal.phase in ("DRAINING", "RETARGETING", "ACQUIRING")
            for terminal in self.executor.terminals.values())

    def _active_admit_snapshot(self):
        return graph_state(self.executor, self.fixed_edges)

    def _recompute_routes(self, reason):
        directed = _directed(self.graph["admit_edges"])
        old = self.routes
        new = self.router.routes_to_destinations(
            self.nodes, self.commodities, directed, self.delay, self.now)
        if old:
            for key in sorted(new):
                if old.get(key) != new[key]:
                    self.route_changes.append({
                        "time_s": self.now, "reason": reason,
                        "node": key[0], "commodity_id": key[1],
                        "old_route": list(old[key]) if old.get(key) is not None else None,
                        "new_route": list(new[key]) if new[key] is not None else None,
                    })
        for commodity in self.commodities:
            key = (commodity.source, commodity.commodity_id)
            old_state = None if not old else (
                "ROUTED" if old.get(key) is not None else "NO_ROUTE_TEMPORARY")
            new_state = "ROUTED" if new[key] is not None else "NO_ROUTE_TEMPORARY"
            if old_state != new_state:
                self.route_state_events.append({
                    "time_s": self.now, "commodity_id": commodity.commodity_id,
                    "old_state": old_state, "new_state": new_state,
                    "reason": reason,
                })
        self.routes = new
        self.next_hop = {
            key: ((route[0], route[1]) if route is not None and len(route) > 1 else None)
            for key, route in self.routes.items()
        }

    def _record(self, label):
        errors = {}
        for commodity in self.commodities:
            key = commodity.commodity_id
            error = (self.arrived[key] - self.delivered[key]
                     - self.queues.total(key) - self.in_flight.total(key))
            errors[key] = error
            self.max_abs_conservation = max(self.max_abs_conservation, abs(error))
            scale = max(1.0, abs(self.arrived[key]))
            self.max_relative_conservation = max(
                self.max_relative_conservation, abs(error)/scale)
            if abs(error) > self.abs_tol + self.rel_tol*scale:
                raise AssertionError(
                    "WORK_CONSERVATION_VIOLATION "
                    f"time={self.now} commodity={key} error={error}")
        self.conservation_samples += 1
        self.timeline.append({
            "time_s": self.now, "label": label,
            "arrived_bits": math.fsum(self.arrived.values()),
            "delivered_bits": math.fsum(self.delivered.values()),
            "queued_bits": self.queues.total(),
            "in_flight_bits": self.in_flight.total(),
            "conservation_error_bits": math.fsum(errors.values()),
            "active_edge_count": len(self.graph["active_edges"]),
            "admit_edge_count": len(self.graph["admit_edges"]),
            "transition_active": self._transition_active(),
        })

    def _inputs(self, external_rates):
        result = defaultdict(float)
        for commodity in self.commodities:
            result[(commodity.source, commodity.commodity_id)] += external_rates[commodity.commodity_id]
        for (edge, commodity_id), rate in self.in_flight.arrival_rates.items():
            if rate < -1e-7:
                raise AssertionError("NEGATIVE_PROPAGATION_ARRIVAL_RATE")
            result[(edge[1], commodity_id)] += max(0.0, rate)
        return result

    def _allocate_service(self, inputs):
        admitted = set(_directed(self.graph["admit_edges"]))
        demands_by_edge = defaultdict(dict)
        active_keys = ({key for key, value in self.queues.bits.items() if value > 1e-12}
                       | {key for key, value in inputs.items() if value > 1e-15})
        for node, commodity_id in sorted(active_keys):
            commodity = self.by_id[commodity_id]
            if node == commodity.destination:
                continue
            edge = self.next_hop[(node, commodity_id)]
            if edge is None:
                continue
            if edge not in admitted:
                raise AssertionError("ROUTER_USED_NON_ADMITTED_EDGE")
            backlog = self.queues.get(node, commodity_id)
            demand = math.inf if backlog > self.state_tol else inputs[(node, commodity_id)]
            if demand > 1e-15:
                demands_by_edge[edge][commodity_id] = demand
        rates = {}
        for edge, demands in demands_by_edge.items():
            allocation = equal_weight_fair_share(self.capacity_bit_s, demands)
            for commodity_id, rate in allocation.items():
                rates[(edge, commodity_id)] = rate
            self.max_capacity_violation = max(
                self.max_capacity_violation,
                max(0.0, sum(allocation.values())-self.capacity_bit_s))
        return rates

    def _schedule_service_segments(self, new_rates, force_refresh=False):
        keys = sorted(set(self.service_rates) | set(new_rates))
        new_delays = dict(self.service_delays)
        for key in keys:
            old = self.service_rates.get(key, 0.0)
            new = new_rates.get(key, 0.0)
            changed = abs(old-new) > max(1e-12, max(abs(old), abs(new))*1e-14)
            if not changed and not force_refresh:
                continue
            edge, commodity_id = key
            if old > 0.0:
                self.sequence += 1
                heapq.heappush(self.propagation_agenda, RateArrivalEvent(
                    self.now+self.service_delays[key], self.sequence,
                    edge, commodity_id, -old))
            if new > 0.0:
                delay = float(self.delay(edge, self.now))
                if not math.isfinite(delay) or delay <= 0.0:
                    raise ValueError("NONPOSITIVE_PROPAGATION_DELAY")
                new_delays[key] = delay
                self.sequence += 1
                heapq.heappush(self.propagation_agenda, RateArrivalEvent(
                    self.now+delay, self.sequence, edge, commodity_id, new))
            else:
                new_delays.pop(key, None)
        self.service_rates = new_rates
        self.service_delays = new_delays

    def _settle_propagation_rate_events(self):
        deltas = defaultdict(float)
        while (self.propagation_agenda
               and self.propagation_agenda[0].time_s <= self.now+1e-12):
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

    def _finalize_quiescent_propagation(self, settled_deltas):
        """Credit numerical residue when the final propagation pulse ends.

        Every delayed arrival is already subtracted from ``in_flight`` and
        credited downstream. Shifted floating-point event intervals can leave a
        small positive remainder after the final negative rate event. Once an
        edge/commodity has no source service, arrival rate or future propagation
        event, that remainder is physically due downstream at the current event
        time. The transfer is state-based and uses no magnitude threshold.
        """
        if not settled_deltas:
            return
        pending = {(event.edge, event.commodity_id)
                   for event in self.propagation_agenda}
        for edge, commodity_id in sorted(settled_deltas):
            key = (edge, commodity_id)
            if self.service_rates.get(key, 0.0) != 0.0:
                continue
            if self.in_flight.arrival_rates.get(key, 0.0) != 0.0:
                continue
            if key in pending:
                continue
            residue = self.in_flight.bits.get(key, 0.0)
            if residue <= 0.0:
                continue

            before = (self.arrived[commodity_id]
                      - self.delivered[commodity_id]
                      - self.queues.total(commodity_id)
                      - self.in_flight.total(commodity_id))
            self.in_flight.set_bits(
                edge, commodity_id, 0.0,
                tolerance=max(self.state_tol, self.abs_tol))
            commodity = self.by_id[commodity_id]
            if edge[1] == commodity.destination:
                self._compensated_add(
                    self.delivered, self.delivered_compensation,
                    commodity_id, residue)
                destination = "DELIVERED"
            else:
                self.queues.add(
                    edge[1], commodity_id, residue,
                    tolerance=max(self.state_tol, self.abs_tol))
                destination = edge[1]
            after = (self.arrived[commodity_id]
                     - self.delivered[commodity_id]
                     - self.queues.total(commodity_id)
                     - self.in_flight.total(commodity_id))
            scale = max(1.0, abs(self.arrived[commodity_id]))
            conservation_limit = self.abs_tol+self.rel_tol*scale
            roundoff_guard = 8.0*math.ulp(scale)
            if abs(after-before) > roundoff_guard:
                raise AssertionError(
                    "PROPAGATION_CLOSURE_CHANGED_CONSERVATION "
                    f"time={self.now} edge={edge} commodity={commodity_id} "
                    f"residue={residue} before={before} after={after}")
            if abs(after) > conservation_limit:
                raise AssertionError(
                    "PROPAGATION_CLOSURE_CONSERVATION_VIOLATION "
                    f"time={self.now} edge={edge} commodity={commodity_id} "
                    f"residue={residue} error={after} limit={conservation_limit}")
            self.propagation_closure_events.append({
                "time_s": self.now,
                "edge": edge,
                "commodity_id": commodity_id,
                "closed_bits": residue,
                "credited_to": destination,
                "conservation_error_before_bits": before,
                "conservation_error_after_bits": after,
            })

    def _proposal_mode(self, command):
        if getattr(command, "release_after", ()):
            return "MBB"
        endpoints = (tuple(command.a), tuple(command.b))
        return ("BBM" if any(self.executor.terminals[e].current_peer is not None
                             for e in endpoints) else "SETUP_ONLY")

    def _apply_due_actions(self):
        while (self.action_index < len(self.actions)
               and self.actions[self.action_index].time_s <= self.now+1e-12):
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

    def _update_transition_episode_state(self):
        active = self._transition_active()
        if active and not self._last_transition_active:
            self._transition_open = {
                "start_s": self.now,
                "baseline_queue_bits": self.queues.total(),
                "peak_queue_bits": self.queues.total(),
                "added_positive_queue_bits": 0.0,
                "end_s": None,
                "clearance_time_s": None,
            }
        elif not active and self._last_transition_active and self._transition_open is not None:
            self._transition_open["end_s"] = self.now
            self.transition_episodes.append(self._transition_open)
            if self.queues.total() <= self._transition_open["baseline_queue_bits"]+max(self.state_tol, self.abs_tol):
                self._transition_open["clearance_time_s"] = 0.0
            else:
                self._pending_clearance.append(self._transition_open)
            self._transition_open = None
        self._last_transition_active = active

    def _microstep(self, force_refresh=False):
        self._settle_propagation_rate_events()
        due_terminal = bool(self.executor.events and self.executor.events[0][0] <= self.now+1e-12)
        due_action = bool(self.action_index < len(self.actions)
                          and self.actions[self.action_index].time_s <= self.now+1e-12)
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

    def _derivatives(self, inputs):
        queue_derivative = {}
        delivery_rates = {}
        active_keys = ({key for key, value in self.queues.bits.items() if value > 1e-12}
                       | {key for key, value in inputs.items() if value > 1e-15})
        for node, commodity_id in sorted(active_keys):
            incoming = inputs[(node, commodity_id)]
            commodity = self.by_id[commodity_id]
            if node == commodity.destination:
                delivery_rates[commodity_id] = (
                    delivery_rates.get(commodity_id, 0.0)+incoming)
                continue
            edge = self.next_hop[(node, commodity_id)]
            outgoing = (self.service_rates.get((edge, commodity_id), 0.0)
                        if edge is not None else 0.0)
            queue_derivative[(node, commodity_id)] = incoming-outgoing
        return queue_derivative, delivery_rates

    def _next_time(self, drain_limit_s, queue_derivative):
        candidates = [drain_limit_s]
        while (self.boundary_index < len(self.boundaries)
               and self.boundaries[self.boundary_index] <= self.now+1e-12):
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
        future = [value for value in candidates if value > self.now+1e-13]
        if not future:
            raise RuntimeError("NO_FORWARD_EVENT")
        return min(future)

    def _integrate(self, next_time, external, inputs, queue_derivative, delivery_rates):
        dt = next_time-self.now
        old_not_delivered = {
            item.commodity_id: self.arrived[item.commodity_id]-self.delivered[item.commodity_id]
            for item in self.commodities}
        old_queue = self.queues.total()

        for commodity in self.commodities:
            key = commodity.commodity_id
            amount = external[key]*dt
            if amount:
                self._compensated_add(
                    self.arrived, self.arrived_compensation, key, amount)
                self.queues.add(commodity.source, key, amount,
                                tolerance=max(self.state_tol, self.abs_tol))
        for (edge, key), rate in sorted(self.service_rates.items()):
            amount = rate*dt
            if amount:
                self.in_flight.add_bits(
                    edge, key, amount, tolerance=max(self.state_tol, self.abs_tol))
                self.transmitted[edge] += amount
                self.transmitted_by_commodity[(edge, key)] += amount
        for (edge, key), rate in sorted(self.in_flight.arrival_rates.items()):
            amount = rate*dt
            if not amount:
                continue
            self.in_flight.add_bits(
                edge, key, -amount, tolerance=max(self.state_tol, self.abs_tol))
            commodity = self.by_id[key]
            if edge[1] == commodity.destination:
                self._compensated_add(
                    self.delivered, self.delivered_compensation, key, amount)
            else:
                self.queues.add(edge[1], key, amount,
                                tolerance=max(self.state_tol, self.abs_tol))
        for (edge, key), rate in sorted(self.service_rates.items()):
            amount = rate*dt
            if not amount:
                continue
            available = self.queues.get(edge[0], key)
            if amount > available+max(self.state_tol, self.abs_tol):
                raise AssertionError("SERVICE_EXCEEDS_INTERVAL_WORK")
            self.queues.add(edge[0], key, -amount,
                            tolerance=max(self.state_tol, self.abs_tol))
        for commodity in self.commodities:
            key = commodity.commodity_id
            slope = external[key]-delivery_rates.get(key, 0.0)
            self._compensated_add(
                self.objective_by_commodity, self.objective_compensation, key,
                commodity.weight*(old_not_delivered[key]*dt+0.5*slope*dt*dt))

        new_queue = self.queues.total()
        self.queue_area += 0.5*(old_queue+new_queue)*dt
        self.max_queue = max(self.max_queue, old_queue, new_queue)
        no_route = [item.commodity_id for item in self.commodities
                    if self.routes[(item.source, item.commodity_id)] is None]
        if no_route:
            self.outage_duration_s += dt
            for key in no_route:
                self.no_route_duration_by_commodity[key] += dt
        components = self.graph["admit_components"]
        if len(components) > 1:
            self.partition_duration_s += dt
            self.partition_node_time_s += (len(self.nodes)-len(components[0]))*dt
        if self._transition_active():
            increase = max(0.0, new_queue-old_queue)
            self.backlog_added_during_transition_bits += increase
            self.peak_transition_backlog_bits = max(
                self.peak_transition_backlog_bits, old_queue, new_queue)
            if self._transition_open is not None:
                self._transition_open["added_positive_queue_bits"] += increase
                self._transition_open["peak_queue_bits"] = max(
                    self._transition_open["peak_queue_bits"], old_queue, new_queue)
        for episode in list(self._pending_clearance):
            if new_queue <= episode["baseline_queue_bits"]+max(self.state_tol, self.abs_tol):
                episode["clearance_time_s"] = next_time-episode["end_s"]
                self._pending_clearance.remove(episode)
        self.now = next_time
        self._record("EVENT_BOUNDARY")

    def advance_to(self, until_s):
        until_s = float(until_s)
        if until_s < self.now or not math.isfinite(until_s):
            raise ValueError("INVALID_ADVANCE_TARGET")
        events = 0
        while self.now < until_s-1e-13:
            events += 1
            if events > 1000000:
                raise RuntimeError("EVENT_LIMIT_EXCEEDED")
            self._step(until_s)
        self.settle_current_time()
        return self

    def settle_current_time(self):
        """Process all real events at the current timestamp without advancing time."""
        is_refresh = False
        if self.next_refresh is not None and self.next_refresh <= self.now+1e-12:
            is_refresh = True
            while self.next_refresh <= self.now+1e-12:
                self.next_refresh += self.geometry_refresh_s
        self._microstep(force_refresh=is_refresh)
        return self

    def _step(self, limit_s):
        is_refresh = False
        if self.next_refresh is not None and self.next_refresh <= self.now+1e-12:
            is_refresh = True
            while self.next_refresh <= self.now+1e-12:
                self.next_refresh += self.geometry_refresh_s
        external, inputs = self._microstep(force_refresh=is_refresh)
        queue_derivative, delivery_rates = self._derivatives(inputs)
        next_time = self._next_time(limit_s, queue_derivative)
        self._integrate(next_time, external, inputs,
                        queue_derivative, delivery_rates)

    def schedule_action(self, action):
        if action.time_s < self.now-1e-12:
            raise ValueError("ACTION_IN_THE_PAST")
        pending = list(self.actions[self.action_index:]) + [action]
        completed = list(self.actions[:self.action_index])
        pending.sort(key=lambda x: (x.time_s, x.action_id))
        if len({x.action_id for x in completed+pending}) != len(completed)+len(pending):
            raise ValueError("DUPLICATE_SCRIPTED_ACTION_ID")
        self.actions = tuple(completed+pending)

    def clone(self):
        return deepcopy(self)

    def canonical_state(self):
        document = {
            "time_s": self.now,
            "terminal": self.executor.snapshot(),
            "queues": self.queues.snapshot(),
            "in_flight": self.in_flight.snapshot(),
            "in_flight_arrival_rates": {
                edge[0]+"->"+edge[1]+"|"+key: value
                for (edge, key), value in sorted(self.in_flight.arrival_rates.items())
                if value != 0.0},
            "arrived": dict(sorted(self.arrived.items())),
            "delivered": dict(sorted(self.delivered.items())),
            "traffic_cursor": self.boundary_index,
            "future_trace_sha256": self.trace.sha256(),
            "routes": {node+"|"+key: (list(route) if route else None)
                       for (node, key), route in sorted(self.routes.items())},
            "propagation_agenda": [event.__dict__ for event in sorted(self.propagation_agenda)],
            "scripted_action_cursor": self.action_index,
            "future_action_ids": [x.action_id for x in self.actions[self.action_index:]],
            "routing_class": type(self.router).__name__,
            "rng_state": None,
        }
        return document

    def canonical_state_sha256(self):
        payload = json.dumps(self.canonical_state(), sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def run(self, drain_limit_s):
        wall_start = time.perf_counter()
        drain_limit_s = float(drain_limit_s)
        if drain_limit_s <= self.trace.arrival_horizon_s:
            raise ValueError("DRAIN_LIMIT_MUST_EXCEED_ARRIVAL_HORIZON")
        while self.now < drain_limit_s-1e-13:
            self._step(drain_limit_s)
            residual = self.queues.total()+self.in_flight.total()
            if (self.now >= self.trace.arrival_horizon_s-1e-12
                    and residual <= max(self.state_tol, self.abs_tol)
                    and self.action_index >= len(self.actions)):
                self.settle_current_time()
                residual = self.queues.total()+self.in_flight.total()
                if residual <= max(self.state_tol, self.abs_tol):
                    break
        total_arrived = math.fsum(self.arrived.values())
        total_delivered_raw = math.fsum(self.delivered.values())
        numerical_delivery_excess = max(0.0, total_delivered_raw-total_arrived)
        if numerical_delivery_excess > self.abs_tol+self.rel_tol*max(1.0, total_arrived):
            raise AssertionError("DELIVERED_EXCEEDS_ARRIVED_BEYOND_TOLERANCE")
        total_delivered = min(total_arrived, total_delivered_raw)
        residual = self.queues.total()+self.in_flight.total()
        drained = residual <= max(self.state_tol, self.abs_tol)
        evaluation_time = self.now
        utilization = {
            edge[0]+"->"+edge[1]: amount/(self.capacity_bit_s*evaluation_time)
            for edge, amount in sorted(self.transmitted.items()) if amount > 0.0}
        clearances = [x["clearance_time_s"] for x in self.transition_episodes
                      if x["clearance_time_s"] is not None]
        metrics = {
            "schema": "gate_d2_transition_service_metrics_v1",
            "evaluation_end_s": evaluation_time,
            "arrival_horizon_s": self.trace.arrival_horizon_s,
            "censored": not drained,
            "mean_bit_delay_s": (math.fsum(self.objective_by_commodity.values())/total_arrived
                                 if drained and total_arrived > 0.0 else None),
            "J_bit_s": math.fsum(self.objective_by_commodity.values()),
            "objective_J_bit_s": math.fsum(self.objective_by_commodity.values()),
            "arrived_bits": total_arrived,
            "delivered_bits": total_delivered,
            "numerical_raw_delivered_bits": total_delivered_raw,
            "numerical_delivery_excess_bits": numerical_delivery_excess,
            "delivery_ratio": total_delivered/total_arrived if total_arrived else 1.0,
            "residual_backlog_bits": residual,
            "queued_bits_at_end": self.queues.total(),
            "in_flight_bits_at_end": self.in_flight.total(),
            "mean_queue_bits": self.queue_area/evaluation_time if evaluation_time else 0.0,
            "max_queue_bits": self.max_queue,
            "link_utilization": utilization,
            "traffic_weighted_hop_count": (
                math.fsum(self.transmitted.values())/total_delivered
                if total_delivered > 0.0 else None),
            "route_change_count": sum(
                row["node"] == self.by_id[row["commodity_id"]].source
                for row in self.route_changes),
            "node_commodity_route_change_count": len(self.route_changes),
            "active_dynamic_link_count": sum(
                not link.draining for link in self.executor.links.values()),
            "switch_count": self.switch_count,
            "BBM_count": self.BBM_count,
            "MBB_count": self.MBB_count,
            "no_route_duration_s": self.outage_duration_s,
            "no_route_duration_by_commodity_s": dict(
                sorted(self.no_route_duration_by_commodity.items())),
            "outage_duration_s": self.outage_duration_s,
            "outage_duration": self.outage_duration_s,
            "partition_duration_s": self.partition_duration_s,
            "partition_node_time_s": self.partition_node_time_s,
            "partition_node_time": self.partition_node_time_s,
            "backlog_added_during_transition_bits": self.backlog_added_during_transition_bits,
            "peak_transition_backlog_bits": self.peak_transition_backlog_bits,
            "backlog_clearance_time_s": max(clearances) if clearances else None,
            "max_abs_conservation_error_bits": self.max_abs_conservation,
            "max_relative_conservation_error": self.max_relative_conservation,
            "conservation_samples": self.conservation_samples,
            "max_capacity_violation_bit_s": self.max_capacity_violation,
            "negative_queue_count": sum(value < 0.0 for value in self.queues.bits.values()),
            "propagation_closure_count": len(self.propagation_closure_events),
            "propagation_closure_bits": math.fsum(
                row["closed_bits"] for row in self.propagation_closure_events),
            "trace_sha256": self.trace.sha256(),
            "runtime": time.perf_counter()-wall_start,
        }
        return {
            "metrics": metrics,
            "timeline": self.timeline,
            "queues": self.queues.snapshot(),
            "in_flight": self.in_flight.snapshot(),
            "arrived_by_commodity": dict(sorted(self.arrived.items())),
            "delivered_by_commodity": dict(sorted(self.delivered.items())),
            "transmitted_by_edge_commodity": {
                edge[0]+"->"+edge[1]+"|"+key: value
                for (edge, key), value in sorted(self.transmitted_by_commodity.items())},
            "routes": {node+"|"+key: (list(route) if route is not None else None)
                       for (node, key), route in sorted(self.routes.items())},
            "route_changes": self.route_changes,
            "route_state_events": self.route_state_events,
            "action_results": self.action_results,
            "terminal_event_sequence": self.terminal_event_sequence,
            "graph_event_sequence": self.graph_event_sequence,
            "transition_episodes": self.transition_episodes,
            "propagation_closure_events": self.propagation_closure_events,
            "final_state": self.canonical_state(),
        }
