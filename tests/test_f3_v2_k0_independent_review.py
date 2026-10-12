"""Independent actual-physics enumeration and tiny proof, no natural K choice."""
from dataclasses import replace
from unittest.mock import patch
import unittest
from dynamic_lisl.f3_v2.k0_fixture import fixture
from dynamic_lisl.f3_v2.k0_snapshot import produce_snapshot, SnapshotBudget
from dynamic_lisl.f3_v2.k0_independent_review import IndependentReviewBudget, review_point
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility


def check(bundle, args, budget=None):
    return review_point(bundle['snapshot'], {k: bundle[k] for k in ('solver', 'physical', 'inventory', 'lifetime')},
        **{k: args[k] for k in ('nodes', 'fixed_edges', 'plane_by_satellite', 'physical_layer', 'setup', 'input_hashes')},
        budget=budget or IndependentReviewBudget(100, 1000, 10.))


class K0IndependentReviewTests(unittest.TestCase):
    def test_three_real_points_independent_complete_enumeration(self):
        for t in (0, 30, 570):
            with self.subTest(time_s=t):
                args, _ = fixture()
                bundle = produce_snapshot(**args, K=4, time_s=t)
                with patch('dynamic_lisl.f3_v2.k0_snapshot.produce_snapshot', side_effect=AssertionError('producer forbidden')), \
                     patch('dynamic_lisl.f3_v2.candidate_source.replacement_inventory', side_effect=AssertionError('source forbidden')), \
                     patch('dynamic_lisl.f3_v2.structural.deterministic_lexicographic_topology', side_effect=AssertionError('builder forbidden')), \
                     patch('dynamic_lisl.f3_v2.certified_topology.certified_bound_topology', side_effect=AssertionError('builder forbidden')):
                    result = check(bundle, args)
                self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_PASS', result)
                self.assertEqual(result['progress']['physical_evaluations'], 36)
                self.assertEqual(result['progress']['subset_evaluations'], 325)
                for key in ('idle_inventory_replayed', 'uncapped_replacements_replayed',
                            'matching_independently_proved', 'topology_independently_proved'):
                    self.assertTrue(result['progress'][key])
                self.assertFalse(result['Gate_K0_PASS'])
                self.assertFalse(result['K_star_selected'])
                self.assertFalse(result['asset_generation_verified'])

    def test_changed_catalogue_detected_even_when_support_is_consistent(self):
        args, scene = fixture()
        bundle = produce_snapshot(**args, K=4, time_s=0)
        args['physical_layer'] = TerminalPairPhysicalFeasibility(TerminalPairCatalog(
            [TerminalPairWindow(**w) for w in scene['windows'][1:]], args['plane_by_satellite']))
        result = check(bundle, args)
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_FAIL_STOP')
        self.assertEqual(result['reason'], 'INDEPENDENT_IDLE_CATALOGUE_MISMATCH')

    def test_exact_context_binding(self):
        args, _ = fixture()
        bundle = produce_snapshot(**args, K=4, time_s=0)
        args['input_hashes'] = {'other_fixture': 'a' * 64}
        result = check(bundle, args)
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_FAIL_STOP')
        self.assertEqual(result['reason'], 'INDEPENDENT_REVIEW_CONTEXT_MISMATCH:INPUT_HASHES')

    def test_physical_cap_does_not_accept_prefix(self):
        args, _ = fixture()
        bundle = produce_snapshot(**args, K=4, time_s=0)
        result = check(bundle, args, IndependentReviewBudget(9, 1000, 10.))
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_UNKNOWN')
        self.assertEqual(result['stage'], 'UNCAPPED_REPLACE_REPLAY')
        self.assertEqual(result['progress']['physical_evaluations'], 9)
        self.assertTrue(result['progress']['idle_inventory_replayed'])
        self.assertFalse(result['progress']['uncapped_replacements_replayed'])

    def test_subset_cap_does_not_promote_incumbent(self):
        args, _ = fixture()
        bundle = produce_snapshot(**args, K=4, time_s=0)
        result = check(bundle, args, IndependentReviewBudget(100, 256, 10.))
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_UNKNOWN')
        self.assertEqual(result['stage'], 'EXHAUSTIVE_TOPOLOGY_PROOF')
        self.assertTrue(result['progress']['matching_independently_proved'])
        self.assertFalse(result['progress']['topology_independently_proved'])

    def test_infeasible_upper_bound_is_independently_proved(self):
        args, _ = fixture()
        bundle = produce_snapshot(**args, K=16, time_s=0)
        result = check(bundle, args)
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_PASS', result)
        self.assertTrue(result['progress']['matching_independently_proved'])
        self.assertTrue(result['progress']['topology_independently_proved'])
        self.assertFalse(result['progress']['uncapped_replacements_replayed'])
        self.assertEqual(result['progress']['physical_evaluations'], 8)

    def test_unknown_solver_stays_unknown(self):
        args, _ = fixture()
        args['budget'] = SnapshotBudget(1, 5., 1, 5.)
        bundle = produce_snapshot(**args, K=4, time_s=0)
        result = check(bundle, args)
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_UNKNOWN')
        self.assertEqual(result['reason'], 'SUPPLIED_SOLVER_UNKNOWN')

    def test_explicit_budgets_and_wall_exhaustion(self):
        for values in ((0, 1, 1.), (1, 0, 1.), (1, 1, float('inf'))):
            with self.assertRaises(ValueError):
                IndependentReviewBudget(*values)
        args, _ = fixture()
        bundle = produce_snapshot(**args, K=4, time_s=0)
        result = check(bundle, args, IndependentReviewBudget(100, 1000, 1e-12))
        self.assertEqual(result['status'], 'INDEPENDENT_POINT_REVIEW_UNKNOWN')
        self.assertEqual(result['reason'], 'INDEPENDENT_REVIEW_WALL_BUDGET')


if __name__ == '__main__':
    unittest.main()
