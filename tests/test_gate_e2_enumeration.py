"""Gate E2 result-blind natural-geometry enumeration tests."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from dynamic_lisl.gate_e2_enumeration import (
    SETUP_TOTAL_S, enumerate_natural_candidates,
    validate_selected_candidates,
)
from dynamic_lisl.scenario_selection import (
    FORBIDDEN_RESULT_KEYS, REQUIRED_KEYS, validate_result_blind_candidate,
)


PROJECT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


class GateE2EnumerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = PROJECT / "outputs/gate_c_simplified_20260922T064019_313843Z"
        cls.reference = read(root.relative_to(PROJECT) / "z_ref.json")
        cls.intervals = [json.loads(line) for line in
                         (root / "terminal_pair_intervals.jsonl")
                         .read_text(encoding="utf-8").splitlines()]
        cls.commodities = read("configs/gate_d0_od_manifest_16.json")["commodities"]
        cls.candidates, cls.selection, cls.audit = enumerate_natural_candidates(
            cls.reference, cls.intervals, cls.commodities)

    def test_inventory_is_result_blind_and_schema_complete(self):
        self.assertGreater(len(self.candidates), 0)
        for row in self.candidates:
            self.assertTrue(REQUIRED_KEYS <= set(row))
            self.assertFalse({key.lower() for key in row} & FORBIDDEN_RESULT_KEYS)
            self.assertTrue(validate_result_blind_candidate(row))

    def test_natural_lifetime_defines_kappa2(self):
        for row in self.candidates:
            self.assertGreater(row["remaining_lifetime_s"], SETUP_TOTAL_S)
            self.assertAlmostEqual(
                row["kappa2"], SETUP_TOTAL_S / row["remaining_lifetime_s"])
            self.assertLess(row["kappa2"], 1.0)

    def test_frozen_selector_retains_empty_strata(self):
        availability = self.selection["availability"]
        self.assertEqual(len(availability), 16)
        self.assertTrue(any(row["status"] == "NO_ELIGIBLE_CASE"
                            for row in availability))
        self.assertEqual(len(self.selection["selected"]),
                         sum(row["status"] == "SELECTED"
                             for row in availability))
        self.assertEqual(self.selection["result_fields_read"], [])

    def test_selected_cases_pass_real_gate_c_and_gate_b_profiler(self):
        validation = validate_selected_candidates(
            self.reference, self.intervals, self.selection["selected"])
        self.assertTrue(validation["all_selected_gate_c_legal"])
        self.assertTrue(validation["all_transition_classes_match"])

    def test_reference_bridge_structure_explains_no_eb_case(self):
        counts = {row["scenario_class"] for row in self.candidates}
        self.assertIn("E-A_BBM_NO_ROUTE", counts)
        self.assertIn("E-C_GENUINE_MBB", counts)
        self.assertIn("E-D_SHARED_CONGESTION_EXTERNALITY", counts)
        self.assertNotIn("E-B_BBM_CONNECTED_REROUTE", counts)

    def test_deterministic_replay(self):
        candidates, selection, audit = enumerate_natural_candidates(
            self.reference, self.intervals, self.commodities)
        self.assertEqual(candidates, self.candidates)
        self.assertEqual(selection, self.selection)
        self.assertEqual(audit, self.audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
