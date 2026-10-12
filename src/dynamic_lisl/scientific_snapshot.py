"""Gate F1 frozen V_v2 current-state scientific snapshot evaluator.

This module does not advance simulation time and does not perform rollout.  It
reuses the frozen common router and the existing work-conserving fair-share
allocator used by D1/D2.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
import math

from .common_router import ExactEvaluationEdgeDelayMemo
from .service_scheduler import equal_weight_fair_share


INPUT_TOLERANCE_BIT_S = 1e-15


def _undirected(edges):
    return tuple(sorted({tuple(sorted(tuple(edge))) for edge in edges}))


def _directed(edges):
    return tuple(sorted((a, b) for edge in _undirected(edges)
                        for a, b in (edge, edge[::-1])))


@dataclass(frozen=True)
class CommoditySnapshot:
    commodity_id: str
    unfinished_bits: float
    source_route: tuple | None
    propagation_cost_s: float | None
    current_demand_nodes: tuple
    current_allocations_bit_s: tuple
    R_f_snap_bit_s: float | None
    Psi_f_bit_s: float | None
    value_bit_s: float
    invalid_reason: str | None = None

    def to_dict(self):
        return {
            "commodity_id": self.commodity_id,
            "unfinished_bits": self.unfinished_bits,
            "source_route": (list(self.source_route)
                             if self.source_route is not None else None),
            "propagation_cost_s": self.propagation_cost_s,
            "current_demand_nodes": list(self.current_demand_nodes),
            "current_allocations_bit_s": {
                node: value for node, value in self.current_allocations_bit_s},
            "R_f_snap_bit_s": self.R_f_snap_bit_s,
            "Psi_f_bit_s": self.Psi_f_bit_s,
            "value_bit_s": (self.value_bit_s if math.isfinite(self.value_bit_s)
                            else "+infinity"),
            "invalid_reason": self.invalid_reason,
        }


@dataclass(frozen=True)
class SnapshotEvaluation:
    topology_edges: tuple
    value_bit_s: float
    total_unfinished_bits: float
    commodities: tuple
    allocator: str = "dynamic_lisl.service_scheduler.equal_weight_fair_share"
    information_class: str = "CURRENT_STATE_ONLY"

    @property
    def finite(self):
        return math.isfinite(self.value_bit_s)

    def to_dict(self):
        return {
            "topology_edges": [list(edge) for edge in self.topology_edges],
            "value_bit_s": (self.value_bit_s if self.finite else "+infinity"),
            "total_unfinished_bits": self.total_unfinished_bits,
            "commodities": [row.to_dict() for row in self.commodities],
            "allocator": self.allocator,
            "information_class": self.information_class,
            "advance_simulation_time": False,
            "multi_step_rollout": False,
        }


class ScientificSnapshotEvaluator:
    """Evaluate frozen V_v2 from one live engine's current state only."""

    canonical_semantics = "GATE_F1_SCORING_HUMAN_FREEZE_V2"

    def __init__(self, engine, use_edge_delay_memoization=True):
        self.engine = engine
        self.use_edge_delay_memoization = bool(use_edge_delay_memoization)

    @classmethod
    def legacy_no_cache_reference(cls, engine):
        """Test/engineering reference for pre-Phase-2A snapshot routing."""
        return cls(engine, use_edge_delay_memoization=False)

    @property
    def now(self):
        return float(self.engine.now)

    def hold_edges(self):
        return _undirected(self.engine.graph["admit_edges"])

    def candidate_edges(self, proposal):
        edges = set(self.hold_edges())
        old_edge = tuple(proposal.get("old_edge") or ())
        new_edge = tuple(proposal.get("new_edge") or ())
        if old_edge:
            if len(old_edge) != 2:
                raise ValueError("SCORING_CANDIDATE_OLD_EDGE_INVALID")
            edges.discard(tuple(sorted(old_edge)))
        if len(new_edge) != 2:
            raise ValueError("SCORING_CANDIDATE_NEW_EDGE_INVALID")
        edges.add(tuple(sorted(new_edge)))
        return tuple(sorted(edges))

    def evaluate_hold(self):
        return self.evaluate_edges(self.hold_edges())

    def evaluate_candidate(self, proposal):
        return self.evaluate_edges(self.candidate_edges(proposal))

    def evaluate_proposal_set(self, proposal_set):
        hold = self.evaluate_hold()
        candidates = tuple((row["proposal_id"], self.evaluate_candidate(row))
                           for row in proposal_set["proposals"])
        return hold, candidates

    def evaluate_edges(self, undirected_edges):
        """Return V_v2 without advancing the engine or reading future state."""
        engine = self.engine
        time_before = float(engine.now)
        topology = _undirected(undirected_edges)
        directed = _directed(topology)
        delay = (ExactEvaluationEdgeDelayMemo(engine.delay)
                 if self.use_edge_delay_memoization else engine.delay)
        routes = engine.router.routes_to_destinations(
            engine.nodes, engine.commodities, directed, delay, engine.now)
        external = engine.trace.rate_at(engine.now)
        # Reuse the D2 local-input construction exactly.  The returned values
        # contain current source lambda and current downstream propagation rates.
        inputs = engine._inputs(external)

        unfinished = {
            commodity.commodity_id:
                engine.queues.total(commodity.commodity_id)
                + engine.in_flight.total(commodity.commodity_id)
            for commodity in engine.commodities
        }
        total_unfinished = math.fsum(unfinished.values())
        demands_by_edge = defaultdict(dict)
        demand_node_by_edge_key = {}
        demand_nodes = defaultdict(list)
        invalid = {}

        for commodity in engine.commodities:
            commodity_id = commodity.commodity_id
            if unfinished[commodity_id] <= 0.0:
                continue
            if routes[(commodity.source, commodity_id)] is None:
                invalid[commodity_id] = "NO_SOURCE_TO_DESTINATION_ROUTE"
                continue
            for node in engine.nodes:
                if node == commodity.destination:
                    continue
                queue_bits = engine.queues.get(node, commodity_id)
                input_rate = inputs[(node, commodity_id)]
                if queue_bits > engine.state_tol:
                    demand = math.inf
                elif input_rate > INPUT_TOLERANCE_BIT_S:
                    demand = input_rate
                else:
                    demand = 0.0
                if demand <= INPUT_TOLERANCE_BIT_S:
                    continue
                route = routes[(node, commodity_id)]
                if route is None or len(route) < 2:
                    invalid[commodity_id] = (
                        "POSITIVE_LOCAL_DEMAND_WITHOUT_LEGAL_ADMITTED_NEXT_HOP")
                    continue
                edge = (node, route[1])
                demands_by_edge[edge][commodity_id] = demand
                demand_node_by_edge_key[(edge, commodity_id)] = node
                demand_nodes[commodity_id].append(node)

        allocations = {}
        for edge, demands in sorted(demands_by_edge.items()):
            allocated = equal_weight_fair_share(engine.capacity_bit_s, demands)
            for commodity_id, rate in allocated.items():
                node = demand_node_by_edge_key[(edge, commodity_id)]
                allocations[(node, commodity_id)] = float(rate)

        rows = []
        for commodity in engine.commodities:
            commodity_id = commodity.commodity_id
            n_f = unfinished[commodity_id]
            if n_f <= 0.0:
                continue
            source_route = routes[(commodity.source, commodity_id)]
            if commodity_id in invalid:
                rows.append(CommoditySnapshot(
                    commodity_id, n_f, source_route, None,
                    tuple(sorted(demand_nodes[commodity_id])), (), None, None,
                    math.inf, invalid[commodity_id]))
                continue
            propagation = math.fsum(float(delay(edge, engine.now))
                                    for edge in zip(source_route, source_route[1:]))
            nodes = tuple(sorted(demand_nodes[commodity_id]))
            local_allocations = tuple(
                (node, allocations.get((node, commodity_id), 0.0))
                for node in nodes)
            if any(value <= 0.0 for _, value in local_allocations):
                rows.append(CommoditySnapshot(
                    commodity_id, n_f, source_route, propagation, nodes,
                    local_allocations, None, None, math.inf,
                    "NONPOSITIVE_ALLOCATION_FOR_POSITIVE_LOCAL_DEMAND"))
                continue
            if nodes:
                r_snap = min(value for _, value in local_allocations)
                psi = n_f * n_f / (2.0 * r_snap)
            else:
                r_snap = None
                psi = 0.0
            value = n_f * propagation + psi
            rows.append(CommoditySnapshot(
                commodity_id, n_f, source_route, propagation, nodes,
                local_allocations, r_snap, psi, value))

        total_value = (math.inf if any(not math.isfinite(row.value_bit_s)
                                       for row in rows)
                       else math.fsum(row.value_bit_s for row in rows))
        if float(engine.now) != time_before:
            raise AssertionError("SCIENTIFIC_SNAPSHOT_ADVANCED_SIMULATION_TIME")
        return SnapshotEvaluation(topology, total_value, total_unfinished,
                                  tuple(rows))
