"""Gate F1 correctness fixtures; no controller performance comparisons."""
from __future__ import annotations

import json
import unittest

from dynamic_lisl.baseline_controllers import (
    HysteresisMinimumHoldController,
    IgnoreSetupDynamicScaffold,
    SetupAwareGreedyScaffold,
    StaticHoldController,
)
from dynamic_lisl.candidate_proposer import (
    CandidateSpec, FrozenTerminalPairProposer, allocate_structural_quota,
)
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.controller_runner import MultiEpochControllerRunner
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_d2_fixtures import (
    ConstantDelay, _catalog, _engine, _trace, _window, _activate,
    fixture_a_bbm_forced_outage, fixture_h_clone_base,
)
from dynamic_lisl.outage_metrics import derive_separated_outage_metrics
from dynamic_lisl.terminal_executor import Connect, TerminalExecutor


GBIT = 1e9


def empty_physical(nodes):
    return TerminalPairPhysicalFeasibility(_catalog(nodes, ()))


def empty_candidates(_state, _context):
    return ()


def hold_score(_state, proposal_set, _context):
    return {"HOLD": 0.0, **{row["proposal_id"]: -1.0
                             for row in proposal_set["proposals"]}}


def records(mbb, bbm):
    rows = []
    for name, count in (("MBB_STRUCTURALLY_FEASIBLE", mbb),
                        ("BBM_REQUIRED", bbm)):
        for index in range(count):
            rows.append({
                "proposal_id": f"{name}-{index:02d}", "stratum": name,
                "usable_lifetime_s": 100.0-index, "plane_gap": index % 4,
                "old_edge": ["A", "B"],
                "old_terminal_ids": [["A", "D1"], ["B", "D1"]],
                "new_edge": ["C", f"N{index:02d}"],
                "new_terminal_ids": [["C", "D2"], [f"N{index:02d}", "D2"]],
            })
    return rows


def timing_engine(expiries=(7.3,)):
    nodes = tuple(chr(ord("A")+index) for index in range(8))
    fixed = tuple((nodes[index], nodes[index+1]) for index in range(len(nodes)-1))
    executor = TerminalExecutor(nodes)
    for index, expiry in enumerate(expiries):
        a, b = nodes[2*index], nodes[2*index+1]
        _activate(executor, (a, "D1"), (b, "D1"), expiry)
    commodities = (Commodity("f0", "A", "H"),)
    return _engine(nodes, fixed, commodities, {"f0": 0.0}, 9.0,
                   executor, (), ConstantDelay())


def bbm_candidate_environment(retarget=2.0, window_end=30.0):
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    executor = TerminalExecutor(nodes)
    old = (("B", "D1"), ("C", "D1"))
    _activate(executor, *old, end_s=30.0)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1", window_end)]))
    spec = CandidateSpec("BBM-1", {
        "a": ("B", "D1"), "b": ("D", "D1"),
        "retarget_a": retarget, "retarget_b": retarget,
        "acquisition": 0.0,
    }, old)
    return nodes, fixed, executor, physical, spec


def switching_runner(controller, decision_end=0.0):
    engine = fixture_h_clone_base()
    nodes = engine.nodes
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1", 30.0)]))
    spec = CandidateSpec("SWITCH", {
        "a": ("B", "D1"), "b": ("D", "D1"),
        "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0,
    }, (("B", "D1"), ("C", "D1")))
    source = lambda state, context: (spec,)
    return MultiEpochControllerRunner(
        engine, physical, engine.fixed_edges, "Z_SPARSE_REFERENCE",
        source, controller, decision_end_s=decision_end)


