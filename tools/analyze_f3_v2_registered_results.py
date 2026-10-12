"""Read sealed v2 results only; never starts a controller or registered run."""
import argparse
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json
from dynamic_lisl.f3_v2.result_analysis import analyze_registered_results,load_sealed_registered_results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--run-directory-map',required=True)
    args=parser.parse_args()
    out=ROOT/'outputs'/('f3_v2_result_analysis_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    write_new_json(out/'invocation.json',{'command':sys.argv,'cwd':str(Path.cwd()),
        'manifest_path':str(Path(args.manifest).resolve()),'run_directory_map_path':str(Path(args.run_directory_map).resolve()),
        'tool_sha256':file_sha256(Path(__file__)),'registered_experiment_started':False})
    try:
        manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        mapping=json.loads(Path(args.run_directory_map).read_text(encoding='utf-8'))
        metrics,sources=load_sealed_registered_results(ROOT,manifest,mapping)
        report=analyze_registered_results(manifest,metrics)
    except Exception as error:
        write_new_json(out/'failure_summary.json',{'status':'ANALYSIS_BLOCKED','error_type':type(error).__name__,
            'error':str(error),'paired_analysis_performed':False,'registered_experiment_started':False})
        write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
        print(json.dumps({'status':'ANALYSIS_BLOCKED','output_dir':str(out),'error':str(error)},indent=2))
        return 1
    write_new_json(out/'summary.json',report)
    write_new_json(out/'source_evidence_hashes.json',sources)
    with (out/'run_ledger.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['run_id','outcome','residual_backlog_bits','delivery_ratio','completion_time_s'])
        writer.writeheader();writer.writerows(report['run_ledger'])
    write_new_json(out/'paired_analysis.json',report['paired_contrasts'])
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out),'paired_analysis_performed':report['paired_analysis_performed']},indent=2))
    return 0 if report['status']=='COMPLETE_REGISTERED_EVIDENCE' else 2


if __name__=='__main__':raise SystemExit(main())
