from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.f3_drain_continuation import (
    F3_BOUNDARY_REACHED, F3_CENSORED, F3_COMPLETE, F3_CONTINUE_DRAIN,
    NO_PROGRESS_CODE, F3DrainContinuationAdapter, classify_f3_termination,
    unfinished_work_bits,
)
from dynamic_lisl.production_candidate_source import DrainDecisionPolicy
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.transition_service_orchestrator import (
    TransitionAwareNetworkServiceEngine,
)


PROJECT = Path(__file__).resolve().parents[1]
D2_PRE_INFLIGHT_CLOSURE_SHA256 = "5b674ee226ac07aba136fc7c207f6abe727a4d63ad9097c1291afa6217750fd4"
D2_SHA256 = "9ed1ecf9b8c5cde21fd5a71113fdd45e2d69a20bb808689ccf40a9392ce172e7"


class _Scalar:
    def __init__(self, value):
        self.value = float(value)

    def total(self):
        return self.value


class ScriptedEngine:
    """Unit-only interface fixture; no registered scenario or controller."""
    def __init__(self, now, residual, steps=()):
        self.now = float(now)
        self.queues = _Scalar(residual)
        self.in_flight = _Scalar(0.0)
        self.steps = list(steps)
        self.run_calls = 0

    def canonical_state_sha256(self):
        return f"{self.now:.12f}|{self.queues.value:.12f}|{len(self.steps)}"

    def run(self, boundary):
        self.run_calls += 1
        if self.steps:
            self.now, residual = self.steps.pop(0)
            self.queues.value = float(residual)
        return {"metrics": {
            "evaluation_end_s": self.now,
            "residual_backlog_bits": self.queues.total(),
            "censored": self.queues.total() > 1.0,
        }}


class ConstantDelay:
    def __init__(self, value):
        self.value = float(value)

    def __call__(self, _edge, _time):
        return self.value


def real_d2_fixture():
    nodes = ("UNIT_A", "UNIT_B")
    trace = PiecewiseConstantTrafficTrace(
        ("unit_flow",),
        (TrafficSegment(0.0, 1.0, {"unit_flow": 0.5}, "UNIT_ONLY"),))
    return TransitionAwareNetworkServiceEngine(
        nodes, (("UNIT_A", "UNIT_B"),), 10.0,
        (Commodity("unit_flow", "UNIT_A", "UNIT_B"),), trace,
        ConstantDelay(0.1), TerminalExecutor(nodes), (),
        conservation_abs_tolerance_bits=1.0,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=0.01)


class GateF3DrainContinuationTests(unittest.TestCase):
    def test_a_residual_0005_is_complete(self):
        engine = ScriptedEngine(250.0, 0.005)
        outcome = F3DrainContinuationAdapter().advance_to_boundary(engine, 252.0)
        self.assertEqual(outcome.status, F3_COMPLETE)
        self.assertEqual(engine.run_calls, 0)

    def test_b_residual_0035_continues_real_advance_then_completes(self):
        engine = ScriptedEngine(250.0, 0.035, ((250.125, 0.005),))
        outcome = F3DrainContinuationAdapter().advance_to_boundary(engine, 252.0)
        self.assertEqual(outcome.status, F3_COMPLETE)
        self.assertGreater(outcome.final_time_s, outcome.start_time_s)
        self.assertEqual(engine.run_calls, 1)

    def test_c_residual_05_before_limit_is_neither_final_class(self):
        self.assertEqual(classify_f3_termination(250.0, 0.5),
                         F3_CONTINUE_DRAIN)
        engine = ScriptedEngine(250.0, 0.5, ((252.0, 0.4),))
        outcome = F3DrainContinuationAdapter().advance_to_boundary(engine, 252.0)
        self.assertEqual(outcome.status, F3_BOUNDARY_REACHED)

    def test_d_residual_above_threshold_at_600_is_censored(self):
        self.assertEqual(classify_f3_termination(600.0, 0.5), F3_CENSORED)

    def test_e_residual_at_threshold_before_600_is_complete(self):
        self.assertEqual(classify_f3_termination(599.9, 0.01), F3_COMPLETE)

    def test_f_no_decision_at_exactly_600(self):
        policy = DrainDecisionPolicy()
        self.assertNotIn(600.0, policy.possible_epochs())
        self.assertFalse(policy.decision_due(600.0, 1.0))

    def test_g_drain_controller_epochs_unchanged(self):
        epochs = DrainDecisionPolicy().possible_epochs()
        self.assertIn(240.0, epochs)
        self.assertIn(242.0, epochs)
        self.assertEqual(epochs[-1], 598.0)
        self.assertEqual(epochs[120:123], (240.0, 242.0, 244.0))

    def test_h_real_d2_evolution_continues_after_internal_return(self):
        engine = real_d2_fixture()
        # Prime the unchanged D2 engine through its own early-return path.
        # D2 calls 0.05 bit "drained" because its internal threshold is
        # 1.0 bit, while the frozen F3 rule must still classify it as work.
        d2_result = engine.run(10.0)
        self.assertFalse(d2_result["metrics"]["censored"])
        self.assertGreater(d2_result["metrics"]["residual_backlog_bits"],
                           0.01)
        self.assertEqual(
            classify_f3_termination(engine.now, unfinished_work_bits(engine)),
            F3_CONTINUE_DRAIN)
        start_time = engine.now
        outcome = F3DrainContinuationAdapter().advance_to_boundary(engine, 10.0)
        self.assertEqual(outcome.status, F3_COMPLETE)
        self.assertGreater(outcome.final_time_s, start_time)
        self.assertLessEqual(outcome.final_unfinished_bits, 0.01)
        self.assertLess(engine.now, 10.0)
        self.assertLessEqual(engine.max_abs_conservation,
                             1.0+1e-12*max(1.0, sum(engine.arrived.values())))
        self.assertLessEqual(engine.max_capacity_violation, 0.01)
        self.assertTrue(all(value >= 0.0 for value in engine.queues.bits.values()))

    def test_i_no_progress_guard_is_explicit(self):
        engine = ScriptedEngine(250.0, 0.5)
        with self.assertRaisesRegex(RuntimeError, NO_PROGRESS_CODE):
            F3DrainContinuationAdapter().advance_to_boundary(engine, 252.0)

    def test_j_authorized_d2_closure_hash_and_frozen_tolerances(self):
        path = PROJECT/"src/dynamic_lisl/transition_service_orchestrator.py"
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertNotEqual(observed, D2_PRE_INFLIGHT_CLOSURE_SHA256)
        self.assertEqual(observed, D2_SHA256)
        contract = json.loads((PROJECT/"configs/gate_d0_traffic_contract.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(contract["conservation_abs_tolerance_bits"], 1.0)
        self.assertEqual(contract["state_tolerance_bits"], 0.01)


if __name__ == "__main__":
    unittest.main()
