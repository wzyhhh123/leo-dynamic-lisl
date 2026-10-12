"""Resolve reviewable file references without freezing or authorizing runs."""
from copy import deepcopy
import json
from pathlib import Path
from .joint_action import canonical_sha256
from .preflight import checked_file
from .evidence import file_sha256


def prepare_execution_review(root,matrix,*,matrix_relative_path):
    path=Path(matrix_relative_path)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('EXACT_LOCAL_SOURCE_MATRIX_REQUIRED')
    actual=(root/path).resolve()
    if not actual.is_relative_to(root.resolve()) or not actual.is_file():
        raise ValueError('EXACT_LOCAL_SOURCE_MATRIX_REQUIRED')
    if json.loads(actual.read_text(encoding='utf-8'))!=matrix:
        raise ValueError('SOURCE_MATRIX_CONTENT_MISMATCH')
    unsigned={k:v for k,v in matrix.items() if k!='draft_canonical_sha256'}
    if matrix.get('status')!='DRAFT_NOT_FROZEN' or matrix.get('frozen') is not False or matrix.get('draft_canonical_sha256')!=canonical_sha256(unsigned):
        raise ValueError('EXACT_DRAFT_MATRIX_REQUIRED')
    runs=matrix['runs'];ids=[r['run_id'] for r in runs]
    if len(runs)!=42 or matrix.get('target_run_count')!=42 or len(set(ids))!=42:
        raise ValueError('EXACT_REGISTERED_DRAFT_42_IDS_REQUIRED')
    if [r['execution_order'] for r in runs]!=list(range(1,43)):
        raise ValueError('DRAFT_EXECUTION_ORDER_MISMATCH')
    allowed={'B0-v2','B1-v2','B2-v2','B3-v2','B4-v2'}
    for row in runs:
        if (row['controller'] not in allowed or row['scale']!=160 or
            row['decision_cadence_s'] not in (2,5) or row['max_batch_replace'] not in (1,4) or
            row['rho'] not in (.5,.8,1.0)):
            raise ValueError('UNREGISTERED_DRAFT_CONFIG')
        if row['controller']=='B2-v2' and row['minimum_hold_s'] not in (4,8):
            raise ValueError('B2_HOLD_GRID_MISMATCH')
    parents=matrix['parent_artifact_sha256']
    if not all(checked_file(root,p,h) for p,h in parents.items()):raise ValueError('DRAFT_PARENT_HASH_MISMATCH')
    primary=[c for c in matrix['contrasts'] if c['kind']=='PRIMARY_CONTROLLER']
    by_id={r['run_id']:r for r in runs}
    if len(primary)!=13:raise ValueError('INCOMPLETE_B4_B3_PRIMARY_PAIRS')
    for contrast in primary:
        left=by_id[contrast['left_run_id']];right=by_id[contrast['right_run_id']]
        if left['controller']!='B4-v2' or right['controller']!='B3-v2':raise ValueError('PRIMARY_CONTROLLER_ORDER_MISMATCH')
        if any(left[k]!=right[k] for k in ('scale','rho','topology_regime','router','traffic','decision_cadence_s','max_batch_replace')):
            raise ValueError('UNFAIR_PRIMARY_PAIR')
    if {c['left_run_id'] for c in primary}!={r['run_id'] for r in runs if r['controller']=='B4-v2'}:
        raise ValueError('PRIMARY_PAIR_COVERAGE_MISMATCH')
    hashes={**parents,matrix_relative_path:file_sha256(root/matrix_relative_path)}
    resolved=[]
    for row in runs:
        item=deepcopy(row)
        if row['topology_regime']=='K4_HISTORICAL_REFERENCE':
            item['K']=4
            item['topology_artifact_sha256']=file_sha256(root/row['topology_artifact'])
            hashes[row['topology_artifact']]=item['topology_artifact_sha256']
        elif row['topology_regime']=='K_STAR':
            item['K']=None;item['topology_artifact_sha256']=None
        else:raise ValueError('UNREGISTERED_TOPOLOGY_REGIME')
        item['traffic_asset_sha256']=file_sha256(root/row['traffic_asset'])
        hashes[row['traffic_asset']]=item['traffic_asset_sha256']
        item['execution_authorized']=False
        resolved.append(item)
    draft={'schema':'F3_V2_EXECUTION_REVIEW_DRAFT_V1','status':'DRAFT_NOT_FROZEN','frozen':False,
        'source_matrix_path':matrix_relative_path,'source_matrix_draft_canonical_sha256':matrix['draft_canonical_sha256'],
        'source_matrix_bytes_sha256':hashes[matrix_relative_path],
        'runs':resolved,'contrasts':deepcopy(matrix['contrasts']),
        'registered_opening_figure_proposal':deepcopy(matrix['registered_opening_figure_proposal']),
        'common_contract':deepcopy(matrix['common_contract']),'file_hashes':hashes,
        'scientific_contract_canonical_sha256':None,'acceptance_evidence':{},'result_provenance':{},
        'unresolved':['scientific contract freeze and canonical binding','authorized full K0 and selected K*',
            'authorized K1 topology and hashes','new production acceptance evidence',
            'per-run measured approved runtime budgets','final per-run provenance and formal manifest freeze',
            'separate human formal run authorization'],
        'checks':{'run_ids_and_order_unchanged':ids==[r['run_id'] for r in resolved],
            'all_13_B4_B3_pairs_same_action_permission':True,'no_extra_run':True,
            'parent_hashes_verified':True,'K_star_not_invented':True,
            'cost_not_invented':all(r['runtime_budget']['estimated_wall_clock_s'] is None for r in resolved)},
        'formal_ready':False,'registered_experiment_started':False}
    draft['draft_canonical_sha256']=canonical_sha256(draft)
    return draft
