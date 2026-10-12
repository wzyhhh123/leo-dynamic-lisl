"""Fail-closed authorization/hash checks, independent of old v1 runtime seals."""
from .joint_action import canonical_sha256
from .evidence import file_sha256
import math
from pathlib import Path


def positive_number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>0


def checked_file(root,relative_path,digest):
    if not isinstance(relative_path,str) or not isinstance(digest,str):return False
    path=Path(relative_path)
    if path.is_absolute() or '..' in path.parts:return False
    candidate=(root/path).resolve()
    try:candidate.relative_to(root.resolve())
    except ValueError:return False
    return candidate.is_file() and file_sha256(candidate)==digest


def validate_preflight(root,manifest,science_contract,k0_report,k1_report,engineering_report,runtime_budget,authorization):
    checks={}
    def frozen(document):
        unsigned={k:v for k,v in document.items() if k!='canonical_sha256'}
        return document.get('frozen') is True and document.get('status')=='FROZEN' and document.get('canonical_sha256')==canonical_sha256(unsigned)
    checks['scientific_contract_frozen']=frozen(science_contract)
    checks['execution_manifest_frozen']=frozen(manifest)
    checks['K0_authorized_complete']=k0_report.get('status')=='PASS' and k0_report.get('full_audit_complete') is True and k0_report.get('human_authorization_verified') is True
    checks['K_star_selected']=type(k0_report.get('K_star')) is int and k0_report['K_star']>0
    checks['K1_authorized_complete']=k1_report.get('status')=='PASS' and k1_report.get('approved_K_star')==k0_report.get('K_star') and k1_report.get('batch_compatibility_checked') is True
    required=('V2_A','V2_B','V2_C','V2_D','V2_E','V2_F','full_regression','serial_8worker_natural_geometry','no_performance_leakage','historical_integrity')
    checks['engineering_acceptance_complete']=all(engineering_report.get(k)=='PASS' for k in required)
    checks['runtime_measured']=runtime_budget.get('status')=='MEASURED_AND_APPROVED' and positive_number(runtime_budget.get('matrix_wall_budget_s'))
    runs=manifest.get('runs',[])
    checks['unique_registered_ids']=bool(runs) and all(isinstance(r.get('run_id'),str) and r['run_id'] for r in runs) and len({r.get('run_id') for r in runs})==len(runs)
    checks['every_run_cost_bound']=bool(runs) and all(positive_number(r.get('runtime_budget',{}).get('estimated_wall_clock_s')) for r in runs)
    checks['matrix_budget_sufficient']=checks['runtime_measured'] and checks['every_run_cost_bound'] and sum(r['runtime_budget']['estimated_wall_clock_s'] for r in runs)<=runtime_budget['matrix_wall_budget_s']
    checks['contract_manifest_bound']=manifest.get('scientific_contract_canonical_sha256')==science_contract.get('canonical_sha256') and checks['scientific_contract_frozen']
    checks['K_star_manifest_bound']=checks['K_star_selected'] and all(r.get('K')==k0_report.get('K_star') or
        (r.get('K')==4 and r.get('topology_regime')=='K4_HISTORICAL_REFERENCE') for r in runs)
    checks['explicit_HOLD_REPLACE_only']=science_contract.get('action_kinds')==['HOLD','BATCH_REPLACE']
    checks['formal_run_authorization']=(authorization.get('status')=='APPROVED' and authorization.get('actor')=='HUMAN' and
        authorization.get('scope')=='REGISTERED_F3_V2' and authorization.get('manifest_canonical_sha256')==manifest.get('canonical_sha256') and
        authorization.get('authorized_run_ids')==[r.get('run_id') for r in runs])
    hashes=manifest.get('file_hashes',{})
    checks['input_and_code_hashes_match']=bool(hashes) and all(checked_file(root,p,h) for p,h in hashes.items())
    # Claims such as "full_regression=PASS" alone cannot authorize production.
    # Pin supporting artifacts from the frozen manifest; inspection of their
    # gate-specific semantics remains required by the engineering report.
    sources={'K0':k0_report,'K1':k1_report,'ENGINEERING':engineering_report,'RUNTIME':runtime_budget}
    refs=manifest.get('acceptance_evidence',{})
    checks['supporting_evidence_hashes_bound']=all(k in refs and checked_file(root,refs[k].get('path'),refs[k].get('sha256')) and
        refs[k]['path'] in hashes and hashes[refs[k]['path']]==refs[k]['sha256'] for k in sources)
    if checks['supporting_evidence_hashes_bound']:
        import json
        checks['supporting_evidence_matches_input']=all(json.loads((root/refs[k]['path']).read_text(encoding='utf-8'))==doc for k,doc in sources.items())
    else:checks['supporting_evidence_matches_input']=False
    return {'status':'READY' if all(checks.values()) else 'NOT_READY','checks':checks,
            'blockers':[k for k,v in checks.items() if not v],'registered_P1_v2_started':False,
            'P2_started':False,'RL_started':False}
