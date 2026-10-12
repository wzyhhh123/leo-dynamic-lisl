"""Traffic-blind K0/K1 solver infrastructure and explicit bounded certificates.

Maximum matching is exact general-graph terminal matching. Satellite-pair and
regime constraints belong to the separate topology builder, not that relaxation.
The deterministic exact builder uses explicit search caps, returns UNKNOWN on
exhaustion, and never promotes an incumbent to an optimal solution/K selection.
No scientific K/thresholds/default compute budgets are frozen here.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import itertools
import math
import time

import networkx as nx

from ..terminal_executor import pair
from ..transition_profiler import graph_components
from .joint_action import canonical_sha256


class ObservedPhysicalLayer:
    """Cost-only read-only delegation; no feasibility shortcuts or caching."""
    def __init__(self,physical_layer):
        self.physical_layer=physical_layer
        self.catalog=physical_layer.catalog
        self.observations=[]

    def evaluate(self,*args,**kwargs):
        start=time.perf_counter()
        result=self.physical_layer.evaluate(*args,**kwargs)
        executor,a,b=args[:3]
        self.observations.append({'index':len(self.observations),
            'time_s':executor.now,'endpoints':pair(a,b),
            'wall_s':time.perf_counter()-start,'accepted':result['accepted'],
            'reason':result['reason']})
        return result


@dataclass(frozen=True)
class StructuralEdge:
    endpoints: tuple
    plane_pair: tuple
    ready_time_s: float
    observed_end_s: float
    right_censored: bool
    observation_cutoff_s: float

    def __post_init__(self):
        object.__setattr__(self, "endpoints", pair(*self.endpoints))
        object.__setattr__(self, "plane_pair", tuple(sorted(self.plane_pair)))
        if self.plane_pair[0] == self.plane_pair[1]:
            raise ValueError("INTER_PLANE_EDGE_REQUIRED")
        if not all(math.isfinite(v) for v in (self.ready_time_s, self.observed_end_s, self.observation_cutoff_s)):
            raise ValueError("FINITE_PHYSICAL_TIMES_REQUIRED")
        if not self.ready_time_s < self.observed_end_s or self.observed_end_s > self.observation_cutoff_s:
            raise ValueError("READY_WINDOW_COVERAGE_INVALID")

    @property
    def usable_within_horizon_s(self):
        return max(0.0, min(self.observed_end_s, self.observation_cutoff_s) - self.ready_time_s)

    @property
    def satellite_pair(self):
        return tuple(e[0] for e in self.endpoints)

    def to_dict(self):
        return {"endpoints": self.endpoints, "plane_pair": self.plane_pair,
                "ready_time_s": self.ready_time_s, "observed_end_s": self.observed_end_s,
                "physical_end_s": None if self.right_censored else self.observed_end_s,
                "observation_cutoff_s": self.observation_cutoff_s,
                "censor_status": "RIGHT_CENSORED_AT_600" if self.right_censored and self.observation_cutoff_s == 600 else (
                    "RIGHT_CENSORED_AT_OBSERVATION_END" if self.right_censored else "NATURAL_END_KNOWN"),
                "L_usable_within_horizon_s": self.usable_within_horizon_s}


def exact_terminal_maximum_matching(edges):
    """Exact cardinality + canonical lexical matching via integer blossom weights.

    Different physical terminal pairs of one satellite pair are retained in this
    relaxation. Do not equate this upper bound with feasible Z_K capacity.
    """
    ordered = tuple(sorted({e.endpoints if isinstance(e, StructuralEdge) else pair(*e) for e in edges}))
    graph = nx.Graph()
    for i, edge in enumerate(ordered):
        # Superincreasing integers provide exact canonical tie resolution.
        graph.add_edge(*edge, weight=1 << (len(ordered)-i-1))
    selected = tuple(sorted(pair(*e) for e in nx.max_weight_matching(graph, maxcardinality=True)))
    return {"status": "EXACT", "cardinality": len(selected), "bindings": selected,
            "scope": "terminal-degree-only maximum cardinality relaxation",
            "parallel_satellite_pairs_enforced": False,
            "matching_sha256": canonical_sha256(selected)}


def legal_edge_inventory(executor, physical_layer, plane_by_satellite, *,
                         retarget_a_s, retarget_b_s, acquisition_s, observation_end_s):
    """Uncapped idle/root Gate C catalog screening; no Q/I/J/controller inputs."""
    rows, rejected = [], []
    for w in physical_layer.catalog.terminal_pair_candidates(executor.now, executor.satellite_ids):
        a,b = pair(w.endpoint_a,w.endpoint_b)
        if plane_by_satellite[a[0]] == plane_by_satellite[b[0]]:
            continue
        p=physical_layer.evaluate(executor,a,b,retarget_a=retarget_a_s,
                                  retarget_b=retarget_b_s,acquisition=acquisition_s)
        if not p["accepted"]:
            rejected.append({"endpoints":(a,b),"reason":p["reason"]})
            continue
        g=p["geometry"]
        rows.append(StructuralEdge((a,b),(plane_by_satellite[a[0]],plane_by_satellite[b[0]]),
                                   g["ready_time"],w.end_s,w.right_censored,observation_end_s))
    return {"edges":tuple(sorted(rows,key=lambda e:e.endpoints)),"rejected":rejected,
            "uncapped":True,"candidate_inventory_sha256":canonical_sha256([e.to_dict() for e in sorted(rows,key=lambda e:e.endpoints)])}


def topology_objective(selected, all_planes):
    counts={p:0 for p in all_planes}
    for e in selected:
        for p in e.plane_pair:counts[p]+=1
    # Exact rational interpretation of the already-computed floats: no time
    # quantization/scaled rounding can change priorities3/4 or canonical ties.
    lifetimes=[Fraction.from_float(e.usable_within_horizon_s) for e in selected]
    total=sum(lifetimes,Fraction())
    minimum=min(lifetimes,default=Fraction())
    return (max(counts.values())-min(counts.values()),
            -len({e.plane_pair for e in selected}), -total, -minimum,
            tuple(e.endpoints for e in selected))


def deterministic_lexicographic_topology(edges, target_K, all_planes, *,
                                         max_search_nodes, wall_timeout_s):
    """Exact capped reference builder, useful for tiny oracle/cost assessment.

    An exhaustive proof is required before status EXACT; reaching a cap returns
    UNKNOWN even with a feasible incumbent. No main-scale deployment claim.
    """
    if type(target_K) is not int or target_K < 0:
        raise ValueError("INVALID_EXACT_K")
    if type(max_search_nodes) is not int or max_search_nodes < 1 or not math.isfinite(wall_timeout_s) or wall_timeout_s<=0:
        raise ValueError("EXPLICIT_SEARCH_BUDGET_REQUIRED")
    edges=tuple(sorted(edges,key=lambda e:e.endpoints))
    if len({e.endpoints for e in edges}) != len(edges):
        raise ValueError("DUPLICATE_PHYSICAL_EDGE")
    planes=tuple(sorted(set(all_planes)))
    if not planes or any(not set(e.plane_pair)<=set(planes) for e in edges):
        raise ValueError("PLANE_MAPPING_MISMATCH")
    start=time.perf_counter();searched=0;best=None;best_key=None;exhausted=None

    stack=[(0,(),frozenset(),frozenset())]
    while stack:
        if searched>=max_search_nodes:
            exhausted="SEARCH_NODE_BUDGET";break
        if time.perf_counter()-start>=wall_timeout_s:
            exhausted="WALL_TIMEOUT";break
        index,chosen,terminals,satpairs=stack.pop()
        searched+=1
        if len(chosen)==target_K:
            key=topology_objective(chosen,planes)
            if best_key is None or key<best_key:best_key=key;best=chosen
            continue
        if len(chosen)+len(edges)-index<target_K:continue
        if index>=len(edges):continue
        e=edges[index]
        stack.append((index+1,chosen,terminals,satpairs))
        if not set(e.endpoints)&terminals and e.satellite_pair not in satpairs:
            stack.append((index+1,chosen+(e,),terminals|frozenset(e.endpoints),satpairs|{e.satellite_pair}))
    status="UNKNOWN" if exhausted else ("EXACT" if best is not None else "EXACT_INFEASIBLE")
    document={"status":status,"target_K":target_K,"nodes_visited":searched,
              "budget_reason":exhausted,"wall_s":time.perf_counter()-start,
              "bindings":tuple(e.endpoints for e in best) if best is not None else None,
              "optimality_certified":exhausted is None,
              "incumbent_not_authorized_for_K1":bool(exhausted),
              "solver_role":"EXACT_BOUNDED_REFERENCE; MAIN_SCALE_COST_UNPROVEN"}
    if best_key is not None:
        document["lexicographic_objective"]=[best_key[0],best_key[1],str(best_key[2]),str(best_key[3]),best_key[4]]
    document["structural_sha256"]=canonical_sha256({k:v for k,v in document.items() if k!="wall_s"})
    return document


def graph_structure(nodes, fixed_edges, bindings):
    dynamic={tuple(sorted(e[0] for e in b)) for b in bindings}
    graph=nx.Graph();graph.add_nodes_from(nodes);graph.add_edges_from(fixed_edges);graph.add_edges_from(dynamic)
    bridges={tuple(sorted(e)) for e in nx.bridges(graph)}
    return {"connected":nx.is_connected(graph),"components":graph_components(nodes,list(graph.edges())),
            "dynamic_edges":sorted(dynamic),"dynamic_bridge_edges":sorted(dynamic&bridges),
            "dynamic_nonbridge_count":len(dynamic-bridges),
            "terminal_occupancy_fraction":len(bindings)/len(nodes)}


def exact_batch_compatibility(action_factory, members, validator, executor, *, max_members, max_evaluations):
    """Tiny uncapped witness/oracle; capped main search is UNKNOWN, never negative proof.

    Resource-independent cardinality and joint-safe cardinality differ. These
    diagnostics never choose K or inspect any traffic/service/performance state.
    """
    members=tuple(members)
    if max_members<1 or max_evaluations<1:
        raise ValueError("EXPLICIT_DIAGNOSTIC_BUDGET_REQUIRED")
    tested=0;legal=[];resource=[];rejected=[];truncated=False
    for size in range(1,min(max_members,len(members))+1):
        for subset in itertools.combinations(members,size):
            if tested>=max_evaluations:
                truncated=True;break
            tested+=1
            physical_validator=getattr(validator,"physical_validator",validator)
            physical=physical_validator.evaluate(executor,action_factory(subset))
            if physical.accepted:
                resource.append(tuple(m.member_id for m in subset))
            p=validator.evaluate(executor,action_factory(subset))
            if p.accepted:legal.append(tuple(m.member_id for m in subset))
            else:rejected.append({"member_ids":tuple(m.member_id for m in subset),"reason":p.reason})
        if truncated:break
    complete=not truncated and max_members>=len(members)
    return {"status":"EXACT" if complete else "UNKNOWN_MAXIMUM",
            "all_subsets_through_size_scanned":not truncated,"scanned_max_size":max_members,
            "max_resource_witness_size":max(map(len,resource),default=0),
            "max_joint_safe_witness_size":max(map(len,legal),default=0),
            "joint_safe_witnesses":legal,"rejections":rejected,"evaluations":tested,
            "K_selection_used":False,"role":"DIAGNOSTIC_ONLY",
            "maximum_scope":"caller-declared action-size bound; a larger uncapped inventory requires a separate exact proof"}
