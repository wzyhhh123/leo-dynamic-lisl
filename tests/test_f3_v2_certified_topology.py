"""Independent exhaustive proof checks for the analytic-bound exact fast path."""
from dataclasses import replace
import itertools
import random
import unittest
from test_f3_v2_structural import edges
from dynamic_lisl.f3_v2.structural import StructuralEdge,topology_objective
from dynamic_lisl.f3_v2.certified_topology import certified_bound_topology


PLANES={'A':0,'B':1,'C':2,'D':3}


def oracle(es,k,planes):
    legal=[]
    for subset in itertools.combinations(sorted(es,key=lambda e:e.endpoints),k):
        terminals=[t for e in subset for t in e.endpoints];pairs=[e.satellite_pair for e in subset]
        if len(set(terminals))==len(terminals) and len(set(pairs))==len(pairs):legal.append(subset)
    return min(legal,key=lambda s:topology_objective(s,planes)) if legal else None


class CertifiedTopologyTests(unittest.TestCase):
    def solve(self,es,k,planes=(0,1,2,3),mapping=PLANES,**kwargs):
        return certified_bound_topology(es,k,planes,plane_by_satellite=mapping,
            max_search_nodes=kwargs.get('max_search_nodes',100000),wall_timeout_s=2)

    def test_uniform_exact_tier_against_independent_full_oracle(self):
        es=[replace(e,observed_end_s=30) for e in edges()]
        exact_cases=0
        for k in range(4):
            expected=oracle(es,k,(0,1,2,3));result=self.solve(es,k)
            if result['status']=='EXACT':
                exact_cases+=1
                self.assertEqual(result['bindings'],tuple(e.endpoints for e in expected))
                self.assertTrue(result['optimality_certified'])
            else:self.assertFalse(result['optimality_certified'])
        self.assertGreaterEqual(exact_cases,3)

    def test_random_uniform_subgraphs_never_false_certify(self):
        rng=random.Random(1011);es=[replace(e,observed_end_s=30) for e in edges()]
        for _ in range(50):
            subset=rng.sample(es,rng.randint(0,min(9,len(es))));k=rng.randrange(4)
            result=self.solve(subset,k);expected=oracle(subset,k,(0,1,2,3))
            if result['status']=='EXACT':
                self.assertIsNotNone(expected)
                self.assertEqual(result['bindings'],tuple(e.endpoints for e in expected))
            else:self.assertIsNone(result['bindings'])

    def test_mixed_lifetimes_not_attainable_does_not_claim_infeasible(self):
        result=self.solve(edges(),2)
        self.assertEqual(result['status'],'UNKNOWN');self.assertFalse(result['optimality_certified'])
        self.assertIsNotNone(oracle(edges(),2,(0,1,2,3)))

    def test_parallel_satellite_pair_is_excluded_even_with_spare_terminals(self):
        es=[StructuralEdge((('A','D1'),('B','D1')),(0,1),2,30,False,30),
            StructuralEdge((('A','D2'),('B','D2')),(0,1),2,30,False,30)]
        self.assertEqual(self.solve(es,2,(0,1),{'A':0,'B':1})['status'],'UNKNOWN')

    def test_exact_replay_and_plane_mapping_not_based_on_satellite_names(self):
        es=[replace(e,observed_end_s=30) for e in edges()]
        self.assertEqual({k:v for k,v in self.solve(es,2).items() if k!='wall_s'},
            {k:v for k,v in self.solve(es[::-1],2).items() if k!='wall_s'})
        swapped={name:3-p for name,p in PLANES.items()}
        changed=[replace(e,plane_pair=tuple(swapped[t[0]] for t in e.endpoints)) for e in es]
        result=self.solve(changed,2,mapping=swapped)
        self.assertEqual(result['bindings'],tuple(e.endpoints for e in oracle(changed,2,(0,1,2,3))))
        with self.assertRaisesRegex(ValueError,'ENDPOINT_PLANE_MAPPING_MISMATCH'):self.solve(changed,2)

    def test_node_cap_never_returns_incumbent_as_exact(self):
        es=[replace(e,observed_end_s=30) for e in edges()]
        result=self.solve(es,2,max_search_nodes=1)
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['budget_reason'],'SEARCH_NODE_BUDGET')
        self.assertIsNone(result['bindings'])


if __name__=='__main__':unittest.main(verbosity=2)
