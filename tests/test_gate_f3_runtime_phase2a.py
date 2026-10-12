"""Gate F3 runtime Phase 2A exact memoization equivalence tests."""
from __future__ import annotations

from collections import Counter
import unittest

from dynamic_lisl.common_router import (
    DeterministicShortestPropagationDelayRouter,
    ExactEvaluationEdgeDelayMemo,
)
from dynamic_lisl.scientific_controllers import (
    IgnoreSetupDynamicController, SetupAwareGreedyController,
)
from dynamic_lisl.scientific_snapshot import ScientificSnapshotEvaluator
from tests.test_gate_f1_scientific_scoring_v2 import (
    beneficial_environment, proposal, proposal_set, visible,
)


class CountingDelay:
    def __init__(self, values=None):
        self.values = values or {}
        self.calls = Counter()

    def __call__(self, edge, time_s):
        key = (tuple(edge), float(time_s))
        self.calls[key] += 1
        return float(self.values.get(tuple(edge), 1.0))


class CountingSnapshot(ScientificSnapshotEvaluator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.edge_evaluations = 0

    def evaluate_edges(self, edges):
        self.edge_evaluations += 1
        return super().evaluate_edges(edges)


class GateF3RuntimePhase2ATests(unittest.TestCase):
    def test_exact_directed_edge_time_key_and_local_lifetime(self):
        provider = CountingDelay({("A", "B"): 1.25, ("B", "A"): 1.5})
        first = ExactEvaluationEdgeDelayMemo(provider)
        self.assertEqual(first(("A", "B"), 2.0), 1.25)
        self.assertEqual(first(("A", "B"), 2.0), 1.25)
        self.assertEqual(first(("B", "A"), 2.0), 1.5)
        self.assertEqual(first(("A", "B"), 2.000000000000001), 1.25)
        self.assertEqual(sum(provider.calls.values()), 3)
        second = ExactEvaluationEdgeDelayMemo(provider)
        self.assertEqual(second(("A", "B"), 2.0), 1.25)
        self.assertEqual(sum(provider.calls.values()), 4)

    def test_router_paths_ties_and_costs_are_exact(self):
        edges = (("A", "B"), ("B", "D"), ("A", "C"), ("C", "D"),
                 ("B", "A"), ("D", "B"), ("C", "A"), ("D", "C"))
        values = {
            ("A", "B"): 1.0, ("B", "D"): 1.0,
            ("A", "C"): 1.0, ("C", "D"): 1.0,
            ("B", "A"): 1.0, ("D", "B"): 1.0,
            ("C", "A"): 1.0, ("D", "C"): 1.0,
        }
        legacy_delay = CountingDelay(values)
        optimized_delay = CountingDelay(values)
        router = DeterministicShortestPropagationDelayRouter()
        legacy = {
            (source, destination): router.path(
                source, destination, edges, legacy_delay, 7.25)
            for source in ("A", "B", "C", "D")
            for destination in ("A", "B", "C", "D")
        }
        memo = ExactEvaluationEdgeDelayMemo(optimized_delay)
        optimized = {
            (source, destination): router.path(
                source, destination, edges, memo, 7.25)
            for source in ("A", "B", "C", "D")
            for destination in ("A", "B", "C", "D")
        }
        self.assertEqual(legacy, optimized)
        self.assertEqual(optimized[("A", "D")], ("A", "B", "D"))
        for key, route in legacy.items():
            if route is None:
                continue
            legacy_cost = sum(values[edge] for edge in zip(route, route[1:]))
            optimized_cost = sum(
                memo(edge, 7.25) for edge in zip(route, route[1:]))
            self.assertEqual(legacy_cost, optimized_cost)
        self.assertLess(sum(optimized_delay.calls.values()),
                        sum(legacy_delay.calls.values()))

    def test_snapshot_and_b1_b3_actions_match_legacy(self):
        rows = proposal_set(
            proposal("FIRST", ("A", "X")),
            proposal("SECOND", ("A", "Y")))
        legacy_engine = beneficial_environment()
        optimized_engine = beneficial_environment()
        legacy_eval = ScientificSnapshotEvaluator.legacy_no_cache_reference(
            legacy_engine)
        optimized_eval = ScientificSnapshotEvaluator(optimized_engine)
        legacy_hold, legacy_candidates = legacy_eval.evaluate_proposal_set(rows)
        optimized_hold, optimized_candidates = (
            optimized_eval.evaluate_proposal_set(rows))
        self.assertEqual(legacy_hold, optimized_hold)
        self.assertEqual(legacy_candidates, optimized_candidates)

        for controller_type in (
                IgnoreSetupDynamicController, SetupAwareGreedyController):
            legacy_engine = beneficial_environment()
            optimized_engine = beneficial_environment()
            legacy_controller = controller_type(legacy_engine)
            legacy_controller.evaluator = (
                ScientificSnapshotEvaluator.legacy_no_cache_reference(
                    legacy_engine))
            optimized_controller = controller_type(optimized_engine)
            legacy_action = legacy_controller.observe(
                visible(legacy_engine), rows, {})
            optimized_action = optimized_controller.observe(
                visible(optimized_engine), rows, {})
            self.assertEqual(legacy_action, optimized_action)

    def test_no_duplicate_topology_shortcut_is_active(self):
        engine = beneficial_environment()
        evaluator = CountingSnapshot(engine)
        duplicate = proposal_set(
            proposal("P1", ("A", "X")),
            proposal("P2", ("A", "X")))
        _hold, candidates = evaluator.evaluate_proposal_set(duplicate)
        self.assertEqual([key for key, _value in candidates], ["P1", "P2"])
        self.assertEqual(evaluator.edge_evaluations, 3)


if __name__ == "__main__":
    unittest.main()
