"""Gate F3 runtime Phase 2B-1 exact adjacency reuse tests."""
from __future__ import annotations

from collections import Counter
import time
import unittest

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.common_router import (
    DeterministicShortestPropagationDelayRouter,
    _build_canonical_adjacency,
)


class ExactDelay:
    def __init__(self, values):
        self.values = dict(values)
        self.calls = Counter()

    def __call__(self, edge, time_s):
        key = (tuple(edge), float(time_s))
        self.calls[key] += 1
        return float(self.values[tuple(edge)])


class InstrumentedRouter(DeterministicShortestPropagationDelayRouter):
    def __init__(self, use_adjacency_reuse):
        super().__init__(use_adjacency_reuse=use_adjacency_reuse,
                         use_same_destination_reuse=False)
        self.adjacency_build_count = 0
        self.adjacency_build_wall_s = 0.0
        self.path_search_count = 0
        self.path_search_wall_s = 0.0

    def _build_adjacency(self, edges):
        started = time.perf_counter()
        value = super()._build_adjacency(edges)
        self.adjacency_build_wall_s += time.perf_counter() - started
        self.adjacency_build_count += 1
        return value

    def _path_with_adjacency(self, *args, **kwargs):
        started = time.perf_counter()
        value = super()._path_with_adjacency(*args, **kwargs)
        self.path_search_wall_s += time.perf_counter() - started
        self.path_search_count += 1
        return value


def route_costs(routes, values):
    return {
        key: (None if route is None else sum(
            values[edge] for edge in zip(route, route[1:])))
        for key, route in routes.items()
    }


class GateF3RuntimePhase2B1Tests(unittest.TestCase):
    def setUp(self):
        self.nodes = ("A", "B", "C", "D", "X")
        self.edges = (
            ("A", "B"), ("B", "D"), ("A", "C"), ("C", "D"),
            ("B", "A"), ("D", "B"), ("C", "A"), ("D", "C"),
            ("D", "A"),
        )
        self.values = {edge: 1.0 for edge in self.edges}

    def compare(self, commodities, edges=None, values=None):
        edges = self.edges if edges is None else tuple(edges)
        values = self.values if values is None else dict(values)
        legacy = InstrumentedRouter(False)
        optimized = InstrumentedRouter(True)
        legacy_delay = ExactDelay(values)
        optimized_delay = ExactDelay(values)
        old = legacy.routes_to_destinations(
            self.nodes, commodities, edges, legacy_delay, 7.25)
        new = optimized.routes_to_destinations(
            self.nodes, commodities, edges, optimized_delay, 7.25)
        self.assertEqual(list(old.items()), list(new.items()))
        self.assertEqual(route_costs(old, values), route_costs(new, values))
        self.assertEqual(legacy.path_search_count,
                         optimized.path_search_count)
        return old, legacy, optimized

    def test_basic_tie_disconnected_directed_and_source_equals_destination(self):
        commodities = (
            Commodity("f_d", "A", "D"),
            Commodity("f_a", "D", "A"),
            Commodity("f_x", "A", "X"),
        )
        routes, legacy, optimized = self.compare(commodities)
        self.assertEqual(routes[("A", "f_d")], ("A", "B", "D"))
        self.assertEqual(routes[("D", "f_a")], ("D", "A"))
        self.assertIsNone(routes[("A", "f_x")])
        self.assertEqual(routes[("D", "f_d")], ("D",))
        self.assertEqual(routes[("A", "f_a")], ("A",))
        self.assertEqual(routes[("X", "f_x")], ("X",))
        self.assertEqual(legacy.path_search_count, len(self.nodes)*3)
        self.assertEqual(optimized.path_search_count, len(self.nodes)*3)

    def test_multiple_same_and_different_destinations_and_exact_build_counts(self):
        commodities = (
            Commodity("f1", "A", "D"),
            Commodity("f2", "B", "D"),
            Commodity("f3", "D", "A"),
        )
        _routes, legacy, optimized = self.compare(commodities)
        expected_queries = len(self.nodes)*len(commodities)
        source_equals_destination = sum(
            1 for commodity in commodities for node in self.nodes
            if node == commodity.destination)
        self.assertEqual(legacy.path_search_count, expected_queries)
        self.assertEqual(optimized.path_search_count, expected_queries)
        self.assertEqual(legacy.adjacency_build_count,
                         expected_queries-source_equals_destination)
        self.assertEqual(optimized.adjacency_build_count, 1)

    def test_topology_change_repeated_determinism_and_canonical_adjacency(self):
        commodities = (Commodity("f", "A", "D"),)
        first, _, _ = self.compare(commodities)
        second, _, _ = self.compare(commodities)
        self.assertEqual(list(first.items()), list(second.items()))
        changed_edges = tuple(edge for edge in self.edges
                              if edge not in (("A", "B"), ("B", "D")))
        changed_values = {edge: self.values[edge] for edge in changed_edges}
        changed, _, _ = self.compare(
            commodities, changed_edges, changed_values)
        self.assertEqual(changed[("A", "f")], ("A", "C", "D"))
        adjacency = _build_canonical_adjacency(
            tuple(reversed(self.edges)) + self.edges)
        expected = {}
        for a, b in sorted(set(tuple(edge) for edge in self.edges)):
            expected.setdefault(a, []).append(b)
        self.assertEqual(adjacency, expected)


if __name__ == "__main__":
    unittest.main()

