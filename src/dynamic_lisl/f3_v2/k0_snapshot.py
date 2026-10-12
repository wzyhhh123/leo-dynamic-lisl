"""Real Gate B/C structural snapshot producer, with no traffic or controller.

Independent pre-established snapshots are an explicit caller hypothesis, never
a claim that forward setup already completed. The formal hypothesis must be
human-frozen before an approved full K0 audit can use this producer.
"""
from dataclasses import asdict, dataclass, replace
from copy import deepcopy
import math
import time
from ..terminal_executor import TerminalExecutor, pair
from .candidate_source import replacement_inventory
from .certified_topology import certified_bound_topology
from .joint_action import canonical_sha256, terminal_state_hash
from .k0_ledger import snapshot_record, lifetime_summary
from .structural import (legal_edge_inventory, exact_terminal_maximum_matching,
    deterministic_lexicographic_topology, graph_structure, topology_objective,
    exact_batch_compatibility)


INITIALIZATION = 'INDEPENDENT_PREESTABLISHED_AT_SNAPSHOT_WITH_FORWARD_GATE_C_CERTIFICATE'


@dataclass(frozen=True)
class SnapshotBudget:
    reference_nodes: int
    reference_wall_s: float
    certificate_nodes: int
    certificate_wall_s: float

    def __post_init__(self):
        if any(type(x) is not int or x<1 for x in (self.reference_nodes,self.certificate_nodes)):
            raise ValueError('EXPLICIT_POSITIVE_SOLVER_NODE_BUDGET_REQUIRED')
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0
               for x in (self.reference_wall_s,self.certificate_wall_s)):
            raise ValueError('EXPLICIT_POSITIVE_SOLVER_WALL_BUDGET_REQUIRED')


@dataclass(frozen=True)
class BatchDiagnosticSpec:
    max_evaluations: int
    policy: object

    def __post_init__(self):
        from ..operational_policy import OperationalPolicy
        if type(self.max_evaluations) is not int or self.max_evaluations<1:
            raise ValueError('EXPLICIT_POSITIVE_BATCH_DIAGNOSTIC_BUDGET_REQUIRED')
        if not isinstance(self.policy,OperationalPolicy):
            raise TypeError('EXPLICIT_EXISTING_SAFETY_POLICY_REQUIRED')


@dataclass(frozen=True)
class SourceScanBudget:
    max_evaluations: int
    wall_s: float

    def __post_init__(self):
        if type(self.max_evaluations) is not int or self.max_evaluations<1:
            raise ValueError('EXPLICIT_UNCAPPED_SCAN_EVALUATION_BUDGET_REQUIRED')
        if type(self.wall_s) not in (int,float) or not math.isfinite(self.wall_s) or self.wall_s<=0:
            raise ValueError('EXPLICIT_UNCAPPED_SCAN_WALL_BUDGET_REQUIRED')


class SnapshotIncomplete(RuntimeError):
    """Operational exhaustion is not solver infeasibility or a complete table."""
    def __init__(self,status,evidence):
        super().__init__(status)
        self.status=status;self.evidence=evidence


