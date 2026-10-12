from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests.runtime_phase1_overlay import approved_runtime_phase1_change


PROJECT = Path(__file__).resolve().parents[1]

from tools.run_gate_f3_p1_execution import (  # noqa: E402
    P1InvariantFailure, persist_run_evidence,
)
from dynamic_lisl.gate_f3_p1_evidence import (  # noqa: E402
    detailed_invariant_report, final_state_evidence,
)
from dynamic_lisl.gate_f3_p1_execution import (  # noqa: E402
    f3_trace_identity, summarize_run,
)


HISTORICAL = {
    "configs/gate_f3_p1_status.json":
        "164bd07f8d80319b07029944db86b0cb70a4dacfef8227225d6b7ac2d6ea3ed3",
    "docs/GATE_F3_P1_RESULT_CN.md":
        "09a966f158a10849490661d6f7e03540e726e17f5abf197602e8e6a435a5af38",
    "outputs/gate_f3_p1_20260925T050259_813979Z/report.json":
        "2125233b4cf2256cd8587febb148c0d880dbbaca596d259519a4aa18f2bdace6",
    "configs/gate_f3_p1_execution_status.json":
        "ce8463e546afc69ba8cf26a7ff4822531d43120b1d0392ab4d1791ab55d50fb6",
    "docs/GATE_F3_P1_EXECUTION_RESULT_CN.md":
        "aa53cfbd294b7c61d76b19d93a825ea1d58d66b70a7898808573c91ad135a37e",
    "outputs/gate_f3_p1_execution_20260925T055958_725913Z/report.json":
        "716490760d78d745ba2bfd49f6e0ab7074333835bb495420d1e19eaed92f84d4",
    "outputs/gate_f3_p1_execution_20260925T055958_725913Z/run_ledger.jsonl":
        "eb583ae9ff2c25e6ad96e83df076e550a39437b96107954190cd9ca23b6e6168",
}

SCIENTIFIC = {
    "src/dynamic_lisl/baseline_controllers.py":
        "44e920bca8fe686ea9c43ce4d9fe4c48679365a6eed0f706b43de20af74b31e8",
    "src/dynamic_lisl/scientific_controllers.py":
        "19726f56bb83c1c77073aac4618bbbe71733fdc9257b59dbf3ea905e6aaf3407",
    "src/dynamic_lisl/rollout_controller.py":
        "5d2b3d4170be148b5cbdf6808a57b9c9cbc105df487405bcef9904c292884e81",
    "src/dynamic_lisl/rollout_evaluator.py":
        "db7e6c187ff834e209a8afe8bab47ec8319fb394739f82f5162da7766bd1db8d",
    "src/dynamic_lisl/forecast.py":
        "fd9c2c56a6abc789cbb1e5d2fa5e2d8dec12a3b7be9bc568d4518602dea77a27",
    "src/dynamic_lisl/production_candidate_source.py":
        "16e70218cb5d097499a8728eba270085f1efb69b26a2349b717eb372dd21cf73",
    "src/dynamic_lisl/candidate_proposer.py":
        "b5d5fdc0e42f6f6646f3a88feaeaa16e22098b9c51cd8182c1f8d402c61d7b23",
    "src/dynamic_lisl/controller_runner.py":
        "187658932a7935135e58e25140db9f32ef0c99c376a11bf2fc206d0198071185",
    "src/dynamic_lisl/terminal_executor.py":
        "80634fd278655ca6c50a758afe5344f025154879ac71ba5b7dc455a210782583",
    "src/dynamic_lisl/gate_c_simplified_feasibility.py":
        "a194dc87ab8b6df15d15574f95a68588897f59dcd8779860e2bf652436311eac",
    "src/dynamic_lisl/transition_service_orchestrator.py":
        "5b674ee226ac07aba136fc7c207f6abe727a4d63ad9097c1291afa6217750fd4",
    "src/dynamic_lisl/common_router.py":
        "4c6e613533eb8837477dac9115ee8760752a6d9cfafeb54cea15ed5d676341ce",
    "src/dynamic_lisl/traffic_trace.py":
        "7d4e9a447e228678303a1686325d9ffd5e73e999de9b95933f4d4cfe3f1f413f",
}


def file_hash(relative):
    return hashlib.sha256((PROJECT/relative).read_bytes()).hexdigest()


