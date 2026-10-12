"""Controller-independent deterministic routing interfaces for Gate D."""
from __future__ import annotations

from abc import ABC, abstractmethod
import heapq
import math


class ExactEvaluationEdgeDelayMemo:
    """Per-topology, exact-key delay memo for one snapshot evaluation only."""

    def __init__(self, propagation_delay_s):
        self.propagation_delay_s = propagation_delay_s
        self.cache = {}

    def __call__(self, edge, time_s):
        key = (tuple(edge), float(time_s))
        if key not in self.cache:
            self.cache[key] = float(
                self.propagation_delay_s(tuple(edge), time_s))
        return self.cache[key]


def _build_canonical_adjacency(directed_edges):
    """Build exactly the adjacency historically constructed by every path()."""
    adjacency = {}
    for a, b in sorted(set(tuple(edge) for edge in directed_edges)):
        adjacency.setdefault(a, []).append(b)
    return adjacency


class CommonRouter(ABC):
    @abstractmethod
    def path(self, source, destination, directed_edges, propagation_delay_s, time_s=0.0):
        raise NotImplementedError


class DeterministicShortestPropagationDelayRouter(CommonRouter):
    """Positive-weight Dijkstra with lexicographic full-path tie breaking."""

    def __init__(self, use_adjacency_reuse=True,
                 use_same_destination_reuse=True):
        self.use_adjacency_reuse = bool(use_adjacency_reuse)
        self.use_same_destination_reuse = bool(use_same_destination_reuse)

    @classmethod
    def legacy_no_adjacency_reuse_reference(cls):
        """Test/engineering reference for per-path adjacency construction."""
        return cls(use_adjacency_reuse=False,
                   use_same_destination_reuse=False)

    @classmethod
    def phase2b1_no_destination_reuse_reference(cls):
        """Exact Phase 2B-1 reference: adjacency reuse, no route reuse."""
        return cls(use_adjacency_reuse=True,
                   use_same_destination_reuse=False)

    def _build_adjacency(self, directed_edges):
        return _build_canonical_adjacency(directed_edges)

    def _path_with_adjacency(self, source, destination, adjacency,
                             propagation_delay_s, time_s=0.0):
        if source == destination:
            return (source,)
        heap = [(0.0, (source,), source)]
        best = {source: (0.0, (source,))}
        while heap:
            distance, route, node = heapq.heappop(heap)
            if best.get(node) != (distance, route):
                continue
            if node == destination:
                return route
            for neighbor in adjacency.get(node, ()):
                weight = float(propagation_delay_s((node, neighbor), time_s))
                if not math.isfinite(weight) or weight <= 0.0:
                    raise ValueError("ROUTER_REQUIRES_POSITIVE_FINITE_WEIGHT")
                candidate = (distance + weight, route + (neighbor,))
                current = best.get(neighbor)
                if current is None or candidate < current:
                    best[neighbor] = candidate
                    heapq.heappush(heap, (candidate[0], candidate[1], neighbor))
        return None

    def path(self, source, destination, directed_edges, propagation_delay_s, time_s=0.0):
        if source == destination:
            return self._path_with_adjacency(
                source, destination, {}, propagation_delay_s, time_s)
        adjacency = self._build_adjacency(directed_edges)
        return self._path_with_adjacency(
            source, destination, adjacency, propagation_delay_s, time_s)

    def routes_to_destinations(self, nodes, commodities, directed_edges,
                               propagation_delay_s, time_s=0.0):
        routes = {}
        if getattr(self, "use_adjacency_reuse", True):
            adjacency = self._build_adjacency(directed_edges)
            ordered_commodities = tuple(sorted(commodities))
            ordered_nodes = tuple(sorted(nodes))
            if getattr(self, "use_same_destination_reuse", True):
                routes_by_destination = {
                    destination: {
                        node: self._path_with_adjacency(
                            node, destination, adjacency,
                            propagation_delay_s, time_s)
                        for node in ordered_nodes}
                    for destination in sorted({
                        commodity.destination
                        for commodity in ordered_commodities})}
                for commodity in ordered_commodities:
                    destination_routes = routes_by_destination[
                        commodity.destination]
                    for node in ordered_nodes:
                        routes[(node, commodity.commodity_id)] = (
                            destination_routes[node])
                return routes
            for commodity in ordered_commodities:
                for node in ordered_nodes:
                    routes[(node, commodity.commodity_id)] = (
                        self._path_with_adjacency(
                            node, commodity.destination, adjacency,
                            propagation_delay_s, time_s))
            return routes
        for commodity in sorted(commodities):
            for node in sorted(nodes):
                routes[(node, commodity.commodity_id)] = self.path(
                    node, commodity.destination, directed_edges,
                    propagation_delay_s, time_s)
        return routes
