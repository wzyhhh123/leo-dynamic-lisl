"""Gate F3 runtime Phase 1 semantic-preservation tests."""
from __future__ import annotations

from copy import deepcopy
import unittest

from dynamic_lisl.candidate_proposer import CandidateSpec, FrozenTerminalPairProposer
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_d2_fixtures import _catalog, _window, fixture_h_clone_base
from dynamic_lisl.terminal_executor import Connect, TerminalExecutor
from dynamic_lisl.transition_profiler import (
    profile_transition, profile_transition_legacy_reference,
)
from tests.test_gate_f1_controller import bbm_candidate_environment


class LegacyReferenceTerminalExecutor(TerminalExecutor):
    """Pre-Phase-1 submit path; test/reference use only."""

    def submit(self, commands):
        return self.submit_legacy_reference(commands)


def as_legacy(executor):
    value = deepcopy(executor)
    value.__class__ = LegacyReferenceTerminalExecutor
    return value


def public_profile(value):
    return {key: item for key, item in value.items()
            if key != "final_executor"}


class GateF3RuntimePhase1Tests(unittest.TestCase):
    def test_clone_field_contract_and_history_boundary(self):
        executor = TerminalExecutor(("A", "B", "C"))
        executor.submit((Connect(("A", "D1"), ("B", "D1"),
                                 30.0, 0.0, 0.0, 0.0),))
        executor.start_tx(("A", "D1"), 3.0)

        transaction = executor.clone_for_transaction()
        counterfactual = executor.clone_for_counterfactual()
        self.assertEqual(transaction.snapshot(), executor.snapshot())
        self.assertEqual(counterfactual.snapshot(), executor.snapshot())
        self.assertEqual(transaction.log, executor.log)
        self.assertIsNot(transaction.log, executor.log)
        self.assertEqual(counterfactual.log, [])
        self.assertIs(transaction.satellite_ids, executor.satellite_ids)
        self.assertIs(transaction.fixed_ports, executor.fixed_ports)
        self.assertIsNot(transaction.terminals[("A", "D1")],
                         executor.terminals[("A", "D1")])
        self.assertIsNot(transaction.links["L1"], executor.links["L1"])
        self.assertIsNot(transaction.links["L1"].tx_end,
                         executor.links["L1"].tx_end)

        executor.unreviewed_future_field = 1
        with self.assertRaisesRegex(AssertionError, "CLONE_AUDIT_REQUIRED"):
            executor.clone_for_counterfactual()

    def test_atomic_submit_matches_recursive_legacy_reference(self):
        optimized = TerminalExecutor(("A", "B", "C", "D"))
        optimized.submit((Connect(("A", "D1"), ("B", "D1"),
                                  30.0, 0.0, 0.0, 0.0),))
        optimized.start_tx(("A", "D1"), 3.0)
        legacy = as_legacy(optimized)
        command = Connect(("A", "D1"), ("C", "D1"),
                          30.0, 2.0, 1.0, 1.0)
        optimized.submit((command,))
        legacy.submit((command,))
        self.assertEqual(optimized.snapshot(), legacy.snapshot())
        self.assertEqual(optimized.log, legacy.log)
        optimized.advance(8.0)
        legacy.advance(8.0)
        self.assertEqual(optimized.snapshot(), legacy.snapshot())
        self.assertEqual(optimized.log, legacy.log)

    def test_transition_profile_matches_recursive_legacy_reference(self):
        _, fixed, executor, physical, spec = bbm_candidate_environment()
        command = physical.evaluate(executor, **spec.proposal)["command"]
        optimized = profile_transition(
            executor, (command,), fixed, 3.0000001)
        legacy_executor = as_legacy(executor)
        legacy = profile_transition_legacy_reference(
            legacy_executor, (command,), fixed, 3.0000001)
        self.assertEqual(public_profile(optimized), public_profile(legacy))
        self.assertEqual(optimized["final_executor"].snapshot(),
                         legacy["final_executor"].snapshot())

    def test_proposal_ids_order_hash_and_metadata_match_legacy(self):
        _, fixed, executor, physical, spec = bbm_candidate_environment()
        noop = CandidateSpec("NOOP", {
            "a": ("B", "D1"), "b": ("C", "D1"),
            "retarget_a": 0.0, "retarget_b": 0.0, "acquisition": 0.0},
            (("B", "D1"), ("C", "D1")))
        illegal = CandidateSpec("ILLEGAL", {
            "a": ("A", "D2"), "b": ("D", "D2"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0})
        candidates = (noop, illegal, spec)
        optimized = FrozenTerminalPairProposer().propose(
            executor, candidates, physical, fixed, "Z_SPARSE_REFERENCE")
        legacy = FrozenTerminalPairProposer(
            profile_transition_legacy_reference).propose(
                as_legacy(executor), candidates, physical, fixed,
                "Z_SPARSE_REFERENCE")
        self.assertEqual(optimized, legacy)
        record = optimized["proposals"][0]
        for field in (
                "proposal_id", "ready_time_s", "remaining_lifetime_s",
                "usable_lifetime_s", "stratum", "safety_policy",
                "transition_profile_classification"):
            self.assertEqual(record[field], legacy["proposals"][0][field])
        self.assertEqual(optimized["proposal_set_sha256"],
                         legacy["proposal_set_sha256"])
        self.assertEqual(
            [(row["proposal_id"], row["reason"]) for row in optimized["pruned"]],
            [("ILLEGAL", "FOR_FAIL_BILATERAL"),
             ("NOOP", "EXACT_PHYSICAL_NOOP")])

    def test_genuine_mbb_profile_and_submit_match_legacy(self):
        engine = fixture_h_clone_base().advance_to(2.0)
        old = (("B", "D1"), ("C", "D1"))
        physical = TerminalPairPhysicalFeasibility(_catalog(
            engine.nodes, [_window("B", "D2", "D", "D2", 30.0)]))
        spec = CandidateSpec("MBB-SWITCH", {
            "a": ("B", "D2"), "b": ("D", "D2"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0,
            "release_after": (old,),
        }, old)
        optimized = FrozenTerminalPairProposer().propose(
            engine.executor, (spec,), physical, engine.fixed_edges,
            "Z_MODERATE")
        legacy_executor = as_legacy(engine.executor)
        legacy = FrozenTerminalPairProposer(
            profile_transition_legacy_reference).propose(
                legacy_executor, (spec,), physical, engine.fixed_edges,
                "Z_MODERATE")
        self.assertEqual(optimized, legacy)
        self.assertEqual(optimized["proposals"][0]["stratum"],
                         "MBB_STRUCTURALLY_FEASIBLE")

        optimized_executor = deepcopy(engine.executor)
        optimized_executor.submit((physical.evaluate(
            optimized_executor, **spec.proposal)["command"],))
        legacy_command = physical.evaluate(
            legacy_executor, **spec.proposal)["command"]
        legacy_executor.submit((legacy_command,))
        optimized_executor.advance(3.0)
        legacy_executor.advance(3.0)
        self.assertEqual(optimized_executor.snapshot(),
                         legacy_executor.snapshot())
        self.assertEqual(optimized_executor.log, legacy_executor.log)


if __name__ == "__main__":
    unittest.main()
