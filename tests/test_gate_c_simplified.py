"""Acceptance tests for the simplified parametric Gate C terminal model."""
import json
import math
import unittest

import numpy as np

from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_c_terminal_geometry import (
    TerminalGeometryConfig, bilateral_for, conic_for_pass, rtn_basis, validate_rtn,
)
from dynamic_lisl.terminal_executor import Connect, TerminalExecutor
from dynamic_lisl.terminal_pair_intervals import (
    TerminalPairCatalog, TerminalPairWindow, positive_intervals,
)
from dynamic_lisl.transition_profiler import profile_transition


TRACE_RECORDS = []


def geometry_config(half_angle=2.0):
    return TerminalGeometryConfig.from_dict({
        "terminal_mounting_rtn": {"D1": [0, 0, 1], "D2": [0, 0, -1]},
        "for_half_angle_deg": {"D1": half_angle, "D2": half_angle},
        "numerical_epsilon_deg": 1e-10,
    })


def states_vertical_pair():
    return (
        np.array([7000.0, 0.0, 0.0]), np.array([0.0, 7.5, 0.0]),
        np.array([7000.0, 0.0, 100.0]), np.array([0.0, 7.5, 0.0]),
    )


def terminal_catalog(records, nodes):
    return TerminalPairCatalog.from_records(records, {node: i for i, node in enumerate(nodes)})


def record(a, da, b, db, start=0.0, end=20.0):
    return dict(sat_a=a, terminal_a=da, sat_b=b, terminal_b=db,
                start_s=start, end_s=end, parent_start_s=start, parent_end_s=end,
                plane_gap=1, distance_km=1000.0)


def activate(executor, a, b, end=20.0):
    executor.submit([Connect(a, b, end, 0.0, 0.0, 0.0)])


