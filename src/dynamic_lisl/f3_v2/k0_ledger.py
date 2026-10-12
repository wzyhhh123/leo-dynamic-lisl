"""Evidence-only K0 review ledger, never selects K* or executes a solver.

Consumes complete snapshot/replay records produced by the structural executor.
Missing/capped/UNKNOWN evidence stays UNKNOWN. Batch compatibility is diagnostic
only and cannot silently become another admissibility predicate.
"""
import math
import statistics
from .joint_action import canonical_sha256
from .preflight import checked_file


TIMES = tuple(range(0, 600, 30))
KS = (4, 8, 16, 24, 32, 40, 48, 64, 80, 96, 120, 160)
THRESHOLDS = {
    'capacity_snapshots': 20, 'all_planes_snapshots': 20,
    'connected_and_bridges_lt_edges_snapshots': 18,
    'replace_ge_16_snapshots': 18, 'MBB_ge_8_and_BBM_ge_8_snapshots': 18,
    'median_MBB_fraction_band': [0.1, 0.9], 'full_audit_replays': 2,
    'snapshot_denominator': 20, 'median_MBB_sample_count': 20,
}


def validate_contract(contract):
    if (contract.get('K_candidates') != list(KS) or contract.get('snapshot_times_s') != list(TIMES)
        or contract.get('satellites') != 160 or contract.get('planes') != 4
        or contract.get('terminals_per_satellite') != 2
        or contract.get('primary_band') != [0.15, 0.5]
        or contract.get('admissibility') != THRESHOLDS
        or contract.get('selection_rule') != 'min_admissible_K'
        or contract.get('observation_horizon_s') != [0.0, 600.0]):
        raise ValueError('K0_V1_1_REGISTERED_CONTRACT_MISMATCH')
    return canonical_sha256(contract)


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError('INVALID_STRUCTURAL_COUNT:' + name)
    return value


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _validate_metrics(K, metrics):
    if not isinstance(metrics,dict):raise ValueError('STRUCTURAL_METRICS_REQUIRED')
    for name in ('matching_capacity','dynamic_bridge_count','replace_count','BBM_count','MBB_count'):
        _count(metrics.get(name),name)
    total=metrics['replace_count'];bbm=metrics['BBM_count'];mbb=metrics['MBB_count']
    fraction=metrics.get('MBB_fraction')
    if (bbm+mbb!=total or metrics['dynamic_bridge_count']>K
        or not K<=metrics['matching_capacity']<=160
        or type(metrics.get('connected')) is not bool
        or not isinstance(metrics.get('represented_planes'),list)
        or metrics['represented_planes']!=sorted(set(metrics['represented_planes']))
        or any(type(p) is not int or p not in range(4) for p in metrics['represented_planes'])
        or (total==0 and fraction is not None)
        or (total>0 and (type(fraction) not in (int,float) or not math.isfinite(fraction) or fraction!=mbb/total))):
        raise ValueError('STRUCTURAL_METRICS_INCONSISTENT')


def lifetime_summary(edges, *, setup_s):
    """Bounded lifetime diagnostic; never substitutes observation end for expiry."""
    if type(setup_s) not in (int,float) or not math.isfinite(setup_s) or setup_s<0:
        raise ValueError('FINITE_NONNEGATIVE_SETUP_REQUIRED')
    edges=tuple(edges)
    ordered=sorted(e.usable_within_horizon_s for e in edges)
    def percentile(q):
        if not ordered:return None
        index=(len(ordered)-1)*q;low=int(index);high=min(low+1,len(ordered)-1)
        return ordered[low]+(ordered[high]-ordered[low])*(index-low)
    return {'metric':'L_usable_within_horizon','count':len(ordered),
        'min_s':min(ordered) if ordered else None,'P10_s':percentile(.1),
        'median_s':statistics.median(ordered) if ordered else None,'P90_s':percentile(.9),
        'max_s':max(ordered) if ordered else None,
        'fraction_le_setup':sum(x<=setup_s for x in ordered)/len(ordered) if ordered else None,
        'fraction_le_10s':sum(x<=10 for x in ordered)/len(ordered) if ordered else None,
        'fraction_le_20s':sum(x<=20 for x in ordered)/len(ordered) if ordered else None,
        'right_censored_count':sum(e.right_censored for e in edges),
        'natural_end_known_count':sum(not e.right_censored for e in edges),
        'quantile_rule':'linear (n-1)q; diagnostic only, no new admissibility predicate',
        'truncated_metric_not_full_physical_lifetime':True}


