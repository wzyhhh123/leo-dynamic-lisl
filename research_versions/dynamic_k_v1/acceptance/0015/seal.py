"""Append-only consecutive 0015 seal, no additional experimental runs."""
import json
from datetime import datetime,timezone,timedelta
import support as w
def bind(p):return w.vc.binding(w.P,p.relative_to(w.P).as_posix())
def main():
    v,base,expected,latest,parent,reserved=w.vc.load_expected(w.P,w.ORIGIN,w.PARENT)
    checks=w.vc.read_json(w.A/'FINAL_EVIDENCE_CHECKS.json')
    assert checks['status']=='PASS_N4_P0F_ISOLATED_EVENT_SEMANTICS_ONLY'
    assert all(w.vc.read_json(w.A/n/'branch_result.json')['status']=='PASS_SINGLE_BRANCH' for n in ('HOLD','ADD'))
    assert w.vc.read_json(w.A/'ORIGINAL_0014_RECONSTRUCTION.json')['status']=='DURABLE_ROOT_RECONSTRUCTION_PASS'
    assert w.vc.read_json(w.A/'CLEAN_REBUILD/reconstruction.json')['status']=='PASS'
    root=w.vc.read_json(w.A/'ROOT_BASELINE/root_binding.json')
    cfg=w.vc.read_json(w.V/'configs/n4_p0e_replay_diagnostic_v1.json')
    cp=w.V/'configs/n4_p0f_isolated_event_timing_v1.json'
    w.write(cp,dict(schema='dynamic_k_n4_p0f_event_timing_engineering_v1',stage='N4_P0F',
        scientific_parameters=cfg['scientific_parameters'],formal_control_parameters=cfg['formal_control_parameters'],
        PILOT_ONLY=cfg['PILOT_ONLY'],process_hashseed_test_only=1414,
        engine_variant='runtime.n4_p0f_events.ExactObservedD2Engine',semantic_version='P0F_EXACT_NOMINAL_V1',
        action_execution='UNCHANGED_N2_ATOMIC',fifo='UNCHANGED_NODE_LOCAL_PER_COMMODITY_FIFO',
        business_tolerance_bits=1e-6,root_time_s=3.,prediction_end_s=9.,
        actual_real160_branches=dict(HOLD=1,ADD=1),catalog_enumeration_executed=False,
        global_monkeypatch=False,legacy_kernel_overwritten=False,full_N4_P0_engineering_pass=False,
        formal_experiments_authorized=False,full_pilot_execution_authorized=False,
        status='PASS_N4_P0F_ISOLATED_ENGINEERING_ONLY'))
    assert all(x is None for x in cfg['scientific_parameters'].values())
    contract=w.V/'contracts/N4_P0F_ISOLATED_EVENT_TIMING_SCOPE_CN.md'
    w.write(w.A/'acceptance_summary.json',dict(status='PASS_N4_P0F_ISOLATED_ENGINEERING_ONLY',
        question_propagation_timing_correct='PASS_WITHIN_ANALYTIC_AND_160_STAR_SCOPE',
        question_original_failure_condition_ADD_completes='YES_VARIANT_3_TO_9_SECONDS',
        original_0014_failure_preserved=True,variant_root_complete_replay='PASS',
        tests=checks,full_N4_P0_engineering_pass=False,scientific_gate_pass=False,
        full_catalog_or_pilot_executed=False))
    files=sorted(p for p in w.A.rglob('*') if p.is_file())+[w.V/'runtime/n4_p0f_events.py',cp,contract]
    w.write(w.A/'manifest_final.json',dict(schema='dynamic_k_n4_p0f_isolated_event_variant_manifest_v1',revision_id='0015',
        files=[bind(p) for p in files],parent_revision=parent,version_origin=bind(w.V/'version_record.json'),
        new_root=root,variant_binding=bind(w.A/'variant_dependencies.json'),recipe=bind(w.A/'replay_recipe.json'),
        root_artifact_anchor=bind(w.A/'root_artifact_anchor.json'),status='PASS_N4_P0F_ISOLATED_ENGINEERING_ONLY',
        full_N4_P0_engineering_pass=False,scientific_gate_pass=False))
    actual,excluded=w.vc.inventory(w.P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for r in reserved:actual.pop(r,None)
    diff=w.vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(x['path'].startswith('research_versions/dynamic_k_v1/') for x in diff['added'])
    audit=w.A/'preseal_change_audit.json'
    w.write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded_count=len(excluded),excluded=excluded,old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[],
        reserved_records_not_overwritten=True))
    actual[audit.relative_to(w.P).as_posix()]=w.vc.file_info(audit);diff=w.vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0015',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0F isolated exact-nominal event timing variant; unchanged frozen originals; analytic/1-bit-loss and targeted regression pass; strict new root replay; HOLD and formerly failing ADD finish 3-to-9 forecast under original 1e-6-bit assertion',
        authorization=dict(actor='human_user',source='current_conversation_user_request',scope='N4_P0F_ISOLATED_NUMERICAL_EVENT_TIMING_ENGINEERING_ONLY',
            request='Verify 0014/full chain; no old frozen asset edits/global monkeypatch; audit all event time gates; independently bound minimal variant; analytic events/FIFO/loss negative; old root reconstruction; strict variant root replay; HOLD/ADD H6, all applicable regressions; preserve old failure and 1e-6; seal 0015 and stop'),
        changes={k:diff[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=v['baseline_seal'],contract=bind(contract),configuration=bind(cp),
            implementation_manifest=bind(w.A/'manifest_final.json'),result_report=bind(w.A/'RESULT_CN.md'),
            variant_source=bind(w.V/'runtime/n4_p0f_events.py'),variant_dependencies=bind(w.A/'variant_dependencies.json'),
            minimal_diff=bind(w.A/'MINIMAL_SOURCE_DIFF.json'),replay_recipe=bind(w.A/'replay_recipe.json'),
            replay_entry=bind(w.A/'replay_entry.py'),root_artifact_anchor=bind(w.A/'root_artifact_anchor.json'),
            root_reconstruction=bind(w.A/'CLEAN_REBUILD/reconstruction.json'),
            analytic_tests=bind(w.A/'analytic_tests.json'),HOLD_ADD_results=bind(w.A/'HOLD_ADD_RESULTS.json'),
            event_checks=bind(w.A/'FINAL_EVIDENCE_CHECKS.json'),old_asset_audit=bind(audit)),
        status='PASS_N4_P0F_ISOLATED_ENGINEERING_ONLY',full_N4_P0_engineering_pass=False,scientific_gate_pass=False,
        formal_experiments_executed=False,full_pilot_executed=False,original_0014_failure_preserved=True)
    path=w.V/'revisions/0015/record.json';path.parent.mkdir(exist_ok=False);w.write(path,record)
    print(json.dumps(dict(revision=bind(path),added=len(diff['added']),modified=0,deleted=0,renamed=0)),flush=True)
if __name__=='__main__':main()
