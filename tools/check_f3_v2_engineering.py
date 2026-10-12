# -*- coding: utf-8 -*-
"""New engineering attempts; canonical unittest CLI; no formal experiments."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT_ATTEMPT=ROOT/'outputs/f3_v2_engineering_20261008T125056_858471Z'
PLANNING_REVISION='outputs/f3_v2_october_plan_revision_20261008T134403_423422Z'
PLANNING_REPORT_HASH='e789776c6ea2172f629257f219b0743af832ad29cb38741da5d42f752af812db'
PLANNING_SEAL_HASH='9c44c5c980a490155c0fa5f5703c802d510bb4a2cb60a6c662ec1bcb017d1cc2'
PLANNING_REVISIONS=(
    (PLANNING_REVISION,PLANNING_REPORT_HASH,PLANNING_SEAL_HASH),
    ('outputs/f3_v2_october_completion_plan_20261008T164358_252159Z',
     '7a1a75f2152f88a4aa74394c6e24ef2c74359c5a20584814e495b948a26a3175',
     '24ce53f34d67e747ce00f20f99e9dcbdde22960e802c6f365d9a52b8a7848436'),
)
sys.path.insert(0,str(ROOT/'src'))


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def authorized_planning_revision(root,rel,parent_hash,current_hash):
    """Only the four planning files explicitly revised by the later user task.

    This is not a scientific/runtime successor authorization. Both the original
    and replacement bytes are pinned by immutable, separately hashed evidence.
    """
    allowed={'docs/F3_V2_OCTOBER_CRITICAL_PATH.md','configs/F3_V2_PAPER_EXPERIMENT_MATRIX_DRAFT.json',
             'configs/F3_V2_RUNTIME_BUDGET_PLAN.json','configs/F3_V2_OCTOBER_DELIVERABLES.json'}
    if rel not in allowed:return False
    # Only two explicit human-requested planning revisions. No discovery/glob,
    # implicit current-hash adoption, science or runtime successor permission.
    tail=parent_hash
    for revision,report_hash,seal_hash in PLANNING_REVISIONS:
        base=root/revision
        report=base/'planning_revision_report.json';seal=base/'artifact_hashes.json'
        if not report.is_file() or not seal.is_file():return False
        if sha(report)!=report_hash or sha(seal)!=seal_hash:return False
        try:
            data=json.loads(seal.read_text(encoding='utf-8'))
            state=json.loads(report.read_text(encoding='utf-8'))
        except (ValueError,OSError):return False
        saved=base/'prior_plan_bytes'/Path(rel).name
        if (state.get('status')!='PLAN_READY_FOR_CONSOLIDATED_HUMAN_REVIEW'
            or data.get('before',{}).get(rel)!=tail
            or not saved.is_file() or sha(saved)!=tail):return False
        tail=data.get('after',{}).get(rel)
        if not isinstance(tail,str):return False
        if tail==current_hash:return True
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',choices=('batch','structure','certified','evidence','worker','all'),required=True)
    parser.add_argument('--full-regression',action='store_true')
    args=parser.parse_args()
    out=ROOT/'outputs'/('f3_v2_engineering_check_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir()
    print(str(out),flush=True)
    env=dict(os.environ)
    env['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(ROOT/'tools')
    reports=[]
    patterns={'batch':['test_f3_v2_batch_executor.py'],
              'structure':['test_f3_v2_structural.py'],
              'certified':['test_f3_v2_certified_topology.py'],
              'evidence':['test_f3_v2_evidence_preflight.py'],
              'worker':['test_f3_v2_worker_failure.py'],
              'all':['test_f3_v2*.py']}[args.scope]
    if args.full_regression:patterns.append('*')
    for i,pattern in enumerate(patterns):
        command=[sys.executable,'-m','unittest','discover','-s','tests','-v']
        if pattern!='*':command+=['-p',pattern]
        start=time.perf_counter()
        proc=subprocess.run(command,cwd=ROOT,env=env,text=True,encoding='utf-8',errors='replace',capture_output=True)
        elapsed=time.perf_counter()-start
        (out/('test_%d_stdout.txt'%i)).write_text(proc.stdout,encoding='utf-8')
        (out/('test_%d_stderr.txt'%i)).write_text(proc.stderr,encoding='utf-8')
        count=re.findall(r'Ran (\d+) tests?',proc.stdout+'\n'+proc.stderr)
        record={'command':command,'cwd':str(ROOT),'returncode':proc.returncode,
                'wall_s':elapsed,'tests':int(count[-1]) if count else None,
                'scope':'FULL_REPOSITORY_REGRESSION' if pattern=='*' else pattern,
                'stdout_path':'test_%d_stdout.txt'%i,'stderr_path':'test_%d_stderr.txt'%i}
        reports.append(record)
        write(out/'test_execution_report.json',reports)
        print(json.dumps(record),flush=True)
        if proc.returncode!=0:break
    before=json.loads((PARENT_ATTEMPT/'historical_integrity_before.json').read_text(encoding='utf-8'))['files']
    changed=[];after={};planning_revisions=[]
    for rel,h in before.items():
        actual=sha(ROOT/rel) if (ROOT/rel).is_file() else None
        after[rel]=actual
        if actual!=h:
            row={'path':rel,'before':h,'after':actual}
            if authorized_planning_revision(ROOT,rel,h,actual):planning_revisions.append(row)
            else:changed.append(row)
    write(out/'historical_integrity_report.json',{'status':'FAIL' if changed else 'PASS',
         'protected_file_count':len(before),'changes':changed,'files_after':after,
         'authorized_planning_only_revisions':planning_revisions,
         'planning_revision_evidence':[r[0] for r in PLANNING_REVISIONS],
         'scientific_runtime_successors_added':False})
    inputs=['configs/gate_f3_v2_joint_action_contract_DRAFT.json',
            'configs/gate_f3_v2_execution_contract_DRAFT.json',
            'configs/gate_k0_contract_v1_1_DRAFT.json','configs/gate_k0_v1_2_batch_audit_proposal_DRAFT.json']
    code=list((ROOT/'src/dynamic_lisl/f3_v2').glob('*.py'))+list((ROOT/'tests').glob('test_f3_v2*.py'))+list((ROOT/'tools').glob('*f3_v2*.py'))
    write(out/'input_code_hashes.json',{'inputs':{r:sha(ROOT/r) for r in inputs},
             'code':{p.relative_to(ROOT).as_posix():sha(p) for p in code}})
    passed=not changed and all(r['returncode']==0 for r in reports) and all(r['tests'] for r in reports)
    report={'status':'ENGINEERING_PASS' if passed else 'FAIL_STOP','scope':args.scope,
            'scientific_contract_status':'DRAFT_NOT_FROZEN','registered_experiment_started':False,
            'K_star_selected':False,'full_regression_executed':args.full_regression,
            'test_reports':reports,'historical_integrity_pass':not changed,
            'historical_parent_attempt':str(PARENT_ATTEMPT),
            'B4_v2_engineering_PASS':False,'formal_preflight_READY':False}
    if passed and args.scope in ('batch','all'):
        # Small deterministic event evidence; never a registered run.
        sys.path.insert(0,str(ROOT/'tests'))
        from test_f3_v2_batch_executor import fixture
        from dynamic_lisl.f3_v2.batch_executor import AtomicBatchExecutor
        for name,modes in [('BBM4',('BBM',)*4),('MBB4',('MBB',)*4),('MIXED',('BBM','MBB','BBM','MBB'))]:
            ex,action,validator,_=fixture(modes)
            plan=validator.evaluate(ex,action)
            write(out/('batch_%s_validation.json'%name),plan.to_dict())
            commit=AtomicBatchExecutor(validator).commit(ex,plan)
            ex.advance(2)
            write(out/('batch_%s_event_evidence.json'%name),{'commit':commit,'terminal_log':ex.log,'final_state':ex.snapshot()})
        report['V2_A_B_C_synthetic_engineering']='PASS'
    write(out/'report.json',report)
    write(out/'artifact_hashes.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps({'status':report['status'],'output_dir':str(out),'registered_experiment_started':False},indent=2))
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
