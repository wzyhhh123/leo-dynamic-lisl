"""Gate C1 deterministic, traffic-agnostic reference-topology study."""
from __future__ import annotations

from collections import Counter
import math

from .transition_profiler import graph_components


def intra_plane_rings(satellite_ids, plane_by_satellite, slot_by_satellite):
    groups = {}
    for sat in satellite_ids:
        groups.setdefault(plane_by_satellite[sat], []).append(sat)
    edges = set()
    for members in groups.values():
        members.sort(key=lambda x: slot_by_satellite[x])
        for a, b in zip(members, members[1:] + members[:1]):
            edges.add(tuple(sorted((a, b))))
    return edges


def _stats(values):
    values = sorted(values)
    if not values:
        return dict(count=0)
    def percentile(q):
        pos = (len(values)-1)*q
        lo, hi = math.floor(pos), math.ceil(pos)
        return values[lo] if lo == hi else values[lo]*(hi-pos)+values[hi]*(pos-lo)
    return dict(count=len(values), min=values[0], median=percentile(.5),
                p95=percentile(.95), max=values[-1],
                mean=sum(values)/len(values))


def _bridges_and_articulations(nodes, edges):
    adjacency = {x: set() for x in nodes}
    for a, b in edges:
        adjacency[a].add(b); adjacency[b].add(a)
    timer = [0]; disc = {}; low = {}; parent = {}; bridges = []; articulation = set()
    def visit(u):
        timer[0] += 1; disc[u] = low[u] = timer[0]; children = 0
        for v in adjacency[u]:
            if v not in disc:
                parent[v] = u; children += 1; visit(v); low[u] = min(low[u], low[v])
                if low[v] > disc[u]: bridges.append(tuple(sorted((u, v))))
                if u not in parent and children > 1: articulation.add(u)
                if u in parent and low[v] >= disc[u]: articulation.add(u)
            elif parent.get(u) != v:
                low[u] = min(low[u], disc[v])
    for node in nodes:
        if node not in disc: visit(node)
    return sorted(bridges), sorted(articulation)


