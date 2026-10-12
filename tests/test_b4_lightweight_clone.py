"""Exact B4 history-sharing clone versus unchanged engine.clone()."""
import copy
from dataclasses import asdict
import unittest
from unittest.mock import patch

from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_f3_p1_execution import ObservationalE2Engine
from dynamic_lisl.rollout_clone import APPEND_ONLY_HISTORY_FIELDS, clone_rollout_engine
from dynamic_lisl.transition_service_orchestrator import ScriptedProposal
from test_gate_f2_rollout import bbm_environment, mbb_environment, public


def history(engine):
    return {name: copy.deepcopy(getattr(engine, name))
            for name in APPEND_ONLY_HISTORY_FIELDS} | {
                "terminal_log": copy.deepcopy(engine.executor.log)}


def assert_engine_equal(case, left, right):
    def value(obj):
        if isinstance(obj, dict):
            return {key: value(item) for key, item in obj.items()}
        if isinstance(obj, (list, tuple)):
            return (type(obj).__name__, [value(item) for item in obj])
        if hasattr(obj, "__dict__"):
            return (type(obj).__name__, value(vars(obj)))
        return obj
    case.assertEqual(left.canonical_state(), right.canonical_state())
    case.assertEqual(set(vars(left)), set(vars(right)))
    for name in vars(left):
        a, b = getattr(left, name), getattr(right, name)
        case.assertEqual(value(a), value(b), name)


class B4LightweightCloneTests(unittest.TestCase):
    def test_f3_reporting_override_matches_legacy(self):
        template, *_ = bbm_environment(decision_time=0.0)
        engine = ObservationalE2Engine(
            template.nodes, template.fixed_edges, template.capacity_bit_s,
            template.commodities, template.trace, template.delay, template.executor,
            conservation_abs_tolerance_bits=1., state_tolerance_bits=0.01)
        engine.advance_to(1.0)
        before = copy.deepcopy(engine.reporting_samples)
        branch = engine.clone()
        legacy = engine.clone_legacy_reference()
        self.assertFalse(branch.reporting_enabled)
        self.assertEqual(branch.reporting_samples, [])
        branch.advance_to(3.0)
        legacy.advance_to(3.0)
        assert_engine_equal(self, branch, legacy)
        self.assertEqual(engine.reporting_samples, before)

    def test_history_complete_and_independent_containers(self):
        engine, *_ = bbm_environment(decision_time=1.0)
        before = history(engine)
        branch = clone_rollout_engine(engine)
        assert_engine_equal(self, branch, engine.clone())
        for name in APPEND_ONLY_HISTORY_FIELDS:
            self.assertIsNot(getattr(branch, name), getattr(engine, name))
            for a, b in zip(getattr(branch, name), getattr(engine, name)):
                self.assertIs(a, b)
            getattr(branch, name).append({"test_only": True})
        self.assertIsNot(branch.executor.log, engine.executor.log)
        self.assertIs(branch.executor.log[0], engine.executor.log[0])
        self.assertEqual(history(engine), before)

    def test_mutable_state_and_pending_episode_aliases(self):
        engine, *_ = bbm_environment(decision_time=1.0)
        episode = {"start_s": 0., "end_s": 1., "baseline_queue_bits": 0.,
                   "peak_queue_bits": 0., "added_positive_queue_bits": 0.,
                   "clearance_time_s": None}
        engine.transition_episodes.append(episode)
        engine._pending_clearance.append(episode)
        engine.future_unknown_field = {"mutable": [1]}
        branch = clone_rollout_engine(engine)
        self.assertIs(branch.transition_episodes[-1], branch._pending_clearance[-1])
        self.assertIsNot(branch._pending_clearance[-1], episode)
        branch._pending_clearance[-1]["clearance_time_s"] = 3.
        branch.future_unknown_field["mutable"].append(2)
        self.assertIsNone(episode["clearance_time_s"])
        self.assertEqual(engine.future_unknown_field, {"mutable": [1]})
        for name in ("executor", "queues", "in_flight", "propagation_agenda",
                     "arrived", "delivered", "objective_by_commodity", "router"):
            self.assertIsNot(getattr(branch, name), getattr(engine, name), name)

    def compare_branches(self, factory):
        engine, physical, spec, proposed, controller = factory()
        before = history(engine)
        state_before = engine.canonical_state()
        forecast = controller._forecast(controller_visible_state(engine))
        evaluator = controller.evaluator
        for candidate in (False, True):
            branches = []
            def optimized(instance):
                value = clone_rollout_engine(instance)
                branches.append(value)
                return value
            def legacy(instance):
                value = original(instance)
                branches.append(value)
                return value
            original = type(engine).clone
            def evaluate():
                if candidate:
                    return evaluator.evaluate_candidate(forecast, proposed["proposals"][0], spec)
                return evaluator.evaluate_hold(forecast)
            with patch.object(type(engine), "clone", legacy):
                expected = evaluate()
            with patch.object(type(engine), "clone", optimized):
                actual = evaluate()
            self.assertEqual(asdict(expected), asdict(actual))
            assert_engine_equal(self, branches[0], branches[1])
        self.assertEqual(history(engine), before)
        self.assertEqual(engine.canonical_state(), state_before)
        state = controller_visible_state(engine)
        expected = controller.evaluate_root_actions(state, public(proposed), {})
        with patch.object(type(engine), "clone", clone_rollout_engine):
            actual = controller.evaluate_root_actions(state, public(proposed), {})
        self.assertEqual(expected, actual)

    def test_bbm_backlog_nonzero_epoch(self):
        self.compare_branches(lambda: bbm_environment(rate=12e9, decision_time=1.0))

    def test_mbb(self):
        self.compare_branches(mbb_environment)

    def test_expiry(self):
        self.compare_branches(lambda: bbm_environment(window_end=4.0))

    def test_zero_work_tie(self):
        self.compare_branches(lambda: bbm_environment(rate=0.0, setup=0.0))

    def test_clone_during_pending_transition_and_after_clearance(self):
        engine, physical, spec, proposed, controller = bbm_environment()
        engine.schedule_action(ScriptedProposal(
            engine.now, "test-root", spec.proposal, physical,
            controller.evaluator.safety.policy, 2.0000001, None))
        engine.settle_current_time()
        for until in (0.5, 2.1, 5.0):
            reference = engine.clone()
            branch = clone_rollout_engine(engine)
            before = history(engine)
            reference.advance_to(until)
            branch.advance_to(until)
            assert_engine_equal(self, reference, branch)
            self.assertEqual(history(engine), before)
            engine.advance_to(until)


if __name__ == "__main__":
    unittest.main()