def _batch_diagnostics(executor,physical,fixed,source,spec):
    from .batch_executor import BatchPhysicalValidator,BatchSafetyValidator
    from .joint_action import JointAction
    frame='K0_STRUCTURAL_BATCH_DIAGNOSTIC'
    root_hash=terminal_state_hash(executor)
    physical_validator=BatchPhysicalValidator(physical,max_batch_replace=4,
        observation_end_s=600,absolute_time_frame_id=frame)
    validator=BatchSafetyValidator(physical_validator,fixed,spec.policy)
    members=source['members'];pool_hash=source['raw_source_sha256']
    factory=lambda ms:JointAction(executor.now,frame,root_hash,pool_hash,ms)
    result=exact_batch_compatibility(factory,members,validator,executor,
        max_members=4,max_evaluations=spec.max_evaluations)
    modes={}
    needed={m for witness in result['joint_safe_witnesses'] for m in witness}
    for member in members:
        if member.member_id not in needed:continue
        item=physical_validator.evaluate(executor,factory((member,)))
        if not item.accepted:raise AssertionError('UNCAPPED_MEMBER_CHANGED_BEFORE_DIAGNOSTIC')
        modes[member.member_id]=item.member_results[0]['transition_mode']
    witnesses=result['joint_safe_witnesses']
    result['joint_safe_count_by_size']={str(n):sum(len(w)==n for w in witnesses) for n in range(1,5)}
    result['joint_safe_mode_compositions']=sorted({tuple(sorted(modes[m] for m in w)) for w in witnesses})
    # The permission bound itself proves no allowed action is larger than four.
    # A four-member witness proves the maximum in that scope even if not all
    # >4 subsets were scanned; the underlying UNKNOWN record is not rewritten.
    result['allowed_size_upper_bound']=4
    result['singleton_mode_revalidations']=len(modes)
    result['subset_budget_excludes_explicit_singleton_mode_revalidations']=True
    result['allowed_resource_maximum_status']=('EXACT_WITHIN_0_TO_4' if result['max_resource_witness_size']==4
        or result['all_subsets_through_size_scanned'] else 'UNKNOWN')
    result['allowed_joint_maximum_status']=('EXACT_WITHIN_0_TO_4' if result['max_joint_safe_witness_size']==4
        or result['all_subsets_through_size_scanned'] else 'UNKNOWN')
    result['safety_policy']=asdict(spec.policy)
    result['no_admissibility_predicate_added']=True
    result['root_unchanged']=terminal_state_hash(executor)==root_hash
    if not result['root_unchanged']:raise AssertionError('BATCH_DIAGNOSTIC_CHANGED_ROOT')
    return result


def _semantic_solver(solver):
    return {k:v for k,v in solver.items() if k not in ('wall_s','structural_sha256')}


def solve_snapshot(edges,K,planes,mapping,matching,budget):
    """Prove infeasibility by an upper bound, or attain an exact lex certificate.

    Analytic failure is not general infeasibility: fall back to the unchanged
    bounded exhaustive reference. Keep both attempts and their UNKNOWN status.
    """
    if matching['status']!='EXACT':raise ValueError('EXACT_MATCHING_REQUIRED')
    if matching['cardinality']<K:
        solver={'status':'EXACT_INFEASIBLE','target_K':K,'bindings':None,
            'optimality_certified':True,'incumbent_not_authorized_for_K1':False,
            'solver_role':'EXACT_TERMINAL_MATCHING_UPPER_BOUND',
            'matching_sha256':matching['matching_sha256'],'capacity_upper_bound':matching['cardinality'],
            'nodes_visited':0,'wall_s':0.0,'budget_reason':None}
        solver['structural_sha256']=canonical_sha256(_semantic_solver(solver))
        return solver,{'matching_bound':solver}
    analytic=certified_bound_topology(edges,K,planes,plane_by_satellite=mapping,
        max_search_nodes=budget.certificate_nodes,wall_timeout_s=budget.certificate_wall_s)
    if analytic['status']=='EXACT':return analytic,{'analytic':analytic}
    reference=deterministic_lexicographic_topology(edges,K,planes,
        max_search_nodes=budget.reference_nodes,wall_timeout_s=budget.reference_wall_s)
    return reference,{'analytic':analytic,'reference':reference}


