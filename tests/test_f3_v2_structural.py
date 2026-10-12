"""Exact matching/topology tiny oracles with no production K selection."""
import itertools
import random
import unittest

from dynamic_lisl.terminal_executor import pair
from dynamic_lisl.f3_v2.structural import (
    StructuralEdge, exact_terminal_maximum_matching, deterministic_lexicographic_topology,
    topology_objective, graph_structure, exact_batch_compatibility)
from test_f3_v2_batch_executor import fixture
from dataclasses import replace


def brute_matching(edges):
    valid=[]
    for n in range(len(edges)+1):
        for subset in itertools.combinations(sorted(edges),n):
            ends=[v for e in subset for v in e]
            if len(set(ends))==len(ends):valid.append(subset)
    return min(valid,key=lambda x:(-len(x),x))


def edges():
    nodes=[("A","D1"),("A","D2"),("B","D1"),("B","D2"),("C","D1"),("D","D1")]
    planes={"A":0,"B":1,"C":2,"D":3}
    return [StructuralEdge(pair(a,b),tuple(sorted((planes[a[0]],planes[b[0]]))),
                           2.,10.+i,False,30.)
            for i,(a,b) in enumerate(itertools.combinations(nodes,2)) if a[0]!=b[0]]


class GateKInfrastructureTests(unittest.TestCase):
    def test_general_graph_triangle_blossom_not_bipartite(self):
        es=[(("A","D1"),("B","D1")),(("B","D1"),("C","D1")),(("A","D1"),("C","D1"))]
        result=exact_terminal_maximum_matching(es)
        self.assertEqual(result["cardinality"],1)
        self.assertEqual(result["bindings"],brute_matching(es))

    def test_exact_matching_against_exhaustive_small_graphs(self):
        rng=random.Random(1108)
        all_edges=[e.endpoints for e in edges()]
        for _ in range(30):
            subset=rng.sample(all_edges,rng.randint(0,min(8,len(all_edges))))
            r=exact_terminal_maximum_matching(subset)
            self.assertEqual(r["bindings"],brute_matching(subset))
            self.assertEqual(r["status"],"EXACT")

    def test_matching_replay_shuffled_order_duplicates(self):
        es=edges()
        self.assertEqual(exact_terminal_maximum_matching(es),exact_terminal_maximum_matching(es[::-1]+es))

    def test_terminal_matching_parallel_pair_is_only_relaxation(self):
        es=[StructuralEdge((("A","D1"),("B","D1")),(0,1),2,30,False,30),
            StructuralEdge((("A","D2"),("B","D2")),(0,1),2,30,False,30)]
        self.assertEqual(exact_terminal_maximum_matching(es)["cardinality"],2)
        r=deterministic_lexicographic_topology(es,2,(0,1),max_search_nodes=100,wall_timeout_s=1)
        self.assertEqual(r["status"],"EXACT_INFEASIBLE")

    def test_lex_topology_matches_independent_exhaustive_oracle(self):
        es=edges();planes=(0,1,2,3)
        for k in (0,1,2,3,4):
            valid=[]
            for s in itertools.combinations(es,k):
                terminals=[v for e in s for v in e.endpoints]
                pairs=[e.satellite_pair for e in s]
                if len(set(terminals))==len(terminals) and len(set(pairs))==len(pairs):
                    valid.append(tuple(sorted(s,key=lambda e:e.endpoints)))
            oracle=min(valid,key=lambda s:topology_objective(s,planes)) if valid else None
            result=deterministic_lexicographic_topology(es,k,planes,max_search_nodes=100000,wall_timeout_s=5)
            self.assertEqual(result["bindings"],None if oracle is None else tuple(e.endpoints for e in oracle))
            self.assertEqual(result["status"],"EXACT" if oracle is not None else "EXACT_INFEASIBLE")

    def test_budget_exhaustion_unknown_never_optimal(self):
        r=deterministic_lexicographic_topology(edges(),2,(0,1,2,3),max_search_nodes=1,wall_timeout_s=1)
        self.assertEqual(r["status"],"UNKNOWN")
        self.assertFalse(r["optimality_certified"])
        self.assertTrue(r["incumbent_not_authorized_for_K1"])

    def test_lifetime_right_censor_not_physical_expiry(self):
        e=StructuralEdge((("A","D1"),("B","D1")),(0,1),572,600,True,600)
        r=e.to_dict()
        self.assertEqual(r["L_usable_within_horizon_s"],28)
        self.assertEqual(r["censor_status"],"RIGHT_CENSORED_AT_600")
        self.assertIsNone(r["physical_end_s"])
        with self.assertRaises(ValueError):replace(e,ready_time_s=600)

    def test_structure_counts_bridges_occupancy(self):
        r=graph_structure(("A","B","C","D"),(("A","B"),("C","D")),
                          ((("B","D1"),("C","D1")),))
        self.assertTrue(r["connected"])
        self.assertEqual(r["dynamic_bridge_edges"],[("B","C")])
        self.assertEqual(r["terminal_occupancy_fraction"],.25)

    def test_batch_compatibility_exact_and_unknown(self):
        ex,a,v,_=fixture(("BBM","MBB","BBM"))
        factory=lambda ms:replace(a,members=ms)
        r=exact_batch_compatibility(factory,a.members,v,ex,max_members=3,max_evaluations=7)
        self.assertEqual(r["status"],"EXACT")
        self.assertEqual(r["max_joint_safe_witness_size"],3)
        self.assertEqual(r["max_resource_witness_size"],3)
        r=exact_batch_compatibility(factory,a.members,v,ex,max_members=3,max_evaluations=2)
        self.assertEqual(r["status"],"UNKNOWN_MAXIMUM")
        self.assertFalse(r["K_selection_used"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