class GateCSimplifiedTests(unittest.TestCase):
    def tearDown(self):
        if hasattr(self, "trace"):
            TRACE_RECORDS.append({"test": self.id(), "profile": self.trace})

    def test_rtn_unit_orthogonal_right_handed_and_deterministic(self):
        r = np.array([[7000.0, 0.0, 0.0], [0.0, -7000.0, 100.0]])
        v = np.array([[0.0, 7.5, 0.1], [7.4, 0.0, 0.0]])
        first = rtn_basis(r, v)
        second = rtn_basis(r, v)
        for a, b in zip(first, second):
            self.assertTrue(np.array_equal(a, b))
            self.assertTrue(np.allclose(np.linalg.norm(a, axis=1), 1.0, atol=1e-12))
        self.assertTrue(validate_rtn(r, v)["passed"])

    def test_satellite_visible_but_all_terminal_pairs_for_fail(self):
        pa = np.array([7000.0, 0.0, 0.0]); va = np.array([0.0, 7.5, 0.0])
        pb = np.array([7000.0, 100.0, 0.0]); vb = np.array([0.0, 7.5, 0.0])
        config = geometry_config(10.0)
        results = [bilateral_for(pa, va, da, pb, vb, db, config)
                   for da in ("D1", "D2") for db in ("D1", "D2")]
        self.assertTrue(all(not item["feasible"] for item in results))

    def test_only_d1_d2_feasible_and_d1_d2_are_distinct(self):
        pa, va, pb, vb = states_vertical_pair()
        config = geometry_config(2.0)
        matrix = {(da, db): bilateral_for(pa, va, da, pb, vb, db, config)["feasible"]
                  for da in ("D1", "D2") for db in ("D1", "D2")}
        self.assertEqual(matrix, {
            ("D1", "D1"): False, ("D1", "D2"): True,
            ("D2", "D1"): False, ("D2", "D2"): False,
        })

    def test_local_pass_remote_fail_reason(self):
        pa, va, pb, vb = states_vertical_pair()
        result = bilateral_for(pa, va, "D1", pb, vb, "D1", geometry_config(2.0))
        self.assertFalse(result["feasible"])
        self.assertEqual(result["reason"], "FOR_FAIL_REMOTE")

    def test_target_exactly_on_for_boundary_is_accepted(self):
        angle = math.radians(30.0)
        target = np.array([math.sin(angle), 0.0, math.cos(angle)])
        passed, measured = conic_for_pass(np.array([0.0, 0.0, 1.0]), target, 30.0)
        self.assertTrue(bool(passed))
        self.assertAlmostEqual(float(measured), 30.0, places=10)

    def test_target_crossing_for_boundary_truncates_interval(self):
        def margin(time_s):
            angle = math.radians(20.0 + 2.0*time_s)
            target = np.array([math.sin(angle), 0.0, math.cos(angle)])
            _, measured = conic_for_pass(np.array([0.0, 0.0, 1.0]), target, 30.0)
            return 30.0-float(measured)
        intervals = positive_intervals(margin, 0.0, 10.0, scan_step_s=2.0)
        self.assertEqual(len(intervals), 1)
        self.assertAlmostEqual(intervals[0][0], 0.0)
        self.assertAlmostEqual(intervals[0][1], 5.0, places=3)

    def test_terminal_pair_interval_shorter_than_satellite_parent(self):
        window = TerminalPairWindow("A", "D1", "B", "D2", 2.0, 8.0,
                                    parent_start_s=0.0, parent_end_s=10.0)
        self.assertLess(window.end_s-window.start_s, window.parent_end_s-window.parent_start_s)

    def test_lifetime_accept_and_explicit_remaining_usable(self):
        executor = TerminalExecutor(("A", "B"))
        catalog = terminal_catalog([record("A", "D1", "B", "D2", end=4.0)], ("A", "B"))
        result = TerminalPairPhysicalFeasibility(catalog).evaluate(
            executor, ("A", "D1"), ("B", "D2"), 1.0, 1.0, 1.0
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["geometry"]["ready_time"], 2.0)
        self.assertEqual(result["geometry"]["remaining_lifetime_s"], 4.0)
        self.assertEqual(result["geometry"]["usable_lifetime_s"], 2.0)

    def test_ready_equal_and_after_end_rejected(self):
        for acquisition in (2.0, 3.0):
            executor = TerminalExecutor(("A", "B"))
            catalog = terminal_catalog([record("A", "D1", "B", "D2", end=3.0)], ("A", "B"))
            result = TerminalPairPhysicalFeasibility(catalog).evaluate(
                executor, ("A", "D1"), ("B", "D2"), 1.0, 1.0, acquisition
            )
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason"], "INSUFFICIENT_LIFETIME")

    def test_occupied_terminal_uses_bbm(self):
        executor = TerminalExecutor(("A", "B", "C", "D"))
        activate(executor, ("B", "D1"), ("C", "D1"))
        catalog = terminal_catalog([record("B", "D1", "D", "D1")], executor.satellite_ids)
        result = TerminalPairPhysicalFeasibility(catalog).evaluate(
            executor, ("B", "D1"), ("D", "D1"), 2.0, 2.0, 0.0
        )
        self.assertTrue(result["accepted"])
        profile = profile_transition(executor, [result["command"]], (("A", "B"), ("C", "D")), 3.0)
        self.trace = {key: value for key, value in profile.items() if key != "final_executor"}
        self.assertTrue(any(item["event"] == "LINK_DOWN" for item in profile["transition_log"]))

    def test_genuine_idle_second_terminal_for_feasible_allows_mbb(self):
        executor = TerminalExecutor(("A", "B", "C", "D"))
        activate(executor, ("B", "D1"), ("C", "D1"))
        catalog = terminal_catalog([record("A", "D2", "D", "D2")], executor.satellite_ids)
        result = TerminalPairPhysicalFeasibility(catalog).evaluate(
            executor, ("A", "D2"), ("D", "D2"), 1.0, 1.0, 0.0,
            release_after=((("B", "D1"), ("C", "D1")),),
        )
        self.assertTrue(result["accepted"])
        profile = profile_transition(executor, [result["command"]], (("A", "B"), ("C", "D")), 2.0)
        self.assertFalse(profile["partition_occurs"])

    def test_idle_second_terminal_for_infeasible_rejects_fake_mbb(self):
        executor = TerminalExecutor(("A", "B", "C", "D"))
        activate(executor, ("B", "D1"), ("C", "D1"))
        catalog = terminal_catalog([], executor.satellite_ids)
        result = TerminalPairPhysicalFeasibility(catalog).evaluate(
            executor, ("A", "D2"), ("D", "D2"), release_after=((("B", "D1"), ("C", "D1")),)
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "FOR_FAIL_BILATERAL")

    def test_repeated_terminal_geometry_replay_is_exact(self):
        pa, va, pb, vb = states_vertical_pair()
        config = geometry_config(2.0)
        first = bilateral_for(pa, va, "D1", pb, vb, "D2", config)
        second = bilateral_for(pa, va, "D1", pb, vb, "D2", config)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
