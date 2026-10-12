"""Content-bound structural evidence review; not an independent optimality proof.

Recompute resources, matching, graph metrics, censor summaries and pre-established
Gate B state. Gate C window generation and global solver proof still require
their independently approved provenance/verification gate before formal K0 PASS.
"""
import math
from .joint_action import canonical_sha256, terminal_state_hash
from .structural import (StructuralEdge, exact_terminal_maximum_matching,
    graph_structure, topology_objective)
from .k0_ledger import lifetime_summary, snapshot_record
from ..terminal_executor import TerminalExecutor, Connect, pair


def _same(a,b,reason):
    if canonical_sha256(a)!=canonical_sha256(b):raise ValueError(reason)


def _edges(rows):
    result=[]
    for row in rows:
        status=row.get('censor_status')
        if status not in ('RIGHT_CENSORED_AT_600','NATURAL_END_KNOWN'):
            raise ValueError('K0_SUPPORT_CENSOR_STATUS_INVALID')
        e=StructuralEdge(tuple(tuple(t) for t in row['endpoints']),tuple(row['plane_pair']),
            row['ready_time_s'],row['observed_end_s'],status=='RIGHT_CENSORED_AT_600',
            row['observation_cutoff_s'])
        _same(e.to_dict(),row,'K0_SUPPORT_LIFETIME_EDGE_INCONSISTENT')
        result.append(e)
    if len({e.endpoints for e in result})!=len(result):
        raise ValueError('K0_SUPPORT_DUPLICATE_IDLE_EDGE')
    return tuple(result)


