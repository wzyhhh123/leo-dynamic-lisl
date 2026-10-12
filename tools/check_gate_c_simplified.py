"""Close Gate C under the simplified parametric terminal geometry contract."""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys
import time
import unittest

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "src"))
sys.path.insert(0, str(project / "tests"))

from dynamic_lisl.common import dump, new_output, read_json, sha
from dynamic_lisl.gate_c_reference_topology import (
    audit_reference_candidate_idle_fraction, build_adjacent_plane_reference,
)
from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig, validate_rtn
from dynamic_lisl.gate_c_transition_report import summarize_transition_consequence
from dynamic_lisl.geometry_interface import VisibilityCatalog
from dynamic_lisl.sgp4_model import Sgp4Model
from dynamic_lisl.terminal_executor import Connect, TerminalExecutor
from dynamic_lisl.terminal_pair_intervals import (
    TerminalPairCatalog, TerminalPairWindow, refine_terminal_pair_windows,
)
from dynamic_lisl.transition_profiler import graph_components, profile_transition


class MachineResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"test": test.id(), "status": "PASS"})
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({"test": test.id(), "status": "FAIL",
                           "detail": self._exc_info_to_string(err, test)})
    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({"test": test.id(), "status": "ERROR",
                           "detail": self._exc_info_to_string(err, test)})


def stats(values):
    values = sorted(float(value) for value in values)
    if not values:
        return {"count": 0}
    def percentile(q):
        position = (len(values)-1)*q
        low, high = math.floor(position), math.ceil(position)
        return values[low] if low == high else values[low]*(high-position)+values[high]*(position-low)
    return {"count": len(values), "min": values[0], "median": percentile(0.5),
            "p95": percentile(0.95), "max": values[-1], "mean": sum(values)/len(values)}


def serialized_windows(windows):
    return "\n".join(json.dumps(window.to_dict(), sort_keys=True, ensure_ascii=False,
                                  allow_nan=False) for window in windows) + "\n"


def interval_resolution_audit(coarse, fine, allowed_shift_s=0.01):
    def group(windows):
        result = {}
        for window in windows:
            key = (window.sat_a, window.terminal_a, window.sat_b, window.terminal_b,
                   window.parent_start_s, window.parent_end_s)
            result.setdefault(key, []).append((window.start_s, window.end_s))
        return {key: sorted(value) for key, value in result.items()}
    first, second = group(coarse), group(fine)
    all_keys = sorted(set(first) | set(second))
    mismatch = [key for key in all_keys if len(first.get(key, ())) != len(second.get(key, ()))]
    shifts = []
    for key in all_keys:
        if key in mismatch:
            continue
        for a, b in zip(first.get(key, ()), second.get(key, ())):
            shifts.extend((abs(a[0]-b[0]), abs(a[1]-b[1])))
    maximum = max(shifts, default=0.0)
    return {"passed": not mismatch and maximum <= allowed_shift_s,
            "coarse_window_count": len(coarse), "fine_window_count": len(fine),
            "group_count_mismatch": len(mismatch),
            "max_boundary_shift_s": maximum,
            "allowed_boundary_shift_s": allowed_shift_s,
            "method": "2 s versus 1 s sign-scan with Brent root refinement",
            "limitation": "resolution consistency is not a mathematical no-missed-tangency proof"}


def reference_audit(reference, catalog, nodes, plane_by_satellite):
    bindings = reference["bindings"]
    terminals = [tuple(binding[side]) for binding in bindings for side in ("a", "b")]
    sat_pairs = [tuple(sorted((binding["a"][0], binding["b"][0]))) for binding in bindings]
    window_checks = [catalog.current_window(tuple(binding["a"]), tuple(binding["b"]), 0.0) is not None
                     for binding in bindings]
    fixed = {tuple(edge) for edge in reference["fixed_edges"]}
    components = graph_components(nodes, fixed | set(sat_pairs))
    return {"bilateral_explicit_terminal_pairs": all(len(binding["a"]) == 2 and len(binding["b"]) == 2
                                                       for binding in bindings),
            "no_dynamic_terminal_double_occupancy": len(terminals) == len(set(terminals)),
            "no_parallel_dynamic_satellite_links": len(sat_pairs) == len(set(sat_pairs)),
            "all_selected_pairs_for_feasible_at_t0": all(window_checks),
            "all_selected_pairs_inter_plane": all(plane_by_satellite[a] != plane_by_satellite[b]
                                                    for a, b in sat_pairs),
            "connected": len(components) == 1,
            "component_count": len(components),
            "pass": (len(terminals) == len(set(terminals)) and len(sat_pairs) == len(set(sat_pairs))
                     and all(window_checks) and len(components) == 1)}


