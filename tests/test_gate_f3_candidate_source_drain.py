from __future__ import annotations

import json
import unittest

from dynamic_lisl.candidate_proposer import FrozenTerminalPairProposer
from dynamic_lisl.common import PROJECT
from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.production_candidate_source import (
    DrainDecisionPolicy,
    FrozenSetupParameters,
    ProductionCandidateSource,
)
from dynamic_lisl.terminal_executor import Connect, Disconnect, TerminalExecutor, pair
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow


def window(a, ta, b, tb, end=100.0, gap=1):
    return TerminalPairWindow(a, ta, b, tb, 0.0, float(end),
                              plane_gap=int(gap), distance_km=1000.0)


class FakeCatalog:
    def __init__(self, windows):
        self.values = tuple(windows)

    def terminal_pair_candidates(self, _time_s, _allowed_satellites=None):
        return self.values


def executor(nodes, bindings=()):
    value = TerminalExecutor(nodes)
    for a, b in bindings:
        value.submit((Connect(tuple(a), tuple(b), 100.0, 0.0, 0.0, 0.0),))
    return value


def source(windows):
    return ProductionCandidateSource(
        FakeCatalog(windows), FrozenSetupParameters.load(PROJECT))


def state(executor_value, state_hash="s" * 64):
    return {"time_s": executor_value.now,
            "current_state_sha256": state_hash}


