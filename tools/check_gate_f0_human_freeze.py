"""Validate the immutable Gate F0 Human Freeze v1 overlay."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from dynamic_lisl.z_moderate_construction import (
    canonical_sha256, construct_z_moderate,
)

OVERLAY_PATH = PROJECT / "configs/gate_f0_human_freeze_v1.json"
Z_PATH = PROJECT / "configs/z_moderate_v1.json"
STATUS_PATH = PROJECT / "configs/gate_f0_human_freeze_status.json"
A_E2_FREEZE = PROJECT / "configs/gate_f0_frozen_a_to_e2_hashes.json"

FORBIDDEN_CONTROLLER_PATHS = (
    "src/dynamic_lisl/gate_f_controller.py",
    "src/dynamic_lisl/topology_controller.py",
    "src/dynamic_lisl/static_hold_controller.py",
    "src/dynamic_lisl/ignore_setup_controller.py",
    "src/dynamic_lisl/hysteresis_controller.py",
    "src/dynamic_lisl/setup_aware_greedy.py",
    "src/dynamic_lisl/mpc_controller.py",
    "src/dynamic_lisl/exact_oracle_controller.py",
    "src/dynamic_lisl/matching_controller.py",
    "src/dynamic_lisl/rl_controller.py",
    "tools/run_gate_f1.py",
    "tools/run_gate_f2.py",
    "tools/run_gate_f3.py",
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def frozen_a_e2_audit():
    record = read(A_E2_FREEZE)
    actual = {
        name: sha(PROJECT / name) if (PROJECT / name).is_file() else None
        for name in sorted(record["files"])
    }
    return {
        "record": str(A_E2_FREEZE.relative_to(PROJECT)).replace("\\", "/"),
        "expected": record["files"],
        "actual": actual,
        "all_unchanged": actual == record["files"],
    }


def parent_audit(overlay):
    parent = overlay["parent"]
    files = {
        parent["contract"]: parent["parent_contract_sha256"],
        parent["baseline_registry"]:
            parent["parent_baseline_registry_sha256"],
        parent["human_decisions"]:
            parent["parent_human_decisions_sha256"],
    }
    actual = {name: sha(PROJECT / name) for name in files}
    return {
        "expected": files,
        "actual": actual,
        "all_unchanged": actual == files,
    }


def main():
    overlay = read(OVERLAY_PATH)
    z_asset = read(Z_PATH)
    current = read(PROJECT / "configs/current.json")
    parent_status = read(PROJECT / "configs/gate_f0_status.json")
    parent_report = read(PROJECT / parent_status["evidence"] / "report.json")

    checks = {}
    checks["parent_f0_checker_still_pass"] = (
        parent_status["gate_f0"] == "PASS_WITH_HUMAN_FREEZE_ITEMS"
        and parent_report["status"] == "PASS_WITH_HUMAN_FREEZE_ITEMS"
        and all(parent_report["checks"].values())
    )

    parent_hash = parent_audit(overlay)
    checks["parent_f0_contract_hashes_unchanged"] = parent_hash["all_unchanged"]
    a_e2_hash = frozen_a_e2_audit()
    checks["frozen_a_to_e2_unchanged_pre"] = a_e2_hash["all_unchanged"]

    payload = dict(overlay)
    expected_overlay_hash = payload.pop("canonical_sha256")
    checks["overlay_canonical_hash"] = (
        canonical_sha256(payload) == expected_overlay_hash
    )
    checks["overlay_parent_references_present"] = all(
        key in overlay["parent"] for key in (
            "parent_contract_sha256",
            "parent_baseline_registry_sha256",
            "parent_human_decisions_sha256",
        )
    )

    epoch = overlay["decision_epoch"]
    checks["decision_cadence_exact"] = (
        epoch["decision_cadence_s"] == 2.0
        and epoch["periodic_decision_enabled"] is True
        and epoch["minimum_controller_reaction_interval_s"] == 2.0
    )
    checks["no_event_trigger_decision"] = all(
        epoch[key] is False for key in (
            "topology_event_immediate_decision",
            "natural_expiry_immediate_decision",
            "link_up_immediate_decision",
            "link_down_immediate_decision",
        )
    )
    checks["simultaneous_policy_exact"] = (
        epoch["simultaneous_periodic_event_policy"]
        == "single_periodic_epoch_after_existing_physical_events_settle"
    )

    proposal = overlay["candidate_proposal"]
    checks["candidate_k_exact"] = (
        proposal["candidate_top_k"] == 16
        and proposal["main_scale_exhaustive_candidate_evaluation_forbidden"]
    )
    checks["candidate_quota_8_8"] = proposal["structural_strata"] == {
        "MBB_STRUCTURALLY_FEASIBLE": 8,
        "BBM_REQUIRED": 8,
    }
    checks["candidate_ranking_exact"] = (
        proposal["within_stratum_ranking"] == [
            "usable_lifetime_s_descending",
            "plane_gap_ascending",
            "old_edge_lexicographic",
            "old_terminal_ids_lexicographic",
            "new_edge_lexicographic",
            "new_terminal_ids_lexicographic",
            "proposal_id_lexicographic",
        ]
        and proposal["ranking_uses_queue_load_or_value"] is False
    )
    checks["proposer_forbidden_inputs"] = set(
        proposal["forbidden_inputs"]
    ) == {
        "J", "delta_J", "future_realized_traffic", "reversal_status",
        "controller_identity", "downstream_performance",
    }
    checks["candidate_universe_fairness"] = (
        proposal["shared_proposal_set_controllers"]
        == ["B1", "B2", "B3", "B4"]
        and proposal["B0_candidate_budget_not_used_by_design"]
        and proposal["B5_tiny_fixture_exact_oracle_exempt_from_k"]
    )

    forecast = overlay["forecast"]
    checks["traffic_persistence_forecast"] = (
        forecast["forecast_class"] == "SHORT_HORIZON_FORECAST"
        and forecast["traffic_forecast"] == "CURRENT_RATE_PERSISTENCE"
        and forecast["forecast_horizon_s"] == 10.0
        and forecast["forecast_update_period_s"] == 2.0
        and not forecast["may_read_unrealized_immutable_trace_segments"]
    )

    z_payload = dict(z_asset)
    z_expected_hash = z_payload.pop("canonical_sha256")
    checks["z_asset_canonical_hash"] = (
        canonical_sha256(z_payload) == z_expected_hash
        and z_expected_hash
        == overlay["z_moderate"]["asset_canonical_sha256"]
    )
    checks["z_design_and_epoch"] = (
        overlay["z_moderate"]["selected_design"]
        == "ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE"
        and overlay["z_moderate"]["construction_epoch_s"] == 0.0
        and z_asset["selected_design"]
        == "ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE"
        and z_asset["construction_epoch_s"] == 0.0
    )
    fresh_a = construct_z_moderate(PROJECT)
    fresh_b = construct_z_moderate(PROJECT)
    checks["z_deterministic_replay"] = (
        fresh_a.get("canonical_sha256") == z_expected_hash
        and fresh_b.get("canonical_sha256") == z_expected_hash
    )
    z_audit = z_asset["structural_audit"]
    checks["z_structural_acceptance"] = (
        z_asset["status"] == "CONSTRUCTED"
        and z_asset["minimality_certificate"]["minimum_added_bindings"] == 1
        and z_audit["dynamic_link_count"] == 4
        and z_audit["used_dynamic_terminals"] == 8
        and z_audit["total_dynamic_terminals"] == 320
        and z_audit["terminal_occupancy_fraction"] == 0.025
        and z_audit["terminal_conflict_count"] == 0
        and z_audit["plane_graph_connected"]
        and z_audit["plane_bridge_count"] == 0
        and z_audit["satellite_graph_connected"]
        and z_audit["satellite_bridge_count"] == 0
        and z_audit["nonbridge_dynamic_edge_count"] == 4
        and z_audit["plane_coverage"] == [0, 1, 2, 3]
        and z_audit["all_binding_gate_c_legality"]
        and z_audit["strict_connected_transition_for_added_binding"]
    )

    safety = overlay["connectivity_safety"]
    checks["sparse_policy_exact"] = (
        safety["Z_SPARSE_REFERENCE"]["policy"]
        == "BOUNDED_TRANSITION_OUTAGE"
        and safety["Z_SPARSE_REFERENCE"][
            "T_max_transition_outage_s"
        ] == 2.0
        and safety["Z_SPARSE_REFERENCE"][
            "applies_only_to_controller_initiated_transition_period"
        ]
        and not safety["Z_SPARSE_REFERENCE"][
            "post_expiry_no_route_in_transition_budget"
        ]
    )
    checks["moderate_policy_exact"] = (
        safety["Z_MODERATE"]["policy"] == "STRICT_CONNECTED"
        and safety["Z_MODERATE"]["profiled_graph"] == "G_admit"
        and safety["Z_MODERATE"]["safety_is_reject_only"]
    )

    nondecisions = overlay["explicit_non_decisions"]
    checks["f3_items_remain_unresolved"] = (
        nondecisions["status"] == "REQUIRES_HUMAN_FREEZE_BEFORE_F3"
        and set(nondecisions["items"]) == {
            "B2_minimum_hold_grid",
            "B2_improvement_threshold_grid",
            "F3_controller_evaluation_cross_product",
            "mixed_complete_censored_controller_ranking",
            "stochastic_seed_policy",
        }
        and not nondecisions[
            "B2_performance_based_parameter_selection_allowed"
        ]
    )
    checks["additive_metrics_registered"] = set(
        overlay["additive_metric_requirement_before_f1_validation"]["required"]
    ) == {
        "transition_period_outage_s",
        "transition_period_no_route_by_commodity_s",
        "post_expiry_no_route_s",
        "post_expiry_no_route_by_commodity_s",
    }

    checks["controller_implementation_absent"] = not any(
        (PROJECT / name).exists() for name in FORBIDDEN_CONTROLLER_PATHS
    )
    checks["controller_performance_outputs_absent"] = not any(
        any((PROJECT / "outputs").glob(pattern)) for pattern in (
            "gate_f1_*", "gate_f2_*", "gate_f3_*",
            "gate_f_controller_*", "controller_comparison_*",
        )
    )
    checks["later_gates_not_started_pre"] = all(
        current.get(key, False) is False for key in (
            "gate_f1_started", "gate_f2_started",
            "gate_f3_started", "rl_started",
        )
    )
    checks["f1_blockers_resolved"] = (
        overlay["resolved_f1_blockers"]["items"] == [1, 2, 3, 4, 5]
        and overlay["resolved_f1_blockers"]["all_resolved"]
        and overlay["z_moderate"]["construction_status"] == "CONSTRUCTED"
    )

    post_a_e2 = frozen_a_e2_audit()
    post_parent = parent_audit(overlay)
    checks["frozen_a_to_e2_unchanged_post"] = post_a_e2["all_unchanged"]
    checks["parent_f0_contract_hashes_unchanged_post"] = (
        post_parent["all_unchanged"]
    )

    passed = all(checks.values())
    status_value = (
        "PASS" if passed else
        "BLOCKED_Z_MODERATE_CONSTRUCTION"
        if z_asset.get("status") != "CONSTRUCTED" else "FAIL"
    )
    readiness = "READY" if passed else "NOT_READY"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = PROJECT / "outputs" / f"gate_f0_human_freeze_{stamp}"
    output.mkdir(parents=True, exist_ok=False)

    report = {
        "schema": "gate_f0_human_freeze_validation_report_v1",
        "statement": f"Gate F0 human freeze v1 = {status_value}",
        "gate_f1_readiness": readiness,
        "checks": checks,
        "overlay_canonical_sha256": expected_overlay_hash,
        "parent_f0_status": parent_status["gate_f0"],
        "f1_blocking_human_items_1_to_5_resolved": passed,
        "z_moderate_status": z_asset["status"],
        "gate_f1_started": False,
        "gate_f2_started": False,
        "gate_f3_started": False,
        "rl_started": False,
        "controller_implementations_created": False,
        "controller_performance_experiments_run": False,
    }
    dump(output / "report.json", report)
    dump(output / "z_moderate_structural_audit.json", {
        "asset": "configs/z_moderate_v1.json",
        "asset_file_sha256": sha(Z_PATH),
        "asset_canonical_sha256": z_expected_hash,
        "deterministic_replay_a_sha256": fresh_a.get("canonical_sha256"),
        "deterministic_replay_b_sha256": fresh_b.get("canonical_sha256"),
        "selected_addition": z_asset.get("selected_addition"),
        "minimality_certificate": z_asset.get("minimality_certificate"),
        "structural_audit": z_asset.get("structural_audit"),
        "candidate_audit": z_asset.get("candidate_audit"),
    })
    dump(output / "frozen_hash_report.json", {
        "parent_f0": post_parent,
        "frozen_a_to_e2": post_a_e2,
        "overlay_file_sha256": sha(OVERLAY_PATH),
        "overlay_canonical_sha256": expected_overlay_hash,
        "z_moderate_file_sha256": sha(Z_PATH),
        "z_moderate_canonical_sha256": z_expected_hash,
    })

    evidence = str(output.relative_to(PROJECT)).replace("\\", "/")
    status = {
        "gate_f0_human_freeze_v1": status_value,
        "statement": report["statement"],
        "gate_f1_readiness": readiness,
        "f1_blocking_human_items_1_to_5_resolved": passed,
        "overlay": "configs/gate_f0_human_freeze_v1.json",
        "overlay_canonical_sha256": expected_overlay_hash,
        "z_moderate": "configs/z_moderate_v1.json",
        "evidence": evidence,
        "parent_f0_status": "PASS_WITH_HUMAN_FREEZE_ITEMS",
        "gate_f1_started": False,
        "gate_f2_started": False,
        "gate_f3_started": False,
        "rl_started": False,
    }
    dump(STATUS_PATH, status)

    if passed:
        current["project_status"] = "GATE_F0_HUMAN_FREEZE_V1_PASS_F1_READY"
        current["gate_f_started"] = True
        current["gate_f0_started"] = True
        current["gate_f1_started"] = False
        current["gate_f2_started"] = False
        current["gate_f3_started"] = False
        current["rl_started"] = False
        current["gate_f0_human_freeze_v1"] = {
            "status": "PASS",
            "record": "configs/gate_f0_human_freeze_status.json",
            "overlay": "configs/gate_f0_human_freeze_v1.json",
            "document": "docs/GATE_F0_HUMAN_FREEZE_V1_CN.md",
            "z_moderate": "configs/z_moderate_v1.json",
            "evidence": evidence,
            "gate_f1_readiness": "READY",
        }
        current["current_command"] = (
            "python tools/check_gate_f0_human_freeze.py"
        )
        dump(PROJECT / "configs/current.json", current)

    print(report["statement"])
    print(f"Gate F1 readiness = {readiness}")
    print(evidence)
    print("Gate F1 started = false")
    print("Gate F2 started = false")
    print("Gate F3 started = false")
    print("RL started = false")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
