"""Isolated, bounded structural orchestration; no K selection or controller.

Natural full-domain execution requires explicit frozen/hash-bound structural
authorization. Engineering mode accepts only the declared eight-node fixture.
UNKNOWN, crash, timeout, changed inputs, or replay mismatch persist then stop.
"""
from dataclasses import asdict, dataclass
import json
import math
import multiprocessing as mp
from pathlib import Path
import time
from .evidence import file_sha256,write_new_json
from .joint_action import canonical_sha256
from .k0_ledger import KS,TIMES,validate_contract,load_review_records,review_ledger
from .preflight import checked_file
from .k0_snapshot import (INITIALIZATION,SnapshotBudget,SourceScanBudget,
    BatchDiagnosticSpec,SnapshotIncomplete,produce_snapshot,write_snapshot_bundle)


@dataclass(frozen=True)
class PointRuntimeSpec:
    solver: SnapshotBudget
    source: SourceScanBudget
    diagnostic_evaluations: int
    point_timeout_s: float
    cleanup_timeout_s: float
    safety_mode: str

    def __post_init__(self):
        if not isinstance(self.solver,SnapshotBudget) or not isinstance(self.source,SourceScanBudget):
            raise TypeError('EXPLICIT_POINT_BUDGETS_REQUIRED')
        if type(self.diagnostic_evaluations) is not int or self.diagnostic_evaluations<1:
            raise ValueError('EXPLICIT_DIAGNOSTIC_EVALUATION_BUDGET_REQUIRED')
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0
               for v in (self.point_timeout_s,self.cleanup_timeout_s)):
            raise ValueError('EXPLICIT_POINT_TIMEOUTS_REQUIRED')
        if self.safety_mode!='STRICT_CONNECTED':raise ValueError('EXPLICIT_REGISTERED_SAFETY_MODE_REQUIRED')


def _frozen(document):
    return (document.get('status')=='FROZEN' and document.get('frozen') is True
        and document.get('canonical_sha256')==canonical_sha256({k:v for k,v in document.items() if k!='canonical_sha256'}))


