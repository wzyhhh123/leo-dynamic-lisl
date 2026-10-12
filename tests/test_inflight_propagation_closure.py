"""Focused regression tests for exact in-flight propagation closure."""
import unittest

from dynamic_lisl.gate_d2_fixtures import (
    fixture_g_natural_expiry,
    fixture_h_clone_base,
)
from dynamic_lisl.in_flight import RateArrivalEvent


class InFlightPropagationClosureTests(unittest.TestCase):
    def test_quiescent_residue_is_credited_at_final_event(self):
        destination = fixture_h_clone_base()
        edge = ("C", "D")
        key = (edge, "f0")
        destination.arrived["f0"] = 100.0
        destination.delivered["f0"] = 99.75
        destination.in_flight.set_bits(edge, "f0", 0.25)
        destination._finalize_quiescent_propagation({key: -1.0})
        self.assertEqual(destination.in_flight.total(), 0.0)
        self.assertEqual(destination.delivered["f0"], 100.0)
        self.assertEqual(len(destination.propagation_closure_events), 1)
        audit = destination.propagation_closure_events[0]
        self.assertEqual(audit["credited_to"], "DELIVERED")
        self.assertEqual(audit["conservation_error_before_bits"], 0.0)
        self.assertEqual(audit["conservation_error_after_bits"], 0.0)

        intermediate = fixture_h_clone_base()
        edge = ("A", "B")
        key = (edge, "f0")
        intermediate.arrived["f0"] = 1.0
        intermediate.in_flight.set_bits(edge, "f0", 1.0)
        intermediate._finalize_quiescent_propagation({key: -1.0})
        self.assertEqual(intermediate.in_flight.total(), 0.0)
        self.assertEqual(intermediate.queues.get("B", "f0"), 1.0)
        self.assertEqual(intermediate.delivered["f0"], 0.0)
        self.assertEqual(
            intermediate.propagation_closure_events[0]["credited_to"], "B")

    def test_residue_is_not_closed_while_work_can_still_arrive(self):
        edge = ("C", "D")
        key = (edge, "f0")

        active = fixture_h_clone_base()
        active.arrived["f0"] = 0.25
        active.in_flight.set_bits(edge, "f0", 0.25)
        active.service_rates[key] = 1.0
        active._finalize_quiescent_propagation({key: -1.0})
        self.assertEqual(active.in_flight.total(), 0.25)
        self.assertEqual(active.propagation_closure_events, [])

        pending = fixture_h_clone_base()
        pending.arrived["f0"] = 0.25
        pending.in_flight.set_bits(edge, "f0", 0.25)
        pending.propagation_agenda.append(
            RateArrivalEvent(1.0, 1, edge, "f0", -1.0))
        pending._finalize_quiescent_propagation({key: -1.0})
        self.assertEqual(pending.in_flight.total(), 0.25)
        self.assertEqual(pending.propagation_closure_events, [])

    def test_natural_closure_is_deterministic_and_conservative(self):
        first = fixture_g_natural_expiry()
        second = fixture_g_natural_expiry()
        first.advance_to(30.0)
        second.advance_to(30.0)
        self.assertEqual(first.in_flight.total(), 0.0)
        self.assertEqual(first.propagation_closure_events,
                         second.propagation_closure_events)
        self.assertGreater(len(first.propagation_closure_events), 0)
        for row in first.propagation_closure_events:
            self.assertLessEqual(
                abs(row["conservation_error_after_bits"]
                    - row["conservation_error_before_bits"]),
                8.0e-5)


if __name__ == "__main__":
    unittest.main()
