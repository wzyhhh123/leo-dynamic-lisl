"""Pre-E2 absolute-time and delayed-action regression tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from tests.runtime_phase1_overlay import approved_runtime_phase1_change

from dynamic_lisl.absolute_time_regression import (
    DELAY_OFFSET_S,
    FRAME_ID,
    SHIFTS_S,
    run_out_of_window_negative,
    run_translated_replay,
    stale_horizon_negative_control,
)


PROJECT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()


class PreE2AbsoluteTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.replays = [run_translated_replay(shift) for shift in SHIFTS_S]

    def test_full_stack_relative_replay_is_translation_invariant(self):
        hashes = {row["relative_time_canonical_hash"] for row in self.replays}
        self.assertEqual(len(hashes), 1)
        traffic = {row["relative_traffic_trace_hash"] for row in self.replays}
        self.assertEqual(len(traffic), 1)
        self.assertEqual(len({row["raw_traffic_trace_hash"]
                              for row in self.replays}), len(SHIFTS_S))

    def test_relative_clock_quantities_are_preserved(self):
        for row in self.replays:
            relative = row["relative"]
            self.assertEqual(relative["absolute_time_frame_id"], FRAME_ID)
            self.assertAlmostEqual(relative["action_offset_s"], DELAY_OFFSET_S)
            self.assertAlmostEqual(relative["ready_offset_from_action_s"], 2.0)
            self.assertAlmostEqual(relative["L_remain_s"], 7.5)
            self.assertAlmostEqual(relative["L_usable_s"], 5.5)

    def test_gate_c_bbm_and_relative_network_outcomes_are_preserved(self):
        reference = self.replays[0]["relative"]
        for row in self.replays[1:]:
            relative = row["relative"]
            self.assertEqual(relative["gate_c"], reference["gate_c"])
            self.assertEqual(relative["transition_mode"], "BBM")
            self.assertEqual(relative["branches"], reference["branches"])
            self.assertEqual(relative["reversal"], reference["reversal"])

    def test_conservation_queue_capacity_and_censor_invariants(self):
        for row in self.replays:
            for branch in row["relative"]["branches"].values():
                metrics = branch["metrics"]
                self.assertLessEqual(
                    metrics.get("max_abs_conservation_error_bits", 0.0), 1.0)
                self.assertEqual(metrics.get("negative_queue_count", 0), 0)
                self.assertLessEqual(
                    metrics.get("max_capacity_violation_bit_s", 0.0), 0.01)
                self.assertFalse(metrics["censored"])

    def test_stale_profiler_horizon_is_rejected_explicitly(self):
        result = stale_horizon_negative_control(100.0)
        self.assertTrue(result["caught"])
        self.assertEqual(
            result["error"],
            "ABSOLUTE_TIME_FRAME_MISMATCH_STALE_PROFILER_HORIZON")

    def test_delayed_action_rechecks_execution_time_legality(self):
        rows = [run_out_of_window_negative(shift) for shift in SHIFTS_S]
        for row in rows:
            self.assertEqual(row["status"], "INFEASIBLE_AT_EXECUTION_TIME")
            self.assertFalse(row["replacement_candidate_used"])
        self.assertEqual(len({json.dumps(row["target_signature"], sort_keys=True)
                              for row in rows}), 1)

    def test_repeated_replay_is_deterministic(self):
        replay = run_translated_replay(SHIFTS_S[-1])
        self.assertEqual(replay["relative_time_canonical_hash"],
                         self.replays[-1]["relative_time_canonical_hash"])
        self.assertEqual(replay["relative"], self.replays[-1]["relative"])

    def test_e0_e1_manifests_and_formal_e1_evidence_are_unchanged(self):
        for record_name in (
                "configs/gate_e0_manifest_hashes.json",
                "configs/gate_e1_manifest_hashes.json"):
            record = read(record_name)["files"]
            self.assertEqual({name: sha(name) for name in record}, record)
        status = read("configs/gate_e1_status.json")
        self.assertEqual(status["gate_e1"], "PASS")
        report = read(Path(status["evidence"]) / "report.json")
        self.assertEqual(
            report["gate_e1_small_scale_interpretable_mechanism_experiments"],
            "PASS")

    def test_frozen_a_to_e1_baseline_is_unchanged_when_present(self):
        name = "configs/pre_e2_frozen_a_to_e1_hashes.json"
        path = PROJECT / name
        if not path.exists():
            self.skipTest("one-time baseline has not been captured yet")
        record = read(name)["files"]
        mismatches = [
            item for item, expected in record.items()
            if (not (PROJECT/item).is_file()
                or (sha(item) != expected
                    and not approved_runtime_phase1_change(
                        PROJECT, item, expected, sha(item))))]
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
