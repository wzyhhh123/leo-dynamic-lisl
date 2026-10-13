"""Append-only 0016 seal after all authorized workers stop."""
from datetime import datetime,timezone,timedelta
import epoch_workflow as w
def main():
    small=w.vc.read_json(w.A/'SMALL_DOMAIN_ACCEPTANCE.json');assert small['status']=='PASS'
    reg=w.vc.read_json(w.A/'REGRESSION_ACCEPTANCE.json');assert reg['status']=='PASS_NO_NEW_FAILURES'
    epoch=w.A/'SINGLE_EPOCH_ACCEPTANCE.json'
    hard=w.A/'CATALOG_HARD_STOP.json';diag=w.A/'CATALOG_DIAGNOSIS.json'
    if epoch.exists():
        verdict=w.vc.read_json(epoch);assert verdict['status']=='PASS_SINGLE_T3_EPOCH_ZERO_PERSIST'
        status='PASS_SINGLE_T3_EPOCH_ENGINEERING_ONLY';complete=True
    else:
        verdict=w.vc.read_json(hard if hard.exists() else diag)
        assert verdict['status'].startswith('STOP_CATALOG')
        status=verdict['status'];complete=False
    v,base,expected,latest,parent,reserved=w.vc.load_expected(w.P,w.ORIGIN,w.PARENT)
    assert latest['revision_id']=='0015'
    old=w.vc.read_json(w.V/'configs/n4_p0f_isolated_event_timing_v1.json')
    assert all(x is None for x in old['scientific_parameters'].values())
    assert all(x is None for x in old['formal_control_parameters'].values())
    cp=w.V/'configs/n4_p0g_single_epoch_engineering_v1.json';contract=w.V/'contracts/N4_P0G_SINGLE_EPOCH_SCOPE_CN.md'
    w.write(cp,dict(schema='dynamic_k_n4_p0g_single_epoch_engineering_v1',stage='N4_P0_SINGLE_EPOCH_RESTORE',
        scientific_parameters=old['scientific_parameters'],formal_control_parameters=old['formal_control_parameters'],
        PILOT_ONLY=old['PILOT_ONLY'],numerical_semantics='P0F_EXACT_NOMINAL_V1',
        explicit_variant_binding=w.bind(w.V/'acceptance/0015/variant_dependencies.json'),
        parent_revision_sha256=w.PARENT,root_time_s=3.,prediction_end_s=9.,
        actual_small_branches=dict(PERSIST=['HOLD','ADD','DROP','BBM','MBB'],ZERO=['HOLD','ADD','DROP','BBM','MBB']),
        engineering_safety_limits=dict(this_PERSIST_BBM_wall_s=1800.,catalog_wall_s=300.),
        catalog_executed=True,decision_epoch_executed=complete,full_N4_P0_engineering_pass=complete,
        formal_experiments_authorized=False,full_pilot_execution_authorized=False,status=status))
    w.write(w.A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0015',
        revision_sha256=w.PARENT,origin_sha256=w.ORIGIN,verified_file_count=6355,
        baseline_file_count=5810,excluded_file_count=202,
        source='Initial complete read-only verifier session 58065, exit 0, before 0016 files created',
        current_parent_chain_rechecked=True))
    w.write(w.A/'acceptance_summary.json',dict(status=status,root_reconstruction='PASS_EXACT_0015',
        small_domain=small,catalog_evidence=w.bind(hard if hard.exists() else diag),
        complete_epoch=complete,epoch_selected_action=None if not complete else verdict['modes'],
        tests=reg,full_N4_P0_engineering_pass=complete,scientific_gate_pass=False,
        original_0014_failure_preserved=True,production_kernel_modified=False,
        all_safety_limits='ENGINEERING_ONLY_NOT_REALTIME_OR_SCIENCE'))
    files=sorted(p for p in w.A.rglob('*') if p.is_file())+[cp,contract]
    w.write(w.A/'manifest_final.json',dict(schema='dynamic_k_p0_single_epoch_manifest_v1',revision_id='0016',
        files=[w.bind(p) for p in files],parent_revision=parent,version_origin=w.bind(w.V/'version_record.json'),
        immutable_variant_source=w.bind(w.V/'runtime/n4_p0f_events.py'),
        immutable_variant_dependencies=w.bind(w.V/'acceptance/0015/variant_dependencies.json'),
        immutable_replay_recipe=w.bind(w.V/'acceptance/0015/replay_recipe.json'),
        root=w.vc.read_json(w.A/'SMALL_ROOT_RECONSTRUCTION.json'),status=status,full_N4_P0_engineering_pass=complete))
    actual,excluded=w.vc.inventory(w.P,progress=lambda p:print(p,flush=True))
    for r in reserved:actual.pop(r,None)
    diff=w.vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(r['path'].startswith('research_versions/dynamic_k_v1/') for r in diff['added'])
    audit=w.A/'preseal_change_audit.json'
    w.write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded_count=len(excluded),excluded=excluded,old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[]))
    actual[audit.relative_to(w.P).as_posix()]=w.vc.file_info(audit);diff=w.vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0016',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='Restore single-epoch acceptance with unchanged 0015 exact nominal event clock; exact root, ten real ZERO/PERSIST scores and observer instrumentation equality pass; complete catalog bounded diagnosis; preserve original failures and all physics/FIFO/energy assertions; result '+status,
        authorization=dict(actor='human_user',source='current_conversation_user_requests_and_async_reply',
            scope='N4_P0_SINGLE_EPOCH_ENGINEERING_RESTORE_WITH_BOUNDED_CATALOG_AND_BBM',
            request='Verify 0015/full chain; same isolated numerical semantics; small-domain all real scores before complete catalog; 300-second catalog cap; only then HOLD plus at most 6 non-HOLD epoch; retain history/1e-6/null science; this branch cumulative 30 minutes unfinished then STOP and seal partial evidence'),
        changes={k:diff[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=v['baseline_seal'],contract=w.bind(contract),configuration=w.bind(cp),
            implementation_manifest=w.bind(w.A/'manifest_final.json'),result_report=w.bind(w.A/'RESULT_CN.md'),
            root_reconstruction=w.bind(w.A/'SMALL_ROOT_RECONSTRUCTION.json'),small_domain=w.bind(w.A/'SMALL_DOMAIN_ACCEPTANCE.json'),
            score_rule_check=w.bind(w.A/'SCORING_RULE_0015_CHECK.json'),catalog=w.bind(hard if hard.exists() else diag),
            regressions=w.bind(w.A/'REGRESSION_ACCEPTANCE.json'),old_asset_audit=w.bind(audit)),status=status,
        full_N4_P0_engineering_pass=complete,scientific_gate_pass=False,formal_experiments_executed=False,
        full_pilot_executed=False,production_code_modified=False,history_modified=False)
    path=w.V/'revisions/0016/record.json';path.parent.mkdir(exist_ok=False);w.write(path,record)
    print(dict(revision=w.bind(path),added=len(diff['added']),modified=0,deleted=0,renamed=0),flush=True)
if __name__=='__main__':main()