def validate_natural_request(root,manifest,contract,authorization):
    """Fail closed before reading a scene or creating any worker."""
    root=Path(root)
    if not _frozen(contract) or not _frozen(manifest):raise ValueError('K0_CONTRACT_AND_EXECUTION_MANIFEST_MUST_BE_FROZEN')
    validate_contract(contract)
    if (contract.get('scope')!='NATURAL_K0_STRUCTURAL_AUDIT'
        or contract.get('human_approval_required') is not False
        or contract.get('revision_execution_forbidden') not in (None,[])
        or contract.get('K_star_selected') is not False or contract.get('K_star') is not None):
        raise ValueError('UNRESOLVED_DRAFT_OR_SELECTION_METADATA_IN_FROZEN_CONTRACT')
    if manifest.get('schema')!='f3_v2_k0_audit_execution_v1' or manifest.get('scope')!='NATURAL_K0_STRUCTURAL_AUDIT':
        raise ValueError('EXPLICIT_NATURAL_K0_SCOPE_REQUIRED')
    if (contract.get('initialization_convention')!=INITIALIZATION
        or manifest.get('initialization_convention')!=INITIALIZATION):
        raise ValueError('SNAPSHOT_INITIALIZATION_HUMAN_FREEZE_REQUIRED')
    expected=[{'K':K,'time_s':t,'replay_index':r} for K in KS for t in TIMES for r in (0,1)]
    if manifest.get('points')!=expected:raise ValueError('EXACT_480_POINT_SEQUENCE_REQUIRED')
    if manifest.get('contract_canonical_sha256')!=contract['canonical_sha256']:
        raise ValueError('CONTRACT_MANIFEST_BINDING_MISMATCH')
    if (authorization.get('status')!='APPROVED' or authorization.get('actor')!='HUMAN'
        or authorization.get('scope')!='NATURAL_K0_STRUCTURAL_AUDIT'
        or authorization.get('manifest_canonical_sha256')!=manifest['canonical_sha256']
        or authorization.get('authorized_points_sha256')!=canonical_sha256(expected)
        or authorization.get('K_star_selection_authorized') is not False):
        raise ValueError('EXACT_HUMAN_STRUCTURAL_RUN_AUTHORIZATION_REQUIRED')
    hashes=manifest.get('file_hashes',{})
    if not hashes or any(not checked_file(root,p,h) for p,h in hashes.items()):
        raise ValueError('STRUCTURAL_INPUT_OR_SOURCE_HASH_MISMATCH')
    for field in ('scene_path','contract_path','backbone_path','windows_path','setup_path'):
        if manifest.get(field) not in hashes:raise ValueError('PINNED_STRUCTURAL_ARTIFACT_REQUIRED:'+field)
    if manifest.get('setup_path')!=contract.get('setup_source'):
        raise ValueError('REGISTERED_GATE_C_SETUP_SOURCE_MISMATCH')
    # Authorization signs the finished manifest. Putting its byte hash INSIDE
    # that manifest would form a circular hash dependency. Bind the detached
    # approval after checking its exact contents, and pin it for all point I/O.
    auth_path=manifest.get('authorization_path')
    if (not isinstance(auth_path,str) or Path(auth_path).is_absolute() or '..' in Path(auth_path).parts
        or auth_path in hashes or not (root/auth_path).is_file()):
        raise ValueError('EXACT_DETACHED_AUTHORIZATION_PATH_REQUIRED')
    if not checked_file(root,auth_path,file_sha256(root/auth_path)):
        raise ValueError('AUTHORIZATION_PATH_OUTSIDE_ROOT')
    on_disk_contract=json.loads((root/manifest['contract_path']).read_text(encoding='utf-8'))
    on_disk_auth=json.loads((root/manifest['authorization_path']).read_text(encoding='utf-8'))
    if on_disk_contract!=contract or on_disk_auth!=authorization:
        raise ValueError('STRUCTURAL_GATE_ARTIFACT_CONTENT_MISMATCH')
    # An authorized new contract cannot silently weaken other scientific fields.
    parent=manifest.get('parent_draft_path')
    if parent not in hashes:raise ValueError('EXPLICIT_PINNED_K0_DRAFT_PARENT_REQUIRED')
    draft=json.loads((root/parent).read_text(encoding='utf-8'))
    mutable_metadata={'status','frozen','scope','human_approval_required','draft_canonical_sha256',
        'full_K0_executed','K_star_selected','K_star','K1_started','full_K0_next_step','revision_execution_forbidden'}
    for key,value in draft.items():
        if key not in mutable_metadata and contract.get(key)!=value:
            raise ValueError('K0_PARENT_SCIENTIFIC_FIELD_CHANGED:'+key)
    for name in ('k0_audit_runner.py','k0_snapshot.py','k0_support.py','k0_ledger.py','structural.py',
                 'certified_topology.py','candidate_source.py','source_diagnostics.py',
                 'batch_executor.py','joint_action.py','physical_trial.py','evidence.py','preflight.py'):
        rel='src/dynamic_lisl/f3_v2/'+name
        if rel not in hashes:raise ValueError('PINNED_CONSUMED_SOURCE_REQUIRED:'+rel)
    for name in ('terminal_executor.py','terminal_pair_intervals.py','gate_c_simplified_feasibility.py',
                 'transition_profiler.py','operational_policy.py'):
        if 'src/dynamic_lisl/'+name not in hashes:raise ValueError('PINNED_GATE_B_C_SOURCE_REQUIRED:'+name)
    if 'tools/run_f3_v2_k0_audit.py' not in hashes:raise ValueError('PINNED_STRUCTURAL_ENTRY_SOURCE_REQUIRED')
    return {'status':'AUTHORIZED_STRUCTURAL_EXECUTION_ONLY','K_star_selection_authorized':False,
        'manifest_canonical_sha256':manifest['canonical_sha256'],
        'file_hashes':{**hashes,auth_path:file_sha256(root/auth_path)}}


def runtime_from_dict(value):
    expected={'solver','source','diagnostic_evaluations','point_timeout_s','cleanup_timeout_s','safety_mode'}
    if set(value)!=expected:raise ValueError('EXACT_RUNTIME_SPEC_SCHEMA_REQUIRED')
    return PointRuntimeSpec(SnapshotBudget(**value['solver']),SourceScanBudget(**value['source']),
        value['diagnostic_evaluations'],value['point_timeout_s'],value['cleanup_timeout_s'],value['safety_mode'])


