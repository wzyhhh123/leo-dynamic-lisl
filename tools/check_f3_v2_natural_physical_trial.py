"""Exact legacy/optimized natural capped pool and size4 physical validation.

Consumes one sealed engineering inventory. Does not evaluate traffic, service,
controllers or J, and does not claim a full legacy inventory scan was executed.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.evidence import write_new_json,file_sha256
from dynamic_lisl.f3_v2.joint_action import BatchReplaceMember,JointAction,terminal_state_hash,canonical_sha256
from dynamic_lisl.f3_v2.batch_executor import BatchPhysicalValidator,BatchSafetyValidator
from dynamic_lisl.f3_v2.joint_proposer import BoundedJointProposer,JointSearchBudget
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.operational_policy import OperationalPolicy


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-attempt',required=True)
    args=parser.parse_args();source=ROOT/args.source_attempt
    out=ROOT/'outputs'/('f3_v2_natural_physical_trial_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'));out.mkdir()
    try:
        seal=json.loads((source/'artifact_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(source/p)!=h for p,h in seal.items()):raise ValueError('SOURCE_SEAL_MISMATCH')
        source_report=json.loads((source/'report.json').read_text(encoding='utf-8'))
        if source_report['status']!='NATURAL_K4_SOURCE_COVERAGE_AUDIT_COMPLETE':raise ValueError('COMPLETE_NATURAL_SOURCE_REQUIRED')
        hashes=json.loads((source/'input_hashes.json').read_text(encoding='utf-8'))
        if any(file_sha256(ROOT/p)!=h for p,h in hashes.items()):raise ValueError('PHYSICAL_INPUT_CHANGED')
        topology=json.loads((ROOT/'configs/z_moderate_v1.json').read_text(encoding='utf-8'))
        nodes=tuple(sorted({n for e in topology['fixed_edges'] for n in e}));planes={n:int(n.split('_')[0][1:]) for n in nodes}
        records=[json.loads(line) for line in (ROOT/'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl').read_text(encoding='utf-8').splitlines()]
        physical=TerminalPairPhysicalFeasibility(TerminalPairCatalog.from_records(records,planes))
        ex=TerminalExecutor(nodes)
        for row in topology['bindings']:ex.submit((Connect(tuple(row['a']),tuple(row['b']),row['end_s'],0,0,0),))
        root=terminal_state_hash(ex)
        if root!=source_report['final_root_sha256']:raise ValueError('EXACT_SOURCE_ROOT_RECONSTRUCTION_FAILED')
        raw=json.loads((source/'raw_source_audit.json').read_text(encoding='utf-8'))
        members=tuple(BatchReplaceMember(**row) for row in raw['members'])
        witness=json.loads((source/'structural_witness.json').read_text(encoding='utf-8'))
        witness_members=tuple(BatchReplaceMember(**row) for row in witness['action']['members'])
        frame='K4_NATURAL_SOURCE_ENGINEERING_ONLY';pool_results=[];plans=[];timings=[]
        for enabled in (False,True):
            validator=BatchSafetyValidator(BatchPhysicalValidator(physical,max_batch_replace=4,observation_end_s=600,
                absolute_time_frame_id=frame,counterfactual_physical_clone=enabled),topology['fixed_edges'],OperationalPolicy('STRICT_CONNECTED'))
            start=time.perf_counter()
            pool=BoundedJointProposer(validator,JointSearchBudget(16,8,4,32,4,184,184,33)).propose(ex,members)
            timings.append(time.perf_counter()-start);pool_results.append(pool)
            plan=validator.evaluate(ex,JointAction(0,frame,root,canonical_sha256([]),witness_members));plans.append(plan)
            write_new_json(out/('optimized_pool.json' if enabled else 'legacy_pool.json'),pool.public_document())
            write_new_json(out/('optimized_witness.json' if enabled else 'legacy_witness.json'),plan.to_dict())
        checks={'pool_document_IDs_order_hash_exact':pool_results[0].public_document()==pool_results[1].public_document(),
            'all_pool_physical_safety_plans_exact':[p.to_dict() for p in pool_results[0].plans]==[p.to_dict() for p in pool_results[1].plans],
            'full_size4_witness_exact':plans[0].to_dict()==plans[1].to_dict(),
            'size4_witness_accepted':all(p.accepted and len(p.action.members)==4 for p in plans),
            'live_root_unchanged':terminal_state_hash(ex)==root,
            'original_source_pool_hash':pool_results[1].pool_sha256==source_report['pool_sha256']}
        report={'status':'NATURAL_PHYSICAL_TRIAL_POOL_EXACT_PASS' if all(checks.values()) else 'FAIL_STOP',
            'checks':checks,'raw_members_compared':len(members),'non_hold_pool_size':len(pool_results[0].actions)-1,
            'legacy_proposer_wall_s':timings[0],'optimized_proposer_wall_s':timings[1],
            'proposer_speedup':timings[0]/timings[1],'source_attempt':args.source_attempt,
            'source_seal_sha256':file_sha256(source/'artifact_hashes.json'),
            'code_hashes':{p.relative_to(ROOT).as_posix():file_sha256(p) for p in (ROOT/'src/dynamic_lisl/f3_v2').glob('*.py')},
            'full_legacy_source_scan_executed':False,'B4_controller_or_service_evaluated':False,
            'formal_K_star_acceptance':False,'K_star_selected':False,'registered_experiment_started':False}
    except Exception as error:
        report={'status':'FAIL_STOP','error_type':type(error).__name__,'error':str(error),'registered_experiment_started':False}
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.name:file_sha256(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out)},indent=2))
    return 0 if report['status']=='NATURAL_PHYSICAL_TRIAL_POOL_EXACT_PASS' else 1


if __name__=='__main__':raise SystemExit(main())
