"""Gate F3 runtime Phase 2B-2 exact same-destination reuse tests."""
from __future__ import annotations

from collections import Counter
import unittest

from dynamic_lisl.commodity import Commodity
from dynamic_lisl.common_router import DeterministicShortestPropagationDelayRouter


class ExactDelay:
    def __init__(self, values):
        self.values=dict(values);self.calls=Counter()
    def __call__(self,edge,time_s):
        self.calls[(tuple(edge),float(time_s))]+=1
        return float(self.values[tuple(edge)])


class CountingRouter(DeterministicShortestPropagationDelayRouter):
    def __init__(self,reuse_destination):
        super().__init__(use_adjacency_reuse=True,
                         use_same_destination_reuse=reuse_destination)
        self.path_search_count=0;self.adjacency_build_count=0
    def _build_adjacency(self,edges):
        self.adjacency_build_count+=1
        return super()._build_adjacency(edges)
    def _path_with_adjacency(self,*args,**kwargs):
        self.path_search_count+=1
        return super()._path_with_adjacency(*args,**kwargs)


def costs(routes,weights):
    return {key:(None if route is None else sum(
        weights[edge] for edge in zip(route,route[1:])))
        for key,route in routes.items()}


class GateF3RuntimePhase2B2Tests(unittest.TestCase):
    def setUp(self):
        self.nodes=('A','B','C','D','X')
        self.edges=(('A','B'),('B','D'),('A','C'),('C','D'),
                    ('B','A'),('D','B'),('C','A'),('D','C'),
                    ('D','A'))
        self.weights={edge:1.0 for edge in self.edges}

    def compare(self,commodities,edges=None,weights=None):
        edges=self.edges if edges is None else tuple(edges)
        weights=self.weights if weights is None else dict(weights)
        legacy=CountingRouter(False);optimized=CountingRouter(True)
        old=legacy.routes_to_destinations(
            self.nodes,commodities,edges,ExactDelay(weights),7.25)
        new=optimized.routes_to_destinations(
            self.nodes,commodities,edges,ExactDelay(weights),7.25)
        self.assertEqual(list(old.items()),list(new.items()))
        self.assertEqual(costs(old,weights),costs(new,weights))
        self.assertEqual(legacy.adjacency_build_count,1)
        self.assertEqual(optimized.adjacency_build_count,1)
        return old,legacy,optimized

    def test_shared_destination_all_nodes_tie_none_directed_and_source_destination(self):
        commodities=(Commodity('f0','A','D'),Commodity('f1','C','D'),
                     Commodity('f2','D','A'),Commodity('f3','A','X'))
        routes,legacy,optimized=self.compare(commodities)
        for node in self.nodes:
            self.assertEqual(routes[(node,'f0')],routes[(node,'f1')])
        self.assertEqual(routes[('A','f0')],('A','B','D'))
        self.assertIsNone(routes[('A','f3')])
        self.assertEqual(routes[('D','f0')],('D',))
        self.assertEqual(routes[('A','f2')],('A',))
        self.assertEqual(legacy.path_search_count,20)
        self.assertEqual(optimized.path_search_count,15)

    def test_mixed_repeated_unique_destinations_and_exact_insertion_order(self):
        commodities=(Commodity('z2','A','D'),Commodity('a0','B','A'),
                     Commodity('a1','C','A'),Commodity('m1','A','X'))
        routes,legacy,optimized=self.compare(commodities)
        expected_keys=[(node,commodity.commodity_id)
                       for commodity in sorted(commodities)
                       for node in sorted(self.nodes)]
        self.assertEqual(list(routes),expected_keys)
        self.assertEqual(legacy.path_search_count,20)
        self.assertEqual(optimized.path_search_count,15)

    def test_repeated_determinism_and_topology_change(self):
        commodities=(Commodity('f0','A','D'),Commodity('f1','C','D'))
        first,_,first_opt=self.compare(commodities)
        second,_,second_opt=self.compare(commodities)
        self.assertEqual(list(first.items()),list(second.items()))
        self.assertEqual(first_opt.path_search_count,5)
        self.assertEqual(second_opt.path_search_count,5)
        changed=tuple(edge for edge in self.edges
                      if edge not in (('A','B'),('B','D')))
        changed_weights={edge:self.weights[edge] for edge in changed}
        changed_routes,_,changed_opt=self.compare(
            commodities,changed,changed_weights)
        self.assertEqual(changed_routes[('A','f0')],('A','C','D'))
        self.assertEqual(changed_opt.path_search_count,5)


if __name__=='__main__':unittest.main()
