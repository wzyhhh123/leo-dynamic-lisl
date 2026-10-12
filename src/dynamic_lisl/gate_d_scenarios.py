"""Frozen-reference helpers for Gate D1 validation and the 160-satellite pilot."""
from __future__ import annotations

from collections import Counter
import numpy as np

from .traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment


SPEED_OF_LIGHT_KM_S = 299792.458


def reference_graph(reference):
    fixed = {tuple(sorted(edge)) for edge in reference["fixed_edges"]}
    dynamic = {tuple(sorted((binding["a"][0], binding["b"][0])))
               for binding in reference["bindings"]}
    edges = tuple(sorted(fixed | dynamic))
    nodes = tuple(sorted({node for edge in edges for node in edge}))
    return nodes, edges, tuple(sorted(dynamic))


class Sgp4EdgeDelayProvider:
    """Distance/c using a common-time native-TEME SGP4 state, cached by time."""
    def __init__(self, model, nodes):
        self.model = model
        self.nodes = tuple(nodes)
        self.index = {node: index for index, node in enumerate(self.nodes)}
        self.cache = {}

    def __call__(self, edge, time_s):
        key = round(float(time_s), 12)
        if key not in self.cache:
            positions, _ = self.model.state([key], self.nodes)
            self.cache[key] = positions[0]
        positions = self.cache[key]
        distance = float(np.linalg.norm(
            positions[self.index[edge[1]]] - positions[self.index[edge[0]]]))
        return distance/SPEED_OF_LIGHT_KM_S

    def distance_km(self, edge, time_s):
        return self(edge, time_s)*SPEED_OF_LIGHT_KM_S


def normalized_profile(commodity_ids, rule):
    boosted = set(rule.get("boosted_ids", ()))
    weights = {key: (float(rule.get("boosted_weight", rule["default"]))
                     if key in boosted else float(rule["default"]))
               for key in commodity_ids}
    total = sum(weights.values())
    if total <= 0.0:
        raise ValueError("EMPTY_SPATIAL_PROFILE")
    return {key: value/total for key, value in weights.items()}


def pilot_trace(contract, commodity_ids, alpha_star_bit_s):
    rho = float(contract["pilot_rho"])
    segments = []
    profiles = {}
    for phase in contract["phases"]:
        profile = normalized_profile(
            commodity_ids, contract["profile_weights"][phase["label"]])
        profiles[phase["label"]] = profile
        rates = {key: rho*alpha_star_bit_s*profile[key] for key in commodity_ids}
        segments.append(TrafficSegment(float(phase["start_s"]),
                                       float(phase["end_s"]), rates,
                                       phase["label"]))
    return PiecewiseConstantTrafficTrace(commodity_ids, segments), profiles


def route_diversity(result, commodities):
    source_routes = {item.commodity_id:
                     result["routes"][item.source + "|" + item.commodity_id]
                     for item in commodities}
    hops = {key: (len(route)-1 if route is not None else None)
            for key, route in source_routes.items()}
    edge_use = Counter()
    for route in source_routes.values():
        if route is None:
            continue
        for a, b in zip(route[:-1], route[1:]):
            edge_use[a + "->" + b] += 1
    hop_values = [value for value in hops.values() if value is not None]
    return {
        "all_OD_have_path": all(route is not None for route in source_routes.values()),
        "source_routes": source_routes,
        "hop_count_by_commodity": hops,
        "distinct_hop_counts": sorted(set(hop_values)),
        "minimum_hops": min(hop_values) if hop_values else None,
        "maximum_hops": max(hop_values) if hop_values else None,
        "mean_hops": sum(hop_values)/len(hop_values) if hop_values else None,
        "shared_route_edges": dict(sorted((edge, count) for edge, count in edge_use.items()
                                          if count > 1)),
        "maximum_OD_overlap_on_one_directed_edge": max(edge_use.values(), default=0),
    }