def verify_snapshot_support(row,supports):
    """Reject empty, swapped or self-consistent-but-disagreeing support JSON."""
    state=row.get('canonical_structural_state',{})
    for key in ('physical','inventory','lifetime'):
        _same(state.get(key),supports[key],'K0_SUPPORT_STATE_CONTENT_MISMATCH:'+key)
    solver=supports['solver'];physical=supports['physical'];raw=supports['inventory'];life=supports['lifetime']
    if row.get('solver_sha256')!=canonical_sha256(solver):
        raise ValueError('K0_SUPPORT_SOLVER_HASH_MISMATCH')
    _same(state.get('solver_semantics'),{k:v for k,v in solver.items() if k not in ('wall_s','structural_sha256')},
        'K0_SUPPORT_SOLVER_SEMANTICS_MISMATCH')
    if solver.get('status')!=row.get('solver_status') or solver.get('target_K')!=row.get('K'):
        raise ValueError('K0_SUPPORT_SOLVER_COORDINATE_MISMATCH')
    nodes=tuple(state.get('nodes',()));mapping=state.get('plane_by_satellite',{});fixed=state.get('fixed_edges',())
    if not nodes or len(set(nodes))!=len(nodes) or set(mapping)!=set(nodes) or set(mapping.values())!={0,1,2,3}:
        raise ValueError('K0_SUPPORT_SCENE_MAPPING_MISMATCH')
    _same(physical.get('nodes'),nodes,'K0_SUPPORT_PHYSICAL_NODES_MISMATCH')
    _same(physical.get('fixed_edges'),fixed,'K0_SUPPORT_FIXED_GRAPH_MISMATCH')
    _same(physical.get('plane_by_satellite'),mapping,'K0_SUPPORT_PHYSICAL_MAPPING_MISMATCH')
    from .k0_snapshot import INITIALIZATION
    if (physical.get('initialization_convention')!=INITIALIZATION
        or physical.get('forward_setup_was_not_executed_before_snapshot') is not True):
        raise ValueError('K0_SUPPORT_SNAPSHOT_INITIALIZATION_MISMATCH')
    ex=TerminalExecutor(nodes);ex.advance(row['time_s'])
    if physical.get('root_idle_sha256')!=terminal_state_hash(ex):
        raise ValueError('K0_SUPPORT_IDLE_ROOT_MISMATCH')
    edges=_edges(life.get('idle_inventory',[]));selected=_edges(life.get('selected_edges',[]))
    by_pair={e.endpoints:e for e in edges}
    for e in edges:
        if (any(t[0] not in mapping or t[1] not in ('D1','D2') for t in e.endpoints)
            or e.plane_pair!=tuple(sorted(mapping[t[0]] for t in e.endpoints))):
            raise ValueError('K0_SUPPORT_EDGE_MAPPING_MISMATCH')
        if e.observation_cutoff_s!=600 or not row['time_s']<=e.ready_time_s<e.observed_end_s<=600:
            raise ValueError('K0_SUPPORT_EDGE_HORIZON_MISMATCH')
    inventory_hash=canonical_sha256([e.to_dict() for e in sorted(edges,key=lambda e:e.endpoints)])
    if inventory_hash!=life.get('idle_inventory_sha256') or inventory_hash!=state.get('idle_inventory_sha256'):
        raise ValueError('K0_SUPPORT_IDLE_INVENTORY_HASH_MISMATCH')
    matching=exact_terminal_maximum_matching(edges)
    _same(state.get('matching'),matching,'K0_SUPPORT_MATCHING_MISMATCH')
    setup=state.get('setup',{});expected={'retarget_a_s','retarget_b_s','acquisition_s'}
    if (set(setup)!=expected or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in setup.values())):
        raise ValueError('K0_SUPPORT_SETUP_REQUIRED')
    setup_s=max(setup['retarget_a_s'],setup['retarget_b_s'])+setup['acquisition_s']
    if setup_s!=life.get('setup_s'):raise ValueError('K0_SUPPORT_SETUP_MISMATCH')
    for key,items in (('idle_candidates',edges),('selected_links',selected)):
        _same(life.get(key),lifetime_summary(items,setup_s=setup_s),'K0_SUPPORT_LIFETIME_SUMMARY_MISMATCH')
    structure=None;planes=[]
    if solver['status']=='EXACT':
        bindings=tuple(pair(*b) for b in solver.get('bindings',()))
        if len(bindings)!=row['K'] or len(set(t for b in bindings for t in b))!=2*row['K']:
            raise ValueError('K0_SUPPORT_TERMINAL_RESOURCE_CONFLICT')
        if len({tuple(t[0] for t in b) for b in bindings})!=row['K'] or any(b not in by_pair for b in bindings):
            raise ValueError('K0_SUPPORT_BINDING_NOT_IN_IDLE_INVENTORY')
        _same([by_pair[b].to_dict() for b in bindings],[e.to_dict() for e in selected],
            'K0_SUPPORT_SELECTED_EDGES_MISMATCH')
        objective=topology_objective(selected,(0,1,2,3))
        _same(solver.get('lexicographic_objective'),[objective[0],objective[1],str(objective[2]),str(objective[3]),objective[4]],
            'K0_SUPPORT_OBJECTIVE_MISMATCH')
        certificates=physical.get('certificates',[])
        if len(certificates)!=len(bindings):raise ValueError('K0_SUPPORT_GATE_C_CERTIFICATES_MISSING')
        for b,cert in zip(bindings,certificates):
            _same(cert.get('endpoints'),b,'K0_SUPPORT_CERTIFICATE_BINDING_MISMATCH')
            g=cert.get('geometry',{});e=by_pair[b];w=g.get('window',{})
            if g.get('ready_time')!=e.ready_time_s or w.get('end_s')!=e.observed_end_s or w.get('right_censored')!=e.right_censored:
                raise ValueError('K0_SUPPORT_GATE_C_WINDOW_MISMATCH')
            _same(pair((w.get('sat_a'),w.get('terminal_a')),(w.get('sat_b'),w.get('terminal_b'))),b,
                'K0_SUPPORT_GATE_C_WINDOW_ENDPOINT_MISMATCH')
            if not (w['start_s']<=row['time_s']<e.ready_time_s<e.observed_end_s<=600):
                # Zero setup is allowed: the decision and ready timestamp may coincide.
                if not (w['start_s']<=row['time_s']<=e.ready_time_s<e.observed_end_s<=600):
                    raise ValueError('K0_SUPPORT_GATE_C_READY_WINDOW_INVALID')
        ex.submit([Connect(*b,by_pair[b].observed_end_s,0.,0.,0.) for b in bindings]);ex.assert_invariants()
        _same(physical.get('terminal_state'),ex.snapshot(),'K0_SUPPORT_PREESTABLISHED_STATE_MISMATCH')
        if physical.get('preestablished_root_sha256')!=terminal_state_hash(ex):
            raise ValueError('K0_SUPPORT_PREESTABLISHED_HASH_MISMATCH')
        if raw.get('root_terminal_sha256')!=terminal_state_hash(ex) or raw.get('time_s')!=row['time_s']:
            raise ValueError('K0_SUPPORT_REPLACE_ROOT_MISMATCH')
        members=raw.get('members',[])
        if [m.get('member_id') for m in members]!=raw.get('selected_member_ids'):
            raise ValueError('K0_SUPPORT_REPLACE_MEMBER_IDS_MISMATCH')
        for i,m in enumerate(members):
            old=pair(*m['old_binding']);new=pair(*m['new_terminal_pair'])
            if old not in bindings or old==new or m.get('canonical_index')!=i:
                raise ValueError('K0_SUPPORT_REPLACE_MEMBER_BINDING_MISMATCH')
            identity={'time_s':row['time_s'],'old':old,'new':new}
            if m.get('member_id')!='V2-RAW-'+canonical_sha256(identity):
                raise ValueError('K0_SUPPORT_REPLACE_MEMBER_ID_MISMATCH')
        structure=graph_structure(nodes,fixed,bindings)
        _same(physical.get('structure'),structure,'K0_SUPPORT_GRAPH_STRUCTURE_MISMATCH')
        if physical.get('status')!='PASS' or physical.get('physical_and_resource_checks') is not True:
            raise ValueError('K0_SUPPORT_PHYSICAL_STATUS_NOT_PASS')
        planes=sorted({p for e in selected for p in e.plane_pair})
    else:
        if selected or physical.get('physical_and_resource_checks') is not False or physical.get('status')!='NOT_EXECUTED_NO_CERTIFIED_TOPOLOGY':
            raise ValueError('K0_SUPPORT_UNCERTIFIED_STATE_EXECUTED')
        if solver['status']=='EXACT_INFEASIBLE' and solver.get('solver_role')=='EXACT_TERMINAL_MATCHING_UPPER_BOUND':
            if matching['cardinality']>=row['K'] or solver.get('capacity_upper_bound')!=matching['cardinality']:
                raise ValueError('K0_SUPPORT_INFEASIBILITY_BOUND_INVALID')
    rebuilt=snapshot_record(K=row['K'],time_s=row['time_s'],matching_capacity=matching['cardinality'],
        represented_planes=planes,connected=None if structure is None else structure['connected'],
        dynamic_bridge_count=None if structure is None else len(structure['dynamic_bridge_edges']),
        replace_inventory=raw,solver=solver,physical_and_resource_checks=physical['physical_and_resource_checks'],
        input_hashes=row['input_hashes'],canonical_structural_state=state,batch_diagnostics=row.get('batch_diagnostics'))
    _same(row,rebuilt,'K0_SUPPORT_REBUILT_RECORD_MISMATCH')
    return {'status':'CONTENT_CONSISTENCY_PASS','matching_recomputed':True,
        'Gate_B_state_reconstructed':solver['status']=='EXACT',
        'Gate_C_window_generation_independently_verified':False,
        'uncapped_inventory_completeness_independently_verified':False,
        'global_optimality_independently_proved_by_this_loader':False,
        'K_star_selected':False,'Gate_K0_PASS':False}
