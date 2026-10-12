# -*- coding: utf-8 -*-
"""Engineering fixture orchestration + budget/timeout controls. No full K0."""
from dataclasses import asdict
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dynamic_lisl.f3_v2.k0_audit_runner import PointRuntimeSpec,run_audit
from dynamic_lisl.f3_v2.k0_snapshot import SnapshotBudget,SourceScanBudget
from dynamic_lisl.f3_v2.k0_fixture import fixture
from dynamic_lisl.f3_v2.evidence import file_sha256,write_new_json


def main():
    out=ROOT/'outputs'/('f3_v2_k0_orchestration_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(exist_ok=False);print(out,flush=True)
    code=list((ROOT/'src/dynamic_lisl/f3_v2').glob('*.py'))+[Path(__file__),
        ROOT/'tools/run_f3_v2_k0_audit.py',ROOT/'tests/test_f3_v2_k0_orchestration.py']
    code_hashes={p.relative_to(ROOT).as_posix():file_sha256(p) for p in code}
    contract_rel='configs/gate_k0_contract_v1_1_DRAFT.json';contract_hash=file_sha256(ROOT/contract_rel)
    write_new_json(out/'input_code_hashes_before.json',{'input':{contract_rel:contract_hash},'code':code_hashes})
    start=time.perf_counter();reports=[]
    try:
        args,scene=fixture();write_new_json(out/'fixture_contract.json',scene)
        solver=SnapshotBudget(100000,5.,100000,5.)
        base=PointRuntimeSpec(solver,SourceScanBudget(100,10),1,20,5,'STRICT_CONNECTED')
        points=[{'K':4,'time_s':t,'replay_index':r} for t in (0,30,570) for r in (0,1)]
        positive=run_audit(root=ROOT,output_dir=out/'positive_six_points',scene=scene,points=points,
            runtime=base,input_hashes=args['input_hashes'],mode='ENGINEERING_FIXTURE_ONLY')
        if positive['status']!='ENGINEERING_STRUCTURAL_ORCHESTRATION_PASS' or positive['completed_points']!=6:
            raise AssertionError('SIX_POINT_ENGINEERING_CHAIN_FAIL')
        reports.append({'name':'six_point_replays','report':positive})
        specifications=[
            ('uncapped_budget_unknown',PointRuntimeSpec(solver,SourceScanBudget(1,10),1,20,5,'STRICT_CONNECTED'),
                points[:2],'AUDIT_STOPPED_BY_UNCAPPED_INVENTORY_UNKNOWN'),
            ('solver_unknown',PointRuntimeSpec(SnapshotBudget(1,5,1,5),SourceScanBudget(100,10),1,20,5,'STRICT_CONNECTED'),
                points[:1],'AUDIT_STOPPED_BY_SOLVER_UNKNOWN'),
            ('point_timeout_unknown',PointRuntimeSpec(solver,SourceScanBudget(100,10),1,.000001,5,'STRICT_CONNECTED'),
                points[:1],'AUDIT_STOPPED_BY_POINT_TIMEOUT_UNKNOWN')]
        for name,runtime,p,expected in specifications:
            report=run_audit(root=ROOT,output_dir=out/name,scene=scene,points=p,runtime=runtime,
                input_hashes=args['input_hashes'],mode='ENGINEERING_FIXTURE_ONLY')
            if report['status']!=expected:raise AssertionError('NEGATIVE_CONTROL_NOT_CAUGHT:'+name)
            if (out/name/'point_001').exists():raise AssertionError('LATER_POINT_STARTED_AFTER_UNKNOWN')
            reports.append({'name':name,'expected_status':expected,'report':report})
        denied=run_audit(root=ROOT,output_dir=out/'unapproved_natural_request',scene=scene,points=points,
            runtime=base,input_hashes=args['input_hashes'],mode='NATURAL_K0_STRUCTURAL_AUDIT',
            contract=json.loads((ROOT/contract_rel).read_text(encoding='utf-8')))
        if denied['status']!='STRUCTURAL_AUDIT_FAIL_STOP' or list((out/'unapproved_natural_request').glob('point_*')):
            raise AssertionError('UNAPPROVED_REQUEST_REACHED_WORKER')
        reports.append({'name':'unapproved_natural_request','report':denied})
        process_reports=[json.loads(p.read_text(encoding='utf-8')) for p in out.rglob('process_report.json')]
        if any(r['child_still_alive'] for r in process_reports):raise AssertionError('CHILD_LIVENESS_AFTER_GATE')
        if file_sha256(ROOT/contract_rel)!=contract_hash or any(file_sha256(ROOT/p)!=h for p,h in code_hashes.items()):
            raise AssertionError('PROTECTED_INPUT_OR_TESTED_SOURCE_CHANGED')
        report={'status':'ENGINEERING_K0_ORCHESTRATION_PASS','scope':'EIGHT_NODE_FIXTURE_AND_NEGATIVE_CONTROLS',
            'studies':reports,'six_point_replay_PASS':True,'uncapped_budget_prefix_preserved':True,
            'solver_unknown_distinct_from_inventory_unknown':True,'timeout_caught':True,
            'unapproved_natural_no_workers':True,'spawned_processes':len(process_reports),
            'all_spawned_children_joined':True,'no_retries':True,
            'frozen_contract_modified':False,'full_natural_K0_executed':False,'Gate_K0_PASS':False,
            'K_star_selected':False,'registered_experiment_started':False,'wall_s':time.perf_counter()-start}
        rc=0
    except Exception as exc:
        report={'status':'ENGINEERING_K0_ORCHESTRATION_FAIL_STOP','exception_type':type(exc).__name__,
            'message':str(exc),'studies_completed':reports,'wall_s':time.perf_counter()-start,
            'K_star_selected':False,'registered_experiment_started':False}
        write_new_json(out/'failure_summary.json',report);rc=1
    write_new_json(out/'report.json',report)
    write_new_json(out/'artifact_hashes.json',{p.relative_to(out).as_posix():file_sha256(p)
        for p in out.rglob('*') if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out),'registered_experiment_started':False},indent=2))
    return rc


if __name__=='__main__':raise SystemExit(main())
