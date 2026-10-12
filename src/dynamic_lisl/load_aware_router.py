"""Independent deterministic current-state load-aware CommonRouter for Gate E0."""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

from .common_router import CommonRouter


@dataclass(frozen=True)
class CurrentNetworkSnapshot:
    time_s: float
    edge_utilization: dict
    node_queue_bits: dict
    offered_rate_bit_s: dict


class DeterministicLoadAwareRouter(CommonRouter):
    """Route on current delay, utilization and aggregate downstream queue only.

    The caller must explicitly install a snapshot for the same simulation time.
    No future trace, action, controller identity or candidate score is accepted.
    """

    def __init__(self, utilization_penalty_s=0.05, queue_penalty_s=0.02,
                 queue_scale_bits=1e9, time_tolerance_s=1e-12):
        self.utilization_penalty_s = float(utilization_penalty_s)
        self.queue_penalty_s = float(queue_penalty_s)
        self.queue_scale_bits = float(queue_scale_bits)
        self.time_tolerance_s = float(time_tolerance_s)
        if (self.utilization_penalty_s < 0 or self.queue_penalty_s < 0
                or self.queue_scale_bits <= 0 or self.time_tolerance_s < 0):
            raise ValueError("INVALID_LOAD_AWARE_ROUTER_PARAMETER")
        self.snapshot = None

    def update_current_state(self, time_s, edge_utilization=(), node_queue_bits=(),
                             offered_rate_bit_s=()):
        time_s = float(time_s)
        if not math.isfinite(time_s):
            raise ValueError("NONFINITE_ROUTING_SNAPSHOT_TIME")
        edge_load = {tuple(edge): float(value)
                     for edge, value in dict(edge_utilization).items()}
        node_queue = {str(node): float(value)
                      for node, value in dict(node_queue_bits).items()}
        offered = {str(key): float(value)
                   for key, value in dict(offered_rate_bit_s).items()}
        if any(not math.isfinite(x) or x < 0 for x in (
                *edge_load.values(), *node_queue.values(), *offered.values())):
            raise ValueError("INVALID_CURRENT_LOAD_SNAPSHOT")
        self.snapshot = CurrentNetworkSnapshot(time_s, edge_load, node_queue, offered)

    def _snapshot_at(self, time_s):
        if self.snapshot is None:
            raise ValueError("CURRENT_LOAD_SNAPSHOT_REQUIRED")
        if abs(self.snapshot.time_s-float(time_s)) > self.time_tolerance_s:
            raise ValueError("STALE_OR_FUTURE_LOAD_SNAPSHOT")
        return self.snapshot

    def _weight(self, edge, propagation_delay_s, time_s, snapshot):
        delay = float(propagation_delay_s(edge, time_s))
        if not math.isfinite(delay) or delay <= 0:
            raise ValueError("ROUTER_REQUIRES_POSITIVE_FINITE_WEIGHT")
        utilization = snapshot.edge_utilization.get(tuple(edge), 0.0)
        downstream_queue = snapshot.node_queue_bits.get(edge[1], 0.0)
        return (delay + self.utilization_penalty_s*utilization
                + self.queue_penalty_s*downstream_queue/self.queue_scale_bits)

    def path(self, source, destination, directed_edges, propagation_delay_s,
             time_s=0.0):
        snapshot = self._snapshot_at(time_s)
        if source == destination:
            return (source,)
        adjacency = {}
        for a, b in sorted(set(tuple(edge) for edge in directed_edges)):
            adjacency.setdefault(a, []).append(b)
        heap = [(0.0, (source,), source)]
        best = {source: (0.0, (source,))}
        while heap:
            cost, route, node = heapq.heappop(heap)
            if best.get(node) != (cost, route):
                continue
            if node == destination:
                return route
            for neighbor in adjacency.get(node, ()):
                edge = (node, neighbor)
                candidate = (cost+self._weight(
                    edge, propagation_delay_s, time_s, snapshot),
                    route+(neighbor,))
                current = best.get(neighbor)
                if current is None or candidate < current:
                    best[neighbor] = candidate
                    heapq.heappush(heap, (candidate[0], candidate[1], neighbor))
        return None

    def routes_to_destinations(self, nodes, commodities, directed_edges,
                               propagation_delay_s, time_s=0.0):
        return {
            (node, commodity.commodity_id): self.path(
                node, commodity.destination, directed_edges,
                propagation_delay_s, time_s)
            for commodity in sorted(commodities) for node in sorted(nodes)
        }

