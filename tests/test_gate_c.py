"""Deterministic Gate C core acceptance tests; no traffic or routing."""
import json
import unittest
from copy import deepcopy

from dynamic_lisl.geometry_interface import VisibilityCatalog
from dynamic_lisl.operational_policy import OperationalPolicy, legal_action_interface
from dynamic_lisl.physical_feasibility import (
    PhysicalFeasibility, allocate_terminal_pairs, provisional_hardware_fixture)
from dynamic_lisl.reference_topology import build_reference_constructions
from dynamic_lisl.terminal_executor import TerminalExecutor, Connect, Disconnect, ACTIVE, IDLE
from dynamic_lisl.transition_profiler import (
    profile_transition, validate_reference_initialization)


TRACE_RECORDS = []


def window(a, b, start=0.0, end=20.0, distance=1000.0, left=False, right=False):
    return dict(sat_a=min(a, b), sat_b=max(a, b), start_s=start, end_s=end,
                left_censored=left, right_censored=right, distance_km=distance,
                plane_gap=abs(ord(a[0])-ord(b[0])) if a and b else 1)


def catalog(nodes, records):
    planes = {node: index for index, node in enumerate(nodes)}
    return VisibilityCatalog.from_records(records, planes)


def activate(executor, a, b, end=20.0):
    executor.submit([Connect(a, b, end, 0, 0, 0)])


def serializable_profile(profile):
    return {key: value for key, value in profile.items() if key != "final_executor"}


