"""Gate D2 transition/service integration acceptance tests (small fixtures)."""
import json
import unittest

from dynamic_lisl.gate_d2_fixtures import (
    SMALL_FIXTURE_BUILDERS,
    fixture_a_bbm_forced_outage,
    fixture_b_genuine_mbb,
    fixture_c_false_mbb_rejection,
    fixture_d_draining_split,
    fixture_e_partition_with_unaffected_flow,
    fixture_f_alternate_path,
    fixture_g_natural_expiry,
    fixture_h_clone_base,
    fixture_h_switch_action,
)


def run(engine, limit=30.0):
    return engine.run(limit)


def normalized(result):
    document = dict(result)
    document["metrics"] = dict(result["metrics"])
    document["metrics"].pop("runtime", None)
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)


class GateD2IntegrationTests(unittest.TestCase):
    def test_a_bbm_two_second_outage_has_analytical_backlog_and_clearance(self):
        result = run(fixture_a_bbm_forced_outage())
        metrics = result["metrics"]
        self.assertEqual(metrics["BBM_count"], 1)
        self.assertAlmostEqual(metrics["outage_duration_s"], 2.0, places=9)
        self.assertAlmostEqual(
            metrics["backlog_added_during_transition_bits"], 16e9,
            delta=1.0)
        self.assertAlmostEqual(metrics["peak_transition_backlog_bits"], 16e9,
                               delta=1.0)
        self.assertAlmostEqual(metrics["backlog_clearance_time_s"], 8.0,
                               places=9)
        states = [x for x in result["route_state_events"]
                  if x["commodity_id"] == "f0"]
        self.assertTrue(any(x["new_state"] == "NO_ROUTE_TEMPORARY" for x in states))
        self.assertTrue(any(x["old_state"] == "NO_ROUTE_TEMPORARY"
                            and x["new_state"] == "ROUTED" for x in states))

    def test_b_genuine_mbb_has_no_forced_zero_service_interval(self):
        result = run(fixture_b_genuine_mbb())
        metrics = result["metrics"]
        self.assertEqual(metrics["MBB_count"], 1)
        self.assertEqual(metrics["BBM_count"], 0)
        self.assertEqual(metrics["outage_duration_s"], 0.0)
        self.assertLessEqual(metrics["max_queue_bits"], 1.0)
        events = [(x["time"], x["event"]) for x in result["terminal_event_sequence"]]
        up = min(t for t, name in events if name == "LINK_UP")
        down = min(t for t, name in events if name == "LINK_DOWN")
        self.assertLessEqual(up, down)

    def test_c_false_mbb_is_rejected_by_gate_c(self):
        result = run(fixture_c_false_mbb_rejection())
        decision = result["action_results"][0]
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["physical_reason"], "FOR_FAIL_BILATERAL")
        self.assertEqual(result["metrics"]["switch_count"], 0)

    def test_d_draining_is_active_not_admit_and_inflight_survives(self):
        result = run(fixture_d_draining_split())
        at_one = next(x for x in result["graph_event_sequence"]
                      if x["time_s"] == 1.0)
        self.assertIn(("B", "C"), at_one["active_edges"])
        self.assertNotIn(("B", "C"), at_one["admit_edges"])
        self.assertTrue(any(x["event"] == "TX_DONE" and x["time"] == 1.5
                            for x in result["terminal_event_sequence"]))
        self.assertGreater(max(x["in_flight_bits"] for x in result["timeline"]), 0.0)
        self.assertLessEqual(result["metrics"]["max_abs_conservation_error_bits"], 1.0)

    def test_e_partition_waits_while_unaffected_flow_continues(self):
        result = run(fixture_e_partition_with_unaffected_flow())
        states = [x for x in result["route_state_events"]
                  if x["commodity_id"] == "affected"]
        self.assertTrue(any(x["new_state"] == "NO_ROUTE_TEMPORARY" for x in states))
        self.assertTrue(any(x["old_state"] == "NO_ROUTE_TEMPORARY"
                            and x["new_state"] == "ROUTED" for x in states))
        self.assertNotIn("unaffected",
                         result["metrics"]["no_route_duration_by_commodity_s"])
        self.assertAlmostEqual(result["delivered_by_commodity"]["unaffected"],
                               result["arrived_by_commodity"]["unaffected"], delta=1.0)
        self.assertGreater(result["metrics"]["partition_node_time_s"], 0.0)

    def test_f_connected_removal_uses_deterministic_alternate_path(self):
        result = run(fixture_f_alternate_path())
        target = [x for x in result["route_changes"]
                  if x["node"] == "A" and x["commodity_id"] == "target"]
        self.assertEqual(target[0]["old_route"], ["A", "C", "D"])
        self.assertEqual(target[0]["new_route"], ["A", "B", "D"])
        self.assertEqual(target[1]["new_route"], ["A", "E", "D"])
        self.assertEqual(result["metrics"]["outage_duration_s"], 0.0)
        transmitted = result["transmitted_by_edge_commodity"]
        self.assertGreater(transmitted["B->D|target"], 0.0)
        self.assertGreater(transmitted["B->D|third_party"], 0.0)

    def test_g_natural_expiry_uses_same_graph_and_routing_path(self):
        result = run(fixture_g_natural_expiry())
        expiry_down = [x for x in result["terminal_event_sequence"]
                       if x["event"] == "LINK_DOWN"
                       and x["details"].get("reason") == "LINK_EXPIRE"]
        self.assertEqual(len(expiry_down), 1)
        change = next(x for x in result["route_changes"]
                      if x["node"] == "A" and x["commodity_id"] == "f0")
        self.assertEqual(change["old_route"], ["A", "C", "D"])
        self.assertEqual(change["new_route"], ["A", "B", "D"])

    def test_h_same_state_clone_covers_all_causal_state_and_same_future_trace(self):
        base = fixture_h_clone_base().advance_to(1.0)
        hold = base.clone()
        switch = base.clone()
        self.assertEqual(hold.canonical_state_sha256(),
                         switch.canonical_state_sha256())
        snapshot = hold.canonical_state()
        self.assertEqual(snapshot["time_s"], snapshot["terminal"]["time"])
        for field in ("queues", "in_flight", "arrived", "delivered",
                      "traffic_cursor", "routes", "propagation_agenda",
                      "scripted_action_cursor", "routing_class", "rng_state"):
            self.assertIn(field, snapshot)
        switch.schedule_action(fixture_h_switch_action(1.0))
        hold_result = run(hold, 20.0)
        switch_result = run(switch, 20.0)
        self.assertEqual(hold_result["metrics"]["trace_sha256"],
                         switch_result["metrics"]["trace_sha256"])
        self.assertEqual(hold_result["metrics"]["arrived_bits"],
                         switch_result["metrics"]["arrived_bits"])
        self.assertEqual(hold_result["metrics"]["switch_count"], 0)
        self.assertEqual(switch_result["metrics"]["switch_count"], 1)

    def test_all_small_fixtures_preserve_work_and_capacity(self):
        for fixture_id, builder in SMALL_FIXTURE_BUILDERS.items():
            with self.subTest(fixture=fixture_id):
                result = run(builder())
                metrics = result["metrics"]
                self.assertLessEqual(metrics["max_abs_conservation_error_bits"], 1.0)
                self.assertEqual(metrics["negative_queue_count"], 0)
                self.assertLessEqual(metrics["max_capacity_violation_bit_s"], 0.01)
                self.assertFalse(metrics["censored"])

    def test_deterministic_replay_is_canonical_exact(self):
        first = run(fixture_a_bbm_forced_outage())
        second = run(fixture_a_bbm_forced_outage())
        self.assertEqual(normalized(first), normalized(second))


if __name__ == "__main__":
    unittest.main(verbosity=2)
