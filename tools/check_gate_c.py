"""Run Gate C core twice, build the 160-satellite Z_ref study, and hash evidence."""
from pathlib import Path
import hashlib
import io
import json
import platform
import sys
import unittest

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "src"))
sys.path.insert(0, str(project / "tests"))

from dynamic_lisl.common import dump, new_output, sha
from dynamic_lisl.geometry_interface import VisibilityCatalog
from dynamic_lisl.reference_topology import build_reference_constructions
import test_gate_c as tests


class MachineResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
    def addSuccess(self, test):
        super().addSuccess(test); self.cases.append({"test": test.id(), "status": "PASS"})
    def addFailure(self, test, err):
        super().addFailure(test, err); self.cases.append({"test": test.id(), "status": "FAIL",
                                                          "detail": self._exc_info_to_string(err, test)})
    def addError(self, test, err):
        super().addError(test, err); self.cases.append({"test": test.id(), "status": "ERROR",
                                                        "detail": self._exc_info_to_string(err, test)})


if not __debug__:
    raise RuntimeError("Gate C requires assertions; do not run Python with -O")

out = new_output("gate_c")
dump(out / "status.json", {"gate_c_core_transition_framework": "RUNNING",
                            "hardware_calibration": "PENDING"})

runs = []
trace_text = []
for run in (1, 2):
    tests.TRACE_RECORDS.clear()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    result = unittest.TextTestRunner(stream=stream, verbosity=2,
                                     resultclass=MachineResult).run(suite)
    (out / ("unittest_run_%d.txt" % run)).write_text(stream.getvalue(), encoding="utf-8")
    print(stream.getvalue(), end="")
    trace = json.dumps(tests.TRACE_RECORDS, sort_keys=True, ensure_ascii=False, allow_nan=False)
    trace_text.append(trace)
    runs.append(result)
(out / "representative_transition_traces.json").write_text(trace_text[0], encoding="utf-8")

# Actual accepted 4-plane/160-satellite asset; this is a construction study, not a
# performance experiment and not an automatic reference freeze.
geometry_meta_path = project / "outputs/geometry_20260921T053240_016088Z/metadata.json"
geometry_meta = json.loads(geometry_meta_path.read_text(encoding="utf-8"))
tle_manifest_path = project / "data/raw/sgp4_x720/manifest.json"
tle_manifest = json.loads(tle_manifest_path.read_text(encoding="utf-8"))
records = tle_manifest["satellites"]
satellite_ids = geometry_meta["sat_ids"]
plane_ids = geometry_meta["plane_ids"]
slot_by_satellite = {row["sat_name"]: row["slot_id"] for row in records}
plane_by_satellite = dict(zip(satellite_ids, plane_ids))
interval_path = project / "outputs/visibility_20260921T055451_308214Z/subset_160/intervals.jsonl"
catalog = VisibilityCatalog.from_gate_a_asset(interval_path, satellite_ids, plane_ids)
subset_ids = satellite_ids[:160]
study = build_reference_constructions(catalog, subset_ids, plane_by_satellite,
                                      slot_by_satellite, 0.0)
dump(out / "z_ref_study.json", study)

acceptance = {
    "C0_geometry_executor_interface": ["test_c0_half_open_window_and_censor_semantics",
                                         "test_c0_inter_plane_scope_excludes_same_plane"],
    "C1_reference_study": ["test_reference_constructions_connected_and_not_fully_occupied",
                             "test_disconnected_reference_initialization"],
    "C2_physical_terminal_feasibility": ["test_visible_but_hardware_range_infeasible",
                                           "test_ready_equal_or_after_visibility_end_rejected",
                                           "test_geometry_visible_but_terminal_reserved",
                                           "test_allocator_order_invariant_and_no_double_occupancy",
                                           "test_subset_allocator_rejects_external_satellite"],
    "C3_transition_profiler": ["test_two_simultaneous_removals_atomic_and_unsafe",
                                 "test_draining_active_connected_admit_disconnected",
                                 "test_setup_visibility_expiry_aborts_without_link_up",
                                 "test_pending_plus_new_batch_profiled_together",
                                 "test_transition_replay_exactly_deterministic"],
    "C4_operational_policy": ["test_bbm_two_second_partition_policy_matrix",
                                "test_outage_equal_to_bound_is_accepted",
                                "test_mbb_no_partition_both_policies_accept",
                                "test_unrecoverable_partition_rejected_by_bounded_policy",
                                "test_natural_expiry_unsafe_has_specific_reason",
                                "test_hold_only_when_all_non_hold_actions_rejected"],
    "C6_acceptance_regressions": ["test_mbb_setup_abort_keeps_old_link"],
}
case_status = {x["test"].split(".")[-1]: x["status"] for x in runs[0].cases}
acceptance_report = {name: {"status": "PASS" if all(case_status.get(test) == "PASS" for test in names) else "FAIL",
                             "tests": names} for name, names in acceptance.items()}
