"""Contract-only tests; synthetic terminal timing, no topology/performance audit."""
from copy import deepcopy
import unittest

from tools.check_gate_k0_v1_1_revision import (
    NEW_TIMES, OLD_TIMES, bounded_lifetime, build_draft, digest, threshold_table,
)
from dynamic_lisl.terminal_executor import Connect, TerminalExecutor
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow


def engine_with_old_tx():
    engine = TerminalExecutor('ABC')
    engine.submit([Connect(('A', 'D1'), ('B', 'D1'), 600.0, 0.0, 0.0, 0.0)])
    engine.advance(570.0)
    engine.start_tx(('A', 'D1'), 575.0)
    return engine


def catalog(a=('A', 'D1'), b=('C', 'D1'), end=600.0, censored=True):
    window = TerminalPairWindow(a[0], a[1], b[0], b[1], 0.0, end,
                                right_censored=censored)
    return TerminalPairCatalog([window], {'A': 0, 'B': 1, 'C': 2})


class K0V11ContractTests(unittest.TestCase):
    def test_schedule_is_twenty_samples_and_last_idle_ready_is_572(self):
        self.assertEqual(len(OLD_TIMES), 21)
        self.assertEqual(NEW_TIMES, list(range(0, 571, 30)))
        self.assertEqual(len(NEW_TIMES), 20)
        self.assertEqual(NEW_TIMES[-1] + 2, 572)
        self.assertTrue(all(0 <= t < t+2 < 600 for t in NEW_TIMES))

    def test_threshold_proportion_and_unchanged_bands(self):
        table = threshold_table()
        for row in table['rows'][:2]:
            self.assertEqual(row['old_fraction'], row['proposed_fraction'])
        for row in table['rows'][2:5]:
            self.assertEqual((row['proposed_numerator'], row['proposed_denominator']), (18, 20))
            self.assertGreater(row['proposed_fraction'], row['old_fraction'])
        self.assertEqual(table['rows'][5]['old_band'], table['rows'][5]['proposed_band'])
        self.assertEqual(table['rows'][6]['proposed_replays'], 2)

    def test_natural_end_metric(self):
        metric = bounded_lifetime({'end_s': 580.0, 'right_censored': False}, 572.0)
        self.assertEqual(metric['L_usable_within_horizon_s'], 8.0)
        self.assertEqual(metric['t_physical_end_s'], 580.0)
        self.assertEqual(metric['censor_flag'], 'KNOWN_NATURAL_END')

    def test_censored_end_does_not_become_natural_expiry(self):
        metric = bounded_lifetime({'end_s': 600.0, 'right_censored': True}, 572.0)
        self.assertEqual(metric['L_usable_within_horizon_s'], 28.0)
        self.assertIsNone(metric['t_physical_end_s'])
        self.assertEqual(metric['censor_flag'], 'RIGHT_CENSORED_AT_600')
        known = bounded_lifetime({'end_s': 600.0, 'right_censored': False}, 572.0)
        self.assertEqual(known['t_physical_end_s'], 600.0)

    def test_metric_zero_is_not_a_legality_override(self):
        self.assertEqual(bounded_lifetime({'end_s': 580.0, 'right_censored': False}, 580.0)
                         ['L_usable_within_horizon_s'], 0.0)
        with self.assertRaisesRegex(ValueError, 'CENSOR_BOUNDARY'):
            bounded_lifetime({'end_s': 590.0, 'right_censored': True}, 572.0)

    def test_actual_idle_ready_and_gate_c_lifetime(self):
        engine = TerminalExecutor('ABC')
        engine.advance(570.0)
        original = deepcopy(engine.__dict__)
        _, geometry = catalog().connect_command(engine, ('A', 'D1'), ('C', 'D1'), 1, 1, 1)
        self.assertEqual(geometry['ready_time'], 572.0)
        self.assertEqual(geometry['usable_lifetime_s'], 28.0)
        self.assertEqual(engine.__dict__, original)

    def test_actual_bbm_waits_for_nonpreemptive_tx(self):
        engine = engine_with_old_tx()
        original = deepcopy(engine.__dict__)
        _, geometry = catalog().connect_command(engine, ('A', 'D1'), ('C', 'D1'), 1, 1, 1)
        self.assertEqual(geometry['ready_time'], 577.0)
        self.assertEqual(geometry['usable_lifetime_s'], 23.0)
        self.assertEqual(engine.__dict__, original)

    def test_actual_mbb_spare_terminals_do_not_wait_for_old_tx(self):
        engine = engine_with_old_tx()
        old = (('A', 'D1'), ('B', 'D1'))
        original = deepcopy(engine.__dict__)
        _, geometry = catalog(('A', 'D2'), ('C', 'D1')).connect_command(
            engine, ('A', 'D2'), ('C', 'D1'), 1, 1, 1, release_after=(old,))
        self.assertEqual(geometry['ready_time'], 572.0)
        self.assertEqual(engine.__dict__, original)

    def test_strict_natural_expiry_and_original_epsilon(self):
        engine = TerminalExecutor('ABC')
        engine.advance(570.0)
        for end in (571.0, 572.0, 572.0 + 0.5e-9):
            with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_LIFETIME'):
                catalog(end=end, censored=False).connect_command(
                    engine, ('A', 'D1'), ('C', 'D1'), 1, 1, 1)
        with self.assertRaises(ValueError):
            catalog(end=570.0, censored=False).connect_command(
                engine, ('A', 'D1'), ('C', 'D1'), 1, 1, 1)

    def test_long_drain_cannot_be_certified_beyond_right_censor(self):
        engine = engine_with_old_tx()
        engine.advance(576.0)
        engine.start_tx(('A', 'D1'), 599.0)
        original = deepcopy(engine.__dict__)
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_LIFETIME'):
            catalog().connect_command(engine, ('A', 'D1'), ('C', 'D1'), 1, 1, 1)
        self.assertEqual(engine.__dict__, original)

    def test_draft_is_not_freeze_and_does_not_mutate_parent(self):
        parent = {'canonical_sha256': 'historical',
                  'snapshot_times_s': OLD_TIMES,
                  'admissibility': {'connected_and_bridges_lt_edges_snapshots': 18,
                                   'replace_ge_16_snapshots': 18,
                                   'MBB_ge_8_and_BBM_ge_8_snapshots': 18},
                  'lexicographic_objectives': ['first', 'second', 'third', 'fourth', 'fifth']}
        original = deepcopy(parent)
        draft = build_draft(parent)
        self.assertEqual(parent, original)
        self.assertEqual(draft['status'], 'DRAFT_NOT_FROZEN')
        self.assertFalse(draft['frozen'])
        self.assertFalse(draft['K_star_selected'])
        self.assertEqual(draft['admissibility']['snapshot_denominator'], 20)
        self.assertEqual(digest({k: v for k, v in draft.items() if k != 'draft_canonical_sha256'}),
                         draft['draft_canonical_sha256'])


if __name__ == '__main__':
    unittest.main()
