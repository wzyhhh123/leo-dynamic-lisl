"""Exact paired engineering source prefix comparison; no full-coverage claim."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
from dynamic_lisl.f3_v2.joint_action import canonical_sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-attempt',required=True);parser.add_argument('--optimized-attempt',required=True)
    args=parser.parse_args()
    out=ROOT/'outputs'/('f3_v2_source_prefix_equivalence_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    report=None
    try:
        dirs=[ROOT/p for p in (args.legacy_attempt,args.optimized_attempt)];records=[];summaries=[]
        for directory in dirs:
            seal=json.loads((directory/'artifact_hashes.json').read_text(encoding='utf-8'))
            if any(file_sha256(directory/p)!=h for p,h in seal.items()):raise ValueError('SOURCE_ATTEMPT_SEAL_MISMATCH')
            summaries.append(json.loads((directory/'report.json').read_text(encoding='utf-8')))
            records.append([json.loads(line) for line in (directory/'row_observations.jsonl').read_text(encoding='utf-8').splitlines()])
        strip=lambda row:{k:v for k,v in row.items() if k!='validator_wall_s'}
        checks={'paired_modes':summaries[0]['legacy_physical_reference'] is True and summaries[1]['legacy_physical_reference'] is False,
            'same_live_root':summaries[0]['final_root_sha256']==summaries[1]['final_root_sha256'],
            'nonempty_equal_observation_count':bool(records[0]) and len(records[0])==len(records[1]),
            'all_row_IDs_order_acceptance_reasons_metadata_exact':[strip(r) for r in records[0]]==[strip(r) for r in records[1]],
            'live_isolation':all(r['live_unchanged'] and r['root_unchanged'] and r['source_wrapper_restored'] for r in summaries),
            'same_input_hashes':json.loads((dirs[0]/'input_hashes.json').read_text(encoding='utf-8'))==json.loads((dirs[1]/'input_hashes.json').read_text(encoding='utf-8')),
            'same_structural_witness':json.loads((dirs[0]/'structural_witness.json').read_text(encoding='utf-8'))['validation']==json.loads((dirs[1]/'structural_witness.json').read_text(encoding='utf-8'))['validation'],
            'no_failure':all(r['status'] in ('SOURCE_OBSERVATION_BUDGET_UNKNOWN','NATURAL_K4_SOURCE_COVERAGE_AUDIT_COMPLETE') for r in summaries)}
        report={'status':'NATURAL_SOURCE_PREFIX_EXACT_EQUIVALENCE_PASS' if all(checks.values()) else 'FAIL_STOP',
            'checks':checks,'observations_compared':len(records[0]),
            'relative_row_sequence_sha256':canonical_sha256([strip(r) for r in records[0]]),
            'legacy_source_wall_s':summaries[0]['source_wall_s'],'optimized_source_wall_s':summaries[1]['source_wall_s'],
            'observed_prefix_speedup':summaries[0]['source_wall_s']/summaries[1]['source_wall_s'],
            'legacy_source_attempt':args.legacy_attempt,'optimized_source_attempt':args.optimized_attempt,
            'supporting_seals':{directory.relative_to(ROOT).as_posix()+'/artifact_hashes.json':file_sha256(directory/'artifact_hashes.json') for directory in dirs},
            'full_raw_inventory_equivalence_claim':False,'full_pool_equivalence_claim':False,
            'formal_K_star_acceptance':False,'registered_experiment_started':False,'tool_sha256':file_sha256(Path(__file__))}
    except Exception as error:
        report={'status':'FAIL_STOP','error_type':type(error).__name__,'error':str(error),'registered_experiment_started':False}
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out)},indent=2))
    return 0 if report['status']=='NATURAL_SOURCE_PREFIX_EXACT_EQUIVALENCE_PASS' else 1


if __name__=='__main__':raise SystemExit(main())
