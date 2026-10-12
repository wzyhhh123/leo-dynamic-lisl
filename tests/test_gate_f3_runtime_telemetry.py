from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from dynamic_lisl.candidate_proposer import CandidateSpec, FrozenTerminalPairProposer
from dynamic_lisl.f3_drain_continuation import F3DrainContinuationAdapter
from dynamic_lisl.f3_progress import PassiveProgressRecorder
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_d2_fixtures import _catalog, _window, fixture_h_clone_base
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor
from dynamic_lisl.production_candidate_source import DrainDecisionPolicy
from dynamic_lisl.scientific_controllers import IgnoreSetupDynamicController
from tools.profile_gate_f3_b1_runtime import build_parser, make_progress_recorder
from tools.run_gate_f3_p1_execution import preflight


class CountingSource:
    def __init__(self, spec):
        self.spec = spec
        self.calls = 0
        self.last_report = None

    def __call__(self, _state, _context):
        self.calls += 1
        self.last_report = {
            "uncapped_counts": {"BBM_RAW": 0, "MBB_RAW": 1},
            "selected_counts": {"BBM_RAW": 0, "MBB_RAW": 1},
            "source_sha256": "UNIT_PASSIVE_SOURCE",
        }
        return (self.spec,)


class CountingProposer:
    def __init__(self):
        self.inner = FrozenTerminalPairProposer()
        self.calls = 0

    def propose(self, *args, **kwargs):
        self.calls += 1
        return self.inner.propose(*args, **kwargs)


class CountingB1(IgnoreSetupDynamicController):
    def __init__(self, engine):
        super().__init__(engine)
        self.calls = 0

    def observe(self, *args, **kwargs):
        self.calls += 1
        return super().observe(*args, **kwargs)


def executor_fixture(recorder=None):
    engine = fixture_h_clone_base().advance_to(2.0)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        engine.nodes, [_window("B", "D2", "D", "D2", 30.0)]))
    old = (("B", "D1"), ("C", "D1"))
    spec = CandidateSpec("MBB_SWITCH", {
        "a": ("B", "D2"), "b": ("D", "D2"),
        "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0,
        "release_after": (old,),
    }, old)
    executor = P1RunExecutor.__new__(P1RunExecutor)
    executor.assets = SimpleNamespace(physical=physical, fixed=engine.fixed_edges)
    executor.row = {"run_id": "ENGINEERING_PROFILE_ONLY-UNIT", "controller": "B1",
                    "rho": 0.5}
    executor.engine = engine
    executor.source = CountingSource(spec)
    executor.proposer = CountingProposer()
    executor.controller = CountingB1(engine)
    executor.candidate_source = executor.source
    executor.policy = DrainDecisionPolicy()
    executor.drain_adapter = F3DrainContinuationAdapter()
    executor.drain_continuation_audit = []
    executor.actions = []
    executor.audits = []
    executor.decision_runtime_total = 0.0
    executor.b4_branch_count_total = 0
    executor.b4_valid_branch_count_total = 0
    executor.b4_invalid_branch_count_total = 0
    executor.progress_recorder = recorder
    executor.epoch_runtime_records = []
    executor._pending_network_advance_wall_s = 0.0
    return executor


def normalize_action(record):
    return {key: value for key, value in record.items()
            if key not in ("controller_decision_runtime_s",
                           "action_canonical_sha256")}


def scientific_result(executor):
    executor._decision(2.0, 1)
    result = executor.engine.run(20.0)
    metrics = {key: value for key, value in result["metrics"].items()
               if key != "runtime"}
    invariants = {
        "work_conservation": metrics["max_abs_conservation_error_bits"] <= 1.0,
        "capacity": metrics["max_capacity_violation_bit_s"] <= 0.01,
        "queue_nonnegative": metrics["negative_queue_count"] == 0,
    }
    return {
        "selected_actions": [normalize_action(x) for x in executor.actions],
        "proposal_ids": [x["selected_proposal_id"] for x in executor.actions],
        "proposal_hashes": [x["proposal_set_sha256"] for x in executor.actions],
        "terminal_event_sequence": result["terminal_event_sequence"],
        "transition_types": [x["actual_gate_b_transition_type"]
                             for x in executor.actions],
        "graph_events": result["graph_event_sequence"],
        "queues": result["queues"],
        "in_flight": result["in_flight"],
        "arrived": result["arrived_by_commodity"],
        "delivered": result["delivered_by_commodity"],
        "unfinished": metrics["residual_backlog_bits"],
        "metrics": metrics,
        "invariants": invariants,
        "call_counts": {
            "candidate_source": executor.source.calls,
            "proposer": executor.proposer.calls,
            "controller_observe": executor.controller.calls,
        },
    }