def _scene_args(scene,input_hashes):
    from ..terminal_pair_intervals import TerminalPairCatalog
    from ..gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
    expected={'scope','nodes','fixed_edges','plane_by_satellite','windows','setup',
        'initialization_convention','controller_or_traffic_invoked','K_star_selected'}
    if set(scene)!=expected or scene['controller_or_traffic_invoked'] is not False or scene['K_star_selected'] is not False:
        raise ValueError('EXACT_STRUCTURAL_ONLY_SCENE_SCHEMA_REQUIRED')
    if (not input_hashes or any(not isinstance(k,str) or not isinstance(h,str) or len(h)!=64
        or any(c not in '0123456789abcdef' for c in h) for k,h in input_hashes.items())):
        raise ValueError('EXACT_STRUCTURAL_INPUT_HASHES_REQUIRED')
    nodes=tuple(scene['nodes']);mapping=scene['plane_by_satellite']
    if (len(set(nodes))!=len(nodes) or set(mapping)!=set(nodes)
        or any(type(p) is not int for p in mapping.values()) or set(mapping.values())!={0,1,2,3}):
        raise ValueError('EXACT_FOUR_PLANE_SCENE_REQUIRED')
    if scene['initialization_convention']!=INITIALIZATION:raise ValueError('EXPLICIT_INITIALIZATION_REQUIRED')
    return dict(nodes=nodes,fixed_edges=scene['fixed_edges'],plane_by_satellite=mapping,
        physical_layer=TerminalPairPhysicalFeasibility(TerminalPairCatalog.from_records(scene['windows'],mapping)),
        setup=scene['setup'],input_hashes=input_hashes,initialization_convention=INITIALIZATION)


def validate_natural_scene(root,scene,manifest,input_hashes):
    """Data preflight only: pins original fixed graph, windows and setup values."""
    root=Path(root)
    if any(not checked_file(root,p,h) for p,h in manifest['file_hashes'].items()):
        raise ValueError('PINNED_SCENE_INPUT_HASH_MISMATCH')
    if scene!=json.loads((root/manifest['scene_path']).read_text(encoding='utf-8')):
        raise ValueError('SCENE_DOES_NOT_MATCH_PINNED_MANIFEST_INPUT')
    if scene.get('scope')!='NATURAL_160_STRUCTURAL_ONLY' or len(scene.get('nodes',()))!=160:
        raise ValueError('NATURAL_160_SCENE_REQUIRED')
    if any(sum(p==plane for p in scene['plane_by_satellite'].values())!=40 for plane in range(4)):
        raise ValueError('NATURAL_4_BY_40_SCENE_REQUIRED')
    if input_hashes!=manifest['file_hashes']:raise ValueError('EXACT_BOUND_INPUT_HASHES_REQUIRED')
    topology=json.loads((root/manifest['backbone_path']).read_text(encoding='utf-8'))
    windows=[json.loads(line) for line in (root/manifest['windows_path']).read_text(encoding='utf-8').splitlines()]
    hardware=json.loads((root/manifest['setup_path']).read_text(encoding='utf-8'))['audit_setup_fixture']
    setup={k:hardware[k] for k in ('retarget_a_s','retarget_b_s','acquisition_s')}
    fixed=topology['fixed_edges'];nodes=sorted({n for e in fixed for n in e})
    mapping={n:int(n.split('_')[0][1:]) for n in nodes}
    if (canonical_sha256(scene['fixed_edges'])!=canonical_sha256(fixed)
        or list(scene['nodes'])!=nodes or scene['plane_by_satellite']!=mapping
        or scene['setup']!=setup or scene['windows']!=windows):
        raise ValueError('SCENE_NOT_DERIVED_FROM_PINNED_BACKBONE_WINDOWS_SETUP')
    _scene_args(scene,input_hashes)
    return {'status':'PINNED_160_STRUCTURAL_SCENE_PASS','solver_started':False}