def produce_snapshot(*,nodes,fixed_edges,plane_by_satellite,physical_layer,K,time_s,
                     setup,budget,input_hashes,initialization_convention,batch_diagnostic=None,
                     source_scan_budget=None,stage_sink=None):
    """Generate one genuine structural point. No main-scale loop or selection."""
    if initialization_convention!=INITIALIZATION:
        raise ValueError('EXPLICIT_K0_SNAPSHOT_INITIALIZATION_REQUIRED')
    nodes=tuple(sorted(nodes));fixed_edges=tuple(tuple(e) for e in fixed_edges)
    planes=tuple(sorted(set(plane_by_satellite.values())))
    if len(set(nodes))!=len(nodes) or set(plane_by_satellite)!=set(nodes) or planes!=(0,1,2,3):
        raise ValueError('EXACT_FOUR_PLANE_SCENE_MAPPING_REQUIRED')
    if any(type(p) is not int for p in plane_by_satellite.values()):raise ValueError('INTEGER_PLANES_REQUIRED')
    if set(n for e in fixed_edges for n in e)-set(nodes):raise ValueError('FIXED_GRAPH_NODE_MISMATCH')
    expected=('retarget_a_s','retarget_b_s','acquisition_s')
    if set(setup)!=set(expected) or any(type(setup[k]) not in (int,float) or not math.isfinite(setup[k]) or setup[k]<0 for k in expected):
        raise ValueError('EXPLICIT_ENDPOINT_SETUP_REQUIRED')
    # Registered coordinates are enforced by the common serializer even for
    # engineering fixtures; constructing invalid points cannot start a scan.
    from .k0_ledger import KS,TIMES
    if type(K) is not int or K not in KS or type(time_s) not in (int,float) or time_s not in TIMES:
        raise ValueError('UNREGISTERED_K0_POINT')
    if not isinstance(budget,SnapshotBudget):raise TypeError('SNAPSHOT_BUDGET_REQUIRED')
    if batch_diagnostic is not None and not isinstance(batch_diagnostic,BatchDiagnosticSpec):
        raise TypeError('EXPLICIT_BATCH_DIAGNOSTIC_SPEC_REQUIRED')
    if source_scan_budget is not None and not isinstance(source_scan_budget,SourceScanBudget):
        raise TypeError('EXPLICIT_SOURCE_SCAN_BUDGET_REQUIRED')
    if stage_sink is not None and not callable(stage_sink):raise TypeError('READ_ONLY_STAGE_SINK_REQUIRED')
    def emit(stage,evidence):
        if stage_sink is not None:stage_sink(stage,deepcopy(evidence))
    ex=TerminalExecutor(nodes);ex.advance(time_s);idle_hash=terminal_state_hash(ex)
    emit('IDLE_ROOT',{'K':K,'time_s':time_s,'terminal_state':ex.snapshot(),
        'root_sha256':idle_hash,'input_hashes':dict(input_hashes),'setup':dict(setup)})
    costs={};start=time.perf_counter()
    inventory=legal_edge_inventory(ex,physical_layer,plane_by_satellite,**setup,observation_end_s=600)
    costs['idle_inventory_s']=time.perf_counter()-start
    if terminal_state_hash(ex)!=idle_hash:raise AssertionError('IDLE_INVENTORY_MUTATED_ROOT')
    emit('IDLE_INVENTORY',{'edges':[e.to_dict() for e in inventory['edges']],
        'rejected':inventory['rejected'],'uncapped':True,
        'candidate_inventory_sha256':inventory['candidate_inventory_sha256']})
    edges=inventory['edges'];edge_map={e.endpoints:e for e in edges}
    start=time.perf_counter();matching=exact_terminal_maximum_matching(edges)
    costs['matching_s']=time.perf_counter()-start
    emit('MATCHING',matching)
    start=time.perf_counter();solver,attempts=solve_snapshot(edges,K,planes,plane_by_satellite,matching,budget)
    costs['builder_s']=time.perf_counter()-start
    emit('SOLVER',{'solver':solver,'attempts':attempts,'budget':asdict(budget)})
    physical={'status':'NOT_EXECUTED_NO_CERTIFIED_TOPOLOGY','initialization_convention':initialization_convention,
        'forward_setup_was_not_executed_before_snapshot':True,'root_idle_sha256':idle_hash,
        'node_count':len(nodes),'nodes':nodes,'fixed_edges':tuple(fixed_edges),
        'plane_by_satellite':dict(plane_by_satellite),'certificates':[],'physical_and_resource_checks':False}
    raw={'status':'NOT_EXECUTED_NO_CERTIFIED_TOPOLOGY','uncapped':True,'performance_input_read':False}
    structure=None;selected=[];root_state=None
    diagnostics={'status':'NOT_EXECUTED_DIAGNOSTIC_ONLY','no_admissibility_predicate_added':True}
    source_observation=None
    if solver['status']=='EXACT':
        bindings=tuple(pair(*b) for b in solver['bindings'])
        if len(bindings)!=K or len(set(bindings))!=K or any(b not in edge_map for b in bindings):
            raise AssertionError('CERTIFIED_SOLVER_BINDINGS_INVALID')
        terminals=[t for b in bindings for t in b]
        if len(set(terminals))!=len(terminals) or len({tuple(t[0] for t in b) for b in bindings})!=K:
            raise AssertionError('CERTIFIED_SOLVER_RESOURCE_CONFLICT')
        selected=[edge_map[b] for b in bindings]
        key=topology_objective(selected,planes)
        objective=[key[0],key[1],str(key[2]),str(key[3]),key[4]]
        if canonical_sha256(objective)!=canonical_sha256(solver['lexicographic_objective']):
            raise AssertionError('CERTIFIED_OBJECTIVE_DISAGREES_WITH_INVENTORY')
        commands=[]
        for b in bindings:
            result=physical_layer.evaluate(ex,*b,retarget_a=setup['retarget_a_s'],
                retarget_b=setup['retarget_b_s'],acquisition=setup['acquisition_s'])
            e=edge_map[b]
            if (not result['accepted'] or result['geometry']['ready_time']!=e.ready_time_s
                or result['geometry']['window']['end_s']!=e.observed_end_s):
                raise AssertionError('SELECTED_GATE_C_CERTIFICATE_CHANGED')
            physical['certificates'].append({'endpoints':b,'geometry':result['geometry']})
            commands.append(replace(result['command'],retarget_a=0.,retarget_b=0.,acquisition=0.))
        # Existing Gate B transaction: a pre-established construction hypothesis
        # at this snapshot, not a simulated root action paying zero setup.
        ex.submit(commands);ex.assert_invariants()
        if len(ex.links)!=K or ex.reservations:raise AssertionError('PREESTABLISHED_GRAPH_NOT_ACTIVE')
        structure=graph_structure(nodes,fixed_edges,bindings)
        root_state=ex.snapshot();root_hash=terminal_state_hash(ex)
        physical.update(status='PASS',physical_and_resource_checks=True,
            preestablished_root_sha256=root_hash,terminal_state=root_state,
            structure=structure)
        emit('PHYSICAL_ROOT',physical)
        start=time.perf_counter()
        source_kwargs=dict(plane_by_satellite=plane_by_satellite,**setup,observation_end_s=600,raw_budget=None)
        if source_scan_budget is None:
            raw_result=replacement_inventory(ex,physical_layer,**source_kwargs)
        else:
            from .source_diagnostics import observe_replacement_source
            observed=observe_replacement_source(ex,physical_layer,
                max_evaluations=source_scan_budget.max_evaluations,wall_budget_s=source_scan_budget.wall_s,
                row_sink=(lambda row:emit('REPLACE_ROW',row)),**source_kwargs)
            source_observation={k:v for k,v in observed.items() if k!='source_result'}
            source_observation['budget']=asdict(source_scan_budget)
            if observed['status']!='SOURCE_OBSERVATION_COMPLETE':
                emit('SOURCE_INCOMPLETE',source_observation)
                status=('UNCAPPED_INVENTORY_UNKNOWN' if observed['status']=='SOURCE_OBSERVATION_BUDGET_UNKNOWN'
                    else 'UNCAPPED_INVENTORY_FAIL_STOP')
                raise SnapshotIncomplete(status,{'solver':solver,'physical':physical,
                    'source_observation':source_observation,'K':K,'time_s':time_s,
                    'partial_inventory_not_a_complete_snapshot':True})
            raw_result=observed['source_result']
        costs['uncapped_replace_s']=time.perf_counter()-start;raw=raw_result['audit']
        if terminal_state_hash(ex)!=root_hash:raise AssertionError('REPLACE_INVENTORY_MUTATED_ROOT')
        emit('UNCAPPED_REPLACE_INVENTORY',raw)
        if batch_diagnostic is not None:
            start=time.perf_counter()
            diagnostics=_batch_diagnostics(ex,physical_layer,fixed_edges,raw_result,batch_diagnostic)
            costs['batch_diagnostics_s']=time.perf_counter()-start
            emit('BATCH_DIAGNOSTIC',diagnostics)
    lifetime={'setup_s':max(setup['retarget_a_s'],setup['retarget_b_s'])+setup['acquisition_s'],
        'idle_candidates':lifetime_summary(edges,setup_s=max(setup['retarget_a_s'],setup['retarget_b_s'])+setup['acquisition_s']),
        'selected_links':lifetime_summary(selected,setup_s=max(setup['retarget_a_s'],setup['retarget_b_s'])+setup['acquisition_s']),
        'idle_inventory': [e.to_dict() for e in edges], 'selected_edges':[e.to_dict() for e in selected],
        'idle_rejections':inventory['rejected'],'idle_inventory_sha256':inventory['candidate_inventory_sha256']}
    canonical_state={'nodes':nodes,'fixed_edges':tuple(fixed_edges),'plane_by_satellite':dict(plane_by_satellite),
        'idle_inventory_sha256':inventory['candidate_inventory_sha256'],
        'matching':matching,'solver_semantics':_semantic_solver(solver),'setup':dict(setup),
        'physical':physical,'inventory':raw,'lifetime':lifetime}
    row=snapshot_record(K=K,time_s=time_s,matching_capacity=matching['cardinality'],
        represented_planes=sorted({p for e in selected for p in e.plane_pair}),
        connected=None if structure is None else structure['connected'],
        dynamic_bridge_count=None if structure is None else len(structure['dynamic_bridge_edges']),
        replace_inventory=raw,solver=solver,physical_and_resource_checks=physical['physical_and_resource_checks'],
        input_hashes=input_hashes,canonical_structural_state=canonical_state,
        batch_diagnostics=diagnostics)
    bundle={'snapshot':row,'solver':solver,'solver_attempts':attempts,'physical':physical,'inventory':raw,
        'lifetime':lifetime,'matching':matching,'component_wall_s':costs,
        'budget':asdict(budget),'controller_or_traffic_invoked':False,
        'K_star_selected':False,'registered_experiment_started':False}
    if source_observation is not None:bundle['source_observation']=source_observation
    emit('SNAPSHOT_COMPLETE',{'relative_structural_replay_sha256':row['relative_structural_replay_sha256'],
        'solver_status':solver['status'],'component_wall_s':costs})
    return bundle


