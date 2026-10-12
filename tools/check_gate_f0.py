"""Validate Gate F0 contracts only; never run controller performance."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CONTRACT = PROJECT / "configs/gate_f0_controller_contract.json"
REGISTRY = PROJECT / "configs/gate_f0_baseline_registry.json"
FROZEN = PROJECT / "configs/gate_f0_frozen_a_to_e2_hashes.json"
STATUS = PROJECT / "configs/gate_f0_status.json"

DOCS = (
    "docs/GATE_F0_TOPOLOGY_CONTROLLER_CONTRACT_CN.md",
    "docs/GATE_F0_INTERFACE_AUDIT_CN.md",
    "docs/GATE_F0_BASELINE_REGISTRY_CN.md",
    "docs/GATE_F0_HUMAN_DECISIONS_REQUIRED_CN.md",
)

FORBIDDEN_IMPLEMENTATION_PATHS = (
    "src/dynamic_lisl/gate_f_controller.py",
    "src/dynamic_lisl/topology_controller.py",
    "src/dynamic_lisl/ignore_setup_controller.py",
    "src/dynamic_lisl/hysteresis_controller.py",
    "src/dynamic_lisl/setup_aware_greedy.py",
    "src/dynamic_lisl/mpc_controller.py",
    "src/dynamic_lisl/matching_controller.py",
    "src/dynamic_lisl/rl_controller.py",
    "tools/run_gate_f1.py",
    "tools/run_gate_f2.py",
    "tools/run_gate_f3.py",
)

REQUIRED_METRICS = {
    "mean_bit_delay_s", "delivered_bits", "delivery_ratio",
    "residual_backlog_bits", "peak_queue_bits", "queue_area_bit_s",
    "link_utilization", "route_change_count", "topology_switch_count",
    "BBM_count", "MBB_count", "transition_backlog_bits",
    "transition_period_outage_s", "post_expiry_no_route_s",
    "partition_node_time_s", "active_dynamic_link_time_link_s",
    "controller_runtime_s", "candidate_count", "rollout_evaluation_count",
}

REQUIRED_FAIRNESS = {
    "same_initial_topology", "same_initial_terminal_states", "same_traffic_trace",
    "same_geometry", "same_gate_b_c_executor", "same_capacity",
    "same_scheduler", "same_router", "same_decision_epochs",
    "same_candidate_universe", "same_drain_and_censor_rule",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def frozen_audit():
    record = read(FROZEN)
    current = {
        name: sha(PROJECT / name) if (PROJECT / name).is_file() else None
        for name in sorted(record["files"])
    }
    return {
        "record": str(FROZEN.relative_to(PROJECT)).replace("\\", "/"),
        "expected": record["files"],
        "current": current,
        "all_unchanged": current == record["files"],
    }


def main():
    checks = {}
    contract = read(CONTRACT)
    registry = read(REGISTRY)
    current = read(PROJECT / "configs/current.json")

    checks["gate_e2_pass"] = current.get("gate_e2", {}).get("status") == "PASS"
    checks["contract_schema"] = (
        contract.get("schema") == "gate_f0_topology_controller_contract_v1"
    )
    checks["contract_status"] = (
        contract.get("status") == "PASS_WITH_HUMAN_FREEZE_ITEMS"
    )
    checks["action_variants"] = (
        set(contract["action_contract"]["variants"]) == {"HOLD", "REPLACE"}
        and not contract["action_contract"]["controller_may_declare_transition_mode"]
        and contract["action_contract"]["packet_next_hop_field_forbidden"]
    )
    checks["causal_chain_complete"] = contract["causal_chain"] == [
        "current_state", "candidate_proposal",
        "gate_c_physical_legality_filter",
        "controller_hold_or_switch_decision",
        "gate_b_real_terminal_execution",
        "g_active_and_g_admit", "common_fast_routing",
        "network_service", "queue_inflight_delivery_state",
    ]
    checks["state_contract_complete"] = all(
        contract["observation_contract"].get(key)
        for key in (
            "network_topology", "terminal_state",
            "candidate_physical_state", "traffic_network_state",
            "allowed_current_state_derived_features",
        )
    )
    checks["future_policy_classes"] = set(
        contract["future_information_policy"]["classes"]
    ) == {
        "CURRENT_STATE_ONLY",
        "SHORT_HORIZON_FORECAST",
        "ORACLE_SMALL_FIXTURE_ONLY",
    }
    checks["decision_ambiguities_explicit"] = (
        contract["decision_epoch_contract"]["cadence_s"] is None
        and len(contract["decision_epoch_contract"]["unresolved"]) >= 4
    )
    checks["candidate_interface_complete"] = (
        contract["candidate_proposal_contract"]["interface_output_unit"]
        == "concrete_terminal_pair"
        and contract["candidate_proposal_contract"]["top_k"] is None
        and contract["candidate_proposal_contract"][
            "exhaustive_search_in_main_scale_forbidden"
        ]
    )
    checks["routing_fairness"] = (
        contract["common_fast_routing"]["primary_contract_id"]
        == "DeterministicShortestPropagationDelayRouter"
        and contract["common_fast_routing"]["robustness_contract_id"]
        == "DeterministicCurrentStateLoadAwareRouter"
    )
    checks["objective_has_no_artificial_penalty"] = (
        contract["objective"]["primary"]
        == "J=sum_f integral N_f(t) dt"
        and len(contract["objective"]["artificial_penalties_forbidden"]) == 4
    )
    checks["secondary_metrics_complete"] = REQUIRED_METRICS.issubset(
        set(contract["secondary_metrics"])
    )
    checks["outage_metrics_separated"] = (
        contract["outage_metric_separation"][
            "cumulative_forced_outage_as_primary_metric_forbidden"
        ]
        and contract["outage_metric_separation"][
            "per_commodity_versions_required"
        ]
    )
    checks["baseline_registry_complete"] = (
        registry.get("schema") == "gate_f0_baseline_registry_v1"
        and {row["id"] for row in registry["baselines"]}
        == {"B0", "B1", "B2", "B3", "B4", "B5"}
        and all(not row["implemented"] for row in registry["baselines"])
    )
    checks["rl_not_required"] = (
        registry["required_rl_baseline"] is False
        and registry["rl_status"] == "NOT_REGISTERED_AS_REQUIRED"
    )
    sparse = contract["topology_regimes"]["Z_SPARSE_REFERENCE"]
    moderate = contract["topology_regimes"]["Z_MODERATE"]
    checks["sparse_regime_retained"] = (
        sparse["retained"] and sparse["dynamic_cross_plane_links"] == 3
        and sparse["dynamic_edges_all_bridges"]
    )
    checks["moderate_principles_without_hidden_density"] = (
        moderate["status"] == "REQUIRES_HUMAN_FREEZE"
        and moderate["traffic_agnostic"] and moderate["result_blind"]
        and moderate["selected_design"] is None
        and moderate["target_dynamic_terminal_occupancy"] is None
        and len(moderate["candidate_designs"]) == 3
    )
    checks["scale_registry"] = contract["scale_registry"] == {
        "development_satellites": 160,
        "generalization_satellites": 240,
        "later_scalability_satellites": 720,
        "f0_runs_scale_experiments": False,
    }
    checks["evaluation_grid_not_invented"] = (
        contract["evaluation_axes"]["concrete_grid"] is None
        and contract["evaluation_axes"]["status"] == "REQUIRES_HUMAN_FREEZE"
    )
    checks["censor_boundary"] = (
        set(contract["censoring_contract"]["statuses"])
        == {"COMPLETE", "CENSORED_AT_DRAIN_LIMIT"}
        and not contract["censoring_contract"][
            "truncated_J_may_rank_complete_performance"
        ]
        and contract["censoring_contract"][
            "mixed_censor_controller_ranking_policy"
        ] is None
    )
    checks["fairness_complete"] = REQUIRED_FAIRNESS.issubset(
        set(contract["fairness_contract"])
    )
    checks["safety_reject_only"] = (
        contract["safety_boundary"]["reject_only_no_reranking"]
        and len(contract["safety_boundary"]["forbidden"]) == 4
    )
    checks["reuse_existing_simulator"] = (
        not contract["interface_reuse"]["second_parallel_simulator_required"]
        and not contract["interface_reuse"]["blocker_found"]
    )
    checks["required_docs_exist"] = all(
        (PROJECT / name).is_file() and (PROJECT / name).stat().st_size > 0
        for name in DOCS
    )
    checks["no_forbidden_controller_implementation"] = not any(
        (PROJECT / name).exists() for name in FORBIDDEN_IMPLEMENTATION_PATHS
    )
    checks["no_gate_f_performance_outputs"] = not any(
        list((PROJECT / "outputs").glob(pattern))
        for pattern in ("gate_f1*", "gate_f2*", "gate_f3*", "gate_f_performance*")
    )
    checks["later_gates_not_started_before_check"] = all(
        current.get(key, False) is False
        for key in ("gate_f1_started", "gate_f2_started",
                    "gate_f3_started", "rl_started")
    )
    checks["human_freeze_document_registered"] = (
        contract["human_freeze_document"]
        == "docs/GATE_F0_HUMAN_DECISIONS_REQUIRED_CN.md"
    )

    pre_hash = frozen_audit()
    checks["frozen_a_to_e2_unchanged_pre"] = pre_hash["all_unchanged"]

    passed = all(checks.values())
    status_value = (
        "PASS_WITH_HUMAN_FREEZE_ITEMS" if passed else "FAIL"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = PROJECT / "outputs" / f"gate_f0_contract_{stamp}"
    output.mkdir(parents=True, exist_ok=False)

    post_hash = frozen_audit()
    checks["frozen_a_to_e2_unchanged_post"] = post_hash["all_unchanged"]
    passed = all(checks.values())
    status_value = (
        "PASS_WITH_HUMAN_FREEZE_ITEMS" if passed else "FAIL"
    )

    report = {
        "schema": "gate_f0_validation_report_v1",
        "statement": f"Gate F0 topology-controller contract = {status_value}",
        "status": status_value,
        "checks": checks,
        "human_freeze_item_count": 9,
        "simulator_blocker": False if passed else None,
        "f1_blocked_by_human_freeze_items": True,
        "controller_implementations_created": False,
        "performance_experiments_run": False,
        "gate_f1_started": False,
        "gate_f2_started": False,
        "gate_f3_started": False,
        "rl_started": False,
    }
    dump(output / "frozen_a_to_e2_hash_report.json",
         {"pre": pre_hash, "post": post_hash})
    dump(output / "report.json", report)
    dump(output / "artifact_hashes.json", {
        name: sha(PROJECT / name)
        for name in (
            *DOCS,
            "configs/gate_f0_controller_contract.json",
            "configs/gate_f0_baseline_registry.json",
            "configs/gate_f0_frozen_a_to_e2_hashes.json",
            "tools/check_gate_f0.py",
        )
    })

    evidence = str(output.relative_to(PROJECT)).replace("\\", "/")
    status = {
        "gate_f0": status_value,
        "statement": report["statement"],
        "evidence": evidence,
        "contract": "docs/GATE_F0_TOPOLOGY_CONTROLLER_CONTRACT_CN.md",
        "interface_audit": "docs/GATE_F0_INTERFACE_AUDIT_CN.md",
        "baseline_registry": "docs/GATE_F0_BASELINE_REGISTRY_CN.md",
        "human_decisions": "docs/GATE_F0_HUMAN_DECISIONS_REQUIRED_CN.md",
        "simulator_blocker": False if passed else None,
        "human_freeze_required_before_f1": True,
        "gate_f1_started": False,
        "gate_f2_started": False,
        "gate_f3_started": False,
        "rl_started": False,
    }
    dump(STATUS, status)

    if passed:
        current["project_status"] = (
            "GATE_F0_TOPOLOGY_CONTROLLER_CONTRACT_PASS_WITH_HUMAN_FREEZE_ITEMS"
        )
        current["gate_f_started"] = True
        current["gate_f0_started"] = True
        current["gate_f1_started"] = False
        current["gate_f2_started"] = False
        current["gate_f3_started"] = False
        current["rl_started"] = False
        current["gate_f0"] = {
            "status": status_value,
            "record": "configs/gate_f0_status.json",
            "contract": status["contract"],
            "interface_audit": status["interface_audit"],
            "baseline_registry": status["baseline_registry"],
            "human_decisions": status["human_decisions"],
            "evidence": evidence,
        }
        current["current_command"] = "python tools/check_gate_f0.py"
        dump(PROJECT / "configs/current.json", current)

    print(report["statement"])
    print(evidence)
    print("Gate F1 started = false")
    print("Gate F2 started = false")
    print("Gate F3 started = false")
    print("RL started = false")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