def _point_worker(root,out,scene,point,runtime,input_hashes):
    """Spawn entry: write all stages, never return a huge bundle through a pipe."""
    from ..operational_policy import OperationalPolicy
    root=Path(root);out=Path(out);start=time.perf_counter();sequence=[0]
    row_file=None
    try:
        rows=out/'replace_rows.jsonl';row_file=rows.open('x',encoding='utf-8')
        def sink(stage,evidence):
            if stage=='REPLACE_ROW':
                row_file.write(json.dumps(evidence,sort_keys=True,allow_nan=False)+'\n');row_file.flush()
            else:
                filename='stage_%03d_%s.json'%(sequence[0],stage);sequence[0]+=1
                write_new_json(out/filename,{'stage':stage,'evidence':evidence})
        args=_scene_args(scene,input_hashes)
        bundle=produce_snapshot(**args,K=point['K'],time_s=point['time_s'],budget=runtime.solver,
            batch_diagnostic=BatchDiagnosticSpec(runtime.diagnostic_evaluations,OperationalPolicy(runtime.safety_mode)),
            source_scan_budget=runtime.source,stage_sink=sink)
        reference=write_snapshot_bundle(out/'complete_bundle',bundle,root=root,replay_index=point['replay_index'])
        # Verifies actual disk artifacts, not a parent's claimed status.
        load_review_records(root,{'schema':'f3_v2_k0_review_inputs_v1','records':[reference]})
        status='SOLVER_UNKNOWN' if bundle['solver']['status']=='UNKNOWN' else 'COMPLETE_STRUCTURAL_POINT'
        result={'status':status,'point':point,'solver_status':bundle['solver']['status'],
            'reference':reference,'wall_s':time.perf_counter()-start,'K_star_selected':False}
    except SnapshotIncomplete as exc:
        write_new_json(out/'incomplete_evidence.json',exc.evidence)
        result={'status':exc.status,'point':point,'wall_s':time.perf_counter()-start,
            'partial_inventory_not_a_complete_snapshot':True,'K_star_selected':False}
    except Exception as exc:
        write_new_json(out/'failure_summary.json',{'status':'POINT_FAIL_STOP','exception_type':type(exc).__name__,
            'message':str(exc),'point':point,'K_star_selected':False})
        result={'status':'POINT_FAIL_STOP','point':point,'wall_s':time.perf_counter()-start,'K_star_selected':False}
    finally:
        if row_file is not None:row_file.close()
    write_new_json(out/'point_outcome.json',result)
    write_new_json(out/'artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})


def _run_point(root,out,scene,point,runtime,input_hashes):
    out.mkdir(exist_ok=False)
    write_new_json(out/'point_input.json',{'point':point,'runtime':asdict(runtime),'input_hashes':input_hashes})
    process=mp.get_context('spawn').Process(target=_point_worker,
        args=(str(root),str(out),scene,point,runtime,input_hashes))
    started=time.perf_counter();process.start();pid=process.pid
    process.join(runtime.point_timeout_s);timed_out=process.is_alive()
    if timed_out:
        process.terminate();process.join(runtime.cleanup_timeout_s)
        if process.is_alive():process.kill();process.join(runtime.cleanup_timeout_s)
    alive=process.is_alive();exitcode=process.exitcode
    record={'spawned_pid':pid,'timed_out':timed_out,'child_still_alive':alive,
        'exitcode':exitcode,'parent_wall_s':time.perf_counter()-started,'point':point,
        'terminated_only_this_attempt_child':timed_out}
    write_new_json(out/'process_report.json',record)
    if alive:raise RuntimeError('STRUCTURAL_CHILD_CLEANUP_FAILED')
    process.close()
    outcome=out/'point_outcome.json'
    if timed_out:
        result={'status':'POINT_TIMEOUT_UNKNOWN','point':point,'partial_files_preserved':True,
            'not_infeasibility':True,'K_star_selected':False}
    elif exitcode!=0 or not outcome.is_file():
        result={'status':'POINT_PROCESS_FAIL_STOP','point':point,'exitcode':exitcode,
            'partial_files_preserved':True,'K_star_selected':False}
    else:result=json.loads(outcome.read_text(encoding='utf-8'))
    write_new_json(out/'parent_outcome.json',result)
    # Parent-only terminal seal includes process evidence. Child seal remains
    # untouched even after a timeout; parent seal has an independent filename.
    write_new_json(out/'parent_artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    return result


def run_audit(*,root,output_dir,scene,points,runtime,input_hashes,mode,
              manifest=None,contract=None,authorization=None):
    root=Path(root).resolve();out=Path(output_dir).resolve()
    if not out.is_relative_to(root):raise ValueError('EXACT_LOCAL_AUDIT_OUTPUT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False);outcomes=[];refs=[];current=None
    try:
        if not isinstance(runtime,PointRuntimeSpec):raise TypeError('EXPLICIT_POINT_RUNTIME_REQUIRED')
        if not points or any(set(p)!={'K','time_s','replay_index'} or type(p['K']) is not int or p['K'] not in KS
            or type(p['time_s']) not in (int,float) or p['time_s'] not in TIMES
            or type(p['replay_index']) is not int or p['replay_index'] not in (0,1) for p in points):
            raise ValueError('EXACT_REGISTERED_POINT_SCHEMA_REQUIRED')
        if len({(p['K'],p['time_s'],p['replay_index']) for p in points})!=len(points):
            raise ValueError('DUPLICATE_POINT_NOT_PERMITTED')
        if mode=='ENGINEERING_FIXTURE_ONLY':
            from .k0_fixture import fixture
            _,expected=fixture()
            if (canonical_sha256(scene)!=canonical_sha256(expected) or len(points)>6
                or any(p['time_s'] not in (0,30,570) or p['K'] not in (4,16) for p in points)):
                raise ValueError('DECLARED_EIGHT_NODE_ENGINEERING_FIXTURE_ONLY')
            gate={'status':'ENGINEERING_FIXTURE_ONLY_NO_NATURAL_AUTHORIZATION','file_hashes':{}}
        elif mode=='NATURAL_K0_STRUCTURAL_AUDIT':
            gate=validate_natural_request(root,manifest or {},contract or {},authorization or {})
            validate_natural_scene(root,scene,manifest,input_hashes)
            if points!=manifest['points'] or asdict(runtime)!=manifest.get('runtime'):
                raise ValueError('POINTS_OR_RUNTIME_DO_NOT_MATCH_FROZEN_MANIFEST')
        else:raise ValueError('EXPLICIT_ENGINEERING_OR_AUTHORIZED_NATURAL_MODE_REQUIRED')
        _scene_args(scene,input_hashes)  # Validate before spawning any worker.
        write_new_json(out/'preflight.json',gate)
        write_new_json(out/'execution_input.json',{'mode':mode,'points':points,'runtime':asdict(runtime),
            'scene_sha256':canonical_sha256(scene),'input_hashes':input_hashes})
        for i,point in enumerate(points):
            current=point
            if any(not checked_file(root,p,h) for p,h in gate['file_hashes'].items()):
                raise ValueError('PINNED_INPUT_CHANGED_BEFORE_POINT')
            result=_run_point(root,out/('point_%03d'%i),scene,point,runtime,input_hashes)
            outcomes.append(result)
            if result['status']!='COMPLETE_STRUCTURAL_POINT':
                raise SnapshotIncomplete('AUDIT_STOPPED_BY_'+result['status'],result)
            if any(not checked_file(root,p,h) for p,h in gate['file_hashes'].items()):
                raise ValueError('PINNED_INPUT_CHANGED_AFTER_POINT')
            refs.append(result['reference'])
            write_new_json(out/('checkpoint_%03d.json'%i),{'completed_points':i+1,'reference':refs[-1]})
        records=load_review_records(root,{'schema':'f3_v2_k0_review_inputs_v1','records':refs})
        groups={}
        for r in records:
            key=(r['snapshot']['K'],r['snapshot']['time_s']);value=r['snapshot']['relative_structural_replay_sha256']
            if key in groups and groups[key]!=value:raise ValueError('STRUCTURAL_REPLAY_MISMATCH')
            groups[key]=value
        if mode=='NATURAL_K0_STRUCTURAL_AUDIT':
            review=review_ledger(contract,records);write_new_json(out/'ledger_review.json',review)
        status=('AUTHORIZED_STRUCTURAL_EVIDENCE_COMPLETE_REQUIRES_INDEPENDENT_GATE_REVIEW'
            if mode=='NATURAL_K0_STRUCTURAL_AUDIT' else 'ENGINEERING_STRUCTURAL_ORCHESTRATION_PASS')
        report={'status':status,'mode':mode,'outcomes':outcomes,'completed_points':len(outcomes),
            'input_hashes_unchanged':True,'Gate_K0_PASS':False,'K_star_selected':False,
            'formal_P1_started':False,'P2_started':False,'RL_started':False}
    except Exception as exc:
        status=exc.status if isinstance(exc,SnapshotIncomplete) else 'STRUCTURAL_AUDIT_FAIL_STOP'
        write_new_json(out/'failure_summary.json',{'status':status,'exception_type':type(exc).__name__,
            'message':str(exc),'current_point':current,'completed_outcomes':outcomes,
            'no_retry_performed':True,'later_points_not_started':True,'K_star_selected':False})
        report={'status':status,'mode':mode,'outcomes':outcomes,
            'completed_points':sum(r['status']=='COMPLETE_STRUCTURAL_POINT' for r in outcomes),
            'Gate_K0_PASS':False,'K_star_selected':False,'formal_P1_started':False,'P2_started':False,'RL_started':False}
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    return report