def snapshot_record(*, K, time_s, matching_capacity, represented_planes, connected,
                    dynamic_bridge_count, replace_inventory, solver,
                    physical_and_resource_checks, input_hashes,
                    canonical_structural_state, batch_diagnostics=None):
    """Make a replay record from executor evidence, without a performance score.

    Producer must retain independently verifiable solver and Gate B/C artifacts;
    their hash-bound presence is enforced by the CLI loader. This serializer does
    not manufacture or independently prove those underlying gate assertions.
    """
    if type(K) is not int or K not in KS or type(time_s) not in (int,float) or time_s not in TIMES:
        raise ValueError('UNREGISTERED_K0_POINT')
    if not input_hashes or not all(isinstance(p,str) and _digest(h) for p,h in input_hashes.items()):
        raise ValueError('EXACT_INPUT_HASHES_REQUIRED')
    status=solver.get('status')
    if status not in ('EXACT','EXACT_INFEASIBLE','UNKNOWN'):
        raise ValueError('EXPLICIT_SOLVER_STATUS_REQUIRED')
    if solver.get('target_K') != K:
        raise ValueError('SOLVER_TARGET_K_MISMATCH')
    metrics=None
    if status != 'UNKNOWN' and solver.get('optimality_certified') is not True:
        raise ValueError('CERTIFIED_SOLVER_RESULT_REQUIRED')
    if status=='EXACT':
        bindings=solver.get('bindings')
        if not isinstance(bindings,(list,tuple)) or len(bindings)!=K:
            raise ValueError('EXACT_K_BINDINGS_REQUIRED')
        terminals=[tuple(t) for b in bindings for t in b]
        sat_pairs=[tuple(sorted(t[0] for t in b)) for b in bindings]
        if len(terminals)!=2*K or len(set(terminals))!=2*K or len(set(sat_pairs))!=K:
            raise ValueError('TOPOLOGY_RESOURCE_OR_PARALLEL_CONFLICT')
        if physical_and_resource_checks is not True:
            raise ValueError('GATE_C_AND_RESOURCE_CERTIFICATE_REQUIRED')
        if type(connected) is not bool:
            raise ValueError('EXPLICIT_CONNECTED_STATE_REQUIRED')
        if sorted(set(represented_planes)) != list(represented_planes) or not set(represented_planes)<=set(range(4)):
            raise ValueError('PLANE_COVERAGE_INVALID')
        audit=replace_inventory
        if audit.get('uncapped') is not True or audit.get('performance_input_read') is not False:
            raise ValueError('UNCAPPED_TRAFFIC_BLIND_INVENTORY_REQUIRED')
        bbm=_count(audit.get('stratum_counts',{}).get('BBM'),'BBM')
        mbb=_count(audit.get('stratum_counts',{}).get('MBB'),'MBB')
        total=_count(audit.get('uncapped_physical_count'),'replace_count')
        ids=audit.get('selected_member_ids',[])
        if bbm+mbb!=total or len(ids)!=total or not all(isinstance(i,str) and i for i in ids) or len(set(ids))!=total:
            raise ValueError('UNCAPPED_INVENTORY_COUNTS_OR_IDS_MISMATCH')
        capacity=_count(matching_capacity,'matching_capacity')
        if capacity<K or capacity>160:
            raise ValueError('MATCHING_CAPACITY_CONTRADICTS_CERTIFIED_TOPOLOGY')
        bridges=_count(dynamic_bridge_count,'dynamic_bridges')
        if bridges>K:raise ValueError('BRIDGE_COUNT_EXCEEDS_K')
        metrics={'matching_capacity':capacity,'represented_planes':list(represented_planes),
            'connected':connected,'dynamic_bridge_count':bridges,'replace_count':total,
            'BBM_count':bbm,'MBB_count':mbb,'MBB_fraction':mbb/total if total else None}
        _validate_metrics(K,metrics)
    row={'schema':'f3_v2_k0_snapshot_replay_v1','K':K,'time_s':time_s,
        'solver_status':status,'solver_sha256':canonical_sha256(solver),
        'metrics':metrics,'input_hashes':dict(input_hashes),
        'canonical_structural_state':canonical_structural_state,
        'batch_diagnostics':batch_diagnostics,
        'batch_diagnostics_used_for_admissibility':False,
        'scope':'STRUCTURAL_REVIEW_NOT_K_SELECTION','K_star_selected':False}
    # Solver wall/RSS may differ between replays; the independently verified
    # solver semantic certificate is already in canonical_structural_state.
    replay={k:v for k,v in row.items() if k!='solver_sha256'}
    row['relative_structural_replay_sha256']=canonical_sha256(replay)
    return row


