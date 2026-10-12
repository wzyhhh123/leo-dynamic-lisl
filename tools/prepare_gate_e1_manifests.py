"""Freeze Gate E1 templates, execution points and break-even families once."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT/"src"))

from dynamic_lisl.gate_e1_experiments import (
    ROUTER_PRIMARY, ROUTER_ROBUSTNESS, common_drain_limit_s,
    frozen_templates, validate_point_physics,
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, document):
    if path.exists():
        raise FileExistsError("REFUSE_TO_OVERWRITE_FROZEN_E1_MANIFEST:"+str(path))
    path.write_text(json.dumps(document, sort_keys=True, indent=2,
                               ensure_ascii=False, allow_nan=False)+"\n",
                    encoding="utf-8")


e0_status = read(PROJECT/"configs/gate_e0_status.json")
if e0_status.get("gate_e0") != "PASS":
    raise RuntimeError("GATE_E0_PASS_REQUIRED")
e0_hash_record = read(PROJECT/"configs/gate_e0_manifest_hashes.json")
for name, expected in e0_hash_record["files"].items():
    if sha(PROJECT/name) != expected:
        raise RuntimeError("E0_FROZEN_MANIFEST_HASH_MISMATCH:"+name)

templates = frozen_templates()
rho_grid = [0.2, 0.5, 0.8, 1.0, 1.2]
kappa1_grid = [0.05, 0.2, 0.5, 1.0]
kappa2_grid = [0.05, 0.2, 0.5, 0.8]
positive_setup_grid = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
routers = [ROUTER_PRIMARY, ROUTER_ROBUSTNESS]
points = []
sequence = 0
for template_id in sorted(templates):
    for router_id in routers:
        for rho in rho_grid:
            for kappa1 in kappa1_grid:
                for kappa2 in kappa2_grid:
                    for tau in positive_setup_grid:
                        sequence += 1
                        t_demand = tau/kappa1
                        l_remain = tau/kappa2
                        point = {
                            "experiment_id": f"E1A_{sequence:06d}",
                            "study": "E1_A_CORE_REGIME",
                            "template_id": template_id, "router_id": router_id,
                            "rho": rho, "tau_setup_s": tau,
                            "kappa1": kappa1, "kappa2": kappa2,
                            "T_demand_s": t_demand, "L_remain_s": l_remain,
                            "drain_limit_s": common_drain_limit_s(t_demand),
                            "branch_set": ["HOLD", "IDEAL_SWITCH", "REAL_SWITCH"],
                        }
                        legality = validate_point_physics(point, templates)
                        if not legality["legal"]:
                            raise RuntimeError("REGISTERED_CORE_POINT_NOT_LEGAL:"+
                                               point["experiment_id"]+":"+
                                               str(legality["reason"]))
                        points.append(point)

for template_id in sorted(templates):
    for router_id in routers:
        sequence += 1
        points.append({
            "experiment_id": f"E1A_ZERO_{sequence:06d}",
            "study": "E1_A_ZERO_SETUP_CORRECTNESS",
            "template_id": template_id, "router_id": router_id,
            "rho": 0.8, "tau_setup_s": 0.0,
            "kappa1": None, "kappa2": None,
            "T_demand_s": 10.0, "L_remain_s": 10.0,
            "drain_limit_s": common_drain_limit_s(10.0),
            "branch_set": ["HOLD", "IDEAL_SWITCH", "REAL_SWITCH"],
        })

for template_id in sorted(templates):
    for router_id in routers:
        sequence += 1
        point = {
            "experiment_id": f"E1B_{sequence:06d}",
            "study": "E1_B_DELAYED_ANCHOR",
            "template_id": template_id, "router_id": router_id,
            "rho": 0.8, "tau_setup_s": 2.0,
            "kappa1": 0.2, "kappa2": 0.2,
            "T_demand_s": 10.0, "L_remain_s": 10.0,
            "drain_limit_s": common_drain_limit_s(10.0),
            "delay_switch_ratios": [0.0, 0.25, 0.5],
            "branch_set": ["HOLD", "IDEAL_SWITCH", "REAL_SWITCH",
                           "DELAYED_SWITCH_0", "DELAYED_SWITCH_0.25",
                           "DELAYED_SWITCH_0.5"],
        }
        if not validate_point_physics(point, templates)["legal"]:
            raise RuntimeError("REGISTERED_DELAY_POINT_NOT_LEGAL")
        points.append(point)

execution = {
    "schema": "gate_e1_execution_manifest_v1",
    "version": 1, "status": "FROZEN_BEFORE_E1_SCIENTIFIC_RUN",
    "created_result_blind": True,
    "source_e0_sweep_manifest": "configs/gate_e0_sweep_manifest.json",
    "source_e0_sweep_manifest_sha256": sha(
        PROJECT/"configs/gate_e0_sweep_manifest.json"),
    "source_e0_scenario_selection_manifest_sha256": sha(
        PROJECT/"configs/gate_e0_scenario_selection_manifest.json"),
    "setup_override_namespace": "gate_e1_sensitivity_only",
    "gate_c_hardware_asset_modified": False,
    "templates": templates,
    "routers": {
        ROUTER_PRIMARY: {
            "class": "DeterministicShortestPropagationDelayRouter",
            "role": "PRIMARY"},
        ROUTER_ROBUSTNESS: {
            "class": "DeterministicLoadAwareRouter",
            "role": "ROBUSTNESS", "future_information": False},
    },
    "grids": {
        "rho": rho_grid, "kappa1": kappa1_grid, "kappa2": kappa2_grid,
        "positive_setup_s": positive_setup_grid,
        "zero_setup_correctness_only": True,
        "delay_switch_ratios": [0.0, 0.25, 0.5],
    },
    "censor_contract": {
        "status": "CENSORED_AT_DRAIN_LIMIT",
        "reversal_status": "NOT_EVALUABLE_CENSORED",
        "break_even_use": False,
    },
    "expected_counts": {
        "core_positive": 3840, "zero_setup_correctness": 8,
        "delayed_anchor": 8, "total_points": 3856,
    },
    "points": points,
}

families = []
for template_id in sorted(templates):
    for router_id in routers:
        families.append({
            "family_id": f"E1C_{template_id}_{router_id}",
            "template_id": template_id, "router_id": router_id,
            "rho": 0.8, "T_demand_s": 20.0, "L_remain_s": 120.0,
            "drain_limit_s": common_drain_limit_s(20.0),
            "setup_grid_s": [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0],
            "fixed_fields": ["S0", "target", "rho", "T_demand_s",
                             "L_remain_s", "traffic_trace", "router_id"],
            "only_varied_field": "tau_setup_s",
        })
break_even = {
    "schema": "gate_e1_break_even_manifest_v1", "version": 1,
    "status": "FROZEN_BEFORE_E1_SCIENTIFIC_RUN",
    "created_result_blind": True,
    "refinement_tolerance_s": 0.01,
    "monotonicity_assumed": False,
    "range_expansion_allowed": False,
    "families": families,
}

execution_path = PROJECT/"configs/gate_e1_execution_manifest.json"
break_path = PROJECT/"configs/gate_e1_break_even_manifest.json"
write_new(execution_path, execution)
write_new(break_path, break_even)
write_new(PROJECT/"configs/gate_e1_manifest_hashes.json", {
    "schema": "gate_e1_manifest_hashes_v1", "version": 1,
    "frozen_before_first_scientific_run": True,
    "files": {
        "configs/gate_e1_execution_manifest.json": sha(execution_path),
        "configs/gate_e1_break_even_manifest.json": sha(break_path),
    },
})

e0_base = read(PROJECT/"configs/gate_e0_frozen_a_to_d_hashes.json")["files"]
e0_evidence = Path(e0_status["evidence"])
extra = [
    "configs/gate_e0_sweep_manifest.json",
    "configs/gate_e0_scenario_selection_manifest.json",
    "configs/gate_e0_manifest_hashes.json",
    "configs/gate_e0_frozen_a_to_d_hashes.json",
    "configs/gate_e0_status.json",
    "docs/GATE_E0_MECHANISM_VALIDATION_CONTRACT_CN.md",
    "docs/GATE_E0_MECHANISM_VALIDATION_RESULT_CN.md",
    "src/dynamic_lisl/mechanism_validation.py",
    "src/dynamic_lisl/scenario_selection.py",
    "src/dynamic_lisl/load_aware_router.py",
    "tests/test_gate_e0.py",
    "tools/check_gate_e0.py",
]
for path in sorted((PROJECT/e0_evidence).iterdir()):
    if path.is_file():
        extra.append(path.relative_to(PROJECT).as_posix())
frozen = dict(e0_base)
for name in extra:
    if name not in frozen:
        frozen[name] = sha(PROJECT/name)
write_new(PROJECT/"configs/gate_e1_frozen_a_to_e0_hashes.json", {
    "schema": "gate_e1_frozen_a_to_e0_hashes_v1",
    "captured_before_first_e1_scientific_run": True,
    "source_gate_e0_evidence": e0_evidence.as_posix(),
    "files": frozen,
})

print(json.dumps({
    "status": "FROZEN", "execution_points": len(points),
    "break_even_families": len(families),
    "frozen_a_to_e0_files": len(frozen),
}, sort_keys=True))
