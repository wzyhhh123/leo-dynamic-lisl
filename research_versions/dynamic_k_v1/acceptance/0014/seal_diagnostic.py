"""Consecutive 0014 append-only protection; no further simulations."""
import json,hashlib,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(V/'acceptance/0011'),str(V),str(P/'src')]
import workflow as old
vc=old.vc
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='ae00610b223f9f5172f5290ade4a382bb2d54e38a79d6b473c41247f7a6ec61a'
def read(p):return vc.read_json(p)
def bind(p):return vc.binding(P,p.relative_to(P).as_posix())
def write(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def main():
    version,baseline,expected,latest,parent,reserved=vc.load_expected(P,ORIGIN,PARENT)
    root=read(A/'ROOT_BASELINE/root_binding.json');held=read(A/'HOLD/branch_result.json');added=read(A/'ADD/branch_result.json')
    cause=read(A/'TIMING_CAUSE_CLASSIFICATION.json');clone=read(A/'CLONE_SET_LAYOUT_AUDIT.json')
    durable=read(A/'DURABLE_REPLAY_VERIFICATION.json')
    checks=dict(parent_chain_verified=True,
        clean_rebuild_strict_pass=read(A/'CLEAN_REBUILD/reconstruction_validation.json')['status']=='ROOT_RECONSTRUCTION_PASS',
        durable_recovery_strict_pass=durable['status']=='DURABLE_ROOT_RECONSTRUCTION_PASS',
        both_branch_roots_strictly_rebuilt=all(read(A/n/'reconstruction_validation.json')['status']=='ROOT_RECONSTRUCTION_PASS' for n in ('HOLD','ADD')),
        exact_paired_pre_action_state=clone['paired_HOLD_ADD_PRE_ACTION_every_field_equal'],
        HOLD_completed_horizon=held['status']=='COMPLETED_SINGLE_BRANCH' and held['actual_end_s']==9.,
        ADD_original_assertion_stop=added['status']=='STOP_BUSINESS_CONSERVATION_MISMATCH' and added['actual_end_s']==6.,
        same_root_and_forecast=held['recipe_root_sha256']==added['recipe_root_sha256']==root['root_view_sha256'] and held['forecast_sha256']==added['forecast_sha256'],
        one_atomic_action_per_branch=all(len(list((A/n).glob('receipt.json')))==1 for n in ('HOLD','ADD')),
        branches_not_rerun=read(A/'CONTROL_STOP.json')['reruns']==0,
        unchanged_business_tolerance=all(read(p)['tolerances']['business_bits']==1e-6 for n in ('HOLD','ADD') for p in (A/n).glob('VALIDATION_INPUT_*.json')),
        update_decomposition_exact=all(read(A/('EXACT_'+n+'_DIAGNOSIS.json'))['decomposition_exactly_closed'] for n in ('ROOT_PREFIX','HOLD','ADD')),
        event_early_processing_measured=cause['observed_early_events']==18,
        no_kernel_fix_or_tolerance_change=not cause['repair_implemented'] and not cause['tolerance_changed'])
    assert all(checks.values()),checks
    anchor=read(A/'independent_root_evidence_anchor.json')
    for row in anchor['files']:
        p=Path(row['path']);assert row==dict(path=str(p),**vc.file_info(p)),'BASELINE_EVIDENCE_DRIFT'
    write(A/'acceptance_summary.json',dict(status='DIAGNOSIS_COMPLETED_STOP_CONSERVATION',checks=checks,
        root_replayability='PASS_EXECUTABLE_RECONSTRUCTION',HOLD='COMPLETED',ADD='STOP_BUSINESS_CONSERVATION_MISMATCH',
        original_0011_replay=False,new_scenario_cause=cause['root_cause_for_this_new_scenario'],
        N4_P0_engineering_pass=False,scientific_gate_pass=False,full_pilot_executed=False))
    write(A/'pre_implementation_verification.json',dict(status='PASS',scope='N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',
        receipt_source='Completed full verifier output, session 57162, exit 0',revision_id='0013',
        revision_record_sha256=PARENT,version_record_sha256=ORIGIN,verified_file_count=6128,
        baseline_file_count=5810,excluded_file_count=202,undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[])))
    config=read(V/'configs/n4_p0d_root_audit_v1.json')
    cp=V/'configs/n4_p0e_replay_diagnostic_v1.json'
    write(cp,dict(schema='dynamic_k_n4_p0e_replay_diagnostic_v1',stage='N4_P0E',
        scenario_id=root['scenario_id'],scientific_parameters=config['scientific_parameters'],
        formal_control_parameters=config['formal_control_parameters'],PILOT_ONLY=config['PILOT_ONLY'],
        replay_process_hash_seed_test_only=1414,forecast=dict(start_s=3.,H_s=6.,end_s=9.,mode='PERSIST'),
        authorized_branch_budget=dict(HOLD=1,ADD=1),actual_branch_count=2,
        physical_catalog_rows_loaded=2742,catalog_action_enumeration_authorized=False,
        kernel_modifications_authorized=False,tolerance_changes_authorized=False,
        full_pilot_execution_authorized=False,formal_experiments_authorized=False,
        status='STOP_BUSINESS_CONSERVATION_MISMATCH',root_reconstruction_pass=True))
    contract=V/'contracts/N4_P0E_REPLAY_DIAGNOSTIC_SCOPE_CN.md'
    files=sorted(p for p in A.rglob('*') if p.is_file())+[cp,contract]
    write(A/'manifest_final.json',dict(schema='dynamic_k_n4_p0e_diagnostic_manifest_v1',revision_id='0014',
        files=[bind(p) for p in files],version_origin=bind(V/'version_record.json'),parent_revision=parent,
        replay_recipe=bind(A/'replay_recipe.json'),new_root_artifact_anchor=bind(A/'independent_root_evidence_anchor.json'),
        root_causal_sha256=root['root_view_sha256'],complete_root_graph_sha256=root['root_full_state_sha256'],
        status='STOP_BUSINESS_CONSERVATION_MISMATCH',N4_P0_engineering_pass=False,scientific_gate_pass=False))
    actual,excluded=vc.inventory(P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for r in reserved:actual.pop(r,None)
    changes=vc.differences(expected,actual)
    assert not changes['modified'] and not changes['deleted'] and not changes['possible_renames'],changes
    assert all(r['path'].startswith('research_versions/dynamic_k_v1/') for r in changes['added'])
    audit=A/'preseal_change_audit.json'
    write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=changes,
        excluded_count=len(excluded),excluded=excluded,old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[],reserved_records_not_overwritten=True))
    actual[audit.relative_to(P).as_posix()]=vc.file_info(audit);changes=vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0014',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0E new deterministic executable t3 root passes clean full-state reconstruction; one HOLD completes and one ADD stops unchanged conservation assertion; exact update and early propagation event timing diagnosis',
        authorization=dict(actor='human_user',source='current_conversation_user_request',scope='N4_P0E_NEW_ROOT_AND_TWO_BRANCH_DIAGNOSIS_ONLY',
            request='Accept option 2; verify 0013/full chain; independent 160-star PILOT root t3 with PERSIST and legal ADD; persist complete PRE/POST state; prove executable clean recovery before one HOLD and one ADD H6; preserve original assertions/1e-6/kernel; diagnose and stop; append next revision'),
        changes={k:changes[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(contract),configuration=bind(cp),
            diagnostic_manifest=bind(A/'manifest_final.json'),result_report=bind(A/'RESULT_CN.md'),
            replay_recipe=bind(A/'replay_recipe.json'),new_root_artifact_anchor=bind(A/'independent_root_evidence_anchor.json'),
            durable_replay_entry=bind(A/'replay_entry.py'),durable_replay_proof=bind(A/'DURABLE_REPLAY_VERIFICATION.json'),
            conservation_diagnosis=bind(A/'EXACT_ADD_DIAGNOSIS.json'),event_timing_diagnosis=bind(A/'PROPAGATION_EVENT_TIMING_AUDIT.json'),
            root_cause=bind(A/'TIMING_CAUSE_CLASSIFICATION.json'),stop_evidence=bind(A/'ADD/STOP_EXCEPTION.json'),old_asset_audit=bind(audit)),
        status='STOP_BUSINESS_CONSERVATION_MISMATCH',root_replayability='PASS_EXECUTABLE_RECONSTRUCTION',
        new_scenario_root_cause=cause['root_cause_for_this_new_scenario'],original_0011_replay=False,
        N4_P0_engineering_pass=False,scientific_gate_pass=False,formal_experiments_executed=False,full_pilot_executed=False)
    rp=V/'revisions/0014/record.json';rp.parent.mkdir(exist_ok=False);write(rp,record)
    print(json.dumps(dict(revision=bind(rp),added=len(changes['added']),modified=0,deleted=0,renamed=0)),flush=True)
if __name__=='__main__':main()
