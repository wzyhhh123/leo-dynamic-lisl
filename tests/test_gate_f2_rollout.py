"""Gate F2 B4 rollout/MPC correctness and mechanism-separation tests."""
from __future__ import annotations

import copy
import json
import math
import unittest

from dynamic_lisl.candidate_proposer import (
    CandidateSpec, FrozenTerminalPairProposer, canonical_sha256,
)
from dynamic_lisl.commodity import Commodity
from dynamic_lisl.controller_runner import (
    MultiEpochControllerRunner, controller_visible_state,
)
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_d2_fixtures import (
    ConstantDelay, GBIT, _activate, _catalog, _engine, _window,
)
from dynamic_lisl.load_aware_router import DeterministicLoadAwareRouter
from dynamic_lisl.rollout_controller import RootActionRolloutMPCController
from dynamic_lisl.scientific_controllers import IgnoreSetupDynamicController
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine


def public(proposed):
    return {key: value for key, value in proposed.items()
            if key != "candidate_specs"}


def empty_set(now=0.0, regime="Z_SPARSE_REFERENCE"):
    body = {
        "schema": "gate_f1_proposal_set_v1", "time_s": now,
        "regime": regime, "candidate_top_k": 16,
        "quota": {"MBB_STRUCTURALLY_FEASIBLE": 8, "BBM_REQUIRED": 8},
        "proposals": [],
    }
    return {**body, "proposal_set_sha256": canonical_sha256(body), "pruned": []}


def bbm_environment(*, rate=8*GBIT, setup=2.0, window_end=30.0,
                    decision_time=0.0, trace=None):
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    executor = TerminalExecutor(nodes)
    old = (("B", "D1"), ("C", "D1"))
    _activate(executor, *old, end_s=30.0)
    if trace is None:
        engine = _engine(
            nodes, fixed, (Commodity("f", "A", "D"),), {"f": rate}, 30.0,
            executor, (), ConstantDelay(0.1), capacity=10*GBIT)
    else:
        engine = TransitionAwareNetworkServiceEngine(
            nodes, fixed, 10*GBIT, (Commodity("f", "A", "D"),), trace,
            ConstantDelay(0.1), executor, (),
            conservation_abs_tolerance_bits=1.0,
            conservation_relative_tolerance=1e-12,
            state_tolerance_bits=0.01)
    engine.advance_to(decision_time)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1", window_end)]))
    spec = CandidateSpec("BBM", {
        "a": ("B", "D1"), "b": ("D", "D1"),
        "retarget_a": setup, "retarget_b": setup, "acquisition": 0.0,
    }, old)
    proposal = FrozenTerminalPairProposer().propose(
        engine.executor, (spec,), physical, fixed, "Z_SPARSE_REFERENCE")
    controller = RootActionRolloutMPCController(
        engine, physical, fixed, "Z_SPARSE_REFERENCE")
    controller.bind_candidate_specs((spec,), engine.now)
    return engine, physical, spec, proposal, controller


def mbb_environment(*, rate=8*GBIT, window_end=30.0):
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    executor = TerminalExecutor(nodes)
    old = (("B", "D1"), ("C", "D1"))
    _activate(executor, *old, end_s=30.0)
    engine = _engine(
        nodes, fixed, (Commodity("f", "A", "D"),), {"f": rate}, 30.0,
        executor, (), ConstantDelay(0.1), capacity=10*GBIT)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("A", "D2", "D", "D2", window_end)]))
    spec = CandidateSpec("MBB", {
        "a": ("A", "D2"), "b": ("D", "D2"),
        "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 1.0,
        "release_after": (old,),
    }, old)
    proposed = FrozenTerminalPairProposer().propose(
        engine.executor, (spec,), physical, fixed, "Z_MODERATE")
    controller = RootActionRolloutMPCController(engine, physical, fixed, "Z_MODERATE")
    controller.bind_candidate_specs((spec,), 0.0)
    return engine, physical, spec, proposed, controller