class GateF3PassiveProgressTests(unittest.TestCase):
    def test_profile_cli_progress_modes_are_mutually_exclusive(self):
        parser = build_parser()
        self.assertTrue(parser.parse_args([]).telemetry_enabled)
        self.assertTrue(parser.parse_args(["--progress"]).telemetry_enabled)
        self.assertFalse(parser.parse_args(["--no-progress"]).telemetry_enabled)
        with self.assertRaises(SystemExit):
            parser.parse_args(["--progress", "--no-progress"])

    def test_recorder_start_end_and_atomic_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = PassiveProgressRecorder(
                directory, attempt_id="UNIT", run_id="UNIT-RUN",
                controller="B1", rho=0.5)
            recorder.epoch_start(sim_time_s=2.0, decision_epoch_index=1)
            recorder.epoch_end(
                sim_time_s=2.0, decision_epoch_index=1,
                total_unfinished_bits=3.0, selected_action_kind="HOLD")
            rows = [json.loads(line) for line in
                    (Path(directory)/"progress.jsonl").read_text().splitlines()]
            latest = json.loads(
                (Path(directory)/"progress_latest.json").read_text())
            self.assertEqual([x["epoch_status"] for x in rows],
                             ["EPOCH_START", "EPOCH_END"])
            self.assertEqual(latest, rows[-1])
            self.assertEqual(latest["phase"], "ARRIVAL")
            self.assertFalse(
                latest["max_horizon_progress_is_completion_probability"])
            self.assertFalse(any(".tmp-" in path.name
                                 for path in Path(directory).iterdir()))

    def test_progress_on_off_scientific_equivalence_and_call_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {"run_id": "ENGINEERING_PROFILE_ONLY-UNIT",
                   "controller": "B1", "rho": 0.5}

            off_dir = root / "off"
            off_dir.mkdir()
            off_recorder = make_progress_recorder(off_dir, row, False)
            self.assertIsNone(off_recorder)
            off = executor_fixture(off_recorder)
            off_result = scientific_result(off)
            self.assertFalse((off_dir / "progress.jsonl").exists())
            self.assertFalse((off_dir / "progress_latest.json").exists())

            on_dir = root / "on"
            on_dir.mkdir()
            on_recorder = make_progress_recorder(on_dir, row, True)
            self.assertIsInstance(on_recorder, PassiveProgressRecorder)
            on = executor_fixture(on_recorder)
            on_result = scientific_result(on)
            progress_rows = [json.loads(line) for line in
                             (on_dir/"progress.jsonl").read_text().splitlines()]
            self.assertTrue((on_dir / "progress_latest.json").exists())
        self.assertEqual(off_result, on_result)
        self.assertEqual(off_result["call_counts"], {
            "candidate_source": 1, "proposer": 1, "controller_observe": 1})
        self.assertEqual([x["epoch_status"] for x in progress_rows],
                         ["EPOCH_START", "EPOCH_END"])
        self.assertEqual(progress_rows[-1]["selected_proposal_id"],
                         off_result["proposal_ids"][0])
        self.assertEqual(off_result["transition_types"], ["MBB"])
        self.assertTrue(all(off_result["invariants"].values()))

    def test_engineering_prefix_rejects_registered_run_id(self):
        executor = executor_fixture(None)
        executor.row["run_id"] = "F3V1-P1-REGISTERED"
        before = executor.engine.canonical_state_sha256()
        with self.assertRaisesRegex(ValueError, "NONREGISTERED"):
            executor.run_engineering_prefix(2.0)
        self.assertEqual(executor.engine.canonical_state_sha256(), before)

    def test_preflight_accepts_read_only_runtime_abort_record(self):
        report, _manifest, p1 = preflight()
        self.assertTrue(report["pass"], {
            key: value for key, value in report["checks"].items() if not value})
        self.assertEqual(len(p1), 12)
        records = report["historical_attempt_records"]
        aborted = [row for row in records
                   if row["status"] == "ABORTED_FOR_RUNTIME_ENGINEERING"]
        self.assertEqual(len(aborted), 1)
        self.assertEqual(aborted[0]["source"], "RUNTIME_ABORT_RECORD.txt")
        self.assertEqual(aborted[0]["result_seal"], "NO")


if __name__ == "__main__":
    unittest.main()
