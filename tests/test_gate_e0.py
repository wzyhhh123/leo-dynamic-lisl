"""Gate E0 contract and harness correctness; no scientific sweep is run."""
import json
from pathlib import Path
import unittest

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.gate_d2_fixtures import (
    fixture_b_genuine_mbb, fixture_h_clone_base, fixture_h_switch_action)
from dynamic_lisl.load_aware_router import DeterministicLoadAwareRouter
from dynamic_lisl.mechanism_validation import (
    PairedCounterfactualHarness,
    REVERSAL_DEADBAND,
    break_even_brackets,
    refine_break_even,
    reversal_classification,
    setup_grid_plan,
    third_party_effect,
    with_total_setup,
)
from dynamic_lisl.scenario_selection import deterministic_select, kappa2_bin


PROJECT = Path(__file__).resolve().parents[1]


class GateE0Tests(unittest.TestCase):
    def test_registered_manifests_have_exact_frozen_domain(self):
        sweep = json.loads((PROJECT/"configs/gate_e0_sweep_manifest.json").read_text())
        selection = json.loads((PROJECT/"configs/gate_e0_scenario_selection_manifest.json").read_text())
        self.assertEqual(sweep["rho_grid"], [0.2, 0.5, 0.8, 1.0, 1.2])
        self.assertEqual(sweep["kappa1_targets"], [0.05, 0.2, 0.5, 1.0])
        self.assertEqual(sweep["kappa2_targets"], [0.05, 0.2, 0.5, 0.8])
        self.assertEqual(sweep["setup_grid_s"], [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0])
        self.assertEqual(sweep["delay_switch_ratios"], [0.0, 0.25, 0.5])
        self.assertEqual(sweep["numerical_reversal_deadband"], 1e-9)
        self.assertEqual(sweep["break_even_refinement_tolerance_s"], 0.01)
        self.assertFalse(sweep["scientific_sweep_executed_in_e0"])
        self.assertEqual(selection["result_fields_read"], [])

    def test_reversal_classifier_is_frozen_and_deadbanded(self):
        self.assertEqual(reversal_classification(100, 90, 110)["classification"],
                         "SETUP_INDUCED_DECISION_REVERSAL")
        self.assertEqual(reversal_classification(100, 110, 90)["classification"],
                         "REVERSE_DIRECTION_REVERSAL")
        self.assertEqual(reversal_classification(100, 90, 95)["classification"],
                         "NO_REVERSAL")
        self.assertEqual(reversal_classification(100, 100*(1+REVERSAL_DEADBAND/2), 110)["classification"],
                         "NUMERICALLY_TIED")
        self.assertEqual(reversal_classification(0, 0, 0)["classification"],
                         "UNDEFINED_ZERO_HOLD_OBJECTIVE")

    def test_setup_plan_and_break_even_rules_do_not_assume_monotonicity(self):
        grid = [0, 0.5, 1, 2, 4, 8, 16]
        self.assertEqual([x["tau_setup_s"] for x in setup_grid_plan(grid)],
                         [float(x) for x in grid])
        self.assertTrue(all(x["status"] == "PLANNED_NOT_EXECUTED"
                            for x in setup_grid_plan(grid)))
        multiple = break_even_brackets([
            {"tau_setup_s": 0, "delta_J_bit_s": -1},
            {"tau_setup_s": 1, "delta_J_bit_s": 1},
            {"tau_setup_s": 2, "delta_J_bit_s": -1},
        ])
        self.assertEqual(multiple["status"], "MULTIPLE_BREAK_EVEN_INTERVALS")
        none = break_even_brackets([
            {"tau_setup_s": 0, "delta_J_bit_s": 1},
            {"tau_setup_s": 1, "delta_J_bit_s": 2},
        ])
        self.assertEqual(none["status"], "NO_BREAK_EVEN_IN_SCANNED_RANGE")
        refined = refine_break_even(lambda x: x-0.333, 0, 1, 0.01)
        self.assertLessEqual(refined["width_s"], 0.01)
        self.assertLessEqual(refined["interval_s"][0], 0.333)
        self.assertGreaterEqual(refined["interval_s"][1], 0.333)

    def test_result_blind_selection_is_lexicographic_and_reports_empty_strata(self):
        base = dict(scenario_class="E-A_BBM_NO_ROUTE", t0_s=1.0,
                    old_edge=["A", "B"], new_edge=["A", "C"],
                    terminal_ids=[["A", "D1"], ["C", "D2"]],
                    gate_c_legal=True, kappa2=0.05)
        result = deterministic_select([
            dict(base, scenario_id="z"), dict(base, scenario_id="a")])
        self.assertEqual(result["selected"][0]["scenario_id"], "a")
        self.assertEqual(result["result_fields_read"], [])
        self.assertTrue(any(x["status"] == "NO_ELIGIBLE_CASE"
                            for x in result["availability"]))
        with self.assertRaisesRegex(ValueError, "RESULT_FIELD_FORBIDDEN"):
            deterministic_select([dict(base, scenario_id="bad", j_hold=1.0)])

    def test_kappa2_boundary_contract(self):
        self.assertEqual(kappa2_bin(0.1), "low")
        self.assertEqual(kappa2_bin(0.35), "medium")
        self.assertEqual(kappa2_bin(0.7), "high")
        self.assertEqual(kappa2_bin(0.70001), "very_high")
        self.assertIsNone(kappa2_bin(0.0))
        self.assertIsNone(kappa2_bin(1.0))

    def test_load_aware_router_is_current_state_only_and_deterministic(self):
        router = DeterministicLoadAwareRouter(
            utilization_penalty_s=1.0, queue_penalty_s=0.0)
        edges = (("A", "B"), ("B", "D"), ("A", "C"), ("C", "D"))
        delay = lambda edge, time_s: 1.0
        with self.assertRaisesRegex(ValueError, "SNAPSHOT_REQUIRED"):
            router.path("A", "D", edges, delay, 0.0)
        router.update_current_state(0.0, {("A", "B"): 1.0, ("B", "D"): 1.0})
        self.assertEqual(router.path("A", "D", edges, delay, 0.0), ("A", "C", "D"))
        self.assertEqual(router.path("A", "D", reversed(edges), delay, 0.0),
                         ("A", "C", "D"))
        with self.assertRaisesRegex(ValueError, "STALE_OR_FUTURE"):
            router.path("A", "D", edges, delay, 1.0)
        routes = router.routes_to_destinations(
            ("A", "B", "C", "D"), (Commodity("f", "A", "D"),),
            edges, delay, 0.0)
        self.assertEqual(routes[("A", "f")], ("A", "C", "D"))

    def test_zero_setup_real_equals_ideal_and_same_target(self):
        action = with_total_setup(fixture_h_switch_action(), 0.0, "REAL_ZERO")
        paired = PairedCounterfactualHarness(
            fixture_h_clone_base(), 1.0, action, 20.0).run()
        real = paired["branches"]["REAL_SWITCH"]
        ideal = paired["branches"]["IDEAL_SWITCH"]
        self.assertEqual(real["status"], "EXECUTED")
        self.assertEqual(ideal["status"], "EXECUTED")
        self.assertAlmostEqual(real["J_bit_s"], ideal["J_bit_s"], delta=1e-6)
        self.assertEqual(real["network_signature"], ideal["network_signature"])
        self.assertTrue(paired["same_target_real_ideal"])
        self.assertTrue(paired["all_pre_action_state_hashes_equal"])
        self.assertTrue(paired["all_future_trace_hashes_equal"])

    def test_clone_identity_and_hold_canonical_replay(self):
        base = fixture_h_clone_base().advance_to(1.0)
        first = base.clone(); second = base.clone()
        self.assertEqual(first.canonical_state_sha256(), second.canonical_state_sha256())
        a = PairedCounterfactualHarness(
            base, 1.0, fixture_h_switch_action(), 20.0)._branch("HOLD")
        b = PairedCounterfactualHarness(
            base, 1.0, fixture_h_switch_action(), 20.0)._branch("HOLD")
        self.assertEqual(a["J_bit_s"], b["J_bit_s"])
        self.assertEqual(a["network_signature"], b["network_signature"])

    def test_real_and_ideal_reject_hidden_objective_penalty(self):
        action = fixture_h_switch_action()
        action.proposal["switch_penalty"] = 1.0
        with self.assertRaisesRegex(ValueError, "HIDDEN_OBJECTIVE_PENALTY"):
            with_total_setup(action, 0.0)

    def test_delayed_switch_does_not_replace_infeasible_candidate(self):
        paired = PairedCounterfactualHarness(
            fixture_h_clone_base(), 1.0, fixture_h_switch_action(), 40.0).run(
                delayed_ratios=(0.5,), demand_timescale_s=60.0)
        delayed = paired["branches"]["DELAYED_SWITCH_0.5"]
        self.assertEqual(delayed["status"], "INFEASIBLE_AT_EXECUTION_TIME")
        self.assertEqual(delayed["target_signature"],
                         paired["branches"]["REAL_SWITCH"]["target_signature"])

    def test_excessive_setup_has_registered_infeasible_status(self):
        action = with_total_setup(fixture_h_switch_action(), 40.0, "TOO_SLOW")
        paired = PairedCounterfactualHarness(
            fixture_h_clone_base(), 1.0, action, 50.0).run()
        self.assertEqual(paired["branches"]["REAL_SWITCH"]["status"],
                         "INFEASIBLE_SETUP_EXCEEDS_WINDOW")

    def test_optional_mbb_alias_uses_same_registered_target(self):
        base = fixture_b_genuine_mbb()
        action = base.actions[0]
        base.actions = ()
        paired = PairedCounterfactualHarness(base, 1.0, action, 30.0).run(
            include_mbb_alias=True)
        mbb = paired["branches"]["MBB_SWITCH"]
        real = paired["branches"]["REAL_SWITCH"]
        self.assertEqual(mbb["status"], "EXECUTED")
        self.assertEqual(mbb["target_signature"], real["target_signature"])
        self.assertEqual(mbb["network_signature"], real["network_signature"])

    def test_third_party_effect_is_per_commodity_without_double_counting(self):
        result = third_party_effect(
            {"focus": 10.0, "third": 20.0},
            {"focus": 8.0, "third": 25.0}, {"focus"})
        self.assertEqual(result["delta_J_focus_bit_s"], -2.0)
        self.assertEqual(result["delta_J_third_bit_s"], 5.0)
        self.assertEqual(sum(result["delta_J_by_commodity_bit_s"].values()), 3.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
