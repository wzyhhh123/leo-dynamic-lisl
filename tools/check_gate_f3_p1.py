"""Validate the stopped Gate F3-P1 preflight without executing performance runs.

This checker deliberately reports the registered blocker.  It does not turn an
underspecified candidate universe into a scientific controller input.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT / "outputs/gate_f3_p1_20260925T050259_813979Z"
EXPECTED = {
    "f3": "118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6",
    "execution": "0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a",
    "traffic": "ce00a04bc57b7ac70717ce21b6646171f66aa1907199db1d4161541907eb5b33",
    "hotspot": "f900a135976f66ee508a790372af162b8475df7f12970423ac704112d3f0a0ee",
    "od_file": "b8e46dd988e4f5136eeb5b8adea4272ad93b3fafc5ed7fc4fb537eff167173de",
}
BLOCKER = "GATE_F3_P1_EXECUTION_BLOCKED_BY_CANDIDATE_SOURCE_NOT_FROZEN"


def read(name: str):
    return json.loads((PROJECT / name).read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_canonical(value) -> bool:
    payload = dict(value)
    expected = payload.pop("canonical_sha256")
    return canonical_sha(payload) == expected


contract = read("configs/gate_f3_experiment_human_freeze_v1.json")
execution = read("configs/gate_f3_execution_manifest_v1.json")
traffic = read("configs/gate_f3_traffic_profiles_v1.json")
hotspot = read("configs/gate_f3_traffic_hotspot_migration_v1.json")
alpha = read("outputs/gate_d1_20260922T133909_838853Z/load_normalization_report.json")
historical = json.loads((OUTPUT / "historical_f3_0_checker_report.json").read_text(
    encoding="utf-8"))
status = read("configs/gate_f3_p1_status.json")

p1 = [row for row in execution["runs"] if row["block_id"] == "P1"]
p1_ids = [row["run_id"] for row in p1]
checks = {
    "historical_F3_0_checker_ran_once_and_passed":
        historical["structural_checker_result"] == "PASS",
    "F3_canonical_exact": contract["canonical_sha256"] == EXPECTED["f3"]
        and verify_canonical(contract),
    "execution_canonical_exact": execution["canonical_sha256"] == EXPECTED["execution"]
        and verify_canonical(execution),
    "traffic_registry_canonical_exact": traffic["canonical_sha256"] == EXPECTED["traffic"]
        and verify_canonical(traffic),
    "hotspot_canonical_exact": hotspot["canonical_sha256"] == EXPECTED["hotspot"]
        and verify_canonical(hotspot),
    "OD_file_hash_exact": sha(PROJECT / "configs/gate_d0_od_manifest_16.json") == EXPECTED["od_file"],
    "alpha_exact": alpha["alpha_star_bit_s"] == 26666666666.666664,
    "alpha_identifier_exact": traffic["alpha_star"]["identifier"]
        == "GATE_D1_FROZEN_REFERENCE_MCF_ALPHA_STAR",
    "P1_count_exactly_12": len(p1) == 12,
    "P1_unique_run_ids": len(p1_ids) == len(set(p1_ids)) == 12,
    "P1_rows_still_planned": all(
        row["performance_status"] == "PLANNED_NOT_EXECUTED" for row in p1),
    "P1_cross_product_exact": {
        (row["scale"], row["topology_regime"], row["router"],
         row["traffic_profile"]) for row in p1
    } == {(160, "Z_MODERATE", "SHORTEST_PROPAGATION_DELAY",
           "TRAFFIC_HOTSPOT_MIGRATION_V1")}
        and {row["rho"] for row in p1} == {0.5, 0.8, 1.0}
        and {row["controller"] for row in p1} == {"B0", "B1", "B3", "B4"},
    "all_frozen_parent_hashes_unchanged": all(
        sha(PROJECT / name) == expected
        for group in contract["parent_hashes"].values()
        for name, expected in group.items()),
    "frozen_F3_0_status_restored_byte_identically": sha(
        PROJECT / "configs/gate_f3_experiment_status.json") == sha(
        OUTPUT / "gate_f3_experiment_status_preflight_backup.json"),
    "no_P1_run_executed": not any((OUTPUT / "runs").iterdir()),
    "separate_P1_status_records_blocker": status["blocker_code"] == BLOCKER,
    "P2_not_started": status["P2_started"] is False,
    "RL_not_started": status["RL_started"] is False,
}

if not all(checks.values()):
    failed = [key for key, value in checks.items() if not value]
    raise SystemExit("GATE_F3_P1_PREFLIGHT_EVIDENCE_INVALID: " + ",".join(failed))

print(BLOCKER)
print("historical F3-0 preflight = PASS")
print("P1 registered runs executed = 0/12")
print("P2 started = false")
print("RL started = false")

