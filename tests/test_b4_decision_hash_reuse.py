"""Exact outputs and retained negative controls for decision-local hashes."""
from dataclasses import asdict, replace
import unittest
from unittest.mock import patch

from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.forecast import CurrentRatePersistenceForecast
from test_gate_f2_rollout import bbm_environment, mbb_environment, public


def compare(controller, proposals):
    engine = controller.engine
    observed = []
    original_hash = type(engine).canonical_state_sha256
    original_forecast = CurrentRatePersistenceForecast.sha256
    for reuse in (False, True):
        controller.reuse_decision_hashes = reuse
        counts = {"live": 0, "branch": 0, "forecast": 0}
        branches = []
        def state_hash(instance):
            counts["live" if instance is engine else "branch"] += 1
            return original_hash(instance)
        def forecast_hash(instance):
            counts["forecast"] += 1
            return original_forecast(instance)
        finish = controller.evaluator._finish
        def capture(*args, **kwargs):
            result = finish(*args, **kwargs)
            branches.append(asdict(result))
            return result
        with patch.object(type(engine), "canonical_state_sha256", state_hash), \
             patch.object(CurrentRatePersistenceForecast, "sha256", forecast_hash), \
             patch.object(controller.evaluator, "_finish", capture):
            decision = controller.evaluate_root_actions(
                controller_visible_state(engine), public(proposals), {})
        observed.append((decision, branches, counts))
    assert observed[0][:2] == observed[1][:2], "EXACT_DECISION_OR_BRANCH_MISMATCH"
    n = observed[0][0]["branch_count"]
    v = observed[0][0]["valid_branch_count"]
    assert observed[0][2] == {"live": n+2, "branch": 2*n+v, "forecast": n+1}
    assert observed[1][2] == {"live": 2, "branch": n+v, "forecast": 1}
    return observed


class B4DecisionHashReuseTests(unittest.TestCase):
    def test_full_17_branch_call_counts_and_tie_order(self):
        engine, _, spec, proposed, controller = bbm_environment(rate=0.0)
        specs = tuple(replace(spec, proposal_id=f"fixture-{i:02d}") for i in range(16))
        controller.bind_candidate_specs(specs, engine.now)
        fixture = {**proposed, "proposals": [
            {**proposed["proposals"][0], "proposal_id": s.proposal_id} for s in specs]}
        values = compare(controller, fixture)
        self.assertEqual(values[0][2], {"live": 19, "branch": 51, "forecast": 18})
        self.assertEqual(values[1][2], {"live": 2, "branch": 34, "forecast": 1})
        self.assertEqual(values[1][0]["selected_action"], "HOLD")

    def test_exact_bbm_mbb_expiry_tie(self):
        for factory in (bbm_environment, mbb_environment,
                        lambda: bbm_environment(window_end=4.0),
                        lambda: bbm_environment(rate=0.0, setup=0.0)):
            with self.subTest(factory=factory):
                engine, _, _, proposed, controller = factory()
                before = engine.canonical_state()
                compare(controller, proposed)
                self.assertEqual(before, engine.canonical_state())

    def test_repeated_decisions_no_stale_root(self):
        engine, _, spec, proposed, controller = bbm_environment()
        compare(controller, proposed)
        compare(controller, proposed)
        engine.advance_to(1.0)
        controller.bind_candidate_specs((spec,), 1.0)
        compare(controller, proposed)

    def test_corrupted_clone_rejected(self):
        engine, _, _, proposed, controller = bbm_environment()
        original = engine.clone
        def bad_clone():
            branch = original()
            branch.arrived["f"] += 1.0
            return branch
        with patch.object(engine, "clone", bad_clone):
            with self.assertRaisesRegex(AssertionError, "B4_EXACT_CLONE_STATE_MISMATCH"):
                controller.evaluate_root_actions(controller_visible_state(engine), public(proposed), {})

    def test_mutated_live_after_last_branch_rejected(self):
        engine, _, _, proposed, controller = bbm_environment()
        original = controller.evaluator.evaluate_candidate
        def corrupt(*args, **kwargs):
            result = original(*args, **kwargs)
            engine.arrived["f"] += 1.0
            return result
        with patch.object(controller.evaluator, "evaluate_candidate", corrupt):
            with self.assertRaisesRegex(AssertionError, "B4_HYPOTHETICAL_BRANCH_MUTATED_LIVE_ENGINE"):
                controller.evaluate_root_actions(controller_visible_state(engine), public(proposed), {})

    def test_exception_does_not_leave_cached_context(self):
        engine, _, _, proposed, controller = bbm_environment()
        with patch.object(controller.evaluator, "evaluate_hold", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                controller.evaluate_root_actions(controller_visible_state(engine), public(proposed), {})
        compare(controller, proposed)

    def test_invalid_branch(self):
        engine, _, _, proposed, controller = bbm_environment()
        # A structurally provided root target that Gate C must reject.
        from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
        from dynamic_lisl.gate_d2_fixtures import _catalog
        controller.evaluator.physical_layer = TerminalPairPhysicalFeasibility(_catalog(engine.nodes, ()))
        results = compare(controller, proposed)
        self.assertEqual(results[1][0]["invalid_branch_count"], 1)


if __name__ == "__main__":
    unittest.main()
