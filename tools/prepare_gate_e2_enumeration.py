"""Enumerate and freeze result-blind Gate E2 natural-geometry scenarios."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from dynamic_lisl.common import dump, read_json, sha
from dynamic_lisl.gate_e2_enumeration import (
    DECISION_FLOOR_S, SETUP_TOTAL_S, canonical_sha256,
    enumerate_natural_candidates, validate_selected_candidates,
)


def main():
    pre = read_json(PROJECT / "configs/pre_e2_absolute_time_status.json")
    if pre.get("pre_e2_absolute_time_regression") != "PASS":
        raise RuntimeError("PRE_E2_ABSOLUTE_TIME_PASS_REQUIRED_STOP")
    inventory_path = PROJECT / "configs/gate_e2_candidate_inventory.json"
    selected_path = PROJECT / "configs/gate_e2_selected_scenarios.json"
    if inventory_path.exists() or selected_path.exists():
        raise FileExistsError("REFUSE_TO_OVERWRITE_FROZEN_GATE_E2_SELECTION")
    reference_path = PROJECT / "outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json"
    intervals_path = PROJECT / "outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl"
    od_path = PROJECT / "configs/gate_d0_od_manifest_16.json"
    reference = read_json(reference_path)
    intervals = [json.loads(line) for line in
                 intervals_path.read_text(encoding="utf-8").splitlines()]
    commodities = read_json(od_path)["commodities"]
    candidates, selection, audit = enumerate_natural_candidates(
        reference, intervals, commodities)
    selected_gate_c_validation = validate_selected_candidates(
        reference, intervals, selection["selected"])
    if not (selected_gate_c_validation["all_selected_gate_c_legal"]
            and selected_gate_c_validation["all_transition_classes_match"]):
        raise RuntimeError("SELECTED_GATE_C_VALIDATION_FAILED_STOP")
    counts = Counter((row["scenario_class"] for row in candidates))
    inventory = {
        "schema": "gate_e2_candidate_inventory_v1",
        "status": "FROZEN_BEFORE_PAIRED_BRANCH_EXECUTION",
        "result_blind": True,
        "result_fields_read": [],
        "source_160_star_reference": str(reference_path.relative_to(PROJECT)).replace("\\", "/"),
        "source_terminal_pair_windows": str(intervals_path.relative_to(PROJECT)).replace("\\", "/"),
        "source_od_manifest": str(od_path.relative_to(PROJECT)).replace("\\", "/"),
        "source_hashes": {
            str(reference_path.relative_to(PROJECT)).replace("\\", "/"): sha(reference_path),
            str(intervals_path.relative_to(PROJECT)).replace("\\", "/"): sha(intervals_path),
            str(od_path.relative_to(PROJECT)).replace("\\", "/"): sha(od_path),
        },
        "enumeration_contract": {
            "decision_time_rule": "max(1.0 s, natural terminal-pair interval start)",
            "decision_floor_s": DECISION_FLOOR_S,
            "tau_setup_s": SETUP_TOTAL_S,
            "setup_source": "Gate C frozen 1 s parallel retarget + 1 s acquisition audit fixture",
            "natural_interval_end_modified": False,
            "candidate_replacement": False,
        },
        "audit": audit,
        "counts_by_class": dict(sorted(counts.items())),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    inventory["canonical_sha256"] = canonical_sha256(inventory)
    selected = {
        "schema": "gate_e2_selected_scenarios_v1",
        "status": "FROZEN_BEFORE_PAIRED_BRANCH_EXECUTION",
        "result_blind": True,
        "result_fields_read": [],
        "selector_manifest": "configs/gate_e0_scenario_selection_manifest.json",
        "candidate_inventory": "configs/gate_e2_candidate_inventory.json",
        "candidate_inventory_sha256": inventory["canonical_sha256"],
        "global_selection_setup_s": SETUP_TOTAL_S,
        "selection": selection,
        "selected_gate_c_validation": selected_gate_c_validation,
        "paired_branches_executed": False,
    }
    selected["canonical_sha256"] = canonical_sha256(selected)
    dump(inventory_path, inventory)
    dump(selected_path, selected)
    print(json.dumps({
        "candidate_count": len(candidates),
        "selected_count": len(selection["selected"]),
        "empty_strata": sum(row["status"] == "NO_ELIGIBLE_CASE"
                            for row in selection["availability"]),
        "inventory_sha256": inventory["canonical_sha256"],
        "selected_sha256": selected["canonical_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
