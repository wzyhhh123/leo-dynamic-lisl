"""Append 0019 static/short-diagnostic evidence; no simulation imports."""
import importlib.util
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta

A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='c5c293b54f0eaf7b74c45effce6a8eafe6d39a4246f4c4b3e79b60b98f2eba4f'
spec=importlib.util.spec_from_file_location('diagnostic_0019_vc',V/'tools/version_control_readme_v1.py')
vc=importlib.util.module_from_spec(spec);spec.loader.exec_module(vc)
def write(p,value):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def bind(p):return vc.binding(P,Path(p).relative_to(P).as_posix())
def main():
    version,base,expected,latest,parent,reserved=vc.load_expected(P,ORIGIN,PARENT)
    assert latest['revision_id']=='0018'
    for row in vc.read_json(A/'AUDIT_INPUT_MANIFEST.json')['files']:
        assert bind(P/row['path'])==row, row
        if row['path'] not in reserved:
            assert expected[row['path']]=={k:row[k] for k in ('byte_count','sha256')}
    watchdog=vc.read_json(A/'WATCHDOG_RESULT.json')
    assert watchdog['status']=='COMPLETED' and watchdog['elapsed_wall_s']<60 and watchdog['child_launch_count']==1
    evidence=vc.read_json(A/'COST_EVIDENCE.json')
    assert len(evidence['controlled_diagnostic']['rows'])==13
    assert evidence['bounds']['full_BBM_reruns']==evidence['bounds']['physical_root_runs']==0
    assert evidence['controlled_diagnostic']['source_sha256']==vc.file_info(V/'runtime/n1b_fifo.py')['sha256']
    for p in A.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    config=V/'configs/n4_p0i_fifo_diagnostic_v1.json'
    cfg=vc.read_json(config)
    assert all(x is None for x in cfg['scientific_parameters'].values())
    assert all(x is None for x in cfg['formal_control_parameters'].values())
    assert cfg['historical_PILOT_ONLY_background']['decision_cadence_s']==3
    assert cfg['historical_PILOT_ONLY_background']['main_pilot_branch_upper_bound']==840
    contract=V/'contracts/N4_P0I_0019_FIFO_DIAGNOSTIC_SCOPE_CN.md'
    write(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0018',
        revision_record_sha256=PARENT,version_record_sha256=ORIGIN,baseline_file_count=5810,
        verified_file_count=6557,excluded_file_count=202,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        source='Complete raw-byte version verifier session33080 exit0 before any0019 file writes'))
    files=sorted(p for p in A.rglob('*') if p.is_file())+[config,contract]
    write(A/'manifest_final.json',dict(schema='dynamic_k_0019_fifo_diagnosis_manifest_v1',revision_id='0019',
        parent_revision=parent,version_origin=bind(V/'version_record.json'),files=[bind(p) for p in files],
        status='DIAGNOSTIC_COMPLETE_ONLY',runtime_changed=False,optimization_implemented=False,
        physical_root_runs=0,prediction_branch_runs=0,short_diagnostic_process_runs=1,
        full_N4_P0_engineering_pass=False))
    actual,excluded=vc.inventory(P,progress=lambda p:print(p,flush=True))
    for p in reserved:actual.pop(p,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(x['path'].startswith('research_versions/dynamic_k_v1/') for x in diff['added'])
    audit=A/'preseal_change_audit.json'
    write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded=excluded,excluded_count=len(excluded),old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[]))
    actual[audit.relative_to(P).as_posix()]=vc.file_info(audit);diff=vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0019',
        parent_record=parent,created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0I FIFO cost diagnosis only: sealed0016-0018 evidence, one 60s-hard-stop synthetic count process, exact control/counter field checks; distinguish measured cost, structural counts and unknown BBM peak/lifetime counts; design sweep/index but do not implement or integrate0018 Gate C',
        authorization=dict(actor='human_user',source='current_conversation_user_request',scope='N4_P0I_FIFO_COST_DIAGNOSIS_ONLY',
            request='Verify0018 fullchain; prioritize sealed evidence; permit one independent readonly lightweight diagnosis at most60s; no1100s BBM rerun, frozen kernel or FIFO changes, approximation, cohort cleanup, tolerance changes, MPC changes, fullcatalog/epoch/pilots/training; append0019 and STOPreview'),
        changes={k:diff[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(contract),configuration=bind(config),
            implementation_manifest=bind(A/'manifest_final.json'),result_report=bind(A/'RESULT_CN.md'),
            cost_evidence=bind(A/'COST_EVIDENCE.json'),inputs=bind(A/'AUDIT_INPUT_MANIFEST.json'),
            validation=bind(A/'DIAGNOSTIC_VALIDATION.json'),old_asset_audit=bind(audit),
            watchdog=bind(A/'WATCHDOG_RESULT.json'),raw_short_counts=bind(A/'DIAGNOSTIC_PROGRESS.jsonl'),
            attribution=bind(A/'FIFO_COST_ATTRIBUTION_CN.md'),decision=bind(A/'EXACT_OPTIMIZATION_DECISION_CN.md')),
        status='DIAGNOSTIC_COMPLETE_ONLY',retained_prior_status='STOP_CATALOG_300S_HARD_LIMIT',
        full_N4_P0_engineering_pass=False,scientific_gate_pass=False,formal_experiments_executed=False,
        optimization_implemented=False,short_diagnostic_process_runs=1,physical_root_runs=0,prediction_branch_runs=0,
        new_regression_runs=0,production_code_modified=False,history_modified=False,
        BBM_complete_cost_attribution='UNRESOLVED_NO_PEAK_LIFETIME_COUNTERS',
        recommendation='WORTH_BOUNDED_EXACT_SWEEP_INDEX_PROOF_NOT_PROVEN_FULL_BBM_SPEEDUP')
    path=V/'revisions/0019/record.json';path.parent.mkdir(exist_ok=False);write(path,record)
    print(json.dumps(dict(revision=bind(path),added=len(diff['added']),modified=0,deleted=0,renamed=0)),flush=True)

if __name__=='__main__':main()