repeat = trace_text[0] == trace_text[1] and runs[0].cases == runs[1].cases
core_pass = (all(run.wasSuccessful() for run in runs) and repeat and
             all(x["status"] == "PASS" for x in acceptance_report.values()))

source_files = [
    project / "src/dynamic_lisl/geometry_interface.py",
    project / "src/dynamic_lisl/physical_feasibility.py",
    project / "src/dynamic_lisl/transition_profiler.py",
    project / "src/dynamic_lisl/operational_policy.py",
    project / "src/dynamic_lisl/reference_topology.py",
    project / "src/dynamic_lisl/terminal_executor.py",
    project / "tests/test_gate_c.py",
    Path(__file__),
]
inputs = {
    "scope": "Gate C core and Z_ref study only; no traffic/routing/optimization/performance run",
    "python": platform.python_version(), "random_seed": None,
    "code_hashes": {str(path.relative_to(project)): sha(path) for path in source_files},
    "input_hashes": {str(path.relative_to(project)): sha(path) for path in [
        geometry_meta_path, tle_manifest_path, interval_path,
        project / "configs/gate_a_acceptance_v0.3.json",
        project / "configs/gate_b_status.json",
        project / "configs/hardware_gate_c.json"]},
}
dump(out / "inputs.json", inputs)
trace_records = json.loads(trace_text[0])
profile_records = [row["profile"] for row in trace_records if row.get("profile")]
classification_counts = {}
for profile in profile_records:
    label = profile.get("classification", "not_classified")
    classification_counts[label] = classification_counts.get(label, 0) + 1
outage_durations = [profile["outage_duration"] for profile in profile_records
                    if profile.get("outage_duration") is not None]
rejection_outage_statistics = {
    "profile_fixture_count": len(profile_records),
    "classification_counts": classification_counts,
    "outage_duration_s": {
        "count": len(outage_durations),
        "min": min(outage_durations) if outage_durations else None,
        "max": max(outage_durations) if outage_durations else None,
        "mean": (sum(outage_durations) / len(outage_durations)) if outage_durations else None,
    },
    "explicit_rejection_fixtures": {
        "HARDWARE_RANGE_FAIL": 1,
        "RESERVATION_CONFLICT": 1,
        "INSUFFICIENT_LIFETIME": 2,
        "NOT_VISIBLE_HOLD_ONLY": 1,
        "STRICT_CONNECTIVITY_VIOLATION": 1,
        "OUTAGE_BOUND_EXCEEDED": 1,
        "UNRECOVERABLE_PARTITION": 1,
        "NATURAL_EXPIRY_UNSAFE": 1,
        "SUBSET_EXTERNAL_SATELLITE": 1
    },
    "note": "Counts are deterministic acceptance fixtures, not empirical network rates"
}
dump(out / "rejection_outage_statistics.json", rejection_outage_statistics)

report = {
    "gate_c_core_transition_framework": "PASS" if core_pass else "FAIL",
    "hardware_calibration": "PENDING",
    "full_gate_c_status": "CORE_PASS_HARDWARE_PENDING" if core_pass else "FAIL",
    "tests_run": runs[0].testsRun, "repeated_runs": 2,
    "deterministic_replay_exact": repeat, "acceptance": acceptance_report,
    "cases": runs[0].cases,
    "z_ref_study": {name: {key: value for key, value in data.items() if key != "bindings"}
                    for name, data in study["constructions"].items()},
    "z_ref_selected": None,
    "rejection_outage_statistics": rejection_outage_statistics,
    "performance_experiments_run": False,
}
dump(out / "report.json", report)
dump(out / "status.json", {"gate_c_core_transition_framework": report["gate_c_core_transition_framework"],
                            "hardware_calibration": "PENDING",
                            "full_gate_c_status": report["full_gate_c_status"]})
dump(out / "hashes.json", {path.name: sha(path) for path in out.iterdir()
                            if path.is_file() and path.name != "hashes.json"})
print("GATE C", report["full_gate_c_status"], out)
raise SystemExit(0 if core_pass else 1)



