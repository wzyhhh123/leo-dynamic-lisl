"""Summarize explicitly listed K0 evidence; no solver, K* selection or controller."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.k0_ledger import review_ledger,load_review_records
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json
from dynamic_lisl.f3_v2.joint_action import canonical_sha256


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-manifest',required=True)
    args=p.parse_args()
    out=ROOT/'outputs'/('f3_v2_k0_ledger_review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    source=Path(args.input_manifest)
    if source.is_absolute() or '..' in source.parts:raise ValueError('EXACT_LOCAL_MANIFEST_REQUIRED')
    path=(ROOT/source).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('EXACT_LOCAL_MANIFEST_REQUIRED')
    contract=ROOT/'configs/gate_k0_contract_v1_1_DRAFT.json'
    before=file_sha256(contract)
    try:
        manifest=json.loads(path.read_text(encoding='utf-8'))
        report=review_ledger(json.loads(contract.read_text(encoding='utf-8')),load_review_records(ROOT,manifest))
        if file_sha256(contract)!=before:raise ValueError('PROTECTED_K0_DRAFT_CHANGED')
        report['source_manifest_sha256']=file_sha256(path)
        report['protected_contract_bytes_sha256']=before
        report.pop('review_sha256',None)
        report['review_sha256']=canonical_sha256(report)
        write_new_json(out/'report.json',report)
        status=report['status']
    except Exception as exc:
        status='K0_LEDGER_REVIEW_FAIL_STOP'
        write_new_json(out/'failure_summary.json',{'status':status,'exception_type':type(exc).__name__,'message':str(exc),
            'K_star_selected':False,'registered_experiment_started':False})
    write_new_json(out/'artifact_hashes.json',{f.name:file_sha256(f) for f in out.iterdir() if f.is_file()})
    print(json.dumps({'status':status,'output_dir':str(out),'K_star_selected':False,'registered_experiment_started':False}))
    return 1 if status.endswith('FAIL_STOP') else 0


if __name__=='__main__':raise SystemExit(main())