def review_ledger(contract, records):
    """Summarize all registered points, including missing ones, without selection."""
    contract_hash=validate_contract(contract)
    groups={};inputs=None
    for record in records:
        r=record['snapshot'];replay=record['replay_index']
        if type(replay) is not int or replay not in (0,1):raise ValueError('EXACT_TWO_REPLAY_INDICES_REQUIRED')
        key=(r.get('K'),r.get('time_s'))
        if type(key[0]) is not int or key[0] not in KS or type(key[1]) not in (int,float) or key[1] not in TIMES:
            raise ValueError('UNREGISTERED_K0_POINT')
        if (r.get('schema')!='f3_v2_k0_snapshot_replay_v1' or r.get('K_star_selected') is not False
            or r.get('batch_diagnostics_used_for_admissibility') is not False):
            raise ValueError('EXACT_STRUCTURAL_REPLAY_SCHEMA_REQUIRED')
        unsigned={k:v for k,v in r.items() if k not in ('relative_structural_replay_sha256','solver_sha256')}
        if r.get('relative_structural_replay_sha256')!=canonical_sha256(unsigned):
            raise ValueError('STRUCTURAL_REPLAY_HASH_MISMATCH')
        if r.get('solver_status') not in ('EXACT','EXACT_INFEASIBLE','UNKNOWN'):
            raise ValueError('EXPLICIT_SOLVER_STATUS_REQUIRED')
        if r['solver_status']=='EXACT':_validate_metrics(key[0],r.get('metrics'))
        elif r.get('metrics') is not None:raise ValueError('UNKNOWN_OR_INFEASIBLE_METRICS_MUST_BE_NULL')
        if inputs is None:inputs=r['input_hashes']
        if inputs!=r['input_hashes']:raise ValueError('AUDIT_INPUTS_CHANGED_BETWEEN_POINTS')
        if replay in groups.setdefault(key,{}):raise ValueError('DUPLICATE_K_TIME_REPLAY')
        groups[key][replay]=r
    rows=[]
    for K in KS:
        point_status=[];metrics=[]
        for t in TIMES:
            pair=groups.get((K,t),{})
            if len(pair)!=2:point_status.append({'time_s':t,'status':'MISSING_REPLAY'});continue
            a,b=pair[0],pair[1]
            if a['relative_structural_replay_sha256']!=b['relative_structural_replay_sha256']:
                point_status.append({'time_s':t,'status':'REPLAY_MISMATCH'});continue
            status=a['solver_status']
            point_status.append({'time_s':t,'status':status})
            if status=='EXACT':metrics.append(a['metrics'])
        known=all(p['status'] in ('EXACT','EXACT_INFEASIBLE') for p in point_status)
        exact=known and len(metrics)==20
        summary=None;admissible=None;reason='INCOMPLETE_OR_UNKNOWN_EVIDENCE'
        if known and not exact:
            admissible=False;reason='CERTIFIED_INFEASIBLE_TOPOLOGY_AT_REGISTERED_POINT'
        elif exact:
            fractions=[m['MBB_fraction'] for m in metrics]
            median=statistics.median(fractions) if all(v is not None for v in fractions) else None
            summary={
                'capacity_snapshots':sum(m['matching_capacity']>=K for m in metrics),
                'all_planes_snapshots':sum(m['represented_planes']==[0,1,2,3] for m in metrics),
                'connected_and_bridges_lt_edges_snapshots':sum(m['connected'] and m['dynamic_bridge_count']<K for m in metrics),
                'replace_ge_16_snapshots':sum(m['replace_count']>=16 for m in metrics),
                'MBB_ge_8_and_BBM_ge_8_snapshots':sum(m['MBB_count']>=8 and m['BBM_count']>=8 for m in metrics),
                'median_MBB_fraction':median,'sample_count':20,
            }
            predicates={k:summary[k]>=v for k,v in THRESHOLDS.items() if k.endswith('_snapshots')}
            predicates['median_MBB_fraction_band']=median is not None and 0.1<=median<=0.9
            predicates['primary_occupancy_band']=0.15<=K/160<=0.5
            predicates['primary_excludes_K4']=K!=4
            summary['predicates']=predicates
            admissible=all(predicates.values());reason='REGISTERED_PREDICATES_EVALUATED'
        rows.append({'K':K,'occupancy_fraction':K/160,'snapshot_count':20,
            'point_status':point_status,'complete_certified_replay_evidence':known,
            'summary':summary,'admissible_review':admissible,'reason':reason})
    report={'schema':'f3_v2_k0_ledger_review_v1',
        'status':'STRUCTURAL_REVIEW_COMPLETE' if all(r['complete_certified_replay_evidence'] for r in rows) else 'STRUCTURAL_REVIEW_INCOMPLETE',
        'contract_document_sha256':contract_hash,'rows':rows,
        'registered_snapshot_records':12*20*2,'supplied_records':len(records),
        'all_input_hashes':inputs,'Gate_K0_PASS':False,'full_audit_complete':False,
        'human_authorization_verified':False,'K_star':None,'K_star_selected':False,
        'formal_selection_requires': ['human-frozen contract and structural-run authorization',
            'independently verified solver/physical/censor artifacts for all points',
            'uncapped inventories and exact replay evidence', 'separate authorized K-selection gate'],
        'batch_compatibility_is_diagnostic_only':True,'traffic_or_controller_execution':False}
    report['review_sha256']=canonical_sha256(report)
    return report