class GateCTests(unittest.TestCase):
    def tearDown(self):
        if hasattr(self, "trace"):
            TRACE_RECORDS.append(dict(test=self.id(), profile=serializable_profile(self.trace)))

    def test_c0_half_open_window_and_censor_semantics(self):
        e = TerminalExecutor(("A", "B"))
        c = catalog(("A", "B"), [window("A", "B", 2, 10, right=True)])
        self.assertIsNone(c.current_window("A", "B", 1.999))
        self.assertIsNotNone(c.current_window("A", "B", 2))
        self.assertIsNone(c.current_window("A", "B", 10))
        e.advance(2)
        command, metadata = c.connect_command(e, ("A", "D1"), ("B", "D2"), 1, 2, 1)
        self.assertEqual(command.visibility_end, 10)
        self.assertEqual(metadata["ready_time"], 5)
        self.assertEqual(metadata["end_semantics"], "prediction_horizon")

    def test_c0_inter_plane_scope_excludes_same_plane(self):
        c = VisibilityCatalog.from_records([window("A", "B")], {"A": 0, "B": 0})
        self.assertIsNone(c.current_window("A", "B", 0))
        self.assertEqual(c.inter_plane_candidates(0), [])

    def test_visible_but_hardware_range_infeasible(self):
        e = TerminalExecutor(("A", "B"))
        p = PhysicalFeasibility(catalog(("A", "B"), [window("A", "B", distance=1200)]),
                                provisional_hardware_fixture(1000))
        result = p.evaluate(e, ("A", "D1"), ("B", "D1"))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "HARDWARE_RANGE_FAIL")

    def test_geometry_visible_but_terminal_reserved(self):
        e = TerminalExecutor(("A", "B", "C"))
        e.submit([Connect(("A", "D1"), ("B", "D1"), 20, 5, 5, 1)])
        p = PhysicalFeasibility(catalog(("A", "B", "C"), [window("A", "C")]),
                                provisional_hardware_fixture())
        result = p.evaluate(e, ("A", "D1"), ("C", "D1"))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "RESERVATION_CONFLICT")
    def test_ready_equal_or_after_visibility_end_rejected(self):
        e = TerminalExecutor(("A", "B"))
        p = PhysicalFeasibility(catalog(("A", "B"), [window("A", "B", end=3)]),
                                provisional_hardware_fixture())
        for acquisition in (2, 3):
            result = p.evaluate(e, ("A", "D1"), ("B", "D1"), 1, 1, acquisition)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason"], "INSUFFICIENT_LIFETIME")

    def _bbm_profile(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"))
        c = catalog(e.satellite_ids, [window("B", "D")])
        physical = PhysicalFeasibility(c, provisional_hardware_fixture())
        result = physical.evaluate(e, ("B", "D1"), ("D", "D1"), 2, 2, 0)
        self.assertTrue(result["accepted"])
        return profile_transition(e, [result["command"]], (("A", "B"), ("C", "D")), 3)

    def test_bbm_two_second_partition_policy_matrix(self):
        profile = self._bbm_profile(); self.trace = profile
        self.assertEqual(profile["classification"], "temporary_recoverable_partition")
        self.assertEqual(profile["outage_duration"], 2)
        self.assertFalse(OperationalPolicy("STRICT_CONNECTED").apply(profile)["accepted"])
        self.assertTrue(OperationalPolicy("BOUNDED_OUTAGE", 5).apply(profile)["accepted"])
        self.assertFalse(OperationalPolicy("BOUNDED_OUTAGE", 1).apply(profile)["accepted"])

    def test_outage_equal_to_bound_is_accepted(self):
        profile = self._bbm_profile()
        self.assertTrue(OperationalPolicy("BOUNDED_OUTAGE", 2).apply(profile)["accepted"])

    def test_mbb_no_partition_both_policies_accept(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"))
        command = Connect(("A", "D2"), ("D", "D2"), 20, 2, 2, 0,
                          release_after=((("B", "D1"), ("C", "D1")),))
        profile = profile_transition(e, [command], (("A", "B"), ("C", "D")), 3)
        self.trace = profile
        self.assertEqual(profile["classification"], "no_partition")
        self.assertTrue(OperationalPolicy("STRICT_CONNECTED").apply(profile)["accepted"])
        self.assertTrue(OperationalPolicy("BOUNDED_OUTAGE", 0).apply(profile)["accepted"])

    def test_two_simultaneous_removals_atomic_and_unsafe(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"), end=5)
        activate(e, ("A", "D2"), ("D", "D2"), end=5)
        fixed = (("A", "B"), ("C", "D"))
        one = deepcopy(e); one.links["L2"].visibility_end = 20
        one.events = [x for x in one.events if not (x[3] == "LINK_EXPIRE" and x[4] == "L2")]
        self.assertFalse(profile_transition(one, [], fixed, 6)["partition_occurs"])
        profile = profile_transition(e, [], fixed, 6); self.trace = profile
        self.assertTrue(profile["partition_occurs"])
        at_five = next(x for x in profile["timeline"] if x["time_s"] == 5)
        self.assertEqual(at_five["events"].count("LINK_DOWN"), 2)

    def test_draining_active_connected_admit_disconnected(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"))
        e.start_tx(("B", "D1"), 2)
        command = Connect(("B", "D1"), ("D", "D1"), 20, 2, 2, 0)
        profile = profile_transition(e, [command], (("A", "B"), ("C", "D")), 5)
        self.trace = profile
        first = profile["timeline"][0]
        self.assertTrue(first["active_connected"])
        self.assertFalse(first["admit_connected"])
        self.assertEqual(profile["outage_duration"], 4)

    def test_setup_visibility_expiry_aborts_without_link_up(self):
        e = TerminalExecutor(("A", "B"))
        e.submit([Connect(("A", "D1"), ("B", "D1"), 20, 1, 1, 5)])
        reservation = next(iter(e.reservations.values()))
        e._schedule(2, 0, "SETUP_EXPIRE", (reservation.reservation_id, reservation.versions))
        profile = profile_transition(e, [], (("A", "B"),), 7); self.trace = profile
        self.assertFalse(profile["final_executor"].links)
        self.assertTrue(any(x["event"] == "ABORT" for x in profile["transition_log"]))
        self.assertFalse(any(x["event"] == "LINK_UP" for x in profile["transition_log"]))

    def test_unrecoverable_partition_rejected_by_bounded_policy(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"))
        profile = profile_transition(e, [Disconnect(("B", "D1"), ("C", "D1"))],
                                     (("A", "B"), ("C", "D")), 5)
        self.trace = profile
        decision = OperationalPolicy("BOUNDED_OUTAGE", 100).apply(profile)
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["reason"], "UNRECOVERABLE_PARTITION")

    def test_pending_plus_new_batch_profiled_together(self):
        e = TerminalExecutor(("A", "B", "C", "D", "E", "F"))
        activate(e, ("B", "D1"), ("C", "D1"))
        activate(e, ("D", "D1"), ("E", "D1"))
        # Existing pending transition restores A/B to C/D after 2 s.
        e.submit([Connect(("B", "D1"), ("D", "D2"), 20, 2, 2, 0)])
        # The new disjoint batch simultaneously removes D/E and restores it at 4 s.
        new_batch = [Connect(("D", "D1"), ("F", "D1"), 20, 4, 4, 0)]
        fixed = (("A", "B"), ("C", "D"), ("E", "F"))
        profile = profile_transition(e, new_batch, fixed, 5)
        self.trace = profile
        self.assertEqual(profile["outage_duration"], 4)
        self.assertEqual(profile["recovery_time"], 4)

    def test_disconnected_reference_initialization(self):
        result = validate_reference_initialization(("A", "B", "C", "D"),
                                                   (("A", "B"), ("C", "D")), ())
        self.assertFalse(result["connected"])
        self.assertEqual(len(result["components"]), 2)

    def test_hold_only_when_all_non_hold_actions_rejected(self):
        e = TerminalExecutor(("A", "B"))
        p = PhysicalFeasibility(catalog(("A", "B"), []), provisional_hardware_fixture())
        result = legal_action_interface(e, [dict(a=("A", "D1"), b=("B", "D1"))], p, (),
                                        OperationalPolicy("STRICT_CONNECTED"), 2)
        self.assertTrue(result["hold_only"])
        self.assertEqual(result["fallback"], "HOLD")

    def test_allocator_order_invariant_and_no_double_occupancy(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        x = allocate_terminal_pairs(e, (("A", "B"), ("A", "C"), ("B", "D")))
        y = allocate_terminal_pairs(e, tuple(reversed((("A", "B"), ("A", "C"), ("B", "D")))))
        self.assertEqual(x, y)
        flattened = [terminal for binding in x for terminal in binding]
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_subset_allocator_rejects_external_satellite(self):
        e = TerminalExecutor(("A", "B", "C"))
        with self.assertRaisesRegex(ValueError, "SUBSET_EXTERNAL"):
            allocate_terminal_pairs(e, (("A", "X"),), allowed_satellites=("A", "B", "C"))

    def test_mbb_setup_abort_keeps_old_link(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"))
        e.submit([Connect(("A", "D2"), ("D", "D2"), 20, 2, 2, 2,
                          release_after=((("B", "D1"), ("C", "D1")),))])
        e.expire_visibility(("A", "D2"), ("D", "D2"))
        self.assertEqual(e.terminals[("B", "D1")].phase, ACTIVE)
        self.assertEqual(e.terminals[("C", "D1")].phase, ACTIVE)

    def test_natural_expiry_unsafe_has_specific_reason(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"), end=2)
        profile = profile_transition(e, [], (("A", "B"), ("C", "D")), 3)
        decision = OperationalPolicy("BOUNDED_OUTAGE", 10).apply(profile)
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["reason"], "NATURAL_EXPIRY_UNSAFE")
    def test_transition_replay_exactly_deterministic(self):
        e = TerminalExecutor(("A", "B", "C", "D"))
        activate(e, ("B", "D1"), ("C", "D1"))
        command = Connect(("B", "D1"), ("D", "D1"), 20, 2, 2, 0)
        a = serializable_profile(profile_transition(e, [command], (("A", "B"), ("C", "D")), 3))
        b = serializable_profile(profile_transition(e, [command], (("A", "B"), ("C", "D")), 3))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_reference_constructions_connected_and_not_fully_occupied(self):
        nodes = tuple("ABCDEFGH")
        planes = {node: index//2 for index, node in enumerate(nodes)}
        slots = {node: index%2 for index, node in enumerate(nodes)}
        records = []
        for i, a in enumerate(nodes):
            for b in nodes[i+1:]:
                if planes[a] != planes[b]: records.append(window(a, b, end=20))
        study = build_reference_constructions(VisibilityCatalog.from_records(records, planes),
                                              nodes, planes, slots)
        self.assertEqual(set(study["constructions"]),
                         {"sparse_connected", "medium_occupancy", "relative_dense"})
        for result in study["constructions"].values():
            self.assertTrue(result["connected"])
            self.assertGreater(result["idle_dynamic_terminal_ratio"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)