def expiry_after_switch_engine(mbb):
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    commodity = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    old = (("B", "D1"), ("C", "D1"))
    _activate(executor, *old, end_s=30.0)
    if mbb:
        window = _window("A", "D2", "D", "D2", 4.0)
        proposal = {"a": ("A", "D2"), "b": ("D", "D2"),
                    "retarget_a": 1.0, "retarget_b": 1.0,
                    "acquisition": 1.0, "release_after": (old,)}
        policy = "Z_MODERATE"
        spec = CandidateSpec("MBB-EXPIRY", proposal, old)
    else:
        window = _window("B", "D1", "D", "D1", 5.0)
        proposal = {"a": ("B", "D1"), "b": ("D", "D1"),
                    "retarget_a": 2.0, "retarget_b": 2.0,
                    "acquisition": 0.0}
        policy = "Z_SPARSE_REFERENCE"
        spec = CandidateSpec("BBM-EXPIRY", proposal, old)
    physical = TerminalPairPhysicalFeasibility(_catalog(nodes, [window]))
    engine = _engine(nodes, fixed, commodity, {"f0": 1*GBIT}, 6.0,
                     executor, (), ConstantDelay(), capacity=2*GBIT)
    controller = IgnoreSetupDynamicScaffold(
        lambda state, proposal_set, context: {
            "HOLD": 0.0,
            **{row["proposal_id"]: 1.0 for row in proposal_set["proposals"]}},
        test_only=True)
    runner = MultiEpochControllerRunner(
        engine, physical, fixed, policy, lambda state, context: (spec,),
        controller, decision_end_s=0.0)
    return runner