def transition_examples():
    fixed = (("A", "B"), ("C", "D"))
    bbm = TerminalExecutor(("A", "B", "C", "D"))
    bbm.submit([Connect(("B", "D1"), ("C", "D1"), 20.0, 0.0, 0.0, 0.0)])
    bbm_profile = profile_transition(
        bbm, [Connect(("B", "D1"), ("D", "D1"), 20.0, 2.0, 2.0, 0.0)], fixed, 3.0)
    mbb = TerminalExecutor(("A", "B", "C", "D"))
    mbb.submit([Connect(("B", "D1"), ("C", "D1"), 20.0, 0.0, 0.0, 0.0)])
    mbb_profile = profile_transition(
        mbb, [Connect(("A", "D2"), ("D", "D2"), 20.0, 2.0, 2.0, 0.0,
                      release_after=((("B", "D1"), ("C", "D1")),))], fixed, 3.0)
    return {"BBM": summarize_transition_consequence(bbm_profile),
            "MBB": summarize_transition_consequence(mbb_profile)}


if not __debug__:
    raise RuntimeError("Gate C acceptance requires assertions")

out = new_output("gate_c_simplified")
dump(out / "status.json", {"gate_c_simplified": "RUNNING", "gate_d_started": False})
started = time.time()

# Acceptance and regression tests run twice for exact deterministic case/status evidence.
runs = []
run_texts = []
for number in (1, 2):
    suite = unittest.defaultTestLoader.discover(str(project / "tests"), pattern="test_*.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2,
                                     resultclass=MachineResult).run(suite)
    text = stream.getvalue()
    (out / ("unittest_run_%d.txt" % number)).write_text(text, encoding="utf-8")
    print(text, end="")
    runs.append(result)
    run_texts.append(json.dumps(result.cases, sort_keys=True, ensure_ascii=False))

hardware_path = project / "configs/hardware_gate_c_simplified_v1.json"
hardware = read_json(hardware_path)
terminal_config = TerminalGeometryConfig.from_dict(hardware)
geometry_meta_path = project / "outputs/geometry_20260921T053240_016088Z/metadata.json"
geometry_meta = read_json(geometry_meta_path)
manifest_path = project / "data/raw/sgp4_x720/manifest.json"
manifest = read_json(manifest_path)
interval_path = project / "outputs/visibility_20260921T055451_308214Z/subset_160/intervals.jsonl"
satellite_catalog = VisibilityCatalog.from_gate_a_asset(
    interval_path, geometry_meta["sat_ids"], geometry_meta["plane_ids"])
model = Sgp4Model.load(project / "data/raw/sgp4_x720")
subset_ids = tuple(geometry_meta["sat_ids"][:160])
plane_by_satellite = dict(zip(geometry_meta["sat_ids"], geometry_meta["plane_ids"]))
slot_by_satellite = {row["sat_name"]: row["slot_id"] for row in manifest["satellites"]}

# RTN audit on all 160 satellites at start, middle, and end of the 600 s asset.
audit_times = [0.0, 300.0, 600.0]
position, velocity = model.state(audit_times, subset_ids)
rtn_audit = validate_rtn(position, velocity)
rtn_audit.update({"satellite_count": len(subset_ids), "times_s": audit_times,
                  "frame": "TEMEOfDate", "attitude": "deterministic ideal RTN"})
dump(out / "rtn_audit.json", rtn_audit)

# Coarse, deterministic replay, and finer-resolution interval assets.
coarse = refine_terminal_pair_windows(
    model, satellite_catalog, terminal_config, subset_ids,
    hardware["terminal_interval_scan_step_s"],
    hardware["terminal_interval_boundary_tolerance_s"],
)
coarse_replay = refine_terminal_pair_windows(
    model, satellite_catalog, terminal_config, subset_ids,
    hardware["terminal_interval_scan_step_s"],
    hardware["terminal_interval_boundary_tolerance_s"],
)
fine = refine_terminal_pair_windows(
    model, satellite_catalog, terminal_config, subset_ids,
    hardware["terminal_interval_fine_scan_step_s"],
    hardware["terminal_interval_boundary_tolerance_s"],
)
coarse_text = serialized_windows(coarse)
coarse_replay_text = serialized_windows(coarse_replay)
(out / "terminal_pair_intervals.jsonl").write_text(coarse_text, encoding="utf-8")
resolution = interval_resolution_audit(coarse, fine)
dump(out / "terminal_pair_interval_resolution_audit.json", resolution)

terminal_catalog = TerminalPairCatalog(
    coarse, plane_by_satellite, satellite_catalog, model, terminal_config)
