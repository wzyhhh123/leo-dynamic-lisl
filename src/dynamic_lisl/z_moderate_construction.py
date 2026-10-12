"""Result-blind Z_MODERATE v1 structural construction.

This is a topology-asset builder, not a controller and not a performance runner.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .operational_policy import OperationalPolicy
from .terminal_executor import Connect, TerminalExecutor
from .terminal_pair_intervals import TerminalPairCatalog
from .transition_profiler import graph_components, profile_transition


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def edge(a, b):
    return tuple(sorted((a, b)))


def plane(node):
    return int(node.split("_", 1)[0][1:])


def bridges(nodes, edges):
    nodes = tuple(sorted(nodes))
    edges = {edge(*item) for item in edges}

    def components(excluded=None):
        kept = edges if excluded is None else edges - {excluded}
        return graph_components(nodes, kept)

    if len(components()) != 1:
        return sorted(edges)
    return sorted(item for item in edges if len(components(item)) > 1)


def _load(project):
    project = Path(project)
    z_ref = json.loads((project / (
        "outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json"
    )).read_text(encoding="utf-8"))
    records = [
        json.loads(line) for line in (project / (
            "outputs/gate_c_simplified_20260922T064019_313843Z/"
            "terminal_pair_intervals.jsonl"
        )).read_text(encoding="utf-8").splitlines()
    ]
    nodes = tuple(sorted({node for item in z_ref["fixed_edges"] for node in item}))
    planes = {node: plane(node) for node in nodes}
    catalog = TerminalPairCatalog.from_records(records, planes)
    return z_ref, nodes, catalog


def _seed_executor(z_ref, nodes):
    executor = TerminalExecutor(nodes)
    for binding in z_ref["bindings"]:
        executor.submit((Connect(
            tuple(binding["a"]), tuple(binding["b"]),
            float(binding["end_s"]), 0.0, 0.0, 0.0,
        ),))
    return executor


def _plane_graph(z_ref, added=()):
    planes = sorted({plane(node) for item in z_ref["fixed_edges"] for node in item})
    dynamic_edges = [
        edge(plane(binding["a"][0]), plane(binding["b"][0]))
        for binding in z_ref["bindings"]
    ]
    dynamic_edges.extend(
        edge(plane(item["a"][0]), plane(item["b"][0])) for item in added
    )
    return planes, sorted(set(dynamic_edges))


def construct_z_moderate(project):
    z_ref, nodes, catalog = _load(project)
    executor = _seed_executor(z_ref, nodes)
    physical = TerminalPairPhysicalFeasibility(catalog)
    plane_nodes, plane_edges_before = _plane_graph(z_ref)
    bridges_before = bridges(plane_nodes, plane_edges_before)
    occupied = {
        endpoint
        for binding in z_ref["bindings"]
        for endpoint in (tuple(binding["a"]), tuple(binding["b"]))
    }
    old_satellite_edges = {
        edge(binding["a"][0], binding["b"][0]) for binding in z_ref["bindings"]
    }

    ranked_raw = []
    pruned = {
        "terminal_or_reservation_conflict": 0,
        "exact_physical_noop_or_identical_binding": 0,
        "does_not_achieve_one_binding_plane_cycle_closure": 0,
    }
    for window in catalog.terminal_pair_candidates(0.0, nodes):
        a, b = window.endpoint_a, window.endpoint_b
        satellite_edge = edge(a[0], b[0])
        if satellite_edge in old_satellite_edges:
            pruned["exact_physical_noop_or_identical_binding"] += 1
            continue
        if a in occupied or b in occupied:
            pruned["terminal_or_reservation_conflict"] += 1
            continue
        candidate_plane_edge = edge(plane(a[0]), plane(b[0]))
        after_edges = sorted(set(plane_edges_before) | {candidate_plane_edge})
        after_bridges = bridges(plane_nodes, after_edges)
        reduction = len(bridges_before) - len(after_bridges)
        if after_bridges:
            pruned["does_not_achieve_one_binding_plane_cycle_closure"] += 1
            continue
        proposal_payload = {
            "old_edge": [],
            "old_terminal_ids": [],
            "new_edge": list(satellite_edge),
            "new_terminal_ids": [list(a), list(b)],
        }
        proposal_id = "ZM-" + canonical_sha256(proposal_payload)[:16]
        ranked_raw.append({
            "proposal_id": proposal_id,
            "a": list(a), "b": list(b),
            "old_edge": [], "old_terminal_ids": [],
            "new_edge": list(satellite_edge),
            "new_terminal_ids": [list(a), list(b)],
            "plane_edge": list(candidate_plane_edge),
            "plane_bridge_deficit_reduction": reduction,
            "remaining_lifetime_s": window.end_s,
            "ready_time_s": 2.0,
            "usable_lifetime_s": window.end_s - 2.0,
            "plane_gap": window.plane_gap,
            "window": window.to_dict(),
        })

    ranked_raw.sort(key=lambda row: (
        -row["plane_bridge_deficit_reduction"],
        -row["usable_lifetime_s"],
        row["plane_gap"],
        tuple(row["old_edge"]),
        tuple(tuple(x) for x in row["old_terminal_ids"]),
        tuple(row["new_edge"]),
        tuple(tuple(x) for x in row["new_terminal_ids"]),
        row["proposal_id"],
    ))

    selected = None
    gate_c_rejections = []
    strict_rejections = 0
    for row in ranked_raw:
        result = physical.evaluate(
            executor, tuple(row["a"]), tuple(row["b"]),
            retarget_a=1.0, retarget_b=1.0, acquisition=1.0,
        )
        if not result["accepted"]:
            gate_c_rejections.append({
                "proposal_id": row["proposal_id"],
                "reason": result["reason"],
            })
            continue
        geometry = result["geometry"]
        row["remaining_lifetime_s"] = geometry["remaining_lifetime_s"]
        row["ready_time_s"] = geometry["ready_time"]
        row["usable_lifetime_s"] = geometry["usable_lifetime_s"]
        row["gate_c_legal"] = True
        row["terminal_conflict"] = False
        profile = profile_transition(
            executor, [result["command"]], z_ref["fixed_edges"],
            min(float(row["window"]["end_s"]), 2.0 + 1e-7),
        )
        policy = OperationalPolicy("STRICT_CONNECTED").apply(profile)
        row["strict_connected_transition"] = bool(policy["accepted"])
        row["transition_profile_classification"] = profile["classification"]
        if not policy["accepted"]:
            strict_rejections += 1
            continue
        selected = deepcopy(row)
        break

    if selected is None:
        return {
            "schema": "z_moderate_v1",
            "status": "Z_MODERATE_CONSTRUCTION_INFEASIBLE_AT_REGISTERED_EPOCH",
            "selected_design": "ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE",
            "construction_epoch_s": 0.0,
            "candidate_audit": {
                "ranked_structural_cycle_closure_candidates": len(ranked_raw),
                "gate_c_rejections_before_exhaustion": gate_c_rejections,
                "strict_connectivity_rejections": strict_rejections,
                "pruned_counts": pruned,
            },
        }

    selected = deepcopy(selected)
    binding = {
        "a": selected["a"], "b": selected["b"],
        "start_s": 0.0,
        "end_s": selected["window"]["end_s"],
        "remaining_lifetime_s": selected["remaining_lifetime_s"],
        "ready_time_s": selected["ready_time_s"],
        "usable_lifetime_s": selected["usable_lifetime_s"],
        "plane_gap": selected["plane_gap"],
        "construction_proposal_id": selected["proposal_id"],
    }
    all_bindings = deepcopy(z_ref["bindings"]) + [binding]
    plane_nodes, plane_edges_after = _plane_graph(z_ref, (binding,))
    plane_bridges_after = bridges(plane_nodes, plane_edges_after)
    dynamic_satellite_edges = [
        edge(item["a"][0], item["b"][0]) for item in all_bindings
    ]
    satellite_edges = (
        {edge(*item) for item in z_ref["fixed_edges"]}
        | set(dynamic_satellite_edges)
    )
    satellite_bridges = bridges(nodes, satellite_edges)
    used_terminals = {
        tuple(endpoint)
        for item in all_bindings
        for endpoint in (item["a"], item["b"])
    }
    terminal_conflicts = (
        2 * len(all_bindings) - len(used_terminals)
    )
    plane_coverage = sorted({
        plane(endpoint[0])
        for item in all_bindings
        for endpoint in (item["a"], item["b"])
    })
    nonbridge_dynamic = [
        list(item) for item in dynamic_satellite_edges
        if item not in set(satellite_bridges)
    ]
    result = {
        "schema": "z_moderate_v1",
        "status": "CONSTRUCTED",
        "selected_design": "ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE",
        "construction_epoch_s": 0.0,
        "traffic_agnostic": True,
        "result_blind": True,
        "parent_topology": (
            "outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json"
        ),
        "minimality_certificate": {
            "bridges_before": len(bridges_before),
            "zero_additions_satisfy_target": len(bridges_before) == 0,
            "one_addition_satisfies_target": len(plane_bridges_after) == 0,
            "minimum_added_bindings": 1,
        },
        "selected_addition": selected,
        "bindings": all_bindings,
        "fixed_edges": z_ref["fixed_edges"],
        "structural_audit": {
            "satellites": len(nodes),
            "planes": len(plane_nodes),
            "dynamic_link_count": len(all_bindings),
            "added_dynamic_link_count": 1,
            "used_dynamic_terminals": len(used_terminals),
            "total_dynamic_terminals": 2 * len(nodes),
            "terminal_occupancy_fraction": len(used_terminals) / (2 * len(nodes)),
            "terminal_conflict_count": terminal_conflicts,
            "plane_graph_edges": [list(item) for item in plane_edges_after],
            "plane_graph_connected": len(
                graph_components(plane_nodes, plane_edges_after)
            ) == 1,
            "plane_bridge_count": len(plane_bridges_after),
            "plane_bridges": [list(item) for item in plane_bridges_after],
            "satellite_graph_connected": len(
                graph_components(nodes, satellite_edges)
            ) == 1,
            "satellite_bridge_count": len(satellite_bridges),
            "satellite_bridges": [list(item) for item in satellite_bridges],
            "nonbridge_dynamic_edge_count": len(nonbridge_dynamic),
            "nonbridge_dynamic_edges": nonbridge_dynamic,
            "plane_coverage": plane_coverage,
            "all_binding_gate_c_legality": True,
            "strict_connected_transition_for_added_binding": selected[
                "strict_connected_transition"
            ],
        },
        "candidate_audit": {
            "ranked_structural_cycle_closure_candidates": len(ranked_raw),
            "gate_c_rejections_before_selection": gate_c_rejections,
            "strict_connectivity_rejections_before_selection": strict_rejections,
            "pruned_counts": pruned,
            "selected_by_frozen_tie_order": True,
        },
        "deterministic_tie_order": [
            "largest_plane_bridge_deficit_reduction",
            "largest_usable_lifetime_s",
            "smallest_plane_gap",
            "old_edge",
            "old_terminal_ids",
            "new_edge",
            "new_terminal_ids",
            "proposal_id",
        ],
    }
    result["canonical_sha256"] = canonical_sha256(result)
    return result