class CandidateSourceTests(unittest.TestCase):
    def test_contract_is_sealed_and_parent_exact(self):
        path = PROJECT / "configs/gate_f3_candidate_source_drain_human_freeze_v1.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        from dynamic_lisl.candidate_proposer import canonical_sha256
        expected = doc.pop("canonical_sha256")
        self.assertEqual(
            expected,
            "ba527d3bc2c4ebca742ec21b8c390d512931d56d9c9ba68ed4eb22a7f47a7f39")
        self.assertEqual(canonical_sha256(doc), expected)

    def test_same_state_replay_and_controller_blind_source(self):
        e = executor(("A", "B", "C"), [(("A", "D1"), ("B", "D1"))])
        s = source((window("A", "D1", "C", "D1"),
                    window("A", "D2", "C", "D2")))
        contexts = [
            {"terminal_executor": e, "controller_id": name}
            for name in ("B1", "B3", "B4")]
        outputs = [s(state(e), context) for context in contexts]
        ids = [[row.proposal_id for row in output] for output in outputs]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[1], ids[2])
        hashes = []
        for context in contexts:
            s(state(e), context)
            hashes.append(s.last_report["source_sha256"])
        self.assertEqual(len(set(hashes)), 1)

    def test_bbm_reuses_one_old_terminal(self):
        e = executor(("A", "B", "C"), [(("A", "D1"), ("B", "D1"))])
        s = source((window("A", "D1", "C", "D1"),))
        specs = s.materialize(e, "a" * 64)
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec.old_binding, pair(("A", "D1"), ("B", "D1")))
        self.assertNotIn("release_after", spec.proposal)
        self.assertEqual(s.last_report["selected_counts"]["BBM_RAW"], 1)

    def test_genuine_mbb_uses_idle_pair_and_release_after(self):
        e = executor(("A", "B", "C"), [(("A", "D1"), ("B", "D1"))])
        s = source((window("A", "D2", "C", "D2"),))
        spec = s.materialize(e, "b" * 64)[0]
        old = pair(("A", "D1"), ("B", "D1"))
        self.assertEqual(spec.proposal["release_after"], (old,))
        self.assertEqual(s.last_report["selected_counts"]["MBB_RAW"], 1)
        trial = TerminalPairPhysicalFeasibility(TerminalPairCatalog(
            [window("A", "D2", "C", "D2")], {"A": 0, "B": 1, "C": 2}))
        physical = trial.evaluate(e, **spec.proposal)
        self.assertTrue(physical["accepted"])
        self.assertTrue(physical["command"].release_after)

    def test_target_touching_another_old_binding_rejected(self):
        e = executor(("A", "B", "C", "D"), [
            (("A", "D1"), ("B", "D1")),
            (("C", "D1"), ("D", "D1")),
        ])
        s = source((window("A", "D1", "C", "D1"),))
        self.assertEqual(s.materialize(e, "c" * 64), ())
        self.assertGreaterEqual(
            s.last_report["rejection_counts"]["MULTI_OLD_BINDING_CONFLICT"], 1)

    def test_target_touching_two_different_old_bindings_rejected(self):
        e = executor(("A", "B", "C", "D"), [
            (("A", "D1"), ("B", "D1")),
            (("C", "D1"), ("D", "D1")),
        ])
        s = source((window("B", "D1", "D", "D1"),))
        self.assertEqual(s.materialize(e, "d" * 64), ())
        self.assertTrue(all(
            row["reason"] == "MULTI_OLD_BINDING_CONFLICT"
            for row in s.last_report["rejections"]))

    def test_exact_noop_rejected(self):
        e = executor(("A", "B"), [(("A", "D1"), ("B", "D1"))])
        s = source((window("A", "D1", "B", "D1"),))
        self.assertEqual(s.materialize(e, "e" * 64), ())
        self.assertEqual(s.last_report["rejection_counts"],
                         {"NO_OP_CURRENT_BINDING": 1})

    def test_parallel_satellite_pair_rejected(self):
        e = executor(("A", "B"), [(("A", "D1"), ("B", "D1"))])
        s = source((window("A", "D2", "B", "D2"),))
        self.assertEqual(s.materialize(e, "f" * 64), ())
        self.assertEqual(s.last_report["rejection_counts"],
                         {"PARALLEL_SATELLITE_PAIR_CONFLICT": 1})

    def test_reserved_terminal_rejected(self):
        e = executor(("A", "B", "C", "D"),
                     [(("A", "D1"), ("B", "D1"))])
        e.submit((Connect(("C", "D1"), ("D", "D1"), 100.0,
                          2.0, 2.0, 1.0),))
        s = source((window("A", "D1", "C", "D1"),))
        self.assertEqual(s.materialize(e, "1" * 64), ())
        self.assertEqual(s.last_report["rejection_counts"],
                         {"RESERVED_TERMINAL_CONFLICT": 1})

    def test_draining_old_binding_not_replaceable(self):
        e = executor(("A", "B", "C"), [(("A", "D1"), ("B", "D1"))])
        e.submit((Disconnect(("A", "D1"), ("B", "D1")),))
        s = source((window("A", "D1", "C", "D1"),))
        self.assertEqual(s.materialize(e, "2" * 64), ())
        self.assertEqual(s.last_report["eligible_old_bindings"], [])

    def test_release_owned_old_binding_not_replaceable(self):
        e = executor(("A", "B", "C", "D"), [
            (("A", "D1"), ("B", "D1")),
            (("C", "D1"), ("D", "D1")),
        ])
        old = pair(("A", "D1"), ("B", "D1"))
        e.submit((Connect(("A", "D2"), ("C", "D2"), 100.0,
                          2.0, 2.0, 1.0, release_after=(old,)),))
        eligible = [row[0] for row in ProductionCandidateSource._eligible_old_links(e)]
        self.assertNotIn(old, eligible)
        self.assertIn(pair(("C", "D1"), ("D", "D1")), eligible)

    def test_unrelated_setup_allows_disjoint_candidate(self):
        e = executor(("A", "B", "C", "D", "E"),
                     [(("A", "D1"), ("B", "D1"))])
        e.submit((Connect(("D", "D1"), ("E", "D1"), 100.0,
                          2.0, 2.0, 1.0),))
        s = source((window("A", "D1", "C", "D1"),))
        specs = s.materialize(e, "3" * 64)
        self.assertEqual(len(specs), 1)
        self.assertNotIn(("D", "D1"), specs[0].proposal.values())

    def test_caps_ids_and_duplicate_removal(self):
        nodes = ["A", "B"]
        windows = []
        for index in range(40):
            node = f"X{index}"
            nodes.append(node)
            windows.append(window("A", "D1", node, "D1", 200-index, index % 4 + 1))
        for index in range(40):
            left, right = f"Y{index}", f"Z{index}"
            nodes.extend((left, right))
            windows.append(window(left, "D1", right, "D1", 300-index, index % 4 + 1))
        # Exact duplicate from a deliberately minimal fake catalog.
        windows.append(windows[0])
        e = executor(nodes, [(("A", "D1"), ("B", "D1"))])
        s = source(windows)
        first = s.materialize(e, "4" * 64)
        first_ids = [row.proposal_id for row in first]
        second_ids = [row.proposal_id for row in s.materialize(e, "4" * 64)]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))
        self.assertLessEqual(s.last_report["selected_counts"]["BBM_RAW"], 32)
        self.assertLessEqual(s.last_report["selected_counts"]["MBB_RAW"], 32)
        self.assertLessEqual(len(first), 64)
        self.assertEqual(s.last_report["selected_counts"],
                         {"BBM_RAW": 32, "MBB_RAW": 32})

    def test_same_target_different_old_binding_remains_distinct(self):
        e = executor(("A", "B", "C", "D", "E", "F"), [
            (("A", "D1"), ("B", "D1")),
            (("C", "D1"), ("D", "D1")),
        ])
        s = source((window("E", "D1", "F", "D1"),))
        specs = s.materialize(e, "5" * 64)
        self.assertEqual(len(specs), 2)
        self.assertEqual(len({row.proposal_id for row in specs}), 2)
        self.assertEqual({row.old_binding for row in specs}, {
            pair(("A", "D1"), ("B", "D1")),
            pair(("C", "D1"), ("D", "D1")),
        })

    def test_existing_common_proposer_stays_top16_and_8_8(self):
        nodes = ["A", "B"]
        windows = []
        for index in range(10):
            node = f"X{index}"
            nodes.append(node)
            windows.append(window("A", "D1", node, "D1", 200-index, 1))
        for index in range(10):
            left, right = f"Y{index}", f"Z{index}"
            nodes.extend((left, right))
            windows.append(window(left, "D1", right, "D1", 300-index, 2))
        e = executor(nodes, [(("A", "D1"), ("B", "D1"))])
        catalog = TerminalPairCatalog(windows, {node: i for i, node in enumerate(nodes)})
        s = ProductionCandidateSource(catalog, FrozenSetupParameters.load(PROJECT))
        specs = s.materialize(e, "6" * 64)
        fixed = tuple((nodes[0], node) for node in nodes[1:])
        proposal_set = FrozenTerminalPairProposer().propose(
            e, specs, TerminalPairPhysicalFeasibility(catalog), fixed, "Z_MODERATE")
        strata = [row["stratum"] for row in proposal_set["proposals"]]
        self.assertLessEqual(len(strata), 16)
        self.assertEqual(strata.count("BBM_REQUIRED"), 8)
        self.assertEqual(strata.count("MBB_STRUCTURALLY_FEASIBLE"), 8)


class DrainDecisionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DrainDecisionPolicy()

    def test_238_and_240_and_242(self):
        self.assertTrue(self.policy.decision_due(238.0, 0.0))
        self.assertTrue(self.policy.decision_due(240.0, 1.0))
        self.assertTrue(self.policy.decision_due(242.0, 1.0))

    def test_t240_observes_zero_lambda(self):
        self.assertTrue(self.policy.assert_arrival_cutoff_state(
            240.0, {"f00": 0.0, "f01": 0.0}))
        with self.assertRaisesRegex(AssertionError, "T240"):
            self.policy.assert_arrival_cutoff_state(240.0, {"f00": 1.0})

    def test_no_decision_after_early_complete(self):
        self.assertFalse(self.policy.decision_due(242.0, 0.01))
        self.assertFalse(self.policy.decision_due(242.0, 0.0))

    def test_no_decision_at_600(self):
        self.assertTrue(self.policy.decision_due(598.0, 1.0))
        self.assertFalse(self.policy.decision_due(600.0, 1.0))
        self.assertEqual(self.policy.possible_epochs()[-1], 598.0)


if __name__ == "__main__":
    unittest.main()

