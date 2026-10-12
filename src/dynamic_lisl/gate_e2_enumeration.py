"""Result-blind natural-candidate enumeration for the 160-satellite Gate E2."""
from __future__ import annotations

from collections import deque
from copy import deepcopy
import hashlib
import json

from .gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .operational_policy import OperationalPolicy
from .scenario_selection import deterministic_select
from .terminal_executor import Connect, TerminalExecutor
from .terminal_pair_intervals import TerminalPairCatalog
from .transition_profiler import graph_components, profile_transition


SETUP_RETARGET_A_S = 1.0
SETUP_RETARGET_B_S = 1.0
SETUP_ACQUISITION_S = 1.0
SETUP_TOTAL_S = 2.0
DECISION_FLOOR_S = 1.0


def edge(a, b):
    return tuple(sorted((a, b)))


def canonical_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def graph_path(nodes, edges, source, destination):
    adjacency = {node: [] for node in nodes}
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    for values in adjacency.values():
        values.sort()
    queue = deque([(source,)])
    seen = {source}
    while queue:
        path = queue.popleft()
        if path[-1] == destination:
            return path
        for neighbor in adjacency[path[-1]]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(path + (neighbor,))
    return None


def path_edges(path):
    if path is None:
        return set()
    return {edge(a, b) for a, b in zip(path[:-1], path[1:])}


def _activate(executor, binding):
    executor.submit((Connect(tuple(binding["a"]), tuple(binding["b"]),
                             float(binding["end_s"]), 0.0, 0.0, 0.0),))


def _base_executor(nodes, bindings, time_s):
    executor = TerminalExecutor(nodes)
    for binding in bindings:
        _activate(executor, binding)
    executor.advance(float(time_s))
    return executor


def _terminal_binding_map(bindings):
    result = {}
    for binding in bindings:
        pair = (tuple(binding["a"]), tuple(binding["b"]))
        result[pair[0]] = pair
        result[pair[1]] = pair
    return result


def _old_edge(pair):
    return edge(pair[0][0], pair[1][0])


def _route_features(nodes, baseline_edges, final_edges, commodities, old_edge):
    old_paths = {row["commodity_id"]: graph_path(
        nodes, baseline_edges, row["source"], row["destination"])
        for row in commodities}
    new_paths = {row["commodity_id"]: graph_path(
        nodes, final_edges, row["source"], row["destination"])
        for row in commodities}
    changed = [key for key in sorted(old_paths)
               if old_paths[key] != new_paths[key]]
    uses_old = [key for key in sorted(old_paths)
                if old_edge in path_edges(old_paths[key])]
    improved = [key for key in changed
                if old_paths[key] is not None and new_paths[key] is not None
                and len(new_paths[key]) < len(old_paths[key])]
    focus = improved or changed or uses_old
    shared = set()
    third = []
    for focus_id in focus:
        focus_edges = path_edges(new_paths[focus_id])
        for other_id in sorted(new_paths):
            if other_id == focus_id:
                continue
            overlap = focus_edges & path_edges(new_paths[other_id])
            if overlap:
                shared.update(overlap)
                third.append(other_id)
    hop_differences = {
        key: ((len(new_paths[key])-1)-(len(old_paths[key])-1))
        for key in changed if old_paths[key] is not None and new_paths[key] is not None}
    return {
        "changed": changed, "uses_old": uses_old, "improved": improved,
        "focus": sorted(set(focus)), "third_party": sorted(set(third)),
        "shared_edges": sorted(shared), "hop_differences": hop_differences,
    }