def fixture():
    trace_hash, _ = f3_trace_identity(0.5)
    row = {
        "run_id": "UNIT-FIXTURE-EVIDENCE-PERSISTENCE",
        "block_id": "UNIT_ONLY", "controller": "UNIT",
        "rho": 0.5, "router": "UNIT_ROUTER", "scale": 4,
        "topology_regime": "UNIT_TOPOLOGY",
        "traffic_profile": "TRAFFIC_HOTSPOT_MIGRATION_V1",
        "traffic_trace_sha256": trace_hash,
    }
    metrics = {
        "evaluation_end_s": 2.0, "arrival_horizon_s": 240.0,
        "censored": False, "mean_bit_delay_s": 0.5,
        "J_bit_s": 50.0, "objective_J_bit_s": 50.0,
        "arrived_bits": 100.0, "delivered_bits": 100.0,
        "delivery_ratio": 1.0, "residual_backlog_bits": 0.0,
        "queued_bits_at_end": 0.0, "in_flight_bits_at_end": 0.0,
        "mean_queue_bits": 1.0, "max_queue_bits": 2.0,
        "route_change_count": 0, "active_dynamic_link_count": 1,
        "switch_count": 0, "BBM_count": 0, "MBB_count": 0,
        "max_abs_conservation_error_bits": 0.0,
        "max_relative_conservation_error": 0.0,
        "max_capacity_violation_bit_s": 0.0,
        "negative_queue_count": 0,
        "trace_sha256": "UNIT_ENGINE_TRACE", "runtime": 0.01,
        "outage_duration_s": 0.0,
    }
    result = {
        "metrics": metrics, "queues": {}, "in_flight": {},
        "route_state_events": [], "transition_episodes": [],
        "terminal_event_sequence": [],
        "final_state": {"terminal": {
            "links": [], "reservations": [], "events": []}},
    }
    audit = {
        "raw_BBM_count_before_cap": 40,
        "raw_MBB_count_before_cap": 50,
        "raw_BBM_count_after_cap": 32,
        "raw_MBB_count_after_cap": 32,
        "final_proposal_count": 16,
    }
    run = {
        "engine_result": result, "actions": [],
        "candidate_audits": [audit],
        "timeseries": [
            {"time_s": 0.0}, {"time_s": 1.0}, {"time_s": 2.0}],
        "decision_runtime_total_s": 0.0,
        "decision_runtime_mean_s": 0.0,
        "b4_branch_count_total": 0,
        "b4_valid_branch_count_total": 0,
        "b4_invalid_branch_count_total": 0,
    }
    final = summarize_run(row, run)
    report = detailed_invariant_report(row, run, final)
    return row, run, final, report


class EvidencePersistenceRepair(unittest.TestCase):
    def test_all_pass_persisted_before_return(self):
        row, run, final, report = fixture()
        self.assertTrue(all(x["pass"] for x in report["invariants"].values()))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            persist_run_evidence(out, row, run, final, report, True)
            saved = json.loads((out/"invariant_report.json").read_text())
            self.assertTrue(saved["aggregate_pass"])
            self.assertTrue(saved["aggregate_evaluated_after_initial_evidence_persistence"])
            self.assertTrue((out/"final_state_evidence.json").is_file())

    def test_one_forced_failure_persists_before_exception(self):
        row, run, final, report = fixture()
        report["invariants"]["queue_nonnegative"]["pass"] = False
        report["invariants"]["queue_nonnegative"]["observed_value"] = {
            "minimum_queue_bits": -1e-12, "negative_queue_count": 1}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with self.assertRaisesRegex(P1InvariantFailure,
                                        "failed_checks=queue_nonnegative"):
                persist_run_evidence(out, row, run, final, report, True)
            self.assertTrue((out/"invariant_report.json").is_file())
            self.assertTrue((out/"failure_summary.json").is_file())
            summary = json.loads((out/"failure_summary.json").read_text())
            self.assertEqual(summary["failed_invariant_names"],
                             ["queue_nonnegative"])
            self.assertIn("invariant_report.json", summary["evidence_files_written"])

    def test_multiple_failures_all_preserved(self):
        row, run, final, report = fixture()
        names = ["work_conservation", "capacity"]
        for name in names:
            report["invariants"][name]["pass"] = False
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with self.assertRaises(P1InvariantFailure) as caught:
                persist_run_evidence(out, row, run, final, report, True)
            self.assertIn("failed_checks=work_conservation,capacity",
                          str(caught.exception))
            summary = json.loads((out/"failure_summary.json").read_text())
            self.assertEqual(summary["failed_invariant_names"], names)
            self.assertFalse(summary["all_invariant_boolean_results"]["capacity"])

    def test_raw_values_and_frozen_tolerances_preserved(self):
        _, _, _, report = fixture()
        conservation = report["invariants"]["work_conservation"]
        capacity = report["invariants"]["capacity"]
        queue = report["invariants"]["queue_nonnegative"]
        self.assertEqual(conservation["observed_value"], 0.0)
        self.assertAlmostEqual(conservation["tolerance"], 0.0010000001)
        self.assertEqual(capacity["tolerance"], 0.01)
        self.assertEqual(queue["tolerance"], 0.0)
        self.assertEqual(report["invariants"]["candidate_raw_BBM_cap"]
                         ["limit_or_expected_value"], 32)

    def test_final_state_evidence_is_diagnostic(self):
        row, run, final, _ = fixture()
        evidence = final_state_evidence(row, run, final)
        self.assertTrue(evidence["diagnostic_only_not_accepted_scientific_result"])
        self.assertEqual(evidence["total_unfinished_work_bits"], 0.0)

    def test_scientific_hashes_unchanged(self):
        mismatches = [
            name for name, expected in SCIENTIFIC.items()
            if (file_hash(name) != expected
                and not approved_runtime_phase1_change(
                    PROJECT, name, expected, file_hash(name)))]
        self.assertEqual(mismatches, [])

    def test_no_registered_run_id_and_historical_evidence_unchanged(self):
        manifest = json.loads((PROJECT/"configs/gate_f3_execution_manifest_v1.json")
                              .read_text(encoding="utf-8"))
        registered = {row["run_id"] for row in manifest["runs"]
                      if row["block_id"] == "P1"}
        row, _, _, _ = fixture()
        self.assertNotIn(row["run_id"], registered)
        self.assertEqual({name: file_hash(name) for name in HISTORICAL},
                         HISTORICAL)


if __name__ == "__main__":
    unittest.main()



