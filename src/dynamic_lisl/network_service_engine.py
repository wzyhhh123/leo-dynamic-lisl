"""Deterministic event-driven fixed-topology fluid network service kernel."""
from __future__ import annotations

from collections import defaultdict
import heapq
import math
import time

from .common_router import DeterministicShortestPropagationDelayRouter
from .gate_d_metrics import empty_transition_metrics
from .in_flight import InFlightState, RateArrivalEvent
from .queue_state import QueueState
from .service_scheduler import equal_weight_fair_share


class NetworkServiceEngine:
    """Propagate aggregate bits through fixed directed service edges.

    Between exogenous-rate changes, delayed-rate arrivals, queue-empty events and
    optional geometry refreshes, every state derivative is constant.  The engine
    integrates those affine segments exactly; observation grids are passive.
    """

    def __init__(self, nodes, undirected_edges, capacity_bit_s, commodities, trace,
                 propagation_delay_s, router=None, active_dynamic_link_count=0,
                 conservation_abs_tolerance_bits=1e-3,
                 conservation_relative_tolerance=1e-12,
                 state_tolerance_bits=1e-6,
                 geometry_refresh_s=None):
        self.nodes = tuple(sorted(set(nodes)))
        if not self.nodes:
            raise ValueError("EMPTY_NETWORK")
        physical = {tuple(sorted(edge)) for edge in undirected_edges}
        if any(len(edge) != 2 or edge[0] == edge[1] for edge in physical):
            raise ValueError("INVALID_PHYSICAL_EDGE")
        self.directed_edges = tuple(sorted((a, b) for edge in physical
                                           for a, b in (edge, edge[::-1])))
        if isinstance(capacity_bit_s, dict):
            self.capacity = {tuple(edge): float(value)
                             for edge, value in capacity_bit_s.items()}
        else:
            self.capacity = {edge: float(capacity_bit_s) for edge in self.directed_edges}
        if set(self.capacity) != set(self.directed_edges) or any(
                not math.isfinite(value) or value <= 0.0 for value in self.capacity.values()):
            raise ValueError("CAPACITY_MAP_MISMATCH_OR_INVALID")
        self.commodities = tuple(sorted(commodities))
        self.by_id = {item.commodity_id: item for item in self.commodities}
        if set(self.by_id) != set(trace.commodity_ids):
            raise ValueError("TRACE_AND_COMMODITY_MISMATCH")
        if any(item.source not in self.nodes or item.destination not in self.nodes
               for item in self.commodities):
            raise ValueError("COMMODITY_ENDPOINT_OUTSIDE_NETWORK")
        self.trace = trace
        self.delay = propagation_delay_s
        self.router = router or DeterministicShortestPropagationDelayRouter()
        self.routes = self.router.routes_to_destinations(
            self.nodes, self.commodities, self.directed_edges, self.delay, 0.0)
        self.next_hop = {}
        for (node, commodity_id), route in self.routes.items():
            self.next_hop[(node, commodity_id)] = (
                (route[0], route[1]) if route is not None and len(route) > 1 else None)
        self.active_dynamic_link_count = int(active_dynamic_link_count)
        self.abs_tol = float(conservation_abs_tolerance_bits)
        self.rel_tol = float(conservation_relative_tolerance)
        self.state_tol = float(state_tolerance_bits)
        self.geometry_refresh_s = (None if geometry_refresh_s is None
                                   else float(geometry_refresh_s))
        if self.geometry_refresh_s is not None and self.geometry_refresh_s <= 0.0:
            raise ValueError("INVALID_GEOMETRY_REFRESH")

    def _inputs(self, external_rates, in_flight):
        result = defaultdict(float)
        for commodity in self.commodities:
            result[(commodity.source, commodity.commodity_id)] += external_rates[commodity.commodity_id]
        for (edge, commodity_id), rate in in_flight.arrival_rates.items():
            if rate < -1e-7:
                raise AssertionError("NEGATIVE_PROPAGATION_ARRIVAL_RATE")
            result[(edge[1], commodity_id)] += max(0.0, rate)
        return result

    def _service(self, queues, inputs):
        demands_by_edge = defaultdict(dict)
        active_queue_keys = ({key for key, value in queues.bits.items() if value > 1e-12}
                             | {key for key, value in inputs.items() if value > 1e-15})
        for node, key in sorted(active_queue_keys):
            commodity = self.by_id[key]
            if node == commodity.destination:
                continue
            edge = self.next_hop[(node, key)]
            if edge is None:
                continue
            backlog = queues.get(node, key)
            demand = math.inf if backlog > self.state_tol else inputs[(node, key)]
            if demand > 1e-15:
                demands_by_edge[edge][key] = demand
        rates = {}
        max_violation = 0.0
        for edge, demands in demands_by_edge.items():
            allocation = equal_weight_fair_share(self.capacity[edge], demands)
            for commodity_id, rate in allocation.items():
                rates[(edge, commodity_id)] = rate
            max_violation = max(max_violation,
                                sum(allocation.values()) - self.capacity[edge])
        return rates, max(0.0, max_violation)

    def _schedule_service_segments(self, now, old_rates, old_delays, new_rates,
                                   agenda, sequence, force_refresh=False):
        keys = sorted(set(old_rates) | set(new_rates))
        new_delays = dict(old_delays)
        for key in keys:
            old = old_rates.get(key, 0.0)
            new = new_rates.get(key, 0.0)
            changed = abs(old-new) > max(1e-12, max(abs(old), abs(new))*1e-14)
            if not changed and not force_refresh:
                continue
            edge, commodity_id = key
            if old > 0.0:
                sequence += 1
                heapq.heappush(agenda, RateArrivalEvent(
                    now + old_delays[key], sequence, edge, commodity_id, -old))
            if new > 0.0:
                delay = float(self.delay(edge, now))
                if not math.isfinite(delay) or delay <= 0.0:
                    raise ValueError("NONPOSITIVE_PROPAGATION_DELAY")
                new_delays[key] = delay
                sequence += 1
                heapq.heappush(agenda, RateArrivalEvent(
                    now + delay, sequence, edge, commodity_id, new))
            else:
                new_delays.pop(key, None)
        return new_delays, sequence

    def run(self, drain_limit_s, observation_step_s=None):
        wall_start = time.perf_counter()
        drain_limit_s = float(drain_limit_s)
        if drain_limit_s <= self.trace.arrival_horizon_s:
            raise ValueError("DRAIN_LIMIT_MUST_EXCEED_ARRIVAL_HORIZON")
        observations = []
        if observation_step_s is not None:
            observation_step_s = float(observation_step_s)
            if observation_step_s <= 0.0:
                raise ValueError("INVALID_OBSERVATION_STEP")
            count = 1
            while count*observation_step_s < drain_limit_s + 1e-12:
                observations.append(min(count*observation_step_s, drain_limit_s))
                count += 1
        observation_index = 0
        trace_boundaries = list(self.trace.boundaries_after(0.0))
        boundary_index = 0
        next_refresh = self.geometry_refresh_s

        queues = QueueState()
        in_flight = InFlightState()
        arrived = defaultdict(float)
        arrived_compensation = defaultdict(float)
        delivered = defaultdict(float)
        delivered_compensation = defaultdict(float)
        objective_by_commodity = defaultdict(float)
        objective_compensation = defaultdict(float)

        def compensated_add(values, compensations, key, increment):
            adjusted = increment-compensations[key]
            total = values[key]+adjusted
            compensations[key] = (total-values[key])-adjusted
            values[key] = total
        queue_area = 0.0
        max_queue = 0.0
        transmitted = defaultdict(float)
        transmitted_by_commodity = defaultdict(float)
        service_rates = {}
        service_delays = {}
        agenda = []
        sequence = 0
        maximum_capacity_violation = 0.0
        max_abs_conservation = 0.0
        max_relative_conservation = 0.0
        conservation_samples = 0
        timeline = []
        now = 0.0
        event_count = 0

        def residual_by_commodity(commodity_id):
            return queues.total(commodity_id) + in_flight.total(commodity_id)

        def record(label):
            nonlocal max_abs_conservation, max_relative_conservation, conservation_samples
            errors = {}
            for commodity in self.commodities:
                key = commodity.commodity_id
                error = (arrived[key] - delivered[key] - queues.total(key)
                         - in_flight.total(key))
                errors[key] = error
                max_abs_conservation = max(max_abs_conservation, abs(error))
                scale = max(1.0, abs(arrived[key]))
                max_relative_conservation = max(max_relative_conservation,
                                                abs(error)/scale)
                if abs(error) > self.abs_tol + self.rel_tol*scale:
                    raise AssertionError(f"WORK_CONSERVATION_VIOLATION time={now} commodity={key} error={error} A={arrived[key]} D={delivered[key]} Q={queues.total(key)} I={in_flight.total(key)}")
            conservation_samples += 1
            timeline.append({
                "time_s": now, "label": label,
                "arrived_bits": sum(arrived.values()),
                "delivered_bits": sum(delivered.values()),
                "queued_bits": queues.total(), "in_flight_bits": in_flight.total(),
                "conservation_error_bits": sum(errors.values()),
            })

        record("INITIAL")
        while now < drain_limit_s - 1e-13:
            event_count += 1
            if event_count > 1000000:
                raise RuntimeError("EVENT_LIMIT_EXCEEDED")

            due_deltas = defaultdict(float)
            while agenda and agenda[0].time_s <= now + 1e-12:
                event = heapq.heappop(agenda)
                due_deltas[(event.edge, event.commodity_id)] += event.delta_rate_bit_s
            for key, delta in due_deltas.items():
                in_flight.arrival_rates[key] += delta
                value = in_flight.arrival_rates[key]
                cancellation_tolerance = max(1e-6, abs(delta)*1e-12)
                if abs(value) <= cancellation_tolerance:
                    in_flight.arrival_rates[key] = 0.0
                elif value < 0.0:
                    raise AssertionError(f"NEGATIVE_DELAYED_RATE time={now} key={key} value={value} delta={delta}")

            while boundary_index < len(trace_boundaries) and trace_boundaries[boundary_index] <= now + 1e-12:
                boundary_index += 1
            while observation_index < len(observations) and observations[observation_index] <= now + 1e-12:
                observation_index += 1
            is_refresh = False
            if next_refresh is not None and next_refresh <= now + 1e-12:
                is_refresh = True
                while next_refresh <= now + 1e-12:
                    next_refresh += self.geometry_refresh_s

            external = self.trace.rate_at(now)
            inputs = self._inputs(external, in_flight)
            new_service, violation = self._service(queues, inputs)
            maximum_capacity_violation = max(maximum_capacity_violation, violation)
            service_delays, sequence = self._schedule_service_segments(
                now, service_rates, service_delays, new_service,
                agenda, sequence, force_refresh=is_refresh)
            service_rates = new_service

            queue_derivative = {}
            delivery_rates = {}
            active_queue_keys = ({key for key, value in queues.bits.items() if value > 1e-12}
                                 | {key for key, value in inputs.items() if value > 1e-15})
            for node, key in sorted(active_queue_keys):
                incoming = inputs[(node, key)]
                commodity = self.by_id[key]
                if node == commodity.destination:
                    delivery_rates[key] = delivery_rates.get(key, 0.0) + incoming
                    continue
                edge = self.next_hop[(node, key)]
                outgoing = service_rates.get((edge, key), 0.0) if edge is not None else 0.0
                queue_derivative[(node, key)] = incoming - outgoing

            candidate_times = [drain_limit_s]
            if boundary_index < len(trace_boundaries):
                candidate_times.append(trace_boundaries[boundary_index])
            if agenda:
                candidate_times.append(agenda[0].time_s)
            if next_refresh is not None:
                candidate_times.append(next_refresh)
            for (node, key), derivative in queue_derivative.items():
                backlog = queues.get(node, key)
                if backlog > self.state_tol and derivative < -1e-15:
                    candidate_times.append(now + backlog/(-derivative))
            future = [value for value in candidate_times if value > now + 1e-13]
            if not future:
                raise RuntimeError("NO_FORWARD_EVENT")
            next_time = min(future)
            dt = next_time - now

            # Observation grids are passive: interpolate the affine state inside
            # the current true-event interval without changing any state variable.
            while (observation_index < len(observations)
                   and observations[observation_index] <= next_time + 1e-12):
                observed_time = observations[observation_index]
                offset = observed_time-now
                if offset >= -1e-12:
                    observed_arrived = math.fsum(arrived.values()) + math.fsum(external.values())*offset
                    observed_delivered = math.fsum(delivered.values()) + math.fsum(delivery_rates.values())*offset
                    observed_queue = math.fsum(
                        queues.get(node, key) + derivative*offset
                        for (node, key), derivative in queue_derivative.items())
                    transit_keys = (set(service_rates)
                                    | {key for key, value in in_flight.arrival_rates.items() if value != 0.0}
                                    | {key for key, value in in_flight.bits.items() if value != 0.0})
                    observed_in_flight = math.fsum(
                        in_flight.bits[(edge, key)]
                        + (service_rates.get((edge, key), 0.0)
                           - in_flight.arrival_rates[(edge, key)])*offset
                        for edge, key in transit_keys)
                    timeline.append({
                        "time_s": observed_time, "label": "PASSIVE_OBSERVATION",
                        "arrived_bits": observed_arrived,
                        "delivered_bits": observed_delivered,
                        "queued_bits": observed_queue,
                        "in_flight_bits": observed_in_flight,
                        "conservation_error_bits": (observed_arrived-observed_delivered
                                                    -observed_queue-observed_in_flight),
                    })
                observation_index += 1

            old_not_delivered = {item.commodity_id:
                                 arrived[item.commodity_id]-delivered[item.commodity_id]
                                 for item in self.commodities}
            old_queue = queues.total()

            # Conservative transactions: every moved amount is subtracted from
            # one state and added to exactly one other state using the same x.
            for commodity in self.commodities:
                key = commodity.commodity_id
                amount = external[key]*dt
                if amount:
                    compensated_add(arrived, arrived_compensation, key, amount)
                    queues.add(commodity.source, key, amount,
                               tolerance=max(self.state_tol, self.abs_tol))
            for (edge, key), rate in sorted(service_rates.items()):
                amount = rate*dt
                if amount:
                    in_flight.add_bits(edge, key, amount,
                                       tolerance=max(self.state_tol, self.abs_tol))
                    transmitted[edge] += amount
                    transmitted_by_commodity[(edge, key)] += amount
            for (edge, key), rate in sorted(in_flight.arrival_rates.items()):
                amount = rate*dt
                if not amount:
                    continue
                in_flight.add_bits(edge, key, -amount,
                                   tolerance=max(self.state_tol, self.abs_tol))
                commodity = self.by_id[key]
                if edge[1] == commodity.destination:
                    compensated_add(delivered, delivered_compensation, key, amount)
                else:
                    queues.add(edge[1], key, amount,
                               tolerance=max(self.state_tol, self.abs_tol))
            for (edge, key), rate in sorted(service_rates.items()):
                amount = rate*dt
                if amount:
                    available = queues.get(edge[0], key)
                    if amount > available + max(self.state_tol, self.abs_tol):
                        raise AssertionError(
                            f"SERVICE_EXCEEDS_INTERVAL_WORK time={now} next={next_time} dt={dt} "
                            f"edge={edge} key={key} available={available} amount={amount} "
                            f"rate={rate} input_rate={inputs[(edge[0], key)]} "
                            f"derivative={queue_derivative[(edge[0], key)]}")
                    queues.add(edge[0], key, -amount,
                               tolerance=max(self.state_tol, self.abs_tol))
            for commodity in self.commodities:
                key = commodity.commodity_id
                slope = external[key] - delivery_rates.get(key, 0.0)
                compensated_add(objective_by_commodity, objective_compensation, key,
                    commodity.weight * (old_not_delivered[key]*dt + 0.5*slope*dt*dt))
            new_queue = queues.total()
            queue_area += 0.5*(old_queue+new_queue)*dt
            max_queue = max(max_queue, old_queue, new_queue)
            now = next_time
            record("EVENT_BOUNDARY")

            no_future_arrivals = now >= self.trace.arrival_horizon_s - 1e-12
            residual = queues.total() + in_flight.total()
            if no_future_arrivals and residual <= max(self.state_tol, self.abs_tol):
                break

        total_arrived = math.fsum(arrived.values())
        total_delivered = math.fsum(delivered.values())
        residual = queues.total() + in_flight.total()
        drained = (residual <= max(self.state_tol, self.abs_tol)
                   and now >= self.trace.arrival_horizon_s)
        utilization = {edge[0] + "->" + edge[1]: transmitted[edge]/(self.capacity[edge]*now)
                       for edge in self.directed_edges if transmitted[edge] > 0.0}
        metrics = {
            "schema": "gate_d1_network_service_metrics_v1",
            "evaluation_end_s": now,
            "arrival_horizon_s": self.trace.arrival_horizon_s,
            "censored": not drained,
            "mean_bit_delay_s": (math.fsum(objective_by_commodity.values())/total_arrived
                                 if drained and total_arrived > 0.0 else None),
            "objective_J_bit_s": math.fsum(objective_by_commodity.values()),
            "objective_by_commodity_bit_s": dict(sorted(objective_by_commodity.items())),
            "arrived_bits": total_arrived,
            "delivered_bits": total_delivered,
            "delivery_ratio": total_delivered/total_arrived if total_arrived else 1.0,
            "residual_backlog_bits": residual,
            "queued_bits_at_end": queues.total(),
            "in_flight_bits_at_end": in_flight.total(),
            "mean_queue_bits": queue_area/now if now > 0.0 else 0.0,
            "max_queue_bits": max_queue,
            "link_utilization": utilization,
            "traffic_weighted_hop_count": (math.fsum(transmitted.values())/total_delivered
                                           if total_delivered > 0.0 else None),
            "max_abs_conservation_error_bits": max_abs_conservation,
            "max_relative_conservation_error": max_relative_conservation,
            "conservation_samples": conservation_samples,
            "max_capacity_violation_bit_s": maximum_capacity_violation,
            "negative_queue_count": sum(value < 0.0 for value in queues.bits.values()),
            "event_count": event_count,
            "trace_sha256": self.trace.sha256(),
            "runtime": time.perf_counter()-wall_start,
        }
        metrics.update(empty_transition_metrics(self.active_dynamic_link_count))
        return {
            "metrics": metrics,
            "timeline": timeline,
            "queues": queues.snapshot(),
            "in_flight": in_flight.snapshot(),
            "arrived_by_commodity": dict(sorted(arrived.items())),
            "delivered_by_commodity": dict(sorted(delivered.items())),
            "transmitted_by_edge_commodity": {
                edge[0] + "->" + edge[1] + "|" + key: value
                for (edge, key), value in sorted(transmitted_by_commodity.items())},
            "routes": {node + "|" + key: (list(route) if route is not None else None)
                       for (node, key), route in sorted(self.routes.items())},
            "no_route_commodities_from_source": [
                item.commodity_id for item in self.commodities
                if self.routes[(item.source, item.commodity_id)] is None],
        }
