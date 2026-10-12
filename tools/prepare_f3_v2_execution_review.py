"""Create an independently hashed review draft, never freeze or launch runs."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.manifest_review import prepare_execution_review
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256


def main():
    rel='configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json'
    out=ROOT/'outputs'/('f3_v2_execution_review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    try:
        matrix=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        draft=prepare_execution_review(ROOT,matrix,matrix_relative_path=rel)
        write_new_json(out/'execution_manifest_DRAFT.json',draft)
        report={'status':'EXECUTION_REVIEW_DRAFT_READY_NOT_FROZEN','registered_ids':42,
            'checks':draft['checks'],'unresolved':draft['unresolved'],'formal_ready':False,
            'registered_experiment_started':False,'source_matrix_unchanged':file_sha256(ROOT/rel)==draft['source_matrix_bytes_sha256']}
    except Exception as error:
        report={'status':'FAIL_STOP','error_type':type(error).__name__,'error':str(error),'registered_experiment_started':False}
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out)},indent=2))
    return 1 if report['status']=='FAIL_STOP' else 0


if __name__=='__main__':raise SystemExit(main())
