"""Exact analytic-bound certificate fast path for the frozen lexicographic rule.

Only uniform maximum-lifetime edges can attain the universal total-lifetime
bound. If a canonical-first topology also attains the plane-balance and coverage
bounds, all five priorities are proved globally optimal. Failure to find this
special certificate is UNKNOWN, never a claim of infeasibility or a relaxed K.
"""
from fractions import Fraction
import math
import time
from .structural import topology_objective
from .joint_action import canonical_sha256


def population_count(value):
    # Existing pytorch environment predates int.bit_count. Exact integer bits,
    # no dependency installation or floating approximation is needed.
    return bin(value).count('1')


def certified_bound_topology(edges,target_K,all_planes,*,plane_by_satellite,max_search_nodes,wall_timeout_s):
    if type(target_K) is not int or target_K<0:raise ValueError('INVALID_EXACT_K')
    if type(max_search_nodes) is not int or max_search_nodes<1 or not math.isfinite(wall_timeout_s) or wall_timeout_s<=0:
        raise ValueError('EXPLICIT_SEARCH_BUDGET_REQUIRED')
    edges=tuple(sorted(edges,key=lambda e:e.endpoints));planes=tuple(sorted(set(all_planes)))
    if not planes or any(not set(e.plane_pair)<=set(planes) for e in edges):raise ValueError('PLANE_MAPPING_MISMATCH')
    if len({e.endpoints for e in edges})!=len(edges):raise ValueError('DUPLICATE_PHYSICAL_EDGE')
    if any(t[0] not in plane_by_satellite for e in edges for t in e.endpoints) or any(
        tuple(sorted(plane_by_satellite[t[0]] for t in e.endpoints))!=e.plane_pair for e in edges):
        raise ValueError('ENDPOINT_PLANE_MAPPING_MISMATCH')
    started=time.perf_counter();visited=0;reason=None;solution=None;pruned={}
    life={e.endpoints:Fraction.from_float(e.usable_within_horizon_s) for e in edges}
    maximum=max(life.values(),default=Fraction())
    eligible=tuple(e for e in edges if life[e.endpoints]==maximum)
    plane_pairs=tuple(sorted({e.plane_pair for e in edges}))
    coverage_bound=min(target_K,len(plane_pairs));pair_index={p:i for i,p in enumerate(plane_pairs)}
    lower=(2*target_K)//len(planes);upper=lower+bool((2*target_K)%len(planes))
    range_bound=upper-lower;plane_index={p:i for i,p in enumerate(planes)}
    bounds={'plane_endpoint_range_lower':int(range_bound),'plane_pair_coverage_upper':coverage_bound,
        'total_usable_lifetime_upper_exact':str(target_K*maximum),
        'minimum_usable_lifetime_upper_exact':str(maximum if target_K else Fraction()),
        'uniform_maximum_edge_count':len(eligible),
        'all_original_edges_retained_in_global_bounds':True}
    if target_K==0:solution=()
    elif len(eligible)<target_K or len({e.plane_pair for e in eligible})<coverage_bound:
        reason='ANALYTIC_BOUND_TIER_NOT_APPLICABLE'
    else:
        terminals=tuple(sorted({t for e in eligible for t in e.endpoints}))
        terminal_index={t:i for i,t in enumerate(terminals)}
        metadata=[]
        for e in eligible:
            a,b=e.plane_pair
            metadata.append(((1<<terminal_index[e.endpoints[0]])|(1<<terminal_index[e.endpoints[1]]),
                plane_index[a],plane_index[b],1<<pair_index[e.plane_pair],e.satellite_pair))
        suffix_terminals=[None]*(len(eligible)+1);suffix_pairs=[0]*(len(eligible)+1)
        suffix_terminals[-1]=(0,)*len(planes)
        for index in range(len(eligible)-1,-1,-1):
            mask,a,b,pmask,_=metadata[index]
            masks=list(suffix_terminals[index+1])
            for t in eligible[index].endpoints:
                masks[plane_index[plane_by_satellite[t[0]]]]|=1<<terminal_index[t]
            suffix_terminals[index]=tuple(masks)
            suffix_pairs[index]=suffix_pairs[index+1]|pmask
        incident=[sum(1<<pair_index[pp] for pp in plane_pairs if p in pp) for p in planes]
        def reject(cause):pruned[cause]=pruned.get(cause,0)+1
        stack=[(0,(),0,frozenset(),(0,)*len(planes),0)]
        while stack:
            if visited>=max_search_nodes:reason='SEARCH_NODE_BUDGET';break
            if time.perf_counter()-started>=wall_timeout_s:reason='WALL_TIMEOUT';break
            index,chosen,used,satpairs,counts,covered=stack.pop();visited+=1
            needed=target_K-len(chosen)
            if needed==0:
                if min(counts)>=lower and max(counts)<=upper and population_count(covered)==coverage_bound:
                    solution=tuple(eligible[i] for i in chosen);break
                reject('FINAL_BOUND_NOT_ATTAINED');continue
            if len(eligible)-index<needed:reject('INSUFFICIENT_EDGES');continue
            masks=suffix_terminals[index]
            available=[population_count(mask & ~used) for mask in masks]
            if any(counts[p]+available[p]<lower for p in range(len(planes))):
                reject('PLANE_LOWER_UNREACHABLE');continue
            if sum(min(upper-counts[p],available[p]) for p in range(len(planes)))<2*needed:
                reject('PLANE_CAPACITY_UPPER');continue
            reachable_pairs=covered
            for pp,pbit in pair_index.items():
                if (suffix_pairs[index]>>pbit)&1 and all(counts[plane_index[p]]<upper for p in pp):
                    reachable_pairs|=1<<pbit
            if population_count(reachable_pairs)<coverage_bound:reject('COVERAGE_UPPER');continue
            if coverage_bound==len(plane_pairs) and any(
                population_count(incident[p] & ~covered)>upper-counts[p] for p in range(len(planes))):
                reject('MISSING_PAIR_ENDPOINT_REQUIREMENT');continue
            mask,a,b,pmask,spair=metadata[index]
            # Fixed-size subsets are visited in canonical lexical order: include
            # the first remaining edge before considering its exclusion. Pruning
            # only removes prefixes unable to attain the certified bound tier.
            stack.append((index+1,chosen,used,satpairs,counts,covered))
            if not mask & used and spair not in satpairs and counts[a]<upper and counts[b]<upper:
                next_counts=list(counts);next_counts[a]+=1;next_counts[b]+=1
                stack.append((index+1,chosen+(index,),used|mask,satpairs|{spair},tuple(next_counts),covered|pmask))
        if solution is None and reason is None:reason='ANALYTIC_BOUND_TIER_EXHAUSTED_NOT_GENERAL_INFEASIBILITY'
    report={'status':'EXACT' if solution is not None else 'UNKNOWN','target_K':target_K,
        'nodes_visited':visited,'budget_reason':reason,'wall_s':time.perf_counter()-started,
        'bindings':tuple(e.endpoints for e in solution) if solution is not None else None,
        'optimality_certified':solution is not None,'incumbent_not_authorized_for_K1':solution is None,
        'solver_role':'ANALYTIC_BOUND_CERTIFICATE_ONLY; no weakened objectives',
        'analytic_bounds':bounds,'canonical_first_feasible_tier_proved':solution is not None}
    report['pruning_counts']=pruned
    report['eligible_inventory_sha256']=canonical_sha256([e.to_dict() for e in eligible])
    if solution is not None:
        key=topology_objective(solution,planes)
        report['lexicographic_objective']=[key[0],key[1],str(key[2]),str(key[3]),key[4]]
    report['structural_sha256']=canonical_sha256({k:v for k,v in report.items() if k!='wall_s'})
    return report