def line_engine(rate=1.0, delay=1.0, router=None):
    nodes = ("A", "B")
    executor = TerminalExecutor(nodes)
    trace = PiecewiseConstantTrafficTrace(
        ("f",), (TrafficSegment(0.0, 30.0, {"f": rate}, "constant"),))
    return TransitionAwareNetworkServiceEngine(
        nodes, (("A", "B"),), 10.0, (Commodity("f", "A", "B"),),
        trace, ConstantDelay(delay), executor, (), router=router,
        conservation_abs_tolerance_bits=1e-9,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=1e-9)


class GateF2RolloutTests(unittest.TestCase):
    def test_a_hold_only_finite_exact_cutoff(self):
        engine = line_engine()
        controller = RootActionRolloutMPCController(
            engine, TerminalPairPhysicalFeasibility(_catalog(engine.nodes, ())),
            engine.fixed_edges, "Z_SPARSE_REFERENCE")
        decision = controller.evaluate_root_actions(
            controller_visible_state(engine), empty_set(), {})
        self.assertEqual(decision["branch_count"], 1)
        self.assertTrue(math.isfinite(decision["HOLD_J_H_bit_s"]))
        self.assertEqual(controller.last_decision["horizon_s"], 10.0)

    def test_b_exact_event_driven_J_H(self):
        engine = line_engine(rate=1.0, delay=1.0)
        controller = RootActionRolloutMPCController(
            engine, TerminalPairPhysicalFeasibility(_catalog(engine.nodes, ())),
            engine.fixed_edges, "Z_SPARSE_REFERENCE")
        result = controller.evaluator.evaluate_hold(controller._forecast(
            controller_visible_state(engine)))
        self.assertAlmostEqual(result.J_H_bit_s, 9.5, places=9)
        self.assertEqual(result.horizon_end_s, 10.0)

    def test_c_historical_J_cancels(self):
        engine = line_engine(rate=1.0, delay=1.0).advance_to(2.0)
        controller = RootActionRolloutMPCController(
            engine, TerminalPairPhysicalFeasibility(_catalog(engine.nodes, ())),
            engine.fixed_edges, "Z_SPARSE_REFERENCE")
        result = controller.evaluator.evaluate_hold(controller._forecast(
            controller_visible_state(engine)))
        self.assertGreater(result.objective_start_bit_s, 0.0)
        self.assertAlmostEqual(
            result.J_H_bit_s,
            result.objective_end_bit_s-result.objective_start_bit_s)
        self.assertAlmostEqual(result.J_H_bit_s, 10.0, places=8)

    def test_d_clone_isolation(self):
        engine, _, spec, proposed, controller = bbm_environment()
        before = engine.canonical_state_sha256()
        proposal_before = json.dumps(spec.proposal, sort_keys=True)
        controller.evaluate_root_actions(controller_visible_state(engine),
                                         public(proposed), {})
        self.assertEqual(engine.canonical_state_sha256(), before)
        self.assertEqual(json.dumps(spec.proposal, sort_keys=True), proposal_before)
        self.assertFalse(controller.last_decision["live_engine_mutated"])

    def test_e_branch_order_invariance(self):
        engine, physical, spec1, proposed1, controller = bbm_environment()
        spec2 = CandidateSpec("BBM-ALT", {
            "a": ("B", "D1"), "b": ("A", "D2"),
            "retarget_a": 2.0, "retarget_b": 2.0, "acquisition": 0.0,
        }, (("B", "D1"), ("C", "D1")))
        physical2 = TerminalPairPhysicalFeasibility(_catalog(
            engine.nodes, [_window("B", "D1", "D", "D1"),
                           _window("A", "D2", "B", "D1")]))
        proposed = FrozenTerminalPairProposer().propose(
            engine.executor, (spec1, spec2), physical2, engine.fixed_edges,
            "Z_SPARSE_REFERENCE")
        controller = RootActionRolloutMPCController(
            engine, physical2, engine.fixed_edges, "Z_SPARSE_REFERENCE")
        controller.bind_candidate_specs((spec1, spec2), engine.now)
        state = controller_visible_state(engine)
        ids = [row["proposal_id"] for row in proposed["proposals"]]
        first = controller.evaluate_root_actions(state, public(proposed), {}, ids)
        second = controller.evaluate_root_actions(state, public(proposed), {}, ids[::-1])
        score1 = {x["branch_id"]: x["J_H_bit_s"] for x in first["branches"]}
        score2 = {x["branch_id"]: x["J_H_bit_s"] for x in second["branches"]}
        self.assertEqual(score1, score2)
        self.assertEqual(first["selected_proposal_id"], second["selected_proposal_id"])

    def test_f_forecast_firewall(self):
        def trace(future_rate):
            return PiecewiseConstantTrafficTrace(("f",), (
                TrafficSegment(0.0, 1.0, {"f": 2*GBIT}, "current"),
                TrafficSegment(1.0, 30.0, {"f": future_rate}, "future"),
            ))
        rows = []
        for future in (0.0, 9*GBIT):
            engine, _, _, proposed, controller = bbm_environment(trace=trace(future))
            decision = controller.evaluate_root_actions(
                controller_visible_state(engine), public(proposed), {})
            rows.append(decision)
        self.assertEqual(rows[0]["HOLD_J_H_bit_s"], rows[1]["HOLD_J_H_bit_s"])
        self.assertEqual(rows[0]["forecast_sha256"], rows[1]["forecast_sha256"])
        self.assertEqual(rows[0]["current_lambda_bit_s"], {"f": 2*GBIT})

    def test_g_same_forecast_all_branches(self):
        engine, _, _, proposed, controller = bbm_environment()
        decision = controller.evaluate_root_actions(
            controller_visible_state(engine), public(proposed), {})
        self.assertTrue(decision["same_forecast_all_branches"])
        self.assertEqual(len({x["forecast_sha256"] for x in decision["branches"]}), 1)

    def test_h_real_BBM_timeline(self):
        engine, _, _, proposed, controller = bbm_environment(setup=2.0)
        controller.evaluate_root_actions(controller_visible_state(engine),
                                         public(proposed), {})
        branch = next(x for x in controller.last_decision["branches"]
                      if x["proposal_id"] == "BBM")
        raw = controller.evaluator.evaluate_candidate(
            controller._forecast(controller_visible_state(engine)),
            proposed["proposals"][0], controller._candidate_specs["BBM"])
        events = [x["event"] for x in raw.terminal_events]
        self.assertIn("LINK_DOWN", events)
        self.assertIn("LINK_UP", events)
        self.assertEqual(raw.action_result["transition_mode"], "BBM")
        self.assertTrue(branch["valid"])

    def test_i_genuine_MBB_timeline(self):
        engine, _, _, proposed, controller = mbb_environment()
        raw = controller.evaluator.evaluate_candidate(
            controller._forecast(controller_visible_state(engine)),
            proposed["proposals"][0], controller._candidate_specs["MBB"])
        self.assertTrue(raw.valid)
        self.assertEqual(raw.action_result["transition_mode"], "MBB")
        self.assertIn("LINK_UP", [x["event"] for x in raw.terminal_events])

    def test_j_natural_expiry_is_valid_consequence(self):
        engine, _, _, proposed, controller = bbm_environment(
            rate=10*GBIT, setup=2.0, window_end=4.0)
        raw = controller.evaluator.evaluate_candidate(
            controller._forecast(controller_visible_state(engine)),
            proposed["proposals"][0], controller._candidate_specs["BBM"])
        self.assertTrue(raw.valid)
        self.assertTrue(math.isfinite(raw.J_H_bit_s))
        self.assertTrue(any(x["event"] == "LINK_DOWN"
                            and x["details"].get("reason") == "LINK_EXPIRE"
                            for x in raw.terminal_events))
        self.assertGreater(raw.separated_outage_metrics["post_expiry_no_route_s"], 0.0)

    def test_k_invalid_root_candidate_is_infinity_with_reason(self):
        engine, _, spec, _, _ = bbm_environment()
        physical = TerminalPairPhysicalFeasibility(_catalog(engine.nodes, ()))
        controller = RootActionRolloutMPCController(
            engine, physical, engine.fixed_edges, "Z_SPARSE_REFERENCE")
        controller.bind_candidate_specs((spec,), engine.now)
        row = {
            "proposal_id": "BBM", "ready_time_s": 2.0,
            "remaining_lifetime_s": 30.0, "usable_lifetime_s": 28.0,
        }
        proposal_set = {**empty_set(), "proposals": [row]}
        decision = controller.evaluate_root_actions(
            controller_visible_state(engine), proposal_set, {})
        bad = decision["branches"][1]
        self.assertFalse(bad["valid"])
        self.assertEqual(bad["J_H_bit_s"], "Infinity")
        self.assertIsNotNone(bad["rejection_reason"])
        self.assertTrue(bad["proposer_executor_consistency_diagnostic"])

    def test_l_hold_exact_tie_wins(self):
        engine, _, _, proposed, controller = bbm_environment(rate=0.0, setup=0.0)
        action = controller.observe(controller_visible_state(engine), public(proposed), {})
        self.assertEqual(action.kind, "HOLD")

    def test_m_replace_exact_tie_uses_proposer_order(self):
        nodes = ("A", "B", "C", "D")
        fixed = (("A", "B"), ("C", "D"))
        engine = _engine(nodes, fixed, (Commodity("f", "A", "D"),),
                         {"f": GBIT}, 30.0, TerminalExecutor(nodes), (),
                         ConstantDelay(0.1), capacity=10*GBIT)
        records = [_window("B", terminal, "C", terminal) for terminal in ("D1", "D2")]
        physical = TerminalPairPhysicalFeasibility(_catalog(nodes, records))
        specs = tuple(CandidateSpec(f"P{index}", {
            "a": ("B", terminal), "b": ("C", terminal),
            "retarget_a": 0.0, "retarget_b": 0.0, "acquisition": 0.0,
        }) for index, terminal in enumerate(("D1", "D2"), 1))
        proposed = FrozenTerminalPairProposer().propose(
            engine.executor, specs, physical, fixed, "Z_SPARSE_REFERENCE")
        controller = RootActionRolloutMPCController(
            engine, physical, fixed, "Z_SPARSE_REFERENCE")
        controller.bind_candidate_specs(specs, 0.0)
        decision = controller.evaluate_root_actions(
            controller_visible_state(engine), public(proposed), {})
        self.assertEqual(decision["selected_proposal_id"],
                         proposed["proposals"][0]["proposal_id"])

    def test_n_no_future_voluntary_action(self):
        engine, _, _, proposed, controller = bbm_environment()
        decision = controller.evaluate_root_actions(
            controller_visible_state(engine), public(proposed), {})
        self.assertFalse(decision["multi_step_future_controller_actions"])
        raw = controller.evaluator.evaluate_candidate(
            controller._forecast(controller_visible_state(engine)),
            proposed["proposals"][0], controller._candidate_specs["BBM"])
        self.assertEqual(raw.action_result["action_id"].count("F2-ROLLOUT"), 1)

    def test_o_no_recursive_controller_invocation(self):
        self.assertFalse(RootActionRolloutMPCController.multi_step_future_controller_actions)
        self.assertTrue(RootActionRolloutMPCController.root_action_only)

    def test_p_live_engine_stays_at_t_after_scoring(self):
        engine, _, _, proposed, controller = bbm_environment(decision_time=1.0)
        controller.observe(controller_visible_state(engine), public(proposed), {})
        self.assertEqual(engine.now, 1.0)

    def test_q_winning_hypothetical_state_discarded(self):
        engine, _, _, proposed, controller = bbm_environment(rate=0.0)
        terminal_before = copy.deepcopy(engine.executor.snapshot())
        controller.observe(controller_visible_state(engine), public(proposed), {})
        self.assertEqual(engine.executor.snapshot(), terminal_before)

    def test_r_live_selected_replace_uses_real_runner_path(self):
        nodes = ("A", "B", "C", "D")
        fixed = (("A", "B"), ("C", "D"))
        engine = _engine(nodes, fixed, (Commodity("f", "A", "D"),),
                         {"f": 5*GBIT}, 20.0, TerminalExecutor(nodes), (),
                         ConstantDelay(0.1), capacity=10*GBIT)
        physical = TerminalPairPhysicalFeasibility(_catalog(
            nodes, [_window("B", "D1", "C", "D1")]))
        spec = CandidateSpec("CONNECT", {
            "a": ("B", "D1"), "b": ("C", "D1"),
            "retarget_a": 0.0, "retarget_b": 0.0, "acquisition": 0.0,
        })
        controller = RootActionRolloutMPCController(
            engine, physical, fixed, "Z_SPARSE_REFERENCE")
        source = controller.candidate_source(lambda _state, _context: (spec,))
        result = MultiEpochControllerRunner(
            engine, physical, fixed, "Z_SPARSE_REFERENCE", source, controller,
            decision_end_s=0.0).run(21.0)
        action = result["controller_actions"][0]
        self.assertEqual(action["selected_action"]["kind"], "REPLACE")
        self.assertTrue(action["accepted"])
        self.assertIsNotNone(action["resulting_gate_b_transition_type"])

    def test_s_t_u_branch_invariants(self):
        engine, _, _, proposed, controller = bbm_environment()
        decision = controller.evaluate_root_actions(
            controller_visible_state(engine), public(proposed), {})
        for row in decision["branches"]:
            if row["valid"]:
                self.assertTrue(row["invariants"]["work_conservation_pass"])
                self.assertTrue(row["invariants"]["nonnegative_queue_pass"])
                self.assertTrue(row["invariants"]["capacity_pass"])

    def test_v_deterministic_repeat(self):
        engine, _, _, proposed, controller = bbm_environment()
        state = controller_visible_state(engine)
        first = controller.evaluate_root_actions(state, public(proposed), {})
        second = controller.evaluate_root_actions(state, public(proposed), {})
        self.assertEqual(first["decision_sha256"], second["decision_sha256"])

    def test_w_primary_router(self):
        engine = line_engine()
        controller = RootActionRolloutMPCController(
            engine, TerminalPairPhysicalFeasibility(_catalog(engine.nodes, ())),
            engine.fixed_edges, "Z_SPARSE_REFERENCE")
        self.assertTrue(math.isfinite(controller.evaluate_root_actions(
            controller_visible_state(engine), empty_set(), {})["HOLD_J_H_bit_s"]))

    def test_x_robustness_router_clone_semantics(self):
        router = DeterministicLoadAwareRouter()
        router.update_current_state(0.0)
        engine = line_engine(router=router)
        # The load-aware D2 production adapter is validated in Gate E; this
        # fixture checks that the exact clone preserves its router state.
        clone = engine.clone()
        self.assertEqual(type(clone.router), DeterministicLoadAwareRouter)
        self.assertEqual(clone.router.snapshot, engine.router.snapshot)

    def test_y_sparse_safety_is_real(self):
        engine, _, _, proposed, _ = bbm_environment(setup=2.001)
        self.assertEqual(proposed["proposals"], [])
        self.assertEqual(proposed["pruned"][0]["reason"], "OUTAGE_BOUND_EXCEEDED")

    def test_z_moderate_strict_connected_is_real(self):
        engine, physical, spec, _, _ = bbm_environment(setup=1.0)
        proposed = FrozenTerminalPairProposer().propose(
            engine.executor, (spec,), physical, engine.fixed_edges, "Z_MODERATE")
        self.assertEqual(proposed["proposals"], [])
        self.assertEqual(proposed["pruned"][0]["reason"],
                         "STRICT_CONNECTIVITY_VIOLATION")

    def test_mechanism_separation_B1_replace_B4_hold(self):
        engine, _, _, proposed, b4 = bbm_environment(
            rate=10*GBIT, setup=2.0, decision_time=1.0)
        state = controller_visible_state(engine)
        b1 = IgnoreSetupDynamicController(engine)
        action_b1 = b1.observe(state, public(proposed), {})
        action_b4 = b4.observe(state, public(proposed), {})
        self.assertEqual(action_b1.kind, "REPLACE")
        self.assertEqual(action_b4.kind, "HOLD")
        self.assertGreater(b4.last_decision["branches"][1]["J_H_bit_s"],
                           b4.last_decision["HOLD_J_H_bit_s"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

