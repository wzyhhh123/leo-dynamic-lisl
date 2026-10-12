"""Registered-ID ledger and censor-safe, preregistered paired summaries only."""
import math
import json
from pathlib import Path
from .joint_action import canonical_sha256
from .evidence import paired_contrast, file_sha256


def validate_analysis_manifest(manifest):
    signed={k:v for k,v in manifest.items() if k!='canonical_sha256'}
    if not (manifest.get('status')=='FROZEN' and manifest.get('frozen') is True and
            manifest.get('canonical_sha256')==canonical_sha256(signed)):
        raise ValueError('ANALYSIS_REQUIRES_EXACT_FROZEN_MANIFEST')
    runs=manifest.get('runs',[]);ids=[r['run_id'] for r in runs]
    if not ids or len(set(ids))!=len(ids):raise ValueError('INVALID_REGISTERED_RUN_IDS')
    return runs


def load_sealed_registered_results(root,manifest,mapping):
    """Reject stale/self-resealed evidence through preregistered provenance.

    A run's own artifact seal detects byte changes; it alone cannot prove that
    the run used the registered inputs/configuration. Those exact hashes are
    also pinned in the frozen manifest. No current simulator/code is executed.
    """
    rows=validate_analysis_manifest(manifest)
    by_id={r['run_id']:r for r in rows}
    if not isinstance(mapping,dict):raise ValueError('INVALID_RESULT_DIRECTORY_MAP')
    if set(mapping)-set(by_id):raise ValueError('UNREGISTERED_RESULT_IDS')
    root=Path(root).resolve();metrics={};sources={}
    required={'invariant_report.json','metrics.json','final_state_evidence.json','action_timeline.json',
              'transition_timeline.json','candidate_source_audit.json','timeseries.json',
              'input_code_hashes.json','failure_summary.json'}
    for rid,relative in mapping.items():
        if not isinstance(relative,str):raise ValueError('INVALID_RESULT_DIRECTORY')
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts:raise ValueError('RESULT_DIRECTORY_OUTSIDE_PROJECT')
        directory=(root/path).resolve()
        try:directory.relative_to(root)
        except ValueError:raise ValueError('RESULT_DIRECTORY_OUTSIDE_PROJECT')
        seals=json.loads((directory/'artifact_hashes.json').read_text(encoding='utf-8'))
        if not isinstance(seals,dict) or not required<=set(seals):raise ValueError('INCOMPLETE_RUN_EVIDENCE:'+rid)
        for name,digest in seals.items():
            if not isinstance(name,str) or Path(name).name!=name or not (directory/name).is_file() or file_sha256(directory/name)!=digest:
                raise ValueError('RUN_EVIDENCE_HASH_MISMATCH:'+rid+':'+str(name))
        expected=manifest.get('result_provenance',{}).get(rid)
        if not expected or not expected.get('inputs') or not expected.get('code'):
            raise ValueError('UNREGISTERED_RESULT_PROVENANCE:'+rid)
        frozen_hashes=manifest.get('file_hashes',{})
        if any(frozen_hashes.get(p)!=h for group in ('inputs','code') for p,h in expected[group].items()):
            raise ValueError('RESULT_PROVENANCE_NOT_BOUND_TO_FROZEN_FILES:'+rid)
        actual=json.loads((directory/'input_code_hashes.json').read_text(encoding='utf-8'))
        binding={'execution_manifest_canonical_sha256':manifest['canonical_sha256'],
                 'registered_run_configuration_sha256':canonical_sha256(by_id[rid])}
        if actual!={'inputs':expected['inputs'],'code':expected['code'],'execution_binding':binding}:
            raise ValueError('REGISTERED_INPUT_CODE_OR_CONFIGURATION_MISMATCH:'+rid)
        data=json.loads((directory/'metrics.json').read_text(encoding='utf-8'))
        invariant=json.loads((directory/'invariant_report.json').read_text(encoding='utf-8'))
        failure=json.loads((directory/'failure_summary.json').read_text(encoding='utf-8'))
        if data.get('outcome')!='EXECUTION_BLOCKED':
            if (invariant.get('status')!='PASS' or not invariant.get('items') or
                not all(item.get('pass') is True for item in invariant['items'].values()) or
                invariant.get('scientific_outcome')!=data.get('outcome') or
                failure.get('failure') is not None or failure.get('status')!=data.get('outcome')):
                raise ValueError('SCIENTIFIC_RESULT_WITH_FAILED_INVARIANTS:'+rid)
        metrics[rid]=data
        sources[rid]={'directory':directory.relative_to(root).as_posix(),
                     'artifact_seal_sha256':file_sha256(directory/'artifact_hashes.json'),
                     'execution_binding':binding}
    return metrics,sources