setup = hardware["audit_setup_fixture"]
reference = build_adjacent_plane_reference(
    terminal_catalog, subset_ids, plane_by_satellite, slot_by_satellite, 0.0,
    setup["retarget_a_s"], setup["retarget_b_s"], setup["acquisition_s"],
)
dump(out / "z_ref.json", reference)
z_audit = reference_audit(reference, terminal_catalog, subset_ids, plane_by_satellite)
z_audit["projected_mbb"] = audit_reference_candidate_idle_fraction(terminal_catalog, reference)
z_audit["right_censored_selected_link_count"] = sum(
    terminal_catalog.current_window(tuple(binding["a"]), tuple(binding["b"]), 0.0).right_censored
    for binding in reference["bindings"])
z_audit["warning"] = ("All selected intervals end at the 600 s prediction horizon; reported lifetime is a conservative asset horizon, not natural expiry"
                      if z_audit["right_censored_selected_link_count"] else None)
dump(out / "z_ref_audit.json", z_audit)

satellite_candidates = satellite_catalog.inter_plane_candidates(0.0, subset_ids)
terminal_candidates = terminal_catalog.terminal_pair_candidates(0.0, subset_ids)
degrees = Counter()
for window in terminal_candidates:
    degrees[window.endpoint_a] += 1
    degrees[window.endpoint_b] += 1
degree_by_type = {terminal: stats(degrees[(satellite, terminal)] for satellite in subset_ids)
                  for terminal in ("D1", "D2")}
incidence_by_type = {terminal: sum(degrees[(satellite, terminal)] for satellite in subset_ids)
                     for terminal in ("D1", "D2")}
plane_gap = Counter(str(window.plane_gap) for window in terminal_candidates)
interval_plane_gap = Counter(str(window.plane_gap) for window in coarse)
setup_ready = max(setup["retarget_a_s"], setup["retarget_b_s"])+setup["acquisition_s"]
candidate_audit = {
    "scope": "accepted 4-plane/160-satellite subset, t=0 s unless marked interval-wide",
    "satellite_pair_candidate_count": len(satellite_candidates),
    "inter_plane_satellite_pair_candidate_count": len(satellite_candidates),
    "expanded_terminal_pair_candidate_count": 4*len(satellite_candidates),
    "bilateral_for_feasible_terminal_pair_count": len(terminal_candidates),
    "for_pass_ratio": len(terminal_candidates)/(4*len(satellite_candidates)),
    "terminal_candidate_degree": degree_by_type,
    "terminal_candidate_incidence": incidence_by_type,
    "d1_to_d2_incidence_ratio": (incidence_by_type["D1"]/incidence_by_type["D2"]
                                  if incidence_by_type["D2"] else None),
    "plane_gap_distribution_at_t0": dict(sorted(plane_gap.items(), key=lambda item: int(item[0]))),
    "adjacent_terminal_pair_count_at_t0": sum(window.plane_gap == 1 for window in terminal_candidates),
    "nonadjacent_terminal_pair_count_at_t0": sum(window.plane_gap != 1 for window in terminal_candidates),
    "terminal_pair_interval_count": len(coarse),
    "interval_plane_gap_distribution": dict(sorted(interval_plane_gap.items(), key=lambda item: int(item[0]))),
    "terminal_pair_interval_duration_s": stats(window.end_s-window.start_s for window in coarse),
    "remaining_lifetime_s_at_t0": stats(window.end_s for window in terminal_candidates),
    "usable_lifetime_s_at_t0": stats(window.end_s-setup_ready for window in terminal_candidates),
    "right_censored_candidate_count_at_t0": sum(window.right_censored for window in terminal_candidates),
    "projected_mbb": z_audit["projected_mbb"],
    "diagnostics": {
        "action_space_empty": not terminal_candidates,
        "D1_zero_total_incidence": incidence_by_type["D1"] == 0,
        "D2_zero_total_incidence": incidence_by_type["D2"] == 0,
        "reference_topology_connected": z_audit["connected"],
        "interpretation": "90 degree FoR is sensitivity-only; ratios are structural diagnostics, not hardware performance claims",
    },
}
dump(out / "candidate_space_audit.json", candidate_audit)

transition_report = transition_examples()
dump(out / "transition_consequence_report.json", transition_report)

baseline_path = project / "configs/gate_c_frozen_baseline_hashes.json"
baseline = read_json(baseline_path)
current_hashes = {name: sha(project / name) for name in baseline["files"]}
frozen_report = {"baseline": baseline["files"], "current": current_hashes,
                 "unchanged": {name: baseline["files"][name] == current_hashes[name]
                               for name in baseline["files"]}}