def _candidate_record(class_name, base, features):
    signature = {
        "class": class_name, "t0": base["t0_s"],
        "old": base["old_edge"], "new": base["new_edge"],
        "terminals": base["terminal_ids"],
    }
    scenario_id = "E2-" + hashlib.sha256(
        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return {
        "scenario_id": scenario_id,
        "scenario_class": class_name,
        "t0_s": base["t0_s"],
        "old_edge": base["old_edge"],
        "new_edge": base["new_edge"],
        "terminal_ids": base["terminal_ids"],
        "gate_c_legal": True,
        "kappa2": base["kappa2"],
        "transition_type": base["transition_type"],
        "connected_during_transition": base["connected_during_transition"],
        "remaining_lifetime_s": base["remaining_lifetime_s"],
        "terminal_occupancy": base["terminal_occupancy"],
        "hop_difference": features["hop_differences"],
        "path_difference": {
            "changed": features["changed"],
            "uses_old": features["uses_old"],
            "improved": features["improved"],
            "third_party": features["third_party"],
            "shared_edge_count": len(features["shared_edges"]),
        },
        "shared_edges": [list(value) for value in features["shared_edges"][:8]],
        "has_third_party_od": bool(features["third_party"]),
        "focus_commodities": features["focus"],
    }


def enumerate_natural_candidates(reference, interval_records, commodities):
    fixed = tuple(tuple(item) for item in reference["fixed_edges"])
    bindings = tuple(reference["bindings"])
    nodes = tuple(sorted({node for item in fixed for node in item}))
    planes = {node: int(node.split("_")[0][1:]) for node in nodes}
    catalog = TerminalPairCatalog.from_records(interval_records, planes)
    physical = TerminalPairPhysicalFeasibility(catalog)
    occupancy = _terminal_binding_map(bindings)
    dynamic_edges = {_old_edge((tuple(row["a"]), tuple(row["b"])))
                     for row in bindings}
    baseline_edges = set(map(lambda item: edge(*item), fixed)) | dynamic_edges
    candidates = []
    audit = {
        "terminal_pair_windows": len(interval_records),
        "proposal_attempts": 0, "physical_rejects": 0,
        "two_occupied_different_binding_skips": 0,
        "duplicate_active_link_skips": 0, "no_structural_effect_skips": 0,
        "classified_rows": 0,
    }
    route_cache = {}
    all_windows = catalog.terminal_pair_candidates(0.0) + [
        row for values in catalog.windows.values() for row in values
        if row.start_s > 0.0]
    for window in sorted(
            all_windows,
            key=lambda row: (max(DECISION_FLOOR_S, row.start_s),
                             row.sat_a, row.terminal_a,
                             row.sat_b, row.terminal_b, row.end_s)):
        t0 = max(DECISION_FLOOR_S, float(window.start_s))
        if t0 + SETUP_TOTAL_S >= window.end_s - 1e-9:
            audit["physical_rejects"] += 1
            continue
        a, b = window.endpoint_a, window.endpoint_b
        new_edge = edge(a[0], b[0])
        if new_edge in dynamic_edges:
            audit["duplicate_active_link_skips"] += 1
            continue
        bound_a, bound_b = occupancy.get(a), occupancy.get(b)
        if bound_a is not None and bound_b is not None and bound_a != bound_b:
            audit["two_occupied_different_binding_skips"] += 1
            continue
        if bound_a is not None or bound_b is not None:
            transition = "BBM"
            old_pairs = (bound_a or bound_b,)
        else:
            transition = "MBB"
            old_pairs = tuple((tuple(row["a"]), tuple(row["b"]))
                              for row in bindings)
        for old_pair in old_pairs:
            audit["proposal_attempts"] += 1
            old = _old_edge(old_pair)
            expected_final_edges = set(baseline_edges) - {old} | {new_edge}
            if len(graph_components(nodes, expected_final_edges)) != 1:
                audit["physical_rejects"] += 1
                continue
            route_key = tuple(sorted(expected_final_edges)), old
            if route_key not in route_cache:
                route_cache[route_key] = _route_features(
                    nodes, baseline_edges, expected_final_edges, commodities, old)
            features = route_cache[route_key]
            if not features["focus"]:
                audit["no_structural_effect_skips"] += 1
                continue
            during_edges = (set(baseline_edges) - {old}
                            if transition == "BBM" else set(baseline_edges))
            connected_during = len(graph_components(nodes, during_edges)) == 1
            base = {
                "t0_s": round(t0, 9),
                "old_edge": list(old),
                "new_edge": list(new_edge),
                "terminal_ids": [list(a), list(b)],
                "kappa2": SETUP_TOTAL_S/(window.end_s-t0),
                "transition_type": transition,
                "connected_during_transition": connected_during,
                "remaining_lifetime_s": window.end_s-t0,
                "terminal_occupancy": {
                    "a": "OCCUPIED" if bound_a else "IDLE",
                    "b": "OCCUPIED" if bound_b else "IDLE",
                },
            }
            classes = []
            if transition == "BBM" and not connected_during:
                classes.append("E-A_BBM_NO_ROUTE")
            if transition == "BBM" and connected_during:
                classes.append("E-B_BBM_CONNECTED_REROUTE")
            if transition == "MBB" and connected_during:
                classes.append("E-C_GENUINE_MBB")
            if (connected_during and features["improved"]
                    and features["third_party"] and features["shared_edges"]):
                classes.append("E-D_SHARED_CONGESTION_EXTERNALITY")
            for class_name in classes:
                candidates.append(_candidate_record(class_name, base, features))
                audit["classified_rows"] += 1
    unique = {row["scenario_id"]: row for row in candidates}
    candidates = sorted(unique.values(), key=lambda row: row["scenario_id"])
    audit["unique_candidate_rows"] = len(candidates)
    selection = deterministic_select(candidates, 1)
    return candidates, selection, audit


def validate_selected_candidates(reference, interval_records, selected):
    """Run selected rows through the actual Gate C/B transition stack."""
    fixed = tuple(tuple(item) for item in reference["fixed_edges"])
    bindings = tuple(reference["bindings"])
    nodes = tuple(sorted({node for item in fixed for node in item}))
    planes = {node: int(node.split("_")[0][1:]) for node in nodes}
    catalog = TerminalPairCatalog.from_records(interval_records, planes)
    physical = TerminalPairPhysicalFeasibility(catalog)
    binding_by_edge = {
        _old_edge((tuple(row["a"]), tuple(row["b"]))):
            (tuple(row["a"]), tuple(row["b"])) for row in bindings}
    results = []
    for row in selected:
        executor = _base_executor(nodes, bindings, row["t0_s"])
        old_pair = binding_by_edge[tuple(row["old_edge"])]
        release_after = ((old_pair,) if row["transition_type"] == "MBB"
                         else ())
        result = physical.evaluate(
            executor, tuple(row["terminal_ids"][0]),
            tuple(row["terminal_ids"][1]), SETUP_RETARGET_A_S,
            SETUP_RETARGET_B_S, SETUP_ACQUISITION_S,
            release_after=release_after)
        if not result["accepted"]:
            results.append({"scenario_id": row["scenario_id"],
                            "accepted": False,
                            "physical_reason": result["reason"]})
            continue
        profile = profile_transition(
            executor, (result["command"],), fixed,
            row["t0_s"] + SETUP_TOTAL_S + 1e-7)
        policy = (OperationalPolicy("BOUNDED_OUTAGE", SETUP_TOTAL_S+1e-7)
                  if row["scenario_class"] == "E-A_BBM_NO_ROUTE" else
                  OperationalPolicy("STRICT_CONNECTED"))
        decision = policy.apply(profile)
        results.append({
            "scenario_id": row["scenario_id"],
            "accepted": decision["accepted"],
            "physical_reason": result["reason"],
            "policy_reason": decision["reason"],
            "profile_classification": profile["classification"],
            "partition_occurs": profile["partition_occurs"],
            "outage_duration_s": profile["outage_duration"],
            "remaining_lifetime_s": result["geometry"]["remaining_lifetime_s"],
            "usable_lifetime_s": result["geometry"]["usable_lifetime_s"],
            "transition_type_matches": (
                (row["transition_type"] == "BBM" and not release_after)
                or (row["transition_type"] == "MBB" and bool(release_after))),
            "connectivity_class_matches": (
                row["connected_during_transition"]
                == (not profile["partition_occurs"])),
        })
    return {
        "cases": results,
        "all_selected_gate_c_legal": all(row["accepted"] for row in results),
        "all_transition_classes_match": all(
            row.get("transition_type_matches", False)
            and row.get("connectivity_class_matches", False)
            for row in results),
    }