class GateF1ControllerInfrastructureTests(unittest.TestCase):
    def test_periodic_callbacks_and_between_epoch_expiry(self):
        engine = timing_engine((7.3,))
        runner = MultiEpochControllerRunner(
            engine, empty_physical(engine.nodes), engine.fixed_edges,
            "Z_MODERATE", empty_candidates, StaticHoldController(),
            decision_end_s=8.0)
        result = runner.run(12.0)
        self.assertEqual(result["decision_callback_times_s"], [0, 2, 4, 6, 8])
        expiry = [row for row in result["engine_result"]["terminal_event_sequence"]
                  if row["event"] == "LINK_DOWN"
                  and row["details"].get("reason") == "LINK_EXPIRE"]
        self.assertEqual([row["time"] for row in expiry], [7.3])
        self.assertNotIn(7.3, result["decision_callback_times_s"])

    def test_events_exactly_before_and_after_epoch_do_not_add_callbacks(self):
        engine = timing_engine((1.999, 2.0, 2.001))
        runner = MultiEpochControllerRunner(
            engine, empty_physical(engine.nodes), engine.fixed_edges,
            "Z_MODERATE", empty_candidates, StaticHoldController(),
            decision_end_s=4.0)
        result = runner.run(12.0)
        self.assertEqual(result["decision_callback_times_s"], [0, 2, 4])
        expiry = [row["time"] for row in result["engine_result"]["terminal_event_sequence"]
                  if row["event"] == "LINK_DOWN"]
        self.assertEqual(expiry, [1.999, 2.0, 2.001])

    def test_quota_exact_eight_eight(self):
        selected = allocate_structural_quota(records(12, 12))
        self.assertEqual(len(selected), 16)
        self.assertEqual(sum(row["stratum"].startswith("MBB") for row in selected), 8)
        self.assertEqual(sum(row["stratum"] == "BBM_REQUIRED" for row in selected), 8)

    def test_quota_spillover(self):
        selected = allocate_structural_quota(records(3, 20))
        self.assertEqual(len(selected), 16)
        self.assertEqual(sum(row["stratum"].startswith("MBB") for row in selected), 3)
        self.assertEqual(sum(row["stratum"] == "BBM_REQUIRED" for row in selected), 13)

    def test_proposal_order_is_deterministic(self):
        original = records(9, 9)
        reversed_rows = list(reversed(original))
        self.assertEqual(allocate_structural_quota(original),
                         allocate_structural_quota(reversed_rows))

    def test_hard_pruning_exact_noop_and_physical_illegal(self):
        nodes, fixed, executor, physical, valid = bbm_candidate_environment()
        noop = CandidateSpec("NOOP", {
            "a": ("B", "D1"), "b": ("C", "D1"),
            "retarget_a": 0.0, "retarget_b": 0.0, "acquisition": 0.0},
            (("B", "D1"), ("C", "D1")))
        illegal = CandidateSpec("ILLEGAL", {
            "a": ("A", "D2"), "b": ("D", "D2"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0})
        result = FrozenTerminalPairProposer().propose(
            executor, (noop, illegal, valid), physical, fixed,
            "Z_SPARSE_REFERENCE")
        self.assertEqual([row["proposal_id"] for row in result["proposals"]],
                         ["BBM-1"])
        reasons = {row["proposal_id"]: row["reason"] for row in result["pruned"]}
        self.assertEqual(reasons["NOOP"], "EXACT_PHYSICAL_NOOP")
        self.assertIn(reasons["ILLEGAL"], {"NOT_VISIBLE", "FOR_FAIL_BILATERAL"})

    def test_sparse_outage_boundary_accepts_equality_and_rejects_longer(self):
        _, fixed, executor, physical, exact = bbm_candidate_environment(2.0)
        accepted = FrozenTerminalPairProposer().propose(
            executor, (exact,), physical, fixed, "Z_SPARSE_REFERENCE")
        self.assertEqual(len(accepted["proposals"]), 1)
        _, fixed2, executor2, physical2, long = bbm_candidate_environment(2.001)
        rejected = FrozenTerminalPairProposer().propose(
            executor2, (long,), physical2, fixed2, "Z_SPARSE_REFERENCE")
        self.assertEqual(rejected["proposals"], [])
        self.assertEqual(rejected["pruned"][0]["reason"], "OUTAGE_BOUND_EXCEEDED")

    def test_moderate_strict_connected_rejects_bridge_bbm(self):
        _, fixed, executor, physical, spec = bbm_candidate_environment(1.0)
        result = FrozenTerminalPairProposer().propose(
            executor, (spec,), physical, fixed, "Z_MODERATE")
        self.assertEqual(result["proposals"], [])
        self.assertEqual(result["pruned"][0]["reason"],
                         "STRICT_CONNECTIVITY_VIOLATION")

    def test_b0_all_hold_and_natural_events_continue(self):
        engine = timing_engine((3.1,))
        result = MultiEpochControllerRunner(
            engine, empty_physical(engine.nodes), engine.fixed_edges,
            "Z_MODERATE", empty_candidates, StaticHoldController(),
            decision_end_s=6.0).run(12.0)
        self.assertTrue(all(row["selected_action"]["kind"] == "HOLD"
                            for row in result["controller_actions"]))
        self.assertEqual(result["engine_result"]["metrics"]["switch_count"], 0)
        self.assertTrue(result["candidate_budget_not_used_by_design"])
        self.assertTrue(any(row["details"].get("reason") == "LINK_EXPIRE"
                            for row in result["engine_result"]["terminal_event_sequence"]
                            if row["event"] == "LINK_DOWN"))

    def test_b1_zero_setup_decision_executes_real_setup(self):
        controller = IgnoreSetupDynamicScaffold(
            lambda state, proposal_set, context: {"HOLD": 0.0, "SWITCH": 1.0},
            test_only=True)
        result = switching_runner(controller).run(20.0)
        action = result["controller_actions"][0]
        self.assertEqual(dict(action["selected_action"]["decision_metadata"])
                         ["decision_assumed_setup_s"], 0.0)
        self.assertEqual(action["resulting_gate_b_transition_type"], "BBM")
        up = next(row["time"] for row in result["engine_result"]["terminal_event_sequence"]
                  if row["event"] == "LINK_UP")
        self.assertEqual(up, 1.0)

    def test_b2_minimum_hold_and_threshold_boundary(self):
        base = IgnoreSetupDynamicScaffold(
            lambda state, proposal_set, context: {"HOLD": 0.0, "P": 1.0},
            test_only=True)
        controller = HysteresisMinimumHoldController(base, 4.0, 1.0)
        proposal_set = {"proposals": [{"proposal_id": "P"}]}
        first = controller.observe({"time_s": 0.0}, proposal_set, {})
        self.assertEqual(first.kind, "REPLACE")
        controller.on_action_result({"decision_epoch_s": 0.0, "accepted": True,
                                     "selected_action": first.to_dict()})
        self.assertEqual(controller.observe({"time_s": 2.0}, proposal_set, {}).kind,
                         "HOLD")
        # Equality at both the hold duration and threshold is accepted.
        self.assertEqual(controller.observe({"time_s": 4.0}, proposal_set, {}).kind,
                         "REPLACE")

    def test_b3_current_state_only_firewall(self):
        seen = {}
        def score(state, proposal_set, context):
            seen.update(state)
            return {"HOLD": 0.0, **{row["proposal_id"]: -1.0
                                     for row in proposal_set["proposals"]}}
        controller = SetupAwareGreedyScaffold(score, test_only=True)
        engine = timing_engine(())
        MultiEpochControllerRunner(
            engine, empty_physical(engine.nodes), engine.fixed_edges,
            "Z_MODERATE", empty_candidates, controller,
            decision_end_s=0.0).run(12.0)
        self.assertFalse({"future_trace", "future_trace_sha256", "future_action_ids",
                          "realized_future_traffic", "final_J", "forecast"} & set(seen))
        with self.assertRaises(AssertionError):
            controller.observe({"time_s": 0.0, "future_trace": {}},
                               {"proposals": []}, {})

    def test_scientific_b1_b3_construction_is_blocked_without_freeze(self):
        with self.assertRaisesRegex(RuntimeError, "SCORING_CONTRACT_UNRESOLVED"):
            IgnoreSetupDynamicScaffold(hold_score)
        with self.assertRaisesRegex(RuntimeError, "SCORING_CONTRACT_UNRESOLVED"):
            SetupAwareGreedyScaffold(hold_score)

    def test_transition_and_expiry_metrics_case_a(self):
        result = fixture_a_bbm_forced_outage().run(30.0)
        metrics = derive_separated_outage_metrics(result)
        self.assertAlmostEqual(metrics["transition_period_outage_s"], 2.0)
        self.assertEqual(metrics["post_expiry_no_route_s"], 0.0)

    def test_transition_and_expiry_metrics_case_b(self):
        result = expiry_after_switch_engine(True).run(12.0)
        metrics = result["separated_outage_metrics"]
        self.assertEqual(metrics["transition_period_outage_s"], 0.0)
        self.assertGreater(metrics["post_expiry_no_route_s"], 0.0)

    def test_transition_and_expiry_metrics_case_c(self):
        result = expiry_after_switch_engine(False).run(12.0)
        metrics = result["separated_outage_metrics"]
        self.assertAlmostEqual(metrics["transition_period_outage_s"], 2.0)
        self.assertGreater(metrics["post_expiry_no_route_s"], 0.0)

    def test_canonical_replay_and_multi_epoch_invariants(self):
        def execute():
            engine = timing_engine((7.3,))
            return MultiEpochControllerRunner(
                engine, empty_physical(engine.nodes), engine.fixed_edges,
                "Z_MODERATE", empty_candidates, StaticHoldController(),
                decision_end_s=8.0).run(12.0)
        first, second = execute(), execute()
        self.assertEqual(first["action_replay_sha256"], second["action_replay_sha256"])
        self.assertEqual(json.dumps(first["controller_actions"], sort_keys=True),
                         json.dumps(second["controller_actions"], sort_keys=True))
        metrics = first["engine_result"]["metrics"]
        self.assertLessEqual(metrics["max_abs_conservation_error_bits"], 1.0)
        self.assertEqual(metrics["negative_queue_count"], 0)
        self.assertLessEqual(metrics["max_capacity_violation_bit_s"], 0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