def build_reference_constructions(catalog, satellite_ids, plane_by_satellite,
                                  slot_by_satellite, time_s=0.0):
    """Return sparse/medium/dense bindings without selecting a winner."""
    nodes = tuple(satellite_ids)
    planes = sorted({plane_by_satellite[node] for node in nodes})
    fixed = intra_plane_rings(nodes, plane_by_satellite, slot_by_satellite)
    candidates = catalog.inter_plane_candidates(time_s, nodes)
    candidates.sort(key=lambda w: (
        0 if abs(plane_by_satellite[w.sat_a]-plane_by_satellite[w.sat_b]) == 1 else 1,
        abs(plane_by_satellite[w.sat_a]-plane_by_satellite[w.sat_b]),
        -(w.end_s-time_s), w.distance_km if w.distance_km is not None else float("inf"),
        w.sat_a, w.sat_b))

    # Seed every adjacent plane boundary before adding density.
    seeds = []
    used_pairs = set()
    degree = Counter()
    for left, right in zip(planes, planes[1:]):
        options = [w for w in candidates if {plane_by_satellite[w.sat_a], plane_by_satellite[w.sat_b]} == {left, right}]
        chosen = next((w for w in options if degree[w.sat_a] < 2 and degree[w.sat_b] < 2), None)
        if chosen is None:
            raise ValueError("No bilateral adjacent-plane seed for reference")
        seeds.append(chosen); used_pairs.add((chosen.sat_a, chosen.sat_b))
        degree[chosen.sat_a] += 1; degree[chosen.sat_b] += 1

    targets = {"sparse_connected": len(planes)-1,
               "medium_occupancy": max(len(planes)-1, len(nodes)//2),
               "relative_dense": max(len(planes)-1, (3*len(nodes))//4)}
    result = {}
    for name, target in targets.items():
        selected = list(seeds)
        local_degree = Counter()
        for w in selected:
            local_degree[w.sat_a] += 1; local_degree[w.sat_b] += 1
        selected_pairs = {(w.sat_a, w.sat_b) for w in selected}
        for window in candidates:
            key = (window.sat_a, window.sat_b)
            if len(selected) >= target: break
            if key in selected_pairs or local_degree[window.sat_a] >= 2 or local_degree[window.sat_b] >= 2:
                continue
            selected.append(window); selected_pairs.add(key)
            local_degree[window.sat_a] += 1; local_degree[window.sat_b] += 1
        if len(selected) != target:
            raise ValueError("Insufficient terminal capacity for %s" % name)
        terminal_use = Counter()
        bindings = []
        for w in sorted(selected, key=lambda x: (x.sat_a, x.sat_b)):
            a = (w.sat_a, "D1" if terminal_use[w.sat_a] == 0 else "D2")
            b = (w.sat_b, "D1" if terminal_use[w.sat_b] == 0 else "D2")
            terminal_use[w.sat_a] += 1; terminal_use[w.sat_b] += 1
            bindings.append((a, b, w))
        result[name] = summarize_reference(name, nodes, fixed, bindings, plane_by_satellite,
                                           catalog, time_s)
    return dict(fixed_edges=sorted(fixed), constructions=result,
                candidate_count=len(candidates), time_s=time_s)


def summarize_reference(name, nodes, fixed_edges, bindings, plane_by_satellite, catalog, time_s):
    dynamic = {tuple(sorted((a[0], b[0]))) for a, b, _ in bindings}
    all_edges = set(fixed_edges) | dynamic
    components = graph_components(nodes, all_edges)
    if len(components) != 1:
        raise AssertionError("Reference construction disconnected")
    degree = Counter()
    for a, b in dynamic: degree[a] += 1; degree[b] += 1
    occupied = sum(degree.values())
    idle_nodes = {x for x in nodes if degree[x] < 2}
    candidate_windows = catalog.inter_plane_candidates(time_s, nodes)
    mbb_pairs = sum(w.sat_a in idle_nodes and w.sat_b in idle_nodes for w in candidate_windows)
    bridges, articulations = _bridges_and_articulations(nodes, all_edges)
    dynamic_bridges = [x for x in bridges if x in dynamic]
    plane_counts = Counter(tuple(sorted((plane_by_satellite[a], plane_by_satellite[b])))
                           for a, b in dynamic)
    ends = [w.end_s for _, _, w in bindings]
    uncensored_ends = [w.end_s for _, _, w in bindings if not w.right_censored]
    # Remove links as known windows expire and find first observed disconnection.
    disconnect_time = None
    for end in sorted(set(uncensored_ends)):
        alive = {tuple(sorted((a[0], b[0]))) for a, b, w in bindings if w.end_s > end}
        if len(graph_components(nodes, set(fixed_edges) | alive)) > 1:
            disconnect_time = end; break
    min_plane, max_plane = min(plane_by_satellite.values()), max(plane_by_satellite.values())
    boundary_nodes = {x for x in nodes if plane_by_satellite[x] in (min_plane, max_plane)}
    interior_nodes = set(nodes)-boundary_nodes
    def occupancy(group):
        return sum(degree[x] for x in group)/(2*len(group)) if group else None
    return dict(
        name=name, connected=True, dynamic_link_count=len(bindings),
        mean_dynamic_degree=2*len(bindings)/len(nodes), max_dynamic_degree=max(degree.values(), default=0),
        terminal_occupancy_ratio=occupied/(2*len(nodes)), idle_dynamic_terminal_ratio=1-occupied/(2*len(nodes)),
        satellites_with_idle_terminal_ratio=len(idle_nodes)/len(nodes),
        projected_mbb_candidate_ratio=(mbb_pairs/len(candidate_windows) if candidate_windows else 0),
        distance_km=_stats([w.distance_km for _, _, w in bindings if w.distance_km is not None]),
        remaining_visibility_s=_stats([w.end_s-time_s for _, _, w in bindings]),
        right_censored_links=sum(w.right_censored for _, _, w in bindings),
        graph_bridge_count=len(bridges), dynamic_bridge_count=len(dynamic_bridges),
        dynamic_bridge_edges=dynamic_bridges, articulation_nodes=articulations,
        plane_pair_link_counts={"%s-%s" % key: value for key, value in sorted(plane_counts.items())},
        natural_expiry_before_horizon=len(uncensored_ends),
        first_observed_disconnect_s=disconnect_time,
        observed_maintainable_until_s=(disconnect_time if disconnect_time is not None else max(ends)),
        maintainability_right_censored=(disconnect_time is None and any(w.right_censored for _, _, w in bindings)),
        boundary_terminal_occupancy_ratio=occupancy(boundary_nodes),
        interior_terminal_occupancy_ratio=occupancy(interior_nodes),
        bindings=[dict(a=a, b=b, visibility=w.to_dict()) for a, b, w in bindings])

