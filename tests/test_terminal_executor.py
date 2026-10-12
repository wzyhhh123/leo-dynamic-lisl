"""Deterministic Gate B resource/lifecycle acceptance tests; synthetic TX only."""
import unittest
from copy import deepcopy
from dynamic_lisl.terminal_executor import (
    TerminalExecutor, Connect, Keep, Disconnect, IDLE, ACTIVE, DRAINING, RETARGETING, ACQUIRING)

TRACES = []
A, B, C, D, E, F = ((s, 'D1') for s in 'ABCDEF')
A2, B2, C2, D2 = ((s, 'D2') for s in 'ABCD')


class GateBTests(unittest.TestCase):
    def setUp(self):
        self.engines = []
        self.e = self.engine()

    def engine(self):
        e = TerminalExecutor('ABCDEF')
        self.engines.append(e)
        return e

    def tearDown(self):
        for e in self.engines:
            e.assert_invariants()
        TRACES.append(dict(test=self.id(), runs=[dict(log=e.log, final=e.snapshot(),
                            invariant_checks=e.invariant_checks) for e in self.engines]))

    def active(self, a=A, b=B, end=100):
        self.e.submit([Connect(a, b, end, 0, 0, 0)])
        self.assertEqual(self.e.terminals[a].phase, ACTIVE)

    def unchanged_failure(self, commands):
        before = deepcopy(self.e.__dict__)
        with self.assertRaises(ValueError):
            self.e.submit(commands)
        self.assertEqual(before, self.e.__dict__)

    def test_normal_bilateral_ready_formula(self):
        self.e.submit([Connect(A, B2, 30, 2, 4, 3)])
        self.assertEqual(self.e.terminals[A].target_peer, B2)
        self.assertEqual(self.e.terminals[A].reservation_id, self.e.terminals[B2].reservation_id)
        self.e.advance(2)
        self.assertEqual(self.e.terminals[A].phase, RETARGETING)
        self.assertEqual(self.e.terminals[B2].phase, RETARGETING)
        self.e.advance(4)
        self.assertEqual(self.e.terminals[A].phase, ACQUIRING)
        self.assertEqual(self.e.terminals[B2].acquisition_start, 4)
        self.e.advance(7)
        self.assertEqual(self.e.terminals[A].current_peer, B2)
        self.assertEqual(self.e.terminals[B2].current_peer, A)
        self.assertEqual(self.e.terminals[A].active_link_start, 7)
        self.assertFalse(self.e.reservations)

    def test_occupied_bbm_drain_last_reception(self):
        self.active()
        self.e.start_tx(A, 5)
        self.e.start_tx(B, 7)
        self.e.submit([Connect(A, C, 50, 2, 1, 3)])
        self.assertEqual(self.e.terminals[A].phase, DRAINING)
        self.assertEqual(self.e.terminals[B].phase, DRAINING)
        self.assertEqual(self.e.terminals[A].current_peer, B)
        self.assertEqual(self.e.terminals[A].target_peer, C)
        self.e.advance(6)
        self.assertEqual(self.e.terminals[A].current_peer, B)
        self.e.advance(7)
        self.assertIsNone(self.e.terminals[A].current_peer)
        self.assertEqual(self.e.terminals[B].phase, IDLE)
        self.assertEqual(self.e.terminals[A].retarget_start, 7)
        self.assertEqual(self.e.terminals[C].retarget_start, 0)
        self.e.advance(12)
        self.assertEqual(self.e.terminals[A].current_peer, C)
        events = [(x['time'], x['event']) for x in self.e.log]
        self.assertIn((7, 'LINK_DOWN'), events)
        self.assertIn((12, 'LINK_UP'), events)

    def test_two_occupied_endpoints_release_both_old_links(self):
        self.active(A, B)
        self.active(C, D)
        self.e.start_tx(A, 3)
        self.e.start_tx(D, 6)
        self.e.submit([Connect(A, C, 30, 4, 2, 1)])
        self.e.advance(3)
        self.assertEqual(self.e.terminals[B].phase, IDLE)
        self.assertEqual(self.e.terminals[C].phase, DRAINING)
        self.e.advance(6)
        self.assertEqual(self.e.terminals[D].phase, IDLE)
        self.e.advance(9)
        self.assertEqual(self.e.terminals[A].current_peer, C)
        self.assertEqual(len(self.e.links), 1)

    def test_mbb_idle_second_terminals_link_up_before_drain(self):
        self.active()
        self.e.start_tx(A, 9)
        self.e.submit([Connect(A2, C2, 40, 2, 3, 1, release_after=((A, B),))])
        self.e.advance(3)
        self.assertEqual(self.e.terminals[A].phase, ACTIVE)
        self.e.start_tx(B, 8)
        self.e.advance(4)
        self.assertEqual(self.e.terminals[A2].phase, ACTIVE)
        self.assertEqual(self.e.terminals[A].phase, DRAINING)
        self.e.advance(9)
        self.assertEqual(self.e.terminals[A].phase, IDLE)
        self.assertEqual(self.e.terminals[B].phase, IDLE)
        self.assertEqual(self.e.terminals[A2].current_peer, C2)
        up = next(k for k,x in enumerate(self.e.log) if x['event']=='LINK_UP' and x['time']==4)
        drain = next(k for k,x in enumerate(self.e.log) if x['event']=='DRAINING')
        self.assertLess(up, drain)

    def test_mbb_requires_two_truly_idle_endpoints(self):
        self.active()
        self.active(C2, D)
        self.unchanged_failure([Connect(A2, C2, 40, release_after=((A, B),))])

    def test_mbb_abort_keeps_old_link_and_unlocks_it(self):
        self.active()
        self.e.submit([Connect(A2, C2, 40, 2, 2, 4, release_after=((A, B),))])
        self.e.advance(3)
        self.e.expire_visibility(A2, C2)
        self.e.advance(6)
        self.assertEqual(self.e.terminals[A].phase, ACTIVE)
        self.assertEqual(self.e.terminals[A2].phase, IDLE)
        self.assertTrue(all(l.release_owner is None for l in self.e.links.values()))
        self.e.submit([Disconnect(A, B)])
        self.assertFalse(self.e.links)

    def test_mbb_old_link_dependency_cannot_be_stolen(self):
        self.active()
        self.e.submit([Connect(A2, C2, 40, release_after=((A, B),))])
        self.unchanged_failure([Disconnect(A, B)])
        self.unchanged_failure([Connect(B, D, 40)])

    def test_bilateral_reservation_conflict_either_endpoint(self):
        self.e.submit([Connect(A, B, 40, 3, 3, 1)])
        self.unchanged_failure([Connect(A, C, 40)])
        self.unchanged_failure([Connect(C, B, 40)])
        self.assertIsNone(self.e.terminals[C].reservation_id)

    def test_bilateral_disconnect(self):
        self.active()
        self.e.submit([Disconnect(A, B)])
        self.assertFalse(self.e.links)
        for x in (A, B):
            self.assertEqual(self.e.terminals[x].phase, IDLE)
            self.assertIsNone(self.e.terminals[x].current_peer)

    def test_draining_rejects_new_tx_both_directions(self):
        self.active()
        self.e.start_tx(A, 4)
        self.e.submit([Disconnect(A, B)])
        for x in (A, B):
            with self.assertRaises(ValueError):
                self.e.start_tx(x, 3)
        self.e.advance(4)
        self.assertTrue(any(x['event']=='TX_DONE' for x in self.e.log))
        self.assertFalse(self.e.links)

    def test_setup_cannot_change_target_retarget_or_acquiring(self):
        self.e.submit([Connect(A, B, 40, 2, 2, 3)])
        self.unchanged_failure([Connect(A, C, 40)])
        self.e.advance(2)
        self.unchanged_failure([Connect(A, C, 40)])
        self.unchanged_failure([Disconnect(A, B)])

    def test_expiry_abort_during_retarget_releases_both(self):
        self.e.submit([Connect(A, B, 40, 5, 5, 2)])
        versions = [self.e.terminals[x].event_version for x in (A, B)]
        self.e.advance(1)
        self.e.expire_visibility(A, B)
        for x, old in zip((A, B), versions):
            self.assertEqual(self.e.terminals[x].phase, IDLE)
            self.assertIsNone(self.e.terminals[x].target_peer)
            self.assertIsNone(self.e.terminals[x].reservation_id)
            self.assertGreater(self.e.terminals[x].event_version, old)
        self.e.advance(40)
        self.assertFalse(self.e.links)

    def test_stale_link_ready_cannot_reactivate_reused_ports(self):
        self.e.submit([Connect(A, B, 40, 1, 1, 5)])
        self.e.advance(2)
        self.e.expire_visibility(A, B)
        self.e.submit([Connect(A, C, 40, 0, 0, 0)])
        self.e.advance(6)
        self.assertEqual(self.e.terminals[A].current_peer, C)
        self.assertEqual(self.e.terminals[B].phase, IDLE)
        self.assertTrue(any(x['event']=='STALE_EVENT' and x['details'].get('kind')=='LINK_READY' for x in self.e.log))

    def test_event_version_guard_rejects_wrong_token(self):
        self.e.submit([Connect(A, B, 40, 1, 1, 5)])
        self.e.advance(1)
        r = next(iter(self.e.reservations.values()))
        self.e._schedule(2, 4, 'LINK_READY', (r.reservation_id, tuple(v-1 for v in r.versions)))
        self.e.advance(2)
        self.assertFalse(self.e.links)
        self.e.advance(6)
        self.assertEqual(self.e.terminals[A].phase, ACTIVE)

    def test_known_short_visibility_and_equality_rejected_atomically(self):
        self.unchanged_failure([Connect(A, B, 2, 1, 1, 1)])
        self.unchanged_failure([Connect(A, B, 1, 1, 1, 1)])

    def test_natural_visibility_expiry_releases_active_pair(self):
        self.active(end=3)
        self.e.advance(3)
        self.assertFalse(self.e.links)
        self.assertEqual(self.e.terminals[A].phase, IDLE)
        self.assertEqual(self.e.terminals[B].phase, IDLE)

    def test_abort_while_draining_does_not_resurrect_old_admission(self):
        self.active()
        self.e.start_tx(A, 5)
        self.e.submit([Connect(A, C, 40)])
        self.e.advance(1)
        self.e.expire_visibility(A, C)
        self.assertEqual(self.e.terminals[A].phase, DRAINING)
        self.assertIsNone(self.e.terminals[A].reservation_id)
        self.assertEqual(self.e.terminals[C].phase, IDLE)
        self.e.advance(5)
        self.assertFalse(self.e.links)

    def test_repeated_keep_has_no_setup_or_version_change(self):
        self.active()
        before = self.e.snapshot()
        for _ in range(3):
            self.e.submit([Keep(B, A)])
        self.assertEqual(self.e.snapshot(), before)
        self.assertEqual(sum(x['event']=='RESERVE_BOTH' for x in self.e.log), 1)

    def test_same_peer_changed_terminal_is_bbm_and_new_setup(self):
        self.active()
        self.e.start_tx(B, 3)
        self.e.submit([Connect(A2, B2, 30, 1, 2, 1)])
        self.assertEqual(self.e.terminals[A].phase, DRAINING)
        self.assertEqual(self.e.terminals[A2].phase, IDLE)
        self.assertIsNotNone(self.e.terminals[A2].reservation_id)
        self.e.advance(3)
        self.assertFalse(self.e.links)
        self.e.advance(6)
        self.assertEqual(self.e.terminals[A2].current_peer, B2)
        self.assertEqual(self.e.terminals[A].phase, IDLE)
        self.assertEqual(sum(x['event']=='LINK_UP' for x in self.e.log), 2)

    def test_parallel_same_satellite_pair_mbb_rejected(self):
        self.active()
        self.unchanged_failure([Connect(A2, B2, 40, release_after=((A, B),))])

    def test_parallel_pending_same_satellite_pair_rejected(self):
        self.e.submit([Connect(A, B, 40)])
        self.unchanged_failure([Connect(A2, B2, 40)])

    def test_multiple_commands_atomic_failure_preserves_old_active(self):
        self.active()
        self.unchanged_failure([Connect(A, C, 40), Connect(D, C, 40)])
        self.assertEqual(self.e.terminals[A].phase, ACTIVE)
        self.assertEqual(self.e.terminals[B].current_peer, A)

    def test_multiple_commands_valid_disjoint_commit(self):
        self.e.submit([Connect(A, B, 40), Connect(C, D, 40)])
        self.assertEqual(len(self.e.reservations), 2)
        self.e.advance(2)
        self.assertEqual(len(self.e.links), 2)

    def test_other_dynamic_and_fixed_ports_unchanged(self):
        self.active(A2, D2)
        before = deepcopy(self.e.terminals[A2])
        fixed = self.e.fixed_ports
        self.e.submit([Connect(A, B, 30, 5, 5, 5)])
        self.e.start_tx(A2, 3)
        self.e.advance(3)
        self.assertEqual(self.e.terminals[A2].current_peer, before.current_peer)
        self.assertEqual(self.e.terminals[A2].phase, ACTIVE)
        self.assertEqual(self.e.terminals[A2].event_version, before.event_version)
        self.assertEqual(self.e.fixed_ports, fixed)
        self.unchanged_failure([Connect(('A','FWD_INTRA'), C, 30)])

    def test_full_duplex_synthetic_tx_and_direction_exclusivity(self):
        self.active()
        self.e.start_tx(A, 4)
        self.e.start_tx(B, 5)
        with self.assertRaises(ValueError):
            self.e.start_tx(A, 3)
        self.e.advance(5)
        self.assertFalse(next(iter(self.e.links.values())).tx_end)

    def test_zero_duration_setup_and_equal_timestamp_drain(self):
        self.active()
        self.e.start_tx(A, 3)
        self.e.submit([Connect(A, C, 20, 0, 0, 0)])
        self.e.advance(3)
        self.assertEqual(self.e.terminals[A].current_peer, C)
        events = [x['event'] for x in self.e.log if x['time']==3]
        self.assertLess(events.index('TX_DONE'), events.index('LINK_DOWN'))
        self.assertLess(events.index('LINK_DOWN'), events.index('LINK_UP'))

    def test_invalid_inputs_no_mutation(self):
        for cmd in [Connect(A, A2, 30), Connect(A, B, float('nan')),
                    Connect(A, B, 30, -1), Connect(A, B, 30, orientation_a=(0,0,0))]:
            self.unchanged_failure([cmd])
        with self.assertRaises(ValueError):
            self.e.advance(-1)

    def test_invariants_detect_unilateral_active_and_inventory_corruption(self):
        self.active()
        bad = deepcopy(self.e)
        bad.terminals[B].current_peer = None
        with self.assertRaises(AssertionError):
            bad.assert_invariants()
        bad = deepcopy(self.e)
        del bad.terminals[A2]
        with self.assertRaises(AssertionError):
            bad.assert_invariants()

    def test_natural_old_expiry_during_mbb_does_not_break_new_setup(self):
        self.active(end=2)
        self.e.submit([Connect(A2, C2, 40, 3, 3, 1, release_after=((A,B),))])
        self.e.advance(2)
        self.assertEqual(self.e.terminals[A].phase, IDLE)
        self.e.advance(4)
        self.assertEqual(self.e.terminals[A2].phase, ACTIVE)
        self.assertEqual(len(self.e.links), 1)


    def test_scheduled_visibility_loss_wins_same_time_ready(self):
        self.e.submit([Connect(A, B, 40, 1, 1, 5)])
        self.e.advance(1)
        r = next(iter(self.e.reservations.values()))
        # Synthetic newly discovered loss, delivered at event priority 0.
        self.e._schedule(6, 0, 'SETUP_EXPIRE', (r.reservation_id, r.versions))
        self.e.advance(6)
        self.assertFalse(self.e.links)
        self.assertFalse(self.e.reservations)
        self.assertTrue(all(self.e.terminals[e].phase == IDLE for e in (A, B)))
        self.assertFalse(any(x['event'] == 'LINK_UP' for x in self.e.log))

    def test_stale_down_cannot_disconnect_new_binding(self):
        self.active()
        self.e.start_tx(A, 5)
        self.e.submit([Connect(A, C, 40, 0, 0, 0)])
        self.e.advance(1)
        self.e.expire_visibility(A, B)
        self.assertEqual(self.e.terminals[A].current_peer, C)
        self.e.advance(5)
        self.assertEqual(self.e.terminals[A].current_peer, C)
        self.assertTrue(any(x['event']=='LINK_DOWN' and x['details']['interrupted_tx']==1 for x in self.e.log))

    def test_reversed_endpoint_order_preserves_individual_durations(self):
        self.e.submit([Connect(B, A, 40, 2, 4, 3)])
        self.assertEqual(self.e.terminals[B].retarget_end, 2)
        self.assertEqual(self.e.terminals[A].retarget_end, 4)
        self.e.advance(7)
        self.assertEqual(self.e.terminals[A].phase, ACTIVE)

    def test_same_peer_one_terminal_changed(self):
        self.active()
        self.e.start_tx(B, 3)
        self.e.submit([Connect(A, B2, 30, 1, 2, 1)])
        self.e.advance(3)
        self.assertEqual(self.e.terminals[B].phase, IDLE)
        self.e.advance(6)
        self.assertEqual(self.e.terminals[A].current_peer, B2)
        self.assertEqual(len(self.e.links), 1)

    def test_setup_refuses_tx(self):
        self.e.submit([Connect(A, B, 40, 1, 1, 2)])
        for time in (0, 1):
            self.e.advance(time)
            for terminal in (A, B):
                with self.assertRaises(ValueError):
                    self.e.start_tx(terminal, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
