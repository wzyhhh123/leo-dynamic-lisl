"""One deterministic adjacent-plane terminal-pair reference topology."""
from __future__ import annotations

from collections import Counter
import math

from .reference_topology import intra_plane_rings
from .transition_profiler import graph_components


def _stats(values):
    values = sorted(float(value) for value in values)
    if not values:
        return {"count": 0}
    def percentile(q):
        position = (len(values) - 1) * q
        low, high = math.floor(position), math.ceil(position)
        return values[low] if low == high else values[low] * (high-position) + values[high] * (position-low)
    return {
        "count": len(values), "min": values[0], "median": percentile(0.5),
        "p95": percentile(0.95), "max": values[-1], "mean": sum(values)/len(values),
    }


def _bridges(nodes, edges):
    adjacency = {node: set() for node in nodes}
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    discovery, low, parent, result = {}, {}, {}, []
    counter = [0]
    def visit(node):
        counter[0] += 1
        discovery[node] = low[node] = counter[0]
        for neighbor in sorted(adjacency[node]):
            if neighbor not in discovery:
                parent[neighbor] = node
                visit(neighbor)
                low[node] = min(low[node], low[neighbor])
                if low[neighbor] > discovery[node]:
                    result.append(tuple(sorted((node, neighbor))))
            elif parent.get(node) != neighbor:
                low[node] = min(low[node], discovery[neighbor])
    for node in nodes:
        if node not in discovery:
            visit(node)
    return sorted(result)


def build_adjacent_plane_reference(catalog, satellite_ids, plane_by_satellite,
                                   slot_by_satellite, time_s=0.0,
                                   retarget_a_s=1.0, retarget_b_s=1.0,
                                   acquisition_s=1.0):
    """Connect consecutive plane components with explicit, nonconflicting terminals."""
    nodes = tuple(satellite_ids)
    fixed = intra_plane_rings(nodes, plane_by_satellite, slot_by_satellite)
    planes = sorted({plane_by_satellite[node] for node in nodes})
    candidates = catalog.terminal_pair_candidates(time_s, nodes)
    selected = []
    used_terminals = set()
    for left, right in zip(planes, planes[1:]):
        options = [window for window in candidates if {
            plane_by_satellite[window.sat_a], plane_by_satellite[window.sat_b]
        } == {left, right}]
        options.sort(key=lambda window: (
            -(window.end_s-time_s),
            window.distance_km if window.distance_km is not None else float("inf"),
            window.sat_a, window.terminal_a, window.sat_b, window.terminal_b,
        ))
        chosen = next((window for window in options
                       if window.endpoint_a not in used_terminals
                       and window.endpoint_b not in used_terminals), None)
        if chosen is None:
            raise ValueError("NO_ADJACENT_PLANE_TERMINAL_PAIR_FOR_REFERENCE")
        selected.append(chosen)
        used_terminals.update((chosen.endpoint_a, chosen.endpoint_b))

    dynamic_edges = {tuple(sorted((window.sat_a, window.sat_b))) for window in selected}
    all_edges = set(fixed) | dynamic_edges
    components = graph_components(nodes, all_edges)
    if len(components) != 1:
        raise AssertionError("Reference topology is not connected")
    setup_ready_s = max(retarget_a_s, retarget_b_s) + acquisition_s
    remaining = [window.end_s-time_s for window in selected]
    usable = [window.end_s-time_s-setup_ready_s for window in selected]
    if any(value <= 0.0 for value in usable):
        raise ValueError("Reference includes setup-infeasible link")
    occupied = 2 * len(selected)
    total_terminals = 2 * len(nodes)
    bridge_edges = _bridges(nodes, all_edges)
    bindings = [{
        "a": list(window.endpoint_a), "b": list(window.endpoint_b),
        "start_s": window.start_s, "end_s": window.end_s,
        "remaining_lifetime_s": window.end_s-time_s,
        "ready_time_s": time_s+setup_ready_s,
        "usable_lifetime_s": window.end_s-time_s-setup_ready_s,
        "plane_gap": window.plane_gap,
    } for window in selected]
    return {
        "schema": "gate_c_z_ref_v1",
        "time_s": time_s,
        "construction": "deterministic_adjacent_plane_oriented_connected",
        "traffic_agnostic": True,
        "fixed_edge_count": len(fixed),
        "dynamic_link_count": len(selected),
        "dynamic_terminal_occupancy_ratio": occupied/total_terminals,
        "idle_dynamic_terminal_ratio": 1.0-occupied/total_terminals,
        "number_of_bridges": len(bridge_edges),
        "bridges": [list(edge) for edge in bridge_edges],
        "initial_connectivity": "CONNECTED",
        "component_count": len(components),
        "remaining_lifetime_distribution_s": _stats(remaining),
        "usable_lifetime_distribution_s": _stats(usable),
        "bindings": bindings,
        "fixed_edges": [list(edge) for edge in sorted(fixed)],
    }


def audit_reference_candidate_idle_fraction(catalog, reference, time_s=0.0):
    occupied = {tuple(binding[side]) for binding in reference["bindings"] for side in ("a", "b")}
    active_satellite_pairs = {tuple(sorted((binding["a"][0], binding["b"][0])))
                              for binding in reference["bindings"]}
    candidates = catalog.terminal_pair_candidates(time_s)
    eligible = [window for window in candidates
                if tuple(sorted((window.sat_a, window.sat_b))) not in active_satellite_pairs]
    mbb = [window for window in eligible if window.endpoint_a not in occupied
           and window.endpoint_b not in occupied]
    return {
        "definition": "candidate terminal pair has both concrete terminals idle under Z_ref and is not a parallel link to an active satellite pair",
        "eligible_candidate_count": len(eligible),
        "projected_mbb_feasible_count": len(mbb),
        "projected_mbb_feasible_fraction": len(mbb)/len(eligible) if eligible else 0.0,
    }