frozen_report["all_unchanged"] = all(frozen_report["unchanged"].values())
dump(out / "frozen_input_hash_report.json", frozen_report)

deterministic = {
    "unit_test_case_status_exact_across_two_runs": run_texts[0] == run_texts[1],
    "terminal_pair_interval_asset_exact_across_two_runs": coarse_text == coarse_replay_text,
    "terminal_pair_interval_sha256": hashlib.sha256(coarse_text.encode("utf-8")).hexdigest(),
    "test_run_count": 2,
    "tests_per_run": runs[0].testsRun,
}
deterministic["pass"] = all((deterministic["unit_test_case_status_exact_across_two_runs"],
                             deterministic["terminal_pair_interval_asset_exact_across_two_runs"]))
dump(out / "deterministic_replay_report.json", deterministic)

tests_pass = all(result.wasSuccessful() for result in runs)
pass_items = {
    "RTN_attitude": rtn_audit["passed"],
    "distinct_D1_D2_mounting": hardware["terminal_mounting_rtn"]["D1"] != hardware["terminal_mounting_rtn"]["D2"],
    "bilateral_FoR_filtering": candidate_audit["for_pass_ratio"] < 1.0 and len(terminal_candidates) > 0,
    "terminal_pair_intervals": len(coarse) > 0 and resolution["passed"],
    "remaining_and_usable_lifetime": candidate_audit["usable_lifetime_s_at_t0"]["count"] > 0,
    "BBM_MBB_transition_reporting": transition_report["BBM"]["transition_mode"] == "BBM" and transition_report["MBB"]["transition_mode"] == "MBB",
    "connected_reference_topology": z_audit["pass"],
    "acceptance_and_regression_tests": tests_pass,
    "deterministic_replay": deterministic["pass"],
    "frozen_Gate_A_B_inputs": frozen_report["all_unchanged"],
}
gate_pass = all(pass_items.values())
source_files = [
    project / "src/dynamic_lisl/gate_c_terminal_geometry.py",
    project / "src/dynamic_lisl/terminal_pair_intervals.py",
    project / "src/dynamic_lisl/gate_c_simplified_feasibility.py",
    project / "src/dynamic_lisl/gate_c_reference_topology.py",
    project / "src/dynamic_lisl/gate_c_transition_report.py",
    project / "tests/test_gate_c_simplified.py",
    Path(__file__),
]
inputs = {"python": platform.python_version(), "random_seed": None,
          "scope": "Gate C simplified terminal geometry only; no traffic/queue/routing/optimization/RL",
          "code_hashes": {str(path.relative_to(project)): sha(path) for path in source_files},
          "input_hashes": {str(path.relative_to(project)): sha(path) for path in (
              geometry_meta_path, manifest_path, interval_path, hardware_path, baseline_path)},
          "elapsed_s": time.time()-started}
dump(out / "inputs.json", inputs)
report = {"gate_c": ("PASS under simplified parametric terminal model" if gate_pass else "FAIL"),
          "pass_items": pass_items, "tests_per_run": runs[0].testsRun,
          "repeated_test_runs": 2, "candidate_space": candidate_audit,
          "reference_topology": {key: value for key, value in reference.items()
                                 if key not in ("bindings", "fixed_edges")},
          "assumptions": ["deterministic ideal RTN/nadir-pointing attitude",
                          "D1=+N and D2=-N are simplified configured mountings",
                          "90 degree conic FoR is sensitivity-only, not calibrated hardware",
                          "tracking capability is sufficient inside FoR in v1",
                          "5000 km remains a diagnostic geometry search cutoff"],
          "deferred": ["detailed PAT and acquisition FoV", "gimbal dynamics", "tracking-rate/acceleration limit",
                       "pointing jitter", "Sun keep-out", "body blockage", "optical link budget",
                       "traffic, queue, routing, matching, MPC and RL"],
          "gate_d_technically_ready": gate_pass,
          "gate_d_started": False}
dump(out / "report.json", report)
status = {"gate_c_simplified": "PASS" if gate_pass else "FAIL",
          "statement": report["gate_c"], "evidence": str(out.relative_to(project)),
          "gate_d_technically_ready": gate_pass, "gate_d_started": False}
dump(out / "status.json", status)
dump(project / "configs/gate_c_simplified_status_v1.json", status)
dump(out / "hashes.json", {path.name: sha(path) for path in out.iterdir()
                            if path.is_file() and path.name != "hashes.json"})
print("GATE C SIMPLIFIED", status["gate_c_simplified"], out)
raise SystemExit(0 if gate_pass else 1)
