"""Additional Gate F1 fairness and canonical-record contract tests."""
from __future__ import annotations

import unittest

from dynamic_lisl.baseline_controllers import (
    IgnoreSetupDynamicScaffold, SetupAwareGreedyScaffold, StaticHoldController,
)
from dynamic_lisl.candidate_proposer import (
    CandidateSpec, FrozenTerminalPairProposer, canonical_sha256,
)
from dynamic_lisl.controller_runner import MultiEpochControllerRunner
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_d2_fixtures import _catalog, _window, fixture_h_clone_base


def environment():
    engine = fixture_h_clone_base()
    physical = TerminalPairPhysicalFeasibility(_catalog(
        engine.nodes, [_window("B", "D1", "D", "D1", 30.0)]))
    spec = CandidateSpec("P", {
        "a": ("B", "D1"), "b": ("D", "D1"),
        "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0},
        (("B", "D1"), ("C", "D1")))
    return engine, physical, spec


class GateF1ContractTests(unittest.TestCase):
    def test_b1_b2_b3_share_byte_equivalent_proposal_set(self):
        engine, physical, spec = environment()
        proposer = FrozenTerminalPairProposer()
        hashes = [proposer.propose(
            engine.executor, (spec,), physical, engine.fixed_edges,
            "Z_SPARSE_REFERENCE")["proposal_set_sha256"]
            for _controller_id in ("B1", "B2", "B3")]
        self.assertEqual(len(set(hashes)), 1)

    def test_action_canonical_hash_covers_final_record(self):
        engine, physical, spec = environment()
        controller = IgnoreSetupDynamicScaffold(
            lambda state, proposal_set, context: {"HOLD": 0.0, "P": 1.0},
            test_only=True)
        result = MultiEpochControllerRunner(
            engine, physical, engine.fixed_edges, "Z_SPARSE_REFERENCE",
            lambda state, context: (spec,), controller,
            decision_end_s=0.0).run(20.0)
        record = result["controller_actions"][0]
        payload = {key: value for key, value in record.items()
                   if key != "action_canonical_sha256"}
        self.assertEqual(record["action_canonical_sha256"],
                         canonical_sha256(payload))

    def test_b0_does_not_invoke_candidate_source(self):
        engine, physical, _spec = environment()
        def forbidden(_state, _context):
            raise AssertionError("B0_INVOKED_PROPOSER")
        result = MultiEpochControllerRunner(
            engine, physical, engine.fixed_edges, "Z_SPARSE_REFERENCE",
            forbidden, StaticHoldController(), decision_end_s=2.0).run(20.0)
        self.assertTrue(result["candidate_budget_not_used_by_design"])

    def test_b3_scoring_receives_actual_setup_metadata_only(self):
        engine, physical, spec = environment()
        observed = []
        def score(state, proposal_set, context):
            observed.extend(proposal_set["proposals"])
            return {"HOLD": 1.0, "P": 0.0}
        controller = SetupAwareGreedyScaffold(score, test_only=True)
        MultiEpochControllerRunner(
            engine, physical, engine.fixed_edges, "Z_SPARSE_REFERENCE",
            lambda state, context: (spec,), controller,
            decision_end_s=0.0).run(20.0)
        self.assertEqual(observed[0]["setup_duration_s"], 1.0)
        self.assertIn("usable_lifetime_s", observed[0])
        self.assertIn("remaining_lifetime_s", observed[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
