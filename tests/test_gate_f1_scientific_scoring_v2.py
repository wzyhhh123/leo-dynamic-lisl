"""Gate F1 scientific V_v2 and B0-B3 correctness acceptance tests."""
from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from dynamic_lisl.baseline_controllers import (
    HysteresisMinimumHoldController, StaticHoldController,
)
from dynamic_lisl.candidate_proposer import CandidateSpec
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.controller_runner import MultiEpochControllerRunner
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_d2_fixtures import (
    ConstantDelay, _catalog, _window, fixture_h_clone_base,
)
from dynamic_lisl.scientific_controllers import (
    IgnoreSetupDynamicController, SetupAwareGreedyController,
)
from dynamic_lisl.scientific_snapshot import ScientificSnapshotEvaluator
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine


def make_engine(nodes, edges, commodities, *, rates=None, capacity=10.0,
                delay=None, segments=None):
    ids = tuple(row.commodity_id for row in commodities)
    if segments is None:
        rates = rates or {key: 0.0 for key in ids}
        segments = (TrafficSegment(0.0, 5.0, rates, "fixture"),)
    trace = PiecewiseConstantTrafficTrace(ids, segments)
    engine = TransitionAwareNetworkServiceEngine(
        nodes, edges, capacity, commodities, trace,
        delay or ConstantDelay(1.0), TerminalExecutor(nodes), (),
        conservation_abs_tolerance_bits=1e-8,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=0.01)
    engine.settle_current_time()
    return engine


def proposal(proposal_id, new_edge, *, old_edge=(), remaining=10.0,
             usable=10.0):
    return {
        "proposal_id": proposal_id,
        "old_edge": list(old_edge),
        "new_edge": list(new_edge),
        "remaining_lifetime_s": remaining,
        "usable_lifetime_s": usable,
    }


def proposal_set(*rows):
    return {"proposals": list(rows)}


def visible(engine, **extra):
    return {"time_s": engine.now, **extra}


def beneficial_environment():
    nodes = ("A", "B", "C", "X", "Y")
    edges = (("A", "B"), ("B", "C"), ("X", "C"), ("Y", "C"))
    overrides = {}
    for edge, value in {
        ("A", "B"): 1.0, ("B", "C"): 1.0,
        ("A", "X"): 0.5, ("X", "C"): 0.5,
        ("A", "Y"): 0.5, ("Y", "C"): 0.5,
    }.items():
        overrides[edge] = overrides[edge[::-1]] = value
    engine = make_engine(nodes, edges, (Commodity("f", "A", "C"),),
                         delay=ConstantDelay(1.0, overrides))
    engine.queues.set("A", "f", 10.0)
    return engine


def scientific_switching_runner(controller_factory, decision_end=2.0):
    engine = fixture_h_clone_base().advance_to(2.0)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        engine.nodes, [_window("B", "D1", "D", "D1", 30.0)]))
    spec = CandidateSpec("SWITCH", {
        "a": ("B", "D1"), "b": ("D", "D1"),
        "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0,
    }, (("B", "D1"), ("C", "D1")))
    controller = controller_factory(engine)
    runner = MultiEpochControllerRunner(
        engine, physical, engine.fixed_edges, "Z_SPARSE_REFERENCE",
        lambda _state, _context: (spec,), controller,
        t0_s=2.0, decision_end_s=decision_end)
    return runner


