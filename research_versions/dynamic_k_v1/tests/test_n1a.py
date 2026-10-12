"""Analytical engineering fixtures; their finite T values are not science freezes."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import unittest

VERSION = Path(__file__).resolve().parents[1]
PROJECT = VERSION.parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
sys.path.insert(0, str(VERSION))
from runtime.n1a import (TerminalEnergyLedger, FixedHorizonEvaluator,
                         validate_measurement, EXECUTION_STATES, POWER_W)
from dynamic_lisl.terminal_executor import TerminalExecutor, Connect, Disconnect
from dynamic_lisl.transition_service_orchestrator import TransitionAwareNetworkServiceEngine
from dynamic_lisl.traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from dynamic_lisl.commodity import Commodity

NODES = tuple(f'S{i:03d}' for i in range(160))
A, B, C = ((s, 'D1') for s in NODES[:3])
A2, C2 = (NODES[0], 'D2'), (NODES[2], 'D2')
EXAMPLES = {}
EVIDENCE = None  # Set by the acceptance runner after verifying the pinned manifest.


def engine(*, rate=10., connected=True, dynamic=False, weight=1., expiry=100.):
    ex = TerminalExecutor(NODES)
    if dynamic:
        ex.submit([Connect(A, B, expiry, 0., 0., 0.)])
    trace = PiecewiseConstantTrafficTrace(('f',), [TrafficSegment(0., 1., {'f': rate})])
    return TransitionAwareNetworkServiceEngine(
        NODES, ((NODES[0], NODES[1]),) if connected and not dynamic else (),
        100., (Commodity('f', NODES[0], NODES[1], weight),), trace,
        lambda edge, now: 1., ex)


def evaluator(e, T=10.):
    return FixedHorizonEvaluator(e, T_s=T, time_tolerance_s=1e-9,
                                energy_tolerance_J=1e-6, business_tolerance_bits=1e-6,
                                evidence_binding=EVIDENCE)


def check_ledger(test, ledger, ex, T, expected_delta):
    ex.advance(T)
    ledger.capture(ex)
    m = ledger.metrics()
    test.assertAlmostEqual(m['E_LCT_J'], 1600*T+expected_delta, places=7)
    test.assertAlmostEqual(m['DeltaE_LCT_J'], expected_delta, places=7)
    for row in m['per_terminal_execution_dwell_s']:
        test.assertAlmostEqual(sum(row['dwell_s'].values()), T, places=10)
    test.assertAlmostEqual(sum(m['five_execution_state_dwell_s'].values()), 320*T)
    return m


class N1aTests(unittest.TestCase):
    def test_01_all_320_idle_exact_1600T(self):
        for T in (1., 7.5, 1000.):
            with self.subTest(T=T):
                r = evaluator(engine(rate=0.), T).run()
                self.assertEqual(r['E_LCT_J'], 1600*T)
                self.assertEqual(r['DeltaE_LCT_J'], 0.)
                self.assertEqual(r['five_execution_state_dwell_s']['IDLE'], 320*T)
        EXAMPLES['all_idle_T_7_5'] = evaluator(engine(rate=0.), 7.5).run()

    def test_02_single_terminal_sequence_and_bilateral_energy_hand_check(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        ex.advance(1.)
        ex.submit([Connect(A, B, 20., 2., 4., 3.)])
        # Both remain RETARGETING until bilateral completion at 5; acquire to 8.
        # Each endpoint: idle1 + retarget4 + acquire3 + active2 = 375 J.
        m = check_ledger(self, ledger, ex, 10., 2*(375.-50.))
        row = next(r for r in m['per_terminal_execution_dwell_s'] if r['terminal_id'] == list(A))
        self.assertEqual(row['dwell_s'], dict(IDLE=1., RETARGETING=4., ACQUIRING=3.,
                                             ACTIVE=2., DRAINING=0.))
        self.assertEqual(sum(POWER_W[k]*v for k, v in row['dwell_s'].items()), 375.)
        EXAMPLES['known_sequence_T_10'] = m

    def test_03_draining_45W_excluded_from_main_K(self):
        ex = TerminalExecutor(NODES)
        ex.submit([Connect(A, B, 50., 0., 0., 0.)])
        ledger = TerminalEnergyLedger(ex)
        ex.start_tx(A, 5.)
        ex.advance(1.)
        ex.submit([Disconnect(A, B)])
        m = check_ledger(self, ledger, ex, 10., 2*5*40.)
        at_one = next(s for s in m['K_time_series'] if s['t_s'] == 1.)
        self.assertEqual((at_one['K_active_admissible'], at_one['K_draining']), (0, 1))
        self.assertEqual(m['five_execution_state_dwell_s']['DRAINING'], 8.)
        self.assertEqual(m['four_energy_state_dwell_s']['ACTIVE'], 10.)

    def test_04_every_terminal_and_total_time_including_fractional_events(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        ex.submit([Connect(A, B, 2.1, .3, .7, .2)])
        m = check_ledger(self, ledger, ex, 7.7, 2*(.9*35.+1.2*40.))
        self.assertGreaterEqual(m['DeltaE_LCT_J'], 0.)

    def test_05_traffic_drains_at_2_but_evaluation_reaches_10(self):
        old = engine(dynamic=True, expiry=6.)
        self.assertEqual(old.run(10.)['metrics']['evaluation_end_s'], 2.)
        r = evaluator(engine(dynamic=True, expiry=6.)).run()
        self.assertEqual(r['simulated_until_s'], 10.)
        self.assertTrue(r['evaluation_completed_normally'])
        self.assertTrue(r['all_offered_business_delivered'])
        self.assertEqual(r['E_LCT_J'], 16000.+2*6*40.)
        self.assertEqual(r['J_T_bit_s'], 10.)
        self.assertEqual(r['N_T_bits'], 0.)
        self.assertEqual(r['R_del_T'], 1.)
        self.assertIsNone(r['mean_delivered_fluid_delay_s'])
        EXAMPLES['early_drained_T_10'] = r

    def test_06_initial_active_no_fake_setup_energy_or_actions(self):
        e = engine(rate=0., dynamic=True)
        history = deepcopy(e.executor.log)
        r = evaluator(e).run()
        self.assertEqual(e.executor.log, history)
        self.assertEqual(r['E_LCT_J'], 16800.)
        self.assertEqual(r['five_execution_state_dwell_s']['RETARGETING'], 0.)
        self.assertEqual(r['five_execution_state_dwell_s']['ACQUIRING'], 0.)
        self.assertEqual(r['K_time_series'][0]['K_active_admissible'], 1)

    def test_07a_real_add_drop_and_tail_without_events(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        ex.advance(1.)
        ex.submit([Connect(A, B, 50., 1., 1., 1.)])
        ex.advance(4.)
        ex.submit([Disconnect(A, B)])
        m = check_ledger(self, ledger, ex, 10., 2*(2*35.+40.))
        self.assertEqual(m['K_time_series'][-1]['K_active_admissible'], 0)

    def test_07b_real_BBM_draining_wait_and_asymmetric_setup(self):
        ex = TerminalExecutor(NODES)
        ex.submit([Connect(A, B, 50., 0., 0., 0.)])
        ledger = TerminalEnergyLedger(ex)
        ex.start_tx(A, 4.)
        ex.advance(1.)
        ex.submit([Connect(A, C, 50., 2., 1., 1.)])
        # A/B active-or-drain0..4; A setup4..7, C setup1..7; A/C active7..10.
        m = check_ledger(self, ledger, ex, 10., 8*40.+9*35.+6*40.)
        self.assertEqual(m['five_execution_state_dwell_s']['DRAINING'], 6.)
        reserved = next(s for s in m['K_time_series'] if s['t_s'] == 1.)
        self.assertEqual(reserved['setup_terminal_count'], 1)
        self.assertEqual(reserved['setup_reserved_terminal_count'], 2)

    def test_07c_real_MBB_overlapping_energy_and_release(self):
        ex = TerminalExecutor(NODES)
        ex.submit([Connect(A, B, 50., 0., 0., 0.)])
        ledger = TerminalEnergyLedger(ex)
        ex.start_tx(A, 6.)
        ex.advance(1.)
        ex.submit([Connect(A2, C2, 50., 1., 1., 1., release_after=((A, B),))])
        # Old endpoints0..6 active/drain; new endpoints setup1..3, active3..10.
        m = check_ledger(self, ledger, ex, 10., 12*40.+4*35.+14*40.)
        at_three = next(s for s in m['K_time_series'] if s['t_s'] == 3.)
        self.assertEqual((at_three['K_active_admissible'], at_three['K_draining']), (1, 1))

    def test_07d_setup_abort_stale_events_not_double_charged(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        ex.submit([Connect(A, B, 30., 2., 2., 2.)])
        ex.advance(1.)
        ex.expire_visibility(A, B)
        m = check_ledger(self, ledger, ex, 10., 2*35.)
        self.assertEqual(m['five_execution_state_dwell_s']['ACTIVE'], 0.)
        self.assertTrue(any(x['event'] == 'ABORT' for x in ex.log))

    def test_07e_natural_expiry_and_no_traffic_advance_terminal_events(self):
        r = evaluator(engine(rate=0., dynamic=True, expiry=3.)).run()
        self.assertEqual(r['E_LCT_J'], 16000.+2*3*40.)
        self.assertEqual(r['K_time_series'][-1]['K_active_admissible'], 0)

    def test_08_same_timestamp_zero_setup_and_release_no_duplicate_dwell(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        ex.submit([Connect(A, B, 5., 0., 0., 0.)])
        m = check_ledger(self, ledger, ex, 10., 10*40.)
        self.assertEqual(m['five_execution_state_dwell_s']['RETARGETING'], 0.)
        times = [s['t_s'] for s in m['K_time_series']]
        self.assertEqual(times, sorted(set(times)))

    def test_09_unfinished_traffic_normal_T_and_analytical_J_N(self):
        r = evaluator(engine(connected=False), 4.).run()
        self.assertTrue(r['evaluation_completed_normally'])
        self.assertFalse(r['all_offered_business_delivered'])
        self.assertEqual(r['N_T_bits'], 10.)
        self.assertEqual(r['J_T_bit_s'], 5.+3*10.)
        self.assertEqual(r['R_del_T'], 0.)
        self.assertEqual(r['E_LCT_J'], 6400.)
        EXAMPLES['partition_remaining_T_4'] = r

    def test_10_clone_restore_replay_identical_and_no_double_accounting(self):
        v = evaluator(engine(dynamic=True, expiry=6.))
        v.advance_to(.5)
        checkpoint = v.checkpoint()
        a = v.run()
        self.assertEqual(a, checkpoint.clone().run())
        self.assertEqual(a, FixedHorizonEvaluator.restore(checkpoint).run())
        self.assertEqual(a, evaluator(engine(dynamic=True, expiry=6.)).run())
        self.assertEqual(a, v.run())
        self.assertEqual(checkpoint.engine.now, .5)

    def test_11_incremental_energy_nonnegative_across_finite_horizons(self):
        for T in (1., 2.3, 10., 1000.):
            for expiry in (2., 7.):
                r = evaluator(engine(rate=0., dynamic=True, expiry=expiry), T).run()
                self.assertGreaterEqual(r['DeltaE_LCT_J'], 0.)
                self.assertLessEqual(r['E_LCT_J'], 320*45*T)

    def test_12_numeric_and_cross_field_tampering_rejected(self):
        good = evaluator(engine(dynamic=True)).run()
        mutations = (
            ('E_LCT_J', math.nan), ('DeltaE_LCT_J', -1.), ('E_LCT_J', math.inf),
            ('E_LCT_J', 0.), ('R_del_T', 2.), ('N_T_bits', 5.), ('J_T_bit_s', -1.),
            ('evaluation_completed_normally', False), ('all_offered_business_delivered', False),
            ('delivered_bits', 20.), ('mean_delivered_fluid_delay_s', 1.),
            ('termination_reason', 'COMPLETE'), ('dynamic_terminal_count', 319))
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                bad = deepcopy(good)
                bad[key] = value
                with self.assertRaises(ValueError):
                    validate_measurement(bad)
        for change in ('per_terminal', 'aggregate', 'K', 'setup', 'reservation', 'duplicate_time'):
            with self.subTest(change=change):
                bad = deepcopy(good)
                if change == 'per_terminal':
                    bad['per_terminal_execution_dwell_s'][0]['dwell_s']['IDLE'] += 1.
                elif change == 'aggregate':
                    bad['four_energy_state_dwell_s']['ACTIVE'] += 1.
                elif change == 'K':
                    bad['K_time_series'][0]['K_active_admissible'] = 2
                elif change == 'setup':
                    bad['K_time_series'][0]['setup_terminal_count'] = 1
                elif change == 'reservation':
                    bad['K_time_series'][0]['setup_reserved_terminal_count'] = 1
                else:
                    bad['K_time_series'].insert(0, deepcopy(bad['K_time_series'][0]))
                with self.assertRaises(ValueError):
                    validate_measurement(bad)

    def test_13_unweighted_J_independent_of_legacy_commodity_weights(self):
        r = evaluator(engine(weight=7.)).run()
        self.assertEqual(r['J_T_bit_s'], 10.)

    def test_14_initial_pending_setup_actual_remaining_time(self):
        e = engine(rate=0., connected=False)
        e.executor.submit([Connect(A, B, 50., 2., 2., 1.)])
        r = evaluator(e).run()
        self.assertEqual(r['E_LCT_J'], 16000.+6*35.+14*40.)

    def test_15_log_loss_rewrite_inventory_gap_and_unlogged_state_rejected(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        ex.submit([Connect(A, B, 50., 1., 1., 1.)])
        ledger.capture(ex)
        ex.log[0]['event'] = 'TAMPERED'
        with self.assertRaisesRegex(ValueError, 'HISTORY'):
            ledger.capture(ex)
        ex2 = TerminalExecutor(NODES)
        ledger2 = TerminalEnergyLedger(ex2)
        ex2.terminals[A].phase = 'RETARGETING'
        with self.assertRaisesRegex(ValueError, 'UNLOGGED'):
            ledger2.capture(ex2)
        ex3 = TerminalExecutor(NODES)
        ledger3 = TerminalEnergyLedger(ex3)
        ex3.submit([Connect(A, B, 50., 1., 1., 1.)])
        ex3.log[-1]['terminals'].pop()
        with self.assertRaisesRegex(ValueError, '320'):
            ledger3.capture(ex3)

    def test_16_horizon_bounds_and_input_mutation_rejected(self):
        for T in (None, 0., .5, math.inf, math.nan):
            with self.subTest(T=T), self.assertRaises(ValueError):
                evaluator(engine(), T)
        v = evaluator(engine())
        with self.assertRaises(ValueError):
            v.advance_to(11.)
        v.engine.trace.segments[0].rates_bit_s['f'] = 20.
        with self.assertRaisesRegex(ValueError, 'INPUT_TRACE_CHANGED'):
            v.run()

    def test_17_partial_checkpoint_is_not_normal_T(self):
        r = evaluator(engine()).advance_to(.5)
        self.assertFalse(r['evaluation_completed_normally'])
        self.assertFalse(r['terminal_accounting_covers_0_T'])
        self.assertFalse(r['all_offered_business_delivered'])

    def test_18_rejected_command_has_no_phantom_energy(self):
        ex = TerminalExecutor(NODES)
        ledger = TerminalEnergyLedger(ex)
        with self.assertRaises(ValueError):
            ex.submit([Connect(A, B, 1., 1., 1., 1.)])
        check_ledger(self, ledger, ex, 10., 0.)

    def test_19_D2_draining_keeps_real_propagation_and_residual_work(self):
        v = evaluator(engine(dynamic=True), 4.)
        v.advance_to(.5)
        v.engine.executor.start_tx(A, 1.5)
        v.engine.executor.submit([Disconnect(A, B)])
        r = v.run()
        self.assertEqual(r['delivered_bits'], 5.)
        self.assertEqual(r['N_T_bits'], 5.)
        self.assertEqual(r['R_del_T'], .5)
        self.assertEqual(r['J_T_bit_s'], 21.25)
        self.assertEqual(r['E_LCT_J'], 6520.)
        self.assertEqual(r['five_execution_state_dwell_s']['DRAINING'], 2.)
        self.assertTrue(r['evaluation_completed_normally'])
        self.assertFalse(r['all_offered_business_delivered'])
        EXAMPLES['real_D2_draining_partial_delivery_T_4'] = r

    def test_20_initial_draining_actual_remaining_phase_no_fake_setup(self):
        e = engine(rate=0., dynamic=True)
        e.executor.start_tx(A, 2.)
        e.executor.submit([Disconnect(A, B)])
        r = evaluator(e, 4.).run()
        self.assertEqual(r['E_LCT_J'], 6400.+4*40.)
        self.assertEqual(r['K_time_series'][0]['K_active_admissible'], 0)
        self.assertEqual(r['K_time_series'][0]['K_draining'], 1)
        self.assertEqual(r['five_execution_state_dwell_s']['DRAINING'], 4.)

    def test_21_wrong_implementation_anchor_rejected_before_execution(self):
        from runtime.bindings import EngineeringBinding
        bad = EngineeringBinding(EVIDENCE.project_root, EVIDENCE.manifest_path, '0'*64)
        e = engine()
        with self.assertRaisesRegex(ValueError, 'ANCHOR_MISMATCH'):
            FixedHorizonEvaluator(e, T_s=10., time_tolerance_s=1e-9,
                                  energy_tolerance_J=1e-6, business_tolerance_bits=1e-6,
                                  evidence_binding=bad)
        self.assertEqual(e.now, 0.)


if __name__ == '__main__':
    unittest.main()
