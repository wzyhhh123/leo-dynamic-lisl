"""Validate the result-blind Gate F3-v1 experiment preregistration only."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = "configs/gate_f3_experiment_human_freeze_v1.json"


def read(name):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()


def canonical_sha(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_canonical(value):
    payload = dict(value)
    expected = payload.pop("canonical_sha256")
    return canonical_sha(payload) == expected


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def performance_artifacts():
    forbidden_names = {
        "controller_performance.json", "B0_vs_B4.json", "ranking.json",
        "performance_plot.png", "performance_plot.pdf", "performance_plot.svg",
    }
    found = []
    for path in (PROJECT / "outputs").rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if (path.name in forbidden_names
                or "gate_f3_performance" in str(path).lower()
                or lowered.startswith("performance_plot")):
            found.append(str(path.relative_to(PROJECT)).replace("\\", "/"))
    return sorted(found)


contract = read(CONTRACT_PATH)
execution = read("configs/gate_f3_execution_manifest_v1.json")
traffic = read("configs/gate_f3_traffic_profiles_v1.json")
stable = read("configs/gate_f3_traffic_stable_v1.json")
hotspot = read("configs/gate_f3_traffic_hotspot_migration_v1.json")
b2 = read("configs/gate_f3_b2_grid_v1.json")
censor = read("configs/gate_f3_censor_policy_v1.json")
figures = read("configs/gate_f3_figure_cases_v1.json")
od = read("configs/gate_d0_od_manifest_16.json")
alpha = read("outputs/gate_d1_20260922T133909_838853Z/load_normalization_report.json")
f2 = read("configs/gate_f2_closure_status.json")

checks = {}
checks["required_parent_assets_exist"] = all(
    (PROJECT / name).is_file()
    for records in contract["parent_hashes"].values() for name in records)
parent_expected = contract["parent_hashes"]
parent_pre = {group: {name: sha(name) for name in records}
              for group, records in parent_expected.items()}
checks["frozen_parent_hashes_unchanged_pre"] = parent_pre == parent_expected
a_to_e2 = read("configs/gate_f0_frozen_a_to_e2_hashes.json")
a_to_e2_pre = {name: sha(name) for name in a_to_e2["files"]}
checks["all_148_A_to_E2_hashes_unchanged_pre"] = (
    len(a_to_e2["files"]) == 148 and a_to_e2_pre == a_to_e2["files"])
checks["gate_F2_closure_yes"] = all((
    f2["gate_f2_overall"] == "PASS", f2["gate_f2_closure"] == "YES",
    f2["F3_readiness"] == "READY"))
checks["F2_0_canonical_unchanged"] = (
    read("configs/gate_f2_rollout_human_freeze_v1.json")["canonical_sha256"]
    == "ca82a1e49f6bdbe56a4c9f2fb79299eac0174844e0bdc6608ea3cb4f12f90b2a")
checks["F3_performance_absent_before_freeze"] = performance_artifacts() == []

all_manifests = [contract, b2, traffic, stable, hotspot, execution, censor, figures]
checks["all_machine_contract_canonical_hashes_valid"] = all(
    verify_canonical(value) for value in all_manifests)
checks["contract_result_blind_and_not_started"] = all((
    contract["result_blind"] is True,
    contract["performance_started"] is False,
    contract["RL_started"] is False,
    execution["performance_started"] is False,
))

od_ids = [row["commodity_id"] for row in od["commodities"]]
source_plane = {row["commodity_id"]: row["source"].split("_")[0]
                for row in od["commodities"]}
expected_h0 = [key for key in od_ids if source_plane[key] == "X0"]
expected_h2 = [key for key in od_ids if source_plane[key] == "X2"]
checks["OD_count_exactly_16"] = (
    len(od_ids) == 16 and len(set(od_ids)) == 16
    and contract["od_manifest"]["commodity_count"] == 16)
checks["OD_manifest_hash_exact"] = all((
    sha("configs/gate_d0_od_manifest_16.json")
        == "b8e46dd988e4f5136eeb5b8adea4272ad93b3fafc5ed7fc4fb537eff167173de",
    contract["od_manifest"]["sha256"]
        == "b8e46dd988e4f5136eeb5b8adea4272ad93b3fafc5ed7fc4fb537eff167173de",
))
checks["H0_nonempty_and_exact"] = bool(expected_h0) and hotspot["H0"] == expected_h0
checks["H2_nonempty_and_exact"] = bool(expected_h2) and hotspot["H2"] == expected_h2

checks["alpha_star_unique_frozen_source"] = all((
    alpha["alpha_star_bit_s"] == 26666666666.666664,
    alpha["normalization_recomputed_after_hotspot"] is False,
    contract["normalization"]["alpha_star_bit_s"] == alpha["alpha_star_bit_s"],
    contract["normalization"]["source"]
        == "outputs/gate_d1_20260922T133909_838853Z/load_normalization_report.json",
    traffic["alpha_star"]["identifier"]
        == "GATE_D1_FROZEN_REFERENCE_MCF_ALPHA_STAR",
    traffic["alpha_star"]["recomputed_by_phase_or_controller"] is False,
))

g0 = traffic["g0"]
g_total = traffic["G_total"]
checks["base_g0_nonnegative_positive_total"] = all((
    set(g0) == set(od_ids), all(float(value) >= 0.0 for value in g0.values()),
    g_total > 0.0, abs(sum(g0.values())-g_total) <= 1e-12,
))
hotspot_sums = [sum(row["g"].values()) for row in hotspot["segments"]]
stable_sums = [sum(row["g"].values()) for row in stable["segments"]]
checks["hotspot_constant_total_load"] = all(
    abs(value-g_total) <= hotspot["constant_total_tolerance"]
    for value in hotspot_sums)
checks["stable_constant_total_load"] = all(
    abs(value-g_total) <= stable["constant_total_tolerance"]
    for value in stable_sums)
checks["hotspot_multiplier_and_renormalization_exact"] = all((
    hotspot["hotspot_multiplier"] == 2.0,
    hotspot["renormalization_formula"]
        == "g_hot_f=g_tilde_f*G_total/sum_j(g_tilde_j)",
    hotspot["normalization_recomputed_per_phase"] is False,
))
checks["stage_boundaries_exact"] = (
    hotspot["stage_boundaries_s"] == [0.0, 60.0, 120.0, 180.0, 240.0])
checks["only_two_traffic_profiles"] = (
    set(traffic["profiles"]) == {
        "TRAFFIC_HOTSPOT_MIGRATION_V1", "TRAFFIC_STABLE_V1"})

checks["rho_sets_exact"] = all((
    contract["rho"]["primary"] == [0.5, 0.8, 1.0],
    contract["rho"]["robustness"] == [0.2, 1.2],
    traffic["rho_primary"] == [0.5, 0.8, 1.0],
    traffic["rho_robustness"] == [0.2, 1.2],
))
checks["scale_exactly_160"] = all((
    contract["scale_satellites"] == 160,
    execution["scale"] == 160,
    set(row["scale"] for row in execution["runs"]) == {160},
))
checks["no_240_or_720_runs"] = not any(
    row["scale"] in (240, 720) for row in execution["runs"])
checks["arrival_and_drain_limits_exact"] = all((
    contract["arrival_horizon_s"] == 240.0,
    contract["absolute_drain_limit_s"] == 600.0,
    censor["arrival_horizon_s"] == 240.0,
    censor["absolute_drain_limit_s"] == 600.0,
))

checks["B2_grid_exact"] = b2["configurations"] == [
    {"controller_id": "B2_H4", "minimum_hold_s": 4.0,
     "improvement_threshold": 0.0},
    {"controller_id": "B2_H8", "minimum_hold_s": 8.0,
     "improvement_threshold": 0.0},
]
checks["core_controller_set_exact"] = (
    contract["controllers"]["core"] == ["B0", "B1", "B3", "B4"])
checks["topology_regimes_exact"] = set(contract["topology_regimes"]) == {
    "Z_MODERATE", "Z_SPARSE_REFERENCE"}
checks["router_assignments_exact"] = contract["routers"] == {
    "primary": "SHORTEST_PROPAGATION_DELAY",
    "robustness": "LOAD_AWARE_CURRENT_STATE",
}

runs = execution["runs"]
run_ids = [row["run_id"] for row in runs]
blocks = {row["block_id"]: row for row in execution["blocks"]}
actual_counts = Counter(row["block_id"] for row in runs)
expected_counts = {"P1": 12, "P2": 12, "R1": 16,
                   "R2": 8, "R3": 8, "R4": 4}
checks["block_counts_exact"] = actual_counts == expected_counts
checks["block_cross_product_counts_reproduced"] = all(
    row["expected_run_count"]
    == len(row["topologies"])*len(row["rho"])*len(row["controllers"])
    == actual_counts[row["block_id"]]
    for row in execution["blocks"])
checks["total_unique_run_ids_60"] = (
    len(runs) == execution["planned_run_count"] == 60
    and len(set(run_ids)) == 60)
checks["no_duplicate_run_id"] = len(run_ids) == len(set(run_ids))
checks["execution_order_exact"] = (
    execution["execution_order"] == ["P1", "P2", "R1", "R2", "R3", "R4"]
    and contract["execution_order"] == execution["execution_order"])
checks["all_runs_planned_not_executed"] = all(
    row["performance_status"] == "PLANNED_NOT_EXECUTED" for row in runs)
checks["deterministic_seed_policy"] = all((
    execution["stochastic_seed_policy"] == "NOT_APPLICABLE",
    execution["replicate_count_per_unique_run_id"] == 1,
    all(row["replicate"] == 1 and row["stochastic_seed"] is None for row in runs),
))

strata = defaultdict(list)
for row in runs:
    key = (row["scale"], row["topology_regime"], row["router"],
           row["traffic_profile"], row["rho"])
    strata[key].append(row)
checks["paired_controllers_share_traffic_hash"] = all(
    len({row["traffic_trace_sha256"] for row in group}) == 1
    for group in strata.values())
checks["router_fairness_within_strata"] = all(
    len({row["router"] for row in group}) == 1 for group in strata.values())

profile_by_id = {stable["profile_id"]: stable, hotspot["profile_id"]: hotspot}
def expected_trace_hash(profile_id, rho):
    profile = profile_by_id[profile_id]
    document = {
        "schema": "gate_f3_exogenous_trace_identity_v1",
        "od_manifest_sha256": contract["od_manifest"]["sha256"],
        "alpha_star_bit_s": contract["normalization"]["alpha_star_bit_s"],
        "profile_id": profile_id,
        "profile_canonical_sha256": profile["canonical_sha256"],
        "rho": rho,
        "segments": [{
            "start_s": segment["start_s"], "end_s": segment["end_s"],
            "rates_bit_s": {
                key: rho*contract["normalization"]["alpha_star_bit_s"]
                     *segment["g"][key]
                for key in od_ids},
        } for segment in profile["segments"]],
        "after_240_s": "ALL_RATES_ZERO",
    }
    return canonical_sha(document)

checks["traffic_hashes_reproducible"] = all(
    row["traffic_trace_sha256"]
    == expected_trace_hash(row["traffic_profile"], row["rho"])
    for row in runs)

checks["mixed_censor_policy_frozen"] = all((
    censor["COMPLETE"].startswith("unfinished work <="),
    censor["CENSORED"].startswith("unfinished work remains"),
    censor["virtual_drain_penalty"] is False,
    censor["censor_scalar_penalty"] is False,
    "J_ranking" in censor["paired_policy"]["either_censored_forbidden"],
))
checks["primary_and_secondary_metrics_frozen"] = all((
    contract["primary_complete_metrics"] == ["J_bit_s", "mean_bit_delay_s"],
    "transition_period_outage_s" in contract["secondary_metrics"],
    "post_expiry_no_route_s" in contract["secondary_metrics"],
    contract["weighted_multimetric_score"] is False,
))
checks["primary_and_secondary_contrasts_exact"] = all((
    contract["primary_contrast"] == ["B4", "B3"],
    contract["secondary_contrasts"]
        == [["B4", "B1"], ["B3", "B1"], ["B1", "B0"]],
    contract["global_controller_ranking_forbidden"] is True,
))
checks["figure_cases_exact"] = figures["cases"] == [
    {"case_id": "FIGURE_CASE_MODERATE", "scale": 160,
     "topology": "Z_MODERATE", "router": "SHORTEST_PROPAGATION_DELAY",
     "traffic": "TRAFFIC_HOTSPOT_MIGRATION_V1", "rho": 0.8,
     "controllers": ["B0", "B1", "B3", "B4"]},
    {"case_id": "FIGURE_CASE_SPARSE", "scale": 160,
     "topology": "Z_SPARSE_REFERENCE", "router": "SHORTEST_PROPAGATION_DELAY",
     "traffic": "TRAFFIC_HOTSPOT_MIGRATION_V1", "rho": 0.8,
     "controllers": ["B0", "B1", "B3", "B4"]},
]
checks["visualization_grid_not_dynamics"] = all((
    figures["visualization_reporting_grid_s"] == 1.0,
    figures["reporting_grid_enters_state_evolution"] is False,
))
checks["manifest_file_hashes_exact"] = all(
    sha(row["path"]) == row["file_sha256"]
    and read(row["path"])["canonical_sha256"] == row["canonical_sha256"]
    for row in contract["manifest_hashes"].values())

timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
out = PROJECT / "outputs" / f"gate_f3_experiment_human_freeze_{timestamp}"
out.mkdir(parents=True, exist_ok=False)

traffic_audit = {
    "schema": "gate_f3_traffic_manifest_audit_v1",
    "OD_count": len(od_ids), "OD_manifest_sha256": contract["od_manifest"]["sha256"],
    "alpha_star_bit_s": alpha["alpha_star_bit_s"],
    "alpha_star_source": contract["normalization"]["source"],
    "alpha_star_identifier": traffic["alpha_star"]["identifier"],
    "H0": expected_h0, "H2": expected_h2,
    "G_total": g_total,
    "hotspot_phase_sums": hotspot_sums,
    "stable_phase_sums": stable_sums,
    "constant_total_pass": checks["hotspot_constant_total_load"]
                           and checks["stable_constant_total_load"],
    "traffic_hashes_reproducible": checks["traffic_hashes_reproducible"],
}
dump(out / "traffic_manifest_audit.json", traffic_audit)

execution_audit = {
    "schema": "gate_f3_execution_manifest_audit_v1",
    "execution_order": execution["execution_order"],
    "block_counts": dict(sorted(actual_counts.items())),
    "run_id_count": len(run_ids),
    "unique_run_id_count": len(set(run_ids)),
    "paired_stratum_count": len(strata),
    "paired_traffic_hash_fairness": checks["paired_controllers_share_traffic_hash"],
    "router_fairness": checks["router_fairness_within_strata"],
    "performance_started": False,
}
dump(out / "execution_manifest_audit.json", execution_audit)
dump(out / "run_count_audit.json", {
    "schema": "gate_f3_run_count_audit_v1",
    "derived_block_counts": dict(sorted(actual_counts.items())),
    "expected_block_counts": expected_counts,
    "cross_product_validation": {
        row["block_id"]: {
            "topology_count": len(row["topologies"]),
            "rho_count": len(row["rho"]),
            "controller_count": len(row["controllers"]),
            "product": len(row["topologies"])*len(row["rho"])*len(row["controllers"]),
        } for row in execution["blocks"]},
    "total": len(runs), "pass": checks["total_unique_run_ids_60"],
})

parent_post = {group: {name: sha(name) for name in records}
               for group, records in parent_expected.items()}
a_to_e2_post = {name: sha(name) for name in a_to_e2["files"]}
checks["frozen_parent_hashes_unchanged_post"] = parent_post == parent_expected
checks["all_148_A_to_E2_hashes_unchanged_post"] = a_to_e2_post == a_to_e2["files"]
checks["no_performance_artifact_created"] = performance_artifacts() == []

passed = all(checks.values())
statement = ("Gate F3 Experiment Human Freeze v1 = PASS" if passed
             else "Gate F3 Experiment Human Freeze v1 = FAIL")
report = {
    "schema": "gate_f3_experiment_human_freeze_report_v1",
    "statement": statement,
    "checks": checks,
    "Gate_F3_canonical_sha256": contract["canonical_sha256"],
    "F3_experiment_contract": "FROZEN" if passed else "NOT_FROZEN",
    "F3_traffic_manifests": "FROZEN" if passed else "NOT_FROZEN",
    "F3_execution_manifest": "FROZEN" if passed else "NOT_FROZEN",
    "F3_mixed_censor_policy": "FROZEN" if passed else "NOT_FROZEN",
    "F3_B2_grid": "FROZEN" if passed else "NOT_FROZEN",
    "planned_run_count": len(runs),
    "P1_readiness": "READY" if passed else "NOT_READY",
    "F3_performance_readiness": "READY" if passed else "NOT_READY",
    "F3_performance_started": False,
    "RL_started": False,
    "H0": expected_h0,
    "H2": expected_h2,
    "OD_manifest_sha256": contract["od_manifest"]["sha256"],
    "alpha_star_source": contract["normalization"]["source"],
    "alpha_star_value_bit_s": contract["normalization"]["alpha_star_bit_s"],
    "alpha_star_identifier": traffic["alpha_star"]["identifier"],
    "manifest_hashes": contract["manifest_hashes"],
    "parent_hash_status": "UNCHANGED" if all((
        checks["frozen_parent_hashes_unchanged_post"],
        checks["all_148_A_to_E2_hashes_unchanged_post"])) else "CHANGED",
    "structural_checker_result": "PASS" if passed else "FAIL",
    "controller_performance_executed": False,
}
dump(out / "report.json", report)
dump(out / "frozen_hash_report.json", {
    "parent_expected": parent_expected,
    "parent_actual_pre": parent_pre,
    "parent_actual_post": parent_post,
    "a_to_e2_file_count": len(a_to_e2["files"]),
    "a_to_e2_pre": a_to_e2_pre,
    "a_to_e2_post": a_to_e2_post,
    "all_unchanged": (parent_post == parent_expected
                      and a_to_e2_post == a_to_e2["files"]),
    "F2_0_canonical_sha256":
        "ca82a1e49f6bdbe56a4c9f2fb79299eac0174844e0bdc6608ea3cb4f12f90b2a",
})

status = {
    "schema": "gate_f3_experiment_status_v1",
    "statement": statement,
    "gate_f3_experiment_human_freeze_v1": "PASS" if passed else "FAIL",
    "canonical_sha256": contract["canonical_sha256"],
    "evidence": str(out.relative_to(PROJECT)).replace("\\", "/"),
    "planned_run_count": len(runs),
    "P1_readiness": "READY" if passed else "NOT_READY",
    "F3_performance_readiness": "READY" if passed else "NOT_READY",
    "performance_started": False,
    "P1_started": False,
    "RL_started": False,
}
dump(PROJECT / "configs/gate_f3_experiment_status.json", status)

artifact_names = (
    "docs/GATE_F3_EXPERIMENT_HUMAN_FREEZE_V1_CN.md",
    CONTRACT_PATH,
    "configs/gate_f3_b2_grid_v1.json",
    "configs/gate_f3_traffic_profiles_v1.json",
    "configs/gate_f3_traffic_stable_v1.json",
    "configs/gate_f3_traffic_hotspot_migration_v1.json",
    "configs/gate_f3_execution_manifest_v1.json",
    "configs/gate_f3_censor_policy_v1.json",
    "configs/gate_f3_figure_cases_v1.json",
    "configs/gate_f3_experiment_status.json",
    "tools/check_gate_f3_experiment_human_freeze.py",
)
dump(out / "artifact_hashes.json", {name: sha(name) for name in artifact_names})

print(statement)
print("F3 experiment contract = " + report["F3_experiment_contract"])
print("F3 traffic manifests = " + report["F3_traffic_manifests"])
print("F3 execution manifest = " + report["F3_execution_manifest"])
print("F3 mixed censor policy = " + report["F3_mixed_censor_policy"])
print("F3 B2 grid = " + report["F3_B2_grid"])
print("F3-v1 planned run count = " + str(len(runs)))
print("P1 readiness = " + report["P1_readiness"])
print("F3 performance readiness = " + report["F3_performance_readiness"])
print("F3 performance started = false")
print("RL started = false")
print(str(out.relative_to(PROJECT)).replace("\\", "/"))
if not passed:
    print("FAILED_CHECKS=" + ",".join(name for name, ok in checks.items() if not ok))
    raise SystemExit(1)

