"""Append-only N4-P0D reports/asset checks and consecutive revision seal."""
import json,hashlib
from datetime import datetime,timezone,timedelta
import root_audit as w
def bind(p):return w.vc.binding(w.P,p.relative_to(w.P).as_posix())
def main():
    a=w.A;v=w.V
    stop=w.vc.read_json(a/'root_comparison_stop.json');summary=w.vc.read_json(a/'actual_root_summary.json')
    diff=w.vc.read_json(a/'ROOT_RECONSTRUCTION_DIFF.json')
    evidence=diff['stage_adjusted_audit_comparison']
    inventory=w.vc.read_json(a/'historical_evidence_inventory.json')
    terminal=w.vc.read_json(a/'terminal_event_and_energy_prefix_evidence.json')
    checks=dict(parent_full_verification_pass=True,
        preimage_raw_sha256_matches_actual=hashlib.sha256((a/'actual_root_hash_preimage.json').read_bytes()).hexdigest()==summary['actual_sha256'],
        independent_expected_anchor_unchanged=stop['expected_sha256']==w.ROOT,
        strict_mismatch_preserved=stop['status']=='STOP_ROOT_BINDING_MISMATCH' and summary['actual_sha256']!=w.ROOT,
        one_new_root_only=stop['root_constructions']==1,
        no_control_action_or_prediction=stop['add_submissions']==stop['prediction_branches']==0,
        exact_t3_stop=summary['simulated_until_s']==3.,
        observation_prefix_equal=evidence['observation_prefix_exact_equal'],
        known_scalar_business_state_equal=evidence['raw_A_Q_I_D_at_last_t3_interval_exact_equal'],
        same_stage_audit_multiset_equal=evidence['historical_prefix_exact_multiset_equal'],
        same_stage_audit_order_difference=not evidence['historical_prefix_exact_order_equal'],
        post_submit_envelope_difference_explained=evidence['bound_after_offline_stage_adjustment_exact_equal'],
        initial_terminal_history_equal=terminal['terminal_history_before_t3_exactly_equals_new_root_history'],
        original_forecast_and_physical_digest_equal=evidence['forecast_digest_exact_equal'] and evidence['physical_input_digest_exact_equal'],
        no_original_native_checkpoint_or_preimage_in_inventory=not inventory['native_checkpoint_file_extensions'] and
            not any('state_json' in x['path'] for r in inventory['acceptance_0011_files'] for x in r.get('relevant_fields',[])),
        original_replay_not_claimed=not stop['original_failure_reproduced'])
    assert all(checks.values()),checks
    for row in inventory['source_bindings']+inventory['physical_input_bindings']:
        assert bind(w.P/row['path'])==row
    w.write('read_only_audit_checks.json',dict(status='PASS_SAVED_ARTIFACT_CHECKS_ONLY',checks=checks,
        new_engine_test_runs=0,old_regression_runs=0,N4_P0_engineering_pass=False,root_cause='UNRESOLVED'))
    w.write('pre_implementation_verification.json',dict(status='PASS',scope='N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',
        receipt_source='Transcribed completed version_control_readme_v1.py verify tool output, session 52641, exit 0',
        version_record_sha256=w.ORIGIN,revision_record_sha256=w.PARENT,revision_id='0012',
        verified_file_count=6105,baseline_file_count=5810,excluded_file_count=202,
        undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),scientific_gate_pass=False))
    old=w.read(v/'configs/n4_p0c_diagnostic_v1.json')
    config=dict(schema='dynamic_k_n4_p0d_root_audit_v1',stage='N4_P0D',scope='ROOT_PROVENANCE_ONLY',
        scientific_parameters=old['scientific_parameters'],formal_control_parameters=old['formal_control_parameters'],
        PILOT_ONLY=old['PILOT_ONLY'],pilot_values_context_only_not_executed=True,
        allowed_root_constructions=1,root_time_s=3.,expected_root_sha256=w.ROOT,
        prediction_authorized=False,actions_authorized=False,second_root_authorized=False,
        full_catalog_diagnostic_authorized=False,full_pilot_execution_authorized=False,
        formal_experiments_authorized=False,kernel_modifications_authorized=False,
        tolerance_changes_authorized=False,hash_normalization_changes_authorized=False,
        status=stop['status'],conservation_root_cause='UNRESOLVED')
    assert all(x is None for x in config['scientific_parameters'].values())
    cp=v/'configs/n4_p0d_root_audit_v1.json'
    with cp.open('x',encoding='utf-8',newline='\n') as f:json.dump(config,f,sort_keys=True,indent=2);f.write('\n')
    contract=v/'contracts/N4_P0D_ROOT_PROVENANCE_SCOPE_CN.md'
    version,baseline,expected,latest,parent,reserved=w.vc.load_expected(w.P,w.ORIGIN,w.PARENT)
    files=[p for p in sorted(a.iterdir()) if p.is_file()]+[cp,contract]
    w.write('manifest_final.json',dict(schema='dynamic_k_n4_p0d_root_audit_manifest_v1',revision_id='0013',
        files=[bind(p) for p in files],version_origin=dict(path='research_versions/dynamic_k_v1/version_record.json',
            **w.vc.file_info(v/'version_record.json')),parent_revision=parent,
        stored_failure_evidence=[w.bound(v/'acceptance/0011'/n) for n in ('conservation_failure_original_attempt02.json',
            'conservation_failure_handle_attempt02.json','conservation_failure_comparison_attempt02.json')],
        status=stop['status'],decision='OPTION_2_ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE',
        original_expected_root_sha256=w.ROOT,actual_diagnostic_root_sha256=summary['actual_sha256'],
        N4_P0_engineering_pass=False,scientific_gate_pass=False))
    actual,excluded=w.vc.inventory(w.P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for r in reserved:actual.pop(r,None)
    changes=w.vc.differences(expected,actual)
    assert not changes['modified'] and not changes['deleted'] and not changes['possible_renames'],changes
    assert all(r['path'].startswith('research_versions/dynamic_k_v1/') for r in changes['added'])
    w.write('preseal_change_audit.json',dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',
        changes_before_audit_creation=changes,excluded_count=len(excluded),excluded=excluded,
        old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[],reserved_records_not_overwritten=True))
    ap=a/'preseal_change_audit.json';actual[ap.relative_to(w.P).as_posix()]=w.vc.file_info(ap)
    changes=w.vc.differences(expected,actual);now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0013',
        parent_record=parent,created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0D original root fingerprint provenance and offline stage-aware diff; one t3 diagnostic mismatched; original native root not recoverable',
        authorization=dict(actor='human_user',source='current_conversation_user_request',scope='N4_P0D_ROOT_PROVENANCE_ONLY',
            request='Verify independent origin/0012/full chain; audit original 0011 root evidence; one read-only new t3 root with pre-assert evidence; stop mismatch; no action, prediction, frozen core, tolerance or hash-anchor changes; append 0013'),
        changes={k:changes[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(contract),configuration=bind(cp),
            diagnostic_manifest=bind(a/'manifest_final.json'),result_report=bind(a/'RESULT_CN.md'),
            root_provenance=bind(a/'ROOT_HASH_PROVENANCE_CN.md'),root_diff=bind(a/'ROOT_RECONSTRUCTION_DIFF.json'),
            replayability_decision=bind(a/'ROOT_REPLAYABILITY_DECISION_CN.md'),stop_evidence=bind(a/'root_comparison_stop.json'),
            raw_hash_preimage=bind(a/'actual_root_hash_preimage.json'),old_asset_audit=bind(ap)),
        status='STOP_ROOT_BINDING_MISMATCH',native_root_recoverability='ORIGINAL_NATIVE_ROOT_NOT_RECOVERABLE',
        conservation_root_cause='UNRESOLVED',N4_P0_engineering_pass=False,N4_P0R_engineering_pass=False,
        scientific_gate_pass=False,formal_experiments_executed=False,full_pilot_executed=False)
    rp=v/'revisions/0013/record.json';rp.parent.mkdir(exist_ok=False)
    with rp.open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(dict(revision=bind(rp),added=len(changes['added']),modified=0,deleted=0,renamed=0)),flush=True)
if __name__=='__main__':main()