class GateF1ScientificScoringV2Tests(unittest.TestCase):
    def test_a_zero_total_unfinished_work_holds(self):
        engine = make_engine(("A", "B"), (("A", "B"),),
                             (Commodity("f", "A", "B"),))
        action = IgnoreSetupDynamicController(engine).observe(
            visible(engine), proposal_set(proposal("P", ("A", "B"))), {})
        self.assertEqual(action.kind, "HOLD")
        self.assertEqual(dict(action.decision_metadata)["reason"],
                         "ZERO_TOTAL_UNFINISHED_WORK")

    def test_b_hold_v2_computation(self):
        engine = beneficial_environment()
        result = ScientificSnapshotEvaluator(engine).evaluate_hold()
        self.assertTrue(result.finite)
        self.assertAlmostEqual(result.value_bit_s, 25.0)

    def test_c_candidate_v2_computation(self):
        engine = beneficial_environment()
        result = ScientificSnapshotEvaluator(engine).evaluate_candidate(
            proposal("P", ("A", "X")))
        self.assertAlmostEqual(result.value_bit_s, 15.0)

    def test_d_no_source_route_is_infinite(self):
        engine = make_engine(("A", "C"), (), (Commodity("f", "A", "C"),))
        engine.queues.set("A", "f", 1.0)
        result = ScientificSnapshotEvaluator(engine).evaluate_hold()
        self.assertTrue(math.isinf(result.value_bit_s))
        self.assertEqual(result.commodities[0].invalid_reason,
                         "NO_SOURCE_TO_DESTINATION_ROUTE")

    def test_e_positive_local_demand_without_next_hop_is_infinite(self):
        engine = make_engine(("A", "B", "C", "X"),
                             (("A", "B"), ("B", "C")),
                             (Commodity("f", "A", "C"),))
        engine.queues.set("A", "f", 1.0)
        engine.queues.set("X", "f", 1.0)
        result = ScientificSnapshotEvaluator(engine).evaluate_hold()
        self.assertTrue(math.isinf(result.value_bit_s))
        self.assertEqual(result.commodities[0].invalid_reason,
                         "POSITIVE_LOCAL_DEMAND_WITHOUT_LEGAL_ADMITTED_NEXT_HOP")

    def test_f_nonpositive_mu_is_infinite(self):
        engine = beneficial_environment()
        with patch("dynamic_lisl.scientific_snapshot.equal_weight_fair_share",
                   return_value={"f": 0.0}):
            result = ScientificSnapshotEvaluator(engine).evaluate_hold()
        self.assertTrue(math.isinf(result.value_bit_s))
        self.assertEqual(result.commodities[0].invalid_reason,
                         "NONPOSITIVE_ALLOCATION_FOR_POSITIVE_LOCAL_DEMAND")

    def test_g_pure_propagation_has_zero_psi_and_finite_value(self):
        segments = (TrafficSegment(0.0, 0.5, {"f": 1.0}, "on"),
                    TrafficSegment(0.5, 2.0, {"f": 0.0}, "off"))
        engine = make_engine(("A", "B", "C"), (("A", "B"), ("B", "C")),
                             (Commodity("f", "A", "C"),), segments=segments)
        engine.advance_to(0.75)
        row = ScientificSnapshotEvaluator(engine).evaluate_hold().commodities[0]
        self.assertEqual(row.current_demand_nodes, ())
        self.assertIsNone(row.R_f_snap_bit_s)
        self.assertEqual(row.Psi_f_bit_s, 0.0)
        self.assertTrue(math.isfinite(row.value_bit_s))

    def test_h_downstream_arrival_has_defined_snapshot_rate(self):
        segments = (TrafficSegment(0.0, 0.5, {"f": 1.0}, "on"),
                    TrafficSegment(0.5, 2.0, {"f": 0.0}, "off"))
        engine = make_engine(("A", "B", "C"), (("A", "B"), ("B", "C")),
                             (Commodity("f", "A", "C"),), segments=segments)
        engine.advance_to(1.25)
        row = ScientificSnapshotEvaluator(engine).evaluate_hold().commodities[0]
        self.assertEqual(row.current_demand_nodes, ("B",))
        self.assertEqual(row.R_f_snap_bit_s, 1.0)

    def test_i_multiple_commodities_use_existing_equal_share(self):
        commodities = (Commodity("f1", "S1", "D"),
                       Commodity("f2", "S2", "D"))
        engine = make_engine(("S1", "S2", "X", "D"),
                             (("S1", "X"), ("S2", "X"), ("X", "D")),
                             commodities)
        engine.queues.set("X", "f1", 1.0)
        engine.queues.set("X", "f2", 1.0)
        rows = {row.commodity_id: row for row in
                ScientificSnapshotEvaluator(engine).evaluate_hold().commodities}
        self.assertEqual(rows["f1"].R_f_snap_bit_s, 5.0)
        self.assertEqual(rows["f2"].R_f_snap_bit_s, 5.0)

    def test_j_finite_demand_share_is_redistributed(self):
        commodities = (Commodity("f1", "S1", "D"),
                       Commodity("f2", "S2", "D"))
        engine = make_engine(("S1", "S2", "X", "D"),
                             (("S1", "X"), ("S2", "X"), ("X", "D")),
                             commodities)
        engine.in_flight.add_bits(("S1", "X"), "f1", 1.0)
        engine.in_flight.arrival_rates[(("S1", "X"), "f1")] = 1.0
        engine.queues.set("X", "f2", 1.0)
        rows = {row.commodity_id: row for row in
                ScientificSnapshotEvaluator(engine).evaluate_hold().commodities}
        self.assertEqual(rows["f1"].R_f_snap_bit_s, 1.0)
        self.assertEqual(rows["f2"].R_f_snap_bit_s, 9.0)

    def test_k_b1_ideal_scoring_executes_real_setup(self):
        result = scientific_switching_runner(IgnoreSetupDynamicController).run(20.0)
        action = result["controller_actions"][0]
        self.assertEqual(action["selected_action"]["kind"], "REPLACE")
        self.assertEqual(dict(action["selected_action"]["decision_metadata"])
                         ["decision_assumed_setup_s"], 0.0)
        self.assertEqual(action["resulting_gate_b_transition_type"], "BBM")
        up = next(row["time"] for row in result["engine_result"]
                  ["terminal_event_sequence"] if row["event"] == "LINK_UP")
        self.assertEqual(up, 3.0)

    def test_l_b1_hold_wins_exact_tie(self):
        engine = make_engine(("A", "B", "X", "Y"), (("A", "B"),),
                             (Commodity("f", "A", "B"),))
        engine.queues.set("A", "f", 1.0)
        action = IgnoreSetupDynamicController(engine).observe(
            visible(engine), proposal_set(proposal("P", ("X", "Y"))), {})
        self.assertEqual(action.kind, "HOLD")

    def test_m_b1_candidate_tie_uses_proposer_order(self):
        engine = beneficial_environment()
        rows = proposal_set(proposal("CANON_FIRST", ("A", "X")),
                            proposal("SECOND", ("A", "Y")))
        action = IgnoreSetupDynamicController(engine).observe(
            visible(engine), rows, {})
        self.assertEqual(action.proposal_id, "CANON_FIRST")

    def test_n_b2_minimum_hold(self):
        class Base:
            controller_id = "TEST_BASE"
            def observe(self, state, proposals, context):
                from dynamic_lisl.baseline_controllers import ControllerAction
                return ControllerAction("REPLACE", "P", (("improvement", 1.0),))
            def on_action_result(self, record):
                return None
        controller = HysteresisMinimumHoldController(Base(), 4.0, 0.0)
        first = controller.observe({"time_s": 0.0}, proposal_set(proposal("P", ("A", "B"))), {})
        controller.on_action_result({"decision_epoch_s": 0.0, "accepted": True,
                                     "selected_action": first.to_dict()})
        self.assertEqual(controller.observe(
            {"time_s": 2.0}, proposal_set(proposal("P", ("A", "B"))), {}).kind,
            "HOLD")

    def test_o_b2_threshold_equality_is_accepted(self):
        class Base:
            controller_id = "TEST_BASE"
            def observe(self, state, proposals, context):
                from dynamic_lisl.baseline_controllers import ControllerAction
                return ControllerAction("REPLACE", "P", (("improvement", 1.0),))
            def on_action_result(self, record):
                return None
        controller = HysteresisMinimumHoldController(Base(), 0.0, 1.0)
        action = controller.observe({"time_s": 0.0},
                                    proposal_set(proposal("P", ("A", "B"))), {})
        self.assertEqual(action.kind, "REPLACE")

    def test_p_b3_rejects_nonpositive_delta(self):
        engine = make_engine(("A", "B", "X", "Y"), (("A", "B"),),
                             (Commodity("f", "A", "B"),))
        engine.queues.set("A", "f", 1.0)
        action = SetupAwareGreedyController(engine).observe(
            visible(engine), proposal_set(proposal("P", ("X", "Y"))), {})
        self.assertEqual(action.kind, "HOLD")

    def test_q_b3_rejects_nonpositive_lifetime(self):
        engine = beneficial_environment()
        row = proposal("P", ("A", "X"), remaining=0.0, usable=0.0)
        action = SetupAwareGreedyController(engine).observe(
            visible(engine), proposal_set(row), {})
        self.assertEqual(action.kind, "HOLD")

    def test_r_b3_selects_maximum_positive_S(self):
        engine = beneficial_environment()
        rows = proposal_set(
            proposal("LOW_ETA", ("A", "X"), remaining=10.0, usable=5.0),
            proposal("HIGH_ETA", ("A", "Y"), remaining=10.0, usable=9.0))
        action = SetupAwareGreedyController(engine).observe(
            visible(engine), rows, {})
        self.assertEqual(action.proposal_id, "HIGH_ETA")

    def test_s_b3_holds_without_positive_score(self):
        engine = make_engine(("A", "B", "X", "Y"), (("A", "B"),),
                             (Commodity("f", "A", "B"),))
        engine.queues.set("A", "f", 1.0)
        action = SetupAwareGreedyController(engine).observe(
            visible(engine), proposal_set(proposal("P", ("X", "Y"))), {})
        self.assertEqual(dict(action.decision_metadata)["reason"],
                         "NO_POSITIVE_SETUP_AWARE_SCORE")

    def test_t_b3_information_firewall(self):
        engine = beneficial_environment()
        with self.assertRaisesRegex(AssertionError, "FIREWALL"):
            SetupAwareGreedyController(engine).observe(
                visible(engine, future_trace={}), proposal_set(), {})

    def test_u_b1_b2_b3_share_v2_evaluator(self):
        engine = beneficial_environment()
        b1 = IgnoreSetupDynamicController(engine)
        b2 = HysteresisMinimumHoldController(b1, 0.0, 0.0)
        b3 = SetupAwareGreedyController(engine)
        self.assertIs(type(b1.evaluator), ScientificSnapshotEvaluator)
        self.assertIs(type(b3.evaluator), ScientificSnapshotEvaluator)
        self.assertIs(b2.base, b1)
        self.assertEqual(b1.evaluator.evaluate_hold(),
                         b3.evaluator.evaluate_hold())

    def test_v_deterministic_repeated_action_trace(self):
        first = scientific_switching_runner(IgnoreSetupDynamicController).run(20.0)
        second = scientific_switching_runner(IgnoreSetupDynamicController).run(20.0)
        self.assertEqual(first["action_replay_sha256"],
                         second["action_replay_sha256"])

    def test_w_conservation(self):
        result = scientific_switching_runner(IgnoreSetupDynamicController).run(20.0)
        self.assertLessEqual(result["engine_result"]["metrics"]
                             ["max_abs_conservation_error_bits"], 1.0)

    def test_x_no_negative_queues(self):
        result = scientific_switching_runner(IgnoreSetupDynamicController).run(20.0)
        self.assertEqual(result["engine_result"]["metrics"]["negative_queue_count"], 0)

    def test_y_no_capacity_violation(self):
        result = scientific_switching_runner(IgnoreSetupDynamicController).run(20.0)
        self.assertLessEqual(result["engine_result"]["metrics"]
                             ["max_capacity_violation_bit_s"], 0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
