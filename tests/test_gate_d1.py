"""Analytical and invariant tests for the Gate D1 fixed-topology kernel."""
import math
import unittest

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.common_router import DeterministicShortestPropagationDelayRouter
from dynamic_lisl.network_service_engine import NetworkServiceEngine
from dynamic_lisl.service_scheduler import equal_weight_fair_share
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment


def trace(rates, end_s):
    ids = tuple(sorted(rates))
    return PiecewiseConstantTrafficTrace(ids, [TrafficSegment(0.0, end_s, rates, "fixture")])


def constant_delay(seconds):
    return lambda edge, time_s: float(seconds)


def engine(nodes, edges, capacity, commodities, traffic, delay):
    return NetworkServiceEngine(
        nodes, edges, capacity, commodities, traffic, constant_delay(delay),
        conservation_abs_tolerance_bits=1e-9,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=1e-10,
    )


class GateD1AnalyticalFixtures(unittest.TestCase):
    def assertClose(self, actual, expected, tolerance=1e-8):
        self.assertAlmostEqual(actual, expected, delta=tolerance)

    def test_single_link_fixture(self):
        commodities = [Commodity("f", "A", "B")]
        result = engine(("A", "B"), (("A", "B"),), 10.0, commodities,
                        trace({"f": 5.0}, 2.0), 0.5).run(5.0, 0.25)
        metrics = result["metrics"]
        self.assertFalse(metrics["censored"])
        self.assertClose(metrics["arrived_bits"], 10.0)
        self.assertClose(metrics["delivered_bits"], 10.0)
        self.assertClose(metrics["max_queue_bits"], 0.0)
        self.assertClose(metrics["objective_J_bit_s"], 5.0)
        self.assertClose(metrics["mean_bit_delay_s"], 0.5)

    def test_two_hop_fixture_and_accounting_chain(self):
        commodities = [Commodity("f", "A", "C")]
        result = engine(("A", "B", "C"), (("A", "B"), ("B", "C")),
                        10.0, commodities, trace({"f": 5.0}, 2.0), 0.2).run(5.0, 0.1)
        metrics = result["metrics"]
        self.assertClose(metrics["arrived_bits"], 10.0)
        self.assertClose(metrics["delivered_bits"], 10.0)
        self.assertClose(metrics["objective_J_bit_s"], 4.0)
        self.assertClose(metrics["mean_bit_delay_s"], 0.4)
        self.assertClose(metrics["traffic_weighted_hop_count"], 2.0)

    def test_shared_bottleneck_fixture_is_fair_and_work_conserving(self):
        commodities = [Commodity("f1", "S1", "D"), Commodity("f2", "S2", "D")]
        edges = (("S1", "X"), ("S2", "X"), ("X", "D"))
        result = engine(("S1", "S2", "X", "D"), edges, 10.0, commodities,
                        trace({"f1": 8.0, "f2": 8.0}, 1.0), 0.1).run(5.0, 0.1)
        metrics = result["metrics"]
        self.assertClose(metrics["arrived_bits"], 16.0)
        self.assertClose(metrics["max_queue_bits"], 6.0)
        self.assertClose(metrics["objective_J_bit_s"], 8.0)
        self.assertClose(metrics["mean_bit_delay_s"], 0.5)
        first = result["transmitted_by_edge_commodity"]["X->D|f1"]
        second = result["transmitted_by_edge_commodity"]["X->D|f2"]
        self.assertClose(first, 8.0)
        self.assertClose(second, 8.0)
        self.assertLessEqual(metrics["max_capacity_violation_bit_s"], 1e-12)

    def test_overload_then_drain_fixture(self):
        commodities = [Commodity("f", "A", "B")]
        result = engine(("A", "B"), (("A", "B"),), 10.0, commodities,
                        trace({"f": 15.0}, 2.0), 0.1).run(5.0, 0.1)
        metrics = result["metrics"]
        self.assertFalse(metrics["censored"])
        self.assertClose(metrics["max_queue_bits"], 10.0)
        self.assertClose(metrics["objective_J_bit_s"], 18.0)
        self.assertClose(metrics["mean_bit_delay_s"], 0.6)
        self.assertClose(metrics["evaluation_end_s"], 3.1)

    def test_disconnected_path_keeps_work_and_reports_censoring(self):
        commodities = [Commodity("f", "A", "B")]
        result = engine(("A", "B", "C"), (("A", "C"),), 10.0, commodities,
                        trace({"f": 10.0}, 1.0), 0.1).run(2.0, 0.5)
        metrics = result["metrics"]
        self.assertTrue(metrics["censored"])
        self.assertEqual(result["no_route_commodities_from_source"], ["f"])
        self.assertClose(metrics["residual_backlog_bits"], 10.0)
        self.assertClose(metrics["delivered_bits"], 0.0)
        self.assertClose(metrics["objective_J_bit_s"], 15.0)

    def test_propagation_in_flight_is_in_conservation_identity(self):
        commodities = [Commodity("f", "A", "B")]
        result = engine(("A", "B"), (("A", "B"),), 10.0, commodities,
                        trace({"f": 5.0}, 1.0), 1.0).run(4.0, 0.5)
        sample = next(row for row in result["timeline"] if abs(row["time_s"]-0.5) < 1e-12)
        self.assertClose(sample["arrived_bits"], 2.5)
        self.assertClose(sample["queued_bits"], 0.0)
        self.assertClose(sample["in_flight_bits"], 2.5)
        self.assertClose(sample["delivered_bits"], 0.0)
        self.assertClose(sample["conservation_error_bits"], 0.0)

    def test_deterministic_equal_length_tie(self):
        router = DeterministicShortestPropagationDelayRouter()
        edges = (("A", "B"), ("B", "D"), ("A", "C"), ("C", "D"))
        first = router.path("A", "D", edges, constant_delay(1.0))
        second = router.path("A", "D", tuple(reversed(edges)), constant_delay(1.0))
        self.assertEqual(first, ("A", "B", "D"))
        self.assertEqual(first, second)

    def test_equal_share_redistributes_unused_capacity(self):
        allocation = equal_weight_fair_share(10.0, {"a": 1.0, "b": math.inf, "c": math.inf})
        self.assertClose(allocation["a"], 1.0)
        self.assertClose(allocation["b"], 4.5)
        self.assertClose(allocation["c"], 4.5)

    def test_trace_integral_and_hash_do_not_depend_on_observation_step(self):
        traffic = PiecewiseConstantTrafficTrace(("f",), [
            TrafficSegment(0.0, 0.3, {"f": 7.0}, "a"),
            TrafficSegment(0.3, 1.0, {"f": 2.0}, "b"),
        ])
        self.assertClose(traffic.cumulative_arrivals(1.0)["f"], 3.5)
        self.assertEqual(traffic.sha256(), PiecewiseConstantTrafficTrace.from_dict(
            traffic.to_dict()).sha256())
        commodities = [Commodity("f", "A", "B")]
        first = engine(("A", "B"), (("A", "B"),), 10.0, commodities,
                       traffic, 0.25).run(4.0, 0.5)
        second = engine(("A", "B"), (("A", "B"),), 10.0, commodities,
                        traffic, 0.25).run(4.0, 0.07)
        for key in ("arrived_bits", "delivered_bits", "objective_J_bit_s",
                    "mean_bit_delay_s", "max_queue_bits"):
            self.assertClose(first["metrics"][key], second["metrics"][key], 1e-10)

    def test_every_recorded_boundary_conserves_work(self):
        commodities = [Commodity("f", "A", "C")]
        result = engine(("A", "B", "C"), (("A", "B"), ("B", "C")),
                        6.0, commodities, trace({"f": 9.0}, 1.0), 0.13).run(5.0, 0.17)
        self.assertTrue(result["timeline"])
        self.assertLessEqual(max(abs(row["conservation_error_bits"])
                                 for row in result["timeline"]), 1e-8)
        self.assertEqual(result["metrics"]["negative_queue_count"], 0)


if __name__ == "__main__":
    unittest.main()
