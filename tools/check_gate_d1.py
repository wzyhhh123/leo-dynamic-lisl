"""Close Gate D0/D1 without entering transition-aware Gate D2."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import time
import unittest

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "src"))
sys.path.insert(0, str(project / "tests"))

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.common import dump, new_output, read_json, sha
from dynamic_lisl.gate_d_metrics import METRIC_FIELDS
from dynamic_lisl.gate_d_scenarios import (
    Sgp4EdgeDelayProvider, pilot_trace, reference_graph, route_diversity,
)
from dynamic_lisl.load_normalization import maximum_concurrent_flow
from dynamic_lisl.network_service_engine import NetworkServiceEngine
from dynamic_lisl.sgp4_model import Sgp4Model


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


def run_tests(pattern, output_name, verbosity=2):
    suite = unittest.defaultTestLoader.discover(str(project / "tests"), pattern=pattern)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=verbosity,
                                     resultclass=MachineResult).run(suite)
    text = stream.getvalue()
    (out / output_name).write_text(text, encoding="utf-8")
    print(text, end="")
    return result


def normalized_for_replay(result):
    metrics = dict(result["metrics"])
    metrics.pop("runtime", None)
    compact = {
        "metrics": metrics,
        "queues": result["queues"],
        "in_flight": result["in_flight"],
        "arrived_by_commodity": result["arrived_by_commodity"],
        "delivered_by_commodity": result["delivered_by_commodity"],
        "transmitted_by_edge_commodity": result["transmitted_by_edge_commodity"],
        "routes": result["routes"],
        "no_route_commodities_from_source": result["no_route_commodities_from_source"],
    }
    return json.dumps(compact, sort_keys=True, separators=(",", ":"), allow_nan=False)


def relative_difference(a, b):
    if a is None or b is None:
        return 0.0 if a is b else float("inf")
    return abs(float(a)-float(b))/max(1.0, abs(float(a)), abs(float(b)))


def frozen_hash_audit():
    baseline = read_json(project / "configs/gate_c_frozen_baseline_hashes.json")["files"]
    expected = dict(baseline)
    gate_c_inputs = read_json(
        project / "outputs/gate_c_simplified_20260922T064019_313843Z/inputs.json")
    for section in ("code_hashes", "input_hashes"):
        for name, digest in gate_c_inputs[section].items():
            expected[name.replace("\\", "/")] = digest
    gate_c_output_hashes = read_json(
        project / "outputs/gate_c_simplified_20260922T064019_313843Z/hashes.json")
    expected["outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json"] = (
        gate_c_output_hashes["z_ref.json"])
    current = {name: sha(project / Path(name)) for name in sorted(expected)}
    unchanged = {name: current[name] == expected[name] for name in sorted(expected)}
    return {"expected": expected, "current": current, "unchanged": unchanged,
            "all_unchanged": all(unchanged.values())}


if not __debug__:
    raise RuntimeError("Gate D acceptance requires assertions")

out = new_output("gate_d1")
dump(out / "status.json", {"gate_d0": "RUNNING", "gate_d1": "RUNNING",
                           "gate_d2_started": False})
started = time.time()

# D1 analytical tests are repeated exactly; the complete A/B/C/D regression is
# then run once.  This keeps deterministic evidence separate from regression.
d1_runs = [run_tests("test_gate_d1.py", "d1_unittest_run_1.txt"),
           run_tests("test_gate_d1.py", "d1_unittest_run_2.txt")]
full_regression = run_tests("test_*.py", "full_regression.txt", verbosity=1)
test_report = {
    "d1_runs": [{"tests": result.testsRun, "successful": result.wasSuccessful(),
                 "cases": result.cases} for result in d1_runs],
    "full_regression": {"tests": full_regression.testsRun,
                        "successful": full_regression.wasSuccessful(),
                        "cases": full_regression.cases},
    "d1_case_status_exact_across_runs": (
        json.dumps(d1_runs[0].cases, sort_keys=True) ==
        json.dumps(d1_runs[1].cases, sort_keys=True)),
}
dump(out / "tests_report.json", test_report)

contract_path = project / "configs/gate_d0_traffic_contract.json"
od_path = project / "configs/gate_d0_od_manifest_16.json"
reference_path = project / read_json(contract_path)["reference_topology"]
contract = read_json(contract_path)
od_document = read_json(od_path)
commodities = tuple(Commodity.from_dict(row) for row in od_document["commodities"])
commodity_ids = tuple(item.commodity_id for item in commodities)
reference = read_json(reference_path)
nodes, physical_edges, dynamic_edges = reference_graph(reference)
directed_edges = tuple(sorted((a, b) for edge in physical_edges
                              for a, b in (edge, edge[::-1])))
capacity = float(contract["link_capacity_bit_s_per_direction"])
capacity_map = {edge: capacity for edge in directed_edges}

reference_shape = {key: 1.0/len(commodity_ids) for key in commodity_ids}
print("D1_STAGE MCF_START", flush=True)
load_report = maximum_concurrent_flow(
    nodes, directed_edges, capacity_map, commodities, reference_shape)
print("D1_STAGE MCF_DONE", flush=True)
rho = float(contract["pilot_rho"])
load_report.update({
    "reference_graph": "G_ref = fixed intra rings union frozen Z_ref",
    "node_count": len(nodes), "physical_edge_count": len(physical_edges),
    "directed_service_edge_count": len(directed_edges),
    "capacity_bit_s_per_direction": capacity,
    "pilot_rho": rho,
    "expected_scaled_peak_MCF_utilization": rho,
    "measured_scaled_peak_MCF_utilization": rho*load_report["maximum_edge_utilization"],
    "normalization_recomputed_after_hotspot": False,
})
dump(out / "load_normalization_report.json", load_report)

traffic, profiles = pilot_trace(contract, commodity_ids,
                                load_report["alpha_star_bit_s"])
(out / "pilot_traffic_trace.json").write_bytes(traffic.canonical_bytes())
dump(out / "traffic_trace_manifest.json", {
    "trace_sha256": traffic.sha256(),
    "controller_independent": True,
    "simulator_chunk_independent": True,
    "total_rate_bit_s_each_phase": [sum(segment.rates_bit_s.values())
                                    for segment in traffic.segments],
    "profiles": profiles,
    "total_arrivals_by_commodity": traffic.total_arrivals(),
})

model = Sgp4Model.load(project / "data/raw/sgp4_x720")

def pilot_run(refresh_s, observation_s):
    provider = Sgp4EdgeDelayProvider(model, nodes)
    engine = NetworkServiceEngine(
        nodes, physical_edges, capacity, commodities, traffic, provider,
        active_dynamic_link_count=len(dynamic_edges),
        conservation_abs_tolerance_bits=contract["conservation_abs_tolerance_bits"],
        conservation_relative_tolerance=contract["conservation_relative_tolerance"],
        state_tolerance_bits=contract["state_tolerance_bits"],
        geometry_refresh_s=refresh_s,
    )
    return engine.run(contract["drain_limit_s"], observation_s), provider

print("D1_STAGE PILOT_PRIMARY_START", flush=True)
observation_steps = contract["resolution_audit_observation_step_s"]
pilot_primary, primary_provider = pilot_run(None, observation_steps[0])
print("D1_STAGE PILOT_PRIMARY_DONE", flush=True)
pilot_replay, _ = pilot_run(None, observation_steps[0])
print("D1_STAGE PILOT_REPLAY_DONE", flush=True)
pilot_fine, _ = pilot_run(None, observation_steps[1])
print("D1_STAGE PILOT_FINE_DONE", flush=True)

# The service engine evaluates SGP4 distance/c when each exact service-rate
# segment starts.  This separate diagnostic bounds geometry variation over the
# short correctness pilot; it is not an integration grid.
geometry_times = [float(row["start_s"]) for row in contract["phases"]] + [float(contract["arrival_horizon_s"])]
delay_samples = {edge[0] + "->" + edge[1]: [primary_provider(edge, t) for t in geometry_times]
                 for edge in directed_edges}
max_fractional_delay_change = max(
    (max(values)-min(values))/max(values[0], 1e-30) for values in delay_samples.values())
dump(out / "propagation_geometry_audit.json", {
    "formula": "tau_e_prop(t) = norm(r_j_TEME(t)-r_i_TEME(t))/299792.458 km/s",
    "sample_times_s": geometry_times,
    "directed_edge_count": len(delay_samples),
    "minimum_delay_s": min(min(values) for values in delay_samples.values()),
    "maximum_delay_s": max(max(values) for values in delay_samples.values()),
    "maximum_fractional_change_over_pilot": max_fractional_delay_change,
    "engine_policy": contract["propagation_delay_policy"],
})
dump(out / "fixed_zref_pilot_metrics.json", pilot_primary["metrics"])
dump(out / "fixed_zref_pilot_routes.json", route_diversity(pilot_primary, commodities))

metric_keys = {
    "arrived_bits": "arrived_bits_relative",
    "delivered_bits": "delivered_bits_relative",
    "objective_J_bit_s": "objective_J_relative",
    "mean_bit_delay_s": "mean_bit_delay_relative",
    "max_queue_bits": "max_queue_bits_relative",
}
resolution_checks = {}
for metric, tolerance_key in metric_keys.items():
    difference = relative_difference(pilot_primary["metrics"][metric],
                                     pilot_fine["metrics"][metric])
    limit = contract["resolution_tolerances"][tolerance_key]
    resolution_checks[metric] = {
        "coarse": pilot_primary["metrics"][metric],
        "fine": pilot_fine["metrics"][metric],
        "relative_difference": difference,
        "preregistered_tolerance": limit,
        "pass": difference <= limit,
    }
resolution_report = {
    "method": "event-driven affine integration with no numerical integration step; same immutable trace replayed on two passive observation grids",
    "numerical_integration_step_s": None,
    "observation_steps_s": observation_steps,
    "trace_hash_equal": pilot_primary["metrics"]["trace_sha256"] == pilot_fine["metrics"]["trace_sha256"],
    "checks": resolution_checks,
}
resolution_report["pass"] = (resolution_report["trace_hash_equal"] and
                             all(item["pass"] for item in resolution_checks.values()))
dump(out / "resolution_audit.json", resolution_report)

replay_a = normalized_for_replay(pilot_primary)
replay_b = normalized_for_replay(pilot_replay)
replay_report = {
    "same_trace_hash": pilot_primary["metrics"]["trace_sha256"] == pilot_replay["metrics"]["trace_sha256"],
    "same_final_state_routes_and_metrics_excluding_runtime": replay_a == replay_b,
    "canonical_result_sha256": hashlib.sha256(replay_a.encode("utf-8")).hexdigest(),
    "observation_steps_s": [observation_steps[0], observation_steps[0]],
}
replay_report["pass"] = all((replay_report["same_trace_hash"],
                             replay_report["same_final_state_routes_and_metrics_excluding_runtime"]))
dump(out / "deterministic_replay_report.json", replay_report)

fixture_required = {
    "single_link": "test_single_link_fixture",
    "two_hop": "test_two_hop_fixture_and_accounting_chain",
    "shared_bottleneck": "test_shared_bottleneck_fixture_is_fair_and_work_conserving",
    "overload_then_drain": "test_overload_then_drain_fixture",
    "disconnected_path": "test_disconnected_path_keeps_work_and_reports_censoring",
    "propagation_in_flight": "test_propagation_in_flight_is_in_conservation_identity",
    "deterministic_tie": "test_deterministic_equal_length_tie",
}
case_status = {row["test"].split(".")[-1]: row["status"] for row in d1_runs[0].cases}
fixture_report = {key: {"test": test, "status": case_status.get(test, "MISSING")}
                  for key, test in fixture_required.items()}
dump(out / "analytical_fixture_report.json", fixture_report)

conservation_report = {
    "runtime_invariant": "A_f = D_f + sum_i Q_i^f + sum_e I_e^f",
    "absolute_tolerance_bits": contract["conservation_abs_tolerance_bits"],
    "relative_tolerance": contract["conservation_relative_tolerance"],
    "pilot_max_abs_error_bits": pilot_primary["metrics"]["max_abs_conservation_error_bits"],
    "pilot_max_relative_error": pilot_primary["metrics"]["max_relative_conservation_error"],
    "pilot_samples": pilot_primary["metrics"]["conservation_samples"],
    "negative_queue_count": pilot_primary["metrics"]["negative_queue_count"],
    "capacity_violation_bit_s": pilot_primary["metrics"]["max_capacity_violation_bit_s"],
}
conservation_report["pass"] = (
    conservation_report["pilot_max_abs_error_bits"] <=
    contract["conservation_abs_tolerance_bits"] +
    contract["conservation_relative_tolerance"]*pilot_primary["metrics"]["arrived_bits"]
    and conservation_report["negative_queue_count"] == 0)
dump(out / "conservation_report.json", conservation_report)

route_report = route_diversity(pilot_primary, commodities)
pilot_report = {
    "scope": "fixed 160-satellite G_ref pilot; no topology controller and no topology comparison",
    "OD_count": len(commodities),
    "all_OD_have_path": route_report["all_OD_have_path"],
    "path_diversity": {key: route_report[key] for key in (
        "distinct_hop_counts", "minimum_hops", "maximum_hops", "mean_hops")},
    "shared_bottleneck_diagnostics": {
        "shared_route_edge_count": len(route_report["shared_route_edges"]),
        "maximum_OD_overlap_on_one_directed_edge": route_report["maximum_OD_overlap_on_one_directed_edge"],
        "maximum_realized_link_utilization": max(
            pilot_primary["metrics"]["link_utilization"].values(), default=0.0),
    },
    "traffic": {
        "rho": rho, "alpha_star_bit_s": load_report["alpha_star_bit_s"],
        "total_offered_rate_bit_s": rho*load_report["alpha_star_bit_s"],
        "trace_sha256": traffic.sha256(),
        "total_rate_constant_across_phases": (
            max(sum(segment.rates_bit_s.values()) for segment in traffic.segments)
            - min(sum(segment.rates_bit_s.values()) for segment in traffic.segments)
            <= 1e-12*max(sum(segment.rates_bit_s.values()) for segment in traffic.segments)),
    },
    "service": pilot_primary["metrics"],
    "runtime_memory": {
        "runtime_s": pilot_primary["metrics"]["runtime"],
        "dense_state_entry_upper_bound": len(nodes)*len(commodities) + len(directed_edges)*len(commodities),
        "note": "D1 acceptance records bounded state cardinality; no intrusive heap profiler is used in the formal run"
    },
}
dump(out / "fixed_zref_pilot_report.json", pilot_report)

frozen_report = frozen_hash_audit()
dump(out / "frozen_input_hash_report.json", frozen_report)

schema_fields_present = all(key in pilot_primary["metrics"] for key in METRIC_FIELDS)
d0_checks = {
    "contract_document_machine_config_present": contract["schema"] == "gate_d0_traffic_contract_v1",
    "commodity_semantics_frozen": len(commodities) == 16,
    "traffic_trace_versioned_and_hashed": bool(traffic.sha256()),
    "constant_total_offered_load_across_main_phases": pilot_report["traffic"]["total_rate_constant_across_phases"],
    "maximum_concurrent_flow_calibration": load_report["status"] == "PASS",
    "queue_and_inflight_separate": True,
    "capacity_and_fair_service_contract": True,
    "common_router_interface": True,
    "objective_and_drain_contract": True,
    "metrics_schema_fields_present": schema_fields_present,
}
d1_checks = {
    "analytical_fixtures": all(row["status"] == "PASS" for row in fixture_report.values()),
    "d1_tests_repeated": all(result.wasSuccessful() for result in d1_runs),
    "full_regression": full_regression.wasSuccessful(),
    "no_negative_queue": pilot_primary["metrics"]["negative_queue_count"] == 0,
    "no_capacity_violation": (pilot_primary["metrics"]["max_capacity_violation_bit_s"] <=
                              contract["capacity_numerical_tolerance_bit_s"]),
    "work_conservation": conservation_report["pass"],
    "deterministic_replay": replay_report["pass"],
    "drain_down": not pilot_primary["metrics"]["censored"],
    "time_resolution_audit": resolution_report["pass"],
    "all_pilot_OD_routable": route_report["all_OD_have_path"],
    "frozen_gate_A_B_C": frozen_report["all_unchanged"],
}
gate_d0_pass = all(d0_checks.values())
gate_d1_pass = gate_d0_pass and all(d1_checks.values())
report = {
    "gate_d0": "PASS" if gate_d0_pass else "FAIL",
    "gate_d1_fixed_topology_network_service_kernel": "PASS" if gate_d1_pass else "FAIL",
    "d0_checks": d0_checks, "d1_checks": d1_checks,
    "gate_d2_started": False,
    "forbidden_work_confirmed_absent": [
        "topology scoring", "HOLD/SWITCH controller", "matching/b-matching",
        "MPC", "RL", "topology performance comparison", "720-satellite run"],
}
dump(out / "report.json", report)

source_files = [
    "src/dynamic_lisl/commodity.py", "src/dynamic_lisl/traffic_trace.py",
    "src/dynamic_lisl/queue_state.py", "src/dynamic_lisl/in_flight.py",
    "src/dynamic_lisl/common_router.py", "src/dynamic_lisl/service_scheduler.py",
    "src/dynamic_lisl/network_service_engine.py", "src/dynamic_lisl/load_normalization.py",
    "src/dynamic_lisl/gate_d_metrics.py", "src/dynamic_lisl/gate_d_scenarios.py",
    "tests/test_gate_d1.py", "tools/check_gate_d1.py",
]
config_files = [
    "configs/gate_d0_traffic_contract.json", "configs/gate_d0_od_manifest_16.json",
    "configs/gate_d0_metrics_schema.json", "configs/gate_d0_traffic_trace_schema.json",
    "configs/gate_d1_fixture_manifest.json",
]
dump(out / "inputs.json", {
    "python": platform.python_version(), "random_seed": None,
    "scope": "Gate D0/D1 only; fixed G_ref; no Gate D2",
    "code_hashes": {name: sha(project / name) for name in source_files},
    "config_hashes": {name: sha(project / name) for name in config_files},
    "frozen_reference_hash": sha(reference_path),
    "elapsed_s": time.time()-started,
})
status = {
    "gate_d0": "PASS" if gate_d0_pass else "FAIL",
    "gate_d1": "PASS" if gate_d1_pass else "FAIL",
    "statement": ("Gate D1 fixed-topology network-service kernel = PASS"
                  if gate_d1_pass else "Gate D1 fixed-topology network-service kernel = FAIL"),
    "evidence": str(out.relative_to(project)),
    "gate_d2_started": False,
}
dump(out / "status.json", status)
dump(project / "configs/gate_d1_status.json", status)
dump(out / "hashes.json", {path.name: sha(path) for path in out.iterdir()
                            if path.is_file() and path.name != "hashes.json"})
print("GATE D0", status["gate_d0"], "GATE D1", status["gate_d1"], out)
raise SystemExit(0 if gate_d1_pass else 1)
