"""One-time Gate F1 contract/frozen-parent record writer; refuses overwrite."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((PROJECT/name).read_text(encoding="utf-8-sig"))


def sha(name):
    return hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()


def dump_new(name, value):
    path = PROJECT/name
    if path.exists():
        raise FileExistsError(f"REFUSE_OVERWRITE {name}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False)+"\n", encoding="utf-8")


def canonical_sha(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


base = read("configs/gate_f0_frozen_a_to_e2_hashes.json")
actual = {name: sha(name) for name in base["files"]}
if actual != base["files"]:
    raise RuntimeError("FROZEN_A_TO_E2_CHANGED")

f0_files = [
    "configs/gate_f0_controller_contract.json",
    "configs/gate_f0_baseline_registry.json",
    "configs/gate_f0_status.json",
    "docs/GATE_F0_TOPOLOGY_CONTROLLER_CONTRACT_CN.md",
    "docs/GATE_F0_INTERFACE_AUDIT_CN.md",
    "docs/GATE_F0_BASELINE_REGISTRY_CN.md",
    "docs/GATE_F0_HUMAN_DECISIONS_REQUIRED_CN.md",
    "configs/gate_f0_human_freeze_v1.json",
    "configs/gate_f0_human_freeze_status.json",
    "docs/GATE_F0_HUMAN_FREEZE_V1_CN.md",
    "configs/z_moderate_v1.json",
]
record = {
    "schema": "gate_f1_frozen_parent_hashes_v1",
    "a_to_e2_record": "configs/gate_f0_frozen_a_to_e2_hashes.json",
    "a_to_e2_file_count": len(actual),
    "a_to_e2_files": actual,
    "f0_and_human_freeze_files": {name: sha(name) for name in f0_files},
    "preflight_evidence": {
        "parent_f0": "outputs/gate_f0_contract_20260924T160512_858290Z",
        "human_freeze": "outputs/gate_f0_human_freeze_20260924T160525_554136Z",
        "overlay_canonical_sha256":
            "c4dbd526b1d21a1f0462a49a5a4b59fa54122f72313b1dbe1115c8608b65256b",
    },
}
dump_new("configs/gate_f1_frozen_parent_hashes.json", record)

contract = {
    "schema": "gate_f1_contract_v1",
    "gate_type": "CORRECTNESS_INTEGRATION",
    "decision_cadence_s": 2.0,
    "physical_events_event_driven": True,
    "candidate_top_k": 16,
    "candidate_structural_quota": {
        "MBB_STRUCTURALLY_FEASIBLE": 8, "BBM_REQUIRED": 8},
    "regime_safety": {
        "Z_SPARSE_REFERENCE": {
            "policy": "BOUNDED_TRANSITION_OUTAGE", "max_s": 2.0},
        "Z_MODERATE": {"policy": "STRICT_CONNECTED"},
    },
    "controllers": {
        "B0": "IMPLEMENTED",
        "B1": "INTERFACE_AND_TEST_SCAFFOLD_ONLY_SCORING_UNRESOLVED",
        "B2": "PARAMETERIZED_LOGIC_IMPLEMENTED_F3_GRID_UNRESOLVED",
        "B3": "INTERFACE_AND_INFORMATION_FIREWALL_ONLY_SCORING_UNRESOLVED",
        "B4": "NOT_IMPLEMENTED", "B5": "NOT_IMPLEMENTED",
    },
    "scoring_contract": {
        "uniquely_frozen": False,
        "status": "BLOCKED_REQUIRES_HUMAN_FREEZE",
        "document": "docs/GATE_F1_SCORING_AMBIGUITY_CN.md",
        "fixture_score_injection_scientific_use_allowed": False,
    },
    "required_outage_metrics": [
        "transition_period_outage_s",
        "transition_period_no_route_by_commodity_s",
        "post_expiry_no_route_s",
        "post_expiry_no_route_by_commodity_s"],
    "forbidden": [
        "B4_MPC", "RL_PPO", "controller_training", "performance_comparison",
        "J_based_tuning", "future_realized_traffic", "A_to_F0_modification"],
    "frozen_parent_hash_record": "configs/gate_f1_frozen_parent_hashes.json",
    "expected_overall_status":
        "BLOCKED_BEFORE_SCIENTIFIC_B1_B3_IMPLEMENTATION",
    "next_gate_state": {"gate_f2_started": False,
                        "gate_f3_started": False, "rl_started": False},
}
contract["canonical_sha256"] = canonical_sha(contract)
dump_new("configs/gate_f1_contract.json", contract)
print("WROTE configs/gate_f1_frozen_parent_hashes.json")
print("WROTE configs/gate_f1_contract.json")
print(contract["canonical_sha256"])
