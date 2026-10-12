"""Gate E1 frozen-manifest and small mechanism correctness tests."""
import hashlib
import json
from pathlib import Path
import unittest

from tests.runtime_phase1_overlay import approved_runtime_phase1_change

from dynamic_lisl.gate_e1_experiments import (
    REQUIRED_BRANCHES, ROUTER_PRIMARY, ROUTER_ROBUSTNESS,
    evaluate_point, frozen_templates, scale_setup,
)


PROJECT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((PROJECT/name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()


def anchor(template_id, router=ROUTER_PRIMARY):
    return {
        "experiment_id": "TEST_"+template_id+"_"+router,
        "study": "E1_TEST", "template_id": template_id,
        "router_id": router, "rho": 0.8, "tau_setup_s": 2.0,
        "kappa1": 0.2, "kappa2": 0.2,
        "T_demand_s": 10.0, "L_remain_s": 10.0,
        "drain_limit_s": 70.0,
    }


class GateE1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = frozen_templates()

    def test_manifests_are_frozen_and_complete(self):
        execution = read("configs/gate_e1_execution_manifest.json")
        breaks = read("configs/gate_e1_break_even_manifest.json")
        hashes = read("configs/gate_e1_manifest_hashes.json")["files"]
        self.assertEqual(len(execution["points"]), 3856)
        self.assertEqual(execution["expected_counts"], {
            "core_positive": 3840, "zero_setup_correctness": 8,
            "delayed_anchor": 8, "total_points": 3856})
        self.assertEqual(len(breaks["families"]), 8)
        self.assertTrue(execution["created_result_blind"])
        self.assertTrue(breaks["created_result_blind"])
        self.assertEqual({name: sha(name) for name in hashes}, hashes)

    def test_setup_mapping_preserves_ratio_and_endpoint_asymmetry(self):
        base = self.templates["E-A_BBM_NO_ROUTE"]["base_transition"]
        for tau in (0, 0.5, 1, 2, 4, 8, 16):
            mapped = scale_setup(base, tau)
            self.assertAlmostEqual(mapped["effective_tau_setup_s"], tau)
            if tau:
                self.assertAlmostEqual(mapped["retarget_a"]/
                                       mapped["retarget_b"], 4/7)
                self.assertAlmostEqual(mapped["acquisition"]/
                                       mapped["retarget_b"], 3/7)

    def test_four_structural_templates_are_frozen(self):
        self.assertEqual(set(self.templates), {
            "E-A_BBM_NO_ROUTE", "E-B_BBM_CONNECTED_REROUTE",
            "E-C_GENUINE_MBB", "E-D_SHARED_CONGESTION_EXTERNALITY"})
        for template in self.templates.values():
            for field in ("nodes", "fixed_edges", "dynamic_terminals_per_node",
                          "old_dynamic_pair", "target_dynamic_pair",
                          "capacity_bit_s_per_direction", "edge_delay_s",
                          "focus_commodities", "third_party_commodities",
                          "base_transition", "structural_reason"):
                self.assertIn(field, template)
        self.assertTrue(self.templates["E-C_GENUINE_MBB"]["release_after"])
        self.assertTrue(self.templates["E-D_SHARED_CONGESTION_EXTERNALITY"]
                        ["third_party_commodities"])

    def test_ea_has_real_bbm_no_route_and_censor_is_not_evaluable(self):
        result = evaluate_point(anchor("E-A_BBM_NO_ROUTE"), self.templates)
        real = result["branches"]["REAL_SWITCH"]
        self.assertGreaterEqual(real["no_route_duration_s"], 2.0)
        self.assertEqual(result["reversal_status"], "NOT_EVALUABLE_CENSORED")
        self.assertFalse(result["break_even_use"])
        self.assertTrue(any(result["branches"][name]["residual_backlog_bits"] > 0
                            for name in REQUIRED_BRANCHES))

    def test_eb_bbm_remains_connected_and_reroutes(self):
        result = evaluate_point(anchor("E-B_BBM_CONNECTED_REROUTE"), self.templates)
        real = result["branches"]["REAL_SWITCH"]
        self.assertEqual(real["no_route_duration_s"], 0.0)
        self.assertGreaterEqual(real["route_change_count"], 2)
        self.assertTrue(real["action_accepted"])

    def test_ec_is_genuine_mbb(self):
        result = evaluate_point(anchor("E-C_GENUINE_MBB"), self.templates)
        real_result = result["branches"]["REAL_SWITCH"]
        self.assertEqual(real_result["no_route_duration_s"], 0.0)
        self.assertTrue(real_result["action_accepted"])
        self.assertTrue(self.templates["E-C_GENUINE_MBB"]["release_after"])

    def test_ed_reports_focus_and_third_party_effects(self):
        result = evaluate_point(
            anchor("E-D_SHARED_CONGESTION_EXTERNALITY"), self.templates)
        self.assertIsInstance(result["focus_delta_J_real_bit_s"], float)
        self.assertIsInstance(result["third_party_delta_J_real_bit_s"], float)
        self.assertEqual(set(result["branches"]["REAL_SWITCH"]
                             ["J_by_commodity_bit_s"]),
                         {"focus", "third", "background"})

    def test_zero_setup_real_ideal_equivalence(self):
        point = anchor("E-B_BBM_CONNECTED_REROUTE")
        point.update(experiment_id="TEST_ZERO", tau_setup_s=0.0,
                     kappa1=None, kappa2=None)
        result = evaluate_point(point, self.templates)
        real = result["branches"]["REAL_SWITCH"]
        ideal = result["branches"]["IDEAL_SWITCH"]
        self.assertAlmostEqual(real["J_bit_s"], ideal["J_bit_s"], delta=1e-6)
        self.assertEqual(real["network_signature"], ideal["network_signature"])

    def test_delayed_anchor_moves_absolute_policy_horizon_with_action(self):
        point = anchor("E-B_BBM_CONNECTED_REROUTE")
        point["delay_switch_ratios"] = [0.0, 0.25, 0.5]
        result = evaluate_point(point, self.templates, include_delayed=True)
        self.assertEqual(set(result["delayed_branches"]), {
            "DELAYED_SWITCH_0", "DELAYED_SWITCH_0.25", "DELAYED_SWITCH_0.5"})
        self.assertEqual(result["delayed_branches"]["DELAYED_SWITCH_0.5"]
                         ["status"], "EXECUTED")
        initial = result["branches"]["HOLD"]["pre_action_state_hash"]
        self.assertTrue(all(row["pre_action_state_hash"] == initial
                            for row in result["delayed_branches"].values()))

    def test_primary_and_robustness_have_identical_registered_points(self):
        points = read("configs/gate_e1_execution_manifest.json")["points"]
        def signature(row):
            return (row["study"], row["template_id"], row["rho"],
                    row["tau_setup_s"], row["kappa1"], row["kappa2"],
                    row["T_demand_s"], row["L_remain_s"])
        primary = {signature(row) for row in points
                   if row["router_id"] == ROUTER_PRIMARY}
        robust = {signature(row) for row in points
                  if row["router_id"] == ROUTER_ROBUSTNESS}
        self.assertEqual(primary, robust)

    def test_break_even_families_keep_timescales_fixed(self):
        families = read("configs/gate_e1_break_even_manifest.json")["families"]
        for family in families:
            self.assertEqual(family["T_demand_s"], 20.0)
            self.assertEqual(family["L_remain_s"], 120.0)
            self.assertEqual(family["setup_grid_s"], [0.0, 0.5, 1.0, 2.0,
                                                       4.0, 8.0, 16.0])
            self.assertEqual(family["only_varied_field"], "tau_setup_s")

    def test_deterministic_replay_and_physical_invariants(self):
        point = anchor("E-D_SHARED_CONGESTION_EXTERNALITY", ROUTER_ROBUSTNESS)
        first = evaluate_point(point, self.templates)
        second = evaluate_point(point, self.templates)
        for branch in REQUIRED_BRANCHES:
            self.assertEqual(first["branches"][branch]["network_signature"],
                             second["branches"][branch]["network_signature"])
            row = first["branches"][branch]
            self.assertLessEqual(row["max_abs_conservation_error_bits"], 1.0)
            self.assertEqual(row["negative_queue_count"], 0)
            self.assertLessEqual(row["max_capacity_violation_bit_s"], 0.01)
        self.assertTrue(all(first["paired_identity"].values()))

    def test_gate_a_to_e0_frozen_hashes_are_unchanged(self):
        frozen = read("configs/gate_e1_frozen_a_to_e0_hashes.json")["files"]
        mismatches = [
            name for name, expected in frozen.items()
            if (not (PROJECT/name).is_file()
                or (sha(name) != expected
                    and not approved_runtime_phase1_change(
                        PROJECT, name, expected, sha(name))))]
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