def write_snapshot_bundle(output_dir,bundle,*,root,replay_index):
    """Exclusive evidence publication; no prior files or FAILED attempt replaced."""
    from pathlib import Path
    from .evidence import write_new_json,file_sha256
    root=Path(root).resolve();out=Path(output_dir).resolve()
    if not out.is_relative_to(root):raise ValueError('EXACT_LOCAL_BUNDLE_DIRECTORY_REQUIRED')
    if type(replay_index) is not int or replay_index not in (0,1):
        raise ValueError('EXACT_TWO_REPLAY_INDICES_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('snapshot','solver','solver_attempts','physical','inventory','lifetime','matching','component_wall_s','budget'):
        write_new_json(out/(name+'.json'),bundle[name])
    if 'source_observation' in bundle:write_new_json(out/'source_observation.json',bundle['source_observation'])
    ref={'path':(out/'snapshot.json').relative_to(root).as_posix(),
        'sha256':file_sha256(out/'snapshot.json'),'replay_index':replay_index,
        'supporting_evidence':{k:{'path':(out/(k+'.json')).relative_to(root).as_posix(),
            'sha256':file_sha256(out/(k+'.json'))} for k in ('solver','physical','inventory','lifetime')}}
    write_new_json(out/'evidence_reference.json',ref)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    return ref