def load_review_records(root, manifest):
    """Load exact references AND check evidence content; never grants K0 PASS."""
    import json
    if manifest.get('schema')!='f3_v2_k0_review_inputs_v1':raise ValueError('K0_REVIEW_INPUT_SCHEMA_REQUIRED')
    records=[]
    for ref in manifest.get('records',[]):
        if not checked_file(root,ref.get('path'),ref.get('sha256')):
            raise ValueError('SNAPSHOT_EVIDENCE_HASH_MISMATCH')
        supports=ref.get('supporting_evidence',{})
        if set(supports)!= {'solver','physical','inventory','lifetime'}:
            raise ValueError('K0_GATE_SPECIFIC_SUPPORT_REQUIRED')
        for support in supports.values():
            if not checked_file(root,support.get('path'),support.get('sha256')):
                raise ValueError('MISSING_OR_CHANGED_K0_SUPPORT')
        row=json.loads((root/ref['path']).read_text(encoding='utf-8'))
        documents={k:json.loads((root/v['path']).read_text(encoding='utf-8')) for k,v in supports.items()}
        from .k0_support import verify_snapshot_support
        verification=verify_snapshot_support(row,documents)
        records.append({'replay_index':ref['replay_index'],'snapshot':row,'support_verification':verification})
    return records