def analyze_registered_results(manifest,metrics_by_run):
    runs=validate_analysis_manifest(manifest);ids=[r['run_id'] for r in runs]
    extra=set(metrics_by_run)-set(ids)
    if extra:raise ValueError('UNREGISTERED_RESULT_IDS:'+repr(sorted(extra)))
    ledger=[];complete=0;censored=0
    for row in runs:
        rid=row['run_id'];metrics=metrics_by_run.get(rid)
        if metrics is None:
            ledger.append({'run_id':rid,'outcome':'MISSING'});continue
        if metrics.get('run_id')!=rid:raise ValueError('METRICS_RUN_ID_MISMATCH')
        outcome=metrics['outcome']
        if metrics.get('engineering_only') is not False:raise ValueError('ENGINEERING_RESULT_IS_NOT_PAPER_EVIDENCE')
        if outcome not in ('COMPLETE','CENSORED_AT_DRAIN_LIMIT','EXECUTION_BLOCKED'):
            raise ValueError('INVALID_RUN_OUTCOME')
        if outcome=='COMPLETE':
            if metrics.get('J_is_complete') is not True or type(metrics.get('J_bit_s')) not in (int,float) or not math.isfinite(metrics['J_bit_s']) or metrics['J_bit_s']<0:
                raise ValueError('COMPLETE_J_NOT_VALIDATED')
            complete+=1
        elif outcome=='CENSORED_AT_DRAIN_LIMIT':
            if metrics.get('J_is_complete') is not False:raise ValueError('CENSORED_J_MUST_BE_MARKED_TRUNCATED')
            censored+=1
        ledger.append({'run_id':rid,'outcome':outcome,'residual_backlog_bits':metrics.get('residual_backlog_bits'),
                       'delivery_ratio':metrics.get('delivery_ratio'),'completion_time_s':metrics.get('completion_time_s')})
    ready=complete+censored==len(runs)
    summary={'status':'COMPLETE_REGISTERED_EVIDENCE' if ready else 'INCOMPLETE_EVIDENCE_PACKAGE',
        'manifest_canonical_sha256':manifest['canonical_sha256'],'registered_runs':len(runs),
        'COMPLETE_count':complete,'CENSORED_count':censored,'run_ledger':ledger,
        'paired_analysis_performed':ready,'paired_contrasts':[],'global_controller_ranking_created':False,
        'statistical_scope':'paired deterministic descriptions; no independent-replicate significance claim'}
    if not ready:return summary
    by_id={r['run_id']:r for r in runs}
    for contrast in manifest.get('contrasts',[]):
        left,right=contrast['left_run_id'],contrast['right_run_id']
        if left not in by_id or right not in by_id:raise ValueError('UNREGISTERED_CONTRAST_REFERENCE')
        if contrast['kind']=='PRIMARY_CONTROLLER':
            for field in ('scale','rho','topology_regime','router','traffic','decision_cadence_s','max_batch_replace'):
                if by_id[left].get(field)!=by_id[right].get(field):raise ValueError('UNFAIR_PRIMARY_PAIR:'+field)
            if by_id[left]['controller']!='B4-v2' or by_id[right]['controller']!='B3-v2':
                raise ValueError('PRIMARY_CONTRAST_MUST_BE_B4_MINUS_B3')
        value=paired_contrast(metrics_by_run[left],metrics_by_run[right])
        summary['paired_contrasts'].append({'contrast_id':contrast['contrast_id'],'kind':contrast['kind'],
                                           'left_run_id':left,'right_run_id':right,**value})
    return summary
