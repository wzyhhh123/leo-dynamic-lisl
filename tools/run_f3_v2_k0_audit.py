# -*- coding: utf-8 -*-
"""Explicitly authorized structural execution, or read-only preflight. No K*."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.k0_audit_runner import validate_natural_request,validate_natural_scene,runtime_from_dict,run_audit
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256


def local_json(relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts:raise ValueError('EXACT_PROJECT_RELATIVE_INPUT_REQUIRED')
    path=(ROOT/p).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('INPUT_PATH_OUTSIDE_PROJECT')
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--contract',required=True)
    parser.add_argument('--authorization',required=True)
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    out=ROOT/'outputs'/('f3_v2_k0_authorized_entry_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    # Wrapper metadata has its own directory. run_audit owns a distinct child
    # attempt, so preflight or parse failure can still leave immutable evidence.
    out.mkdir(exist_ok=False)
    try:
        manifest=local_json(args.manifest);contract=local_json(args.contract);auth=local_json(args.authorization)
        if args.contract!=manifest.get('contract_path') or args.authorization!=manifest.get('authorization_path'):
            raise ValueError('CLI_ARTIFACTS_DO_NOT_MATCH_MANIFEST_PATHS')
        gate=validate_natural_request(ROOT,manifest,contract,auth)
        runtime=runtime_from_dict(manifest['runtime'])
        scene=local_json(manifest['scene_path'])
        gate['scene_preflight']=validate_natural_scene(ROOT,scene,manifest,manifest['file_hashes'])
        write_new_json(out/'preflight.json',gate)
        if args.preflight_only:
            report={'status':'STRUCTURAL_PREFLIGHT_PASS_NO_EXECUTION','registered_experiment_started':False,
                'structural_workers_started':False,'K_star_selected':False,'Gate_K0_PASS':False}
        else:
            report=run_audit(root=ROOT,output_dir=out/'structural_attempt',scene=scene,
                points=manifest['points'],runtime=runtime,input_hashes=manifest['file_hashes'],
                mode='NATURAL_K0_STRUCTURAL_AUDIT',manifest=manifest,contract=contract,authorization=auth)
        rc=0 if report['status'] in ('STRUCTURAL_PREFLIGHT_PASS_NO_EXECUTION',
            'AUTHORIZED_STRUCTURAL_EVIDENCE_COMPLETE_REQUIRES_INDEPENDENT_GATE_REVIEW') else 1
    except Exception as exc:
        report={'status':'STRUCTURAL_ENTRY_FAIL_STOP','exception_type':type(exc).__name__,'message':str(exc),
            'registered_experiment_started':False,'structural_workers_started':False,
            'K_star_selected':False,'Gate_K0_PASS':False};rc=1
        write_new_json(out/'failure_summary.json',report)
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out),'K_star_selected':False,
        'registered_P1_v2_started':False},indent=2))
    return rc


if __name__=='__main__':raise SystemExit(main())
