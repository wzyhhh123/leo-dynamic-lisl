"""Consecutive limited engineering seal; never runs forecasts or catalog scans."""
from datetime import datetime,timezone,timedelta
import support18 as s
def main():
    v,base,expected,latest,parent,reserved=s.vc.load_expected(s.P,s.ORIGIN,s.PARENT)
    assert latest['revision_id']=='0017'
    evidence=['CORRECTNESS_ACCEPTANCE_TUPLE.json','REJECTION_COVERAGE_TUPLE.json','ROLLBACK_AND_TAMPER_FINAL.json',
        'TERMINAL_LIFECYCLE_ENERGY_TUPLE.json','DISJOINT_STAGE_PROFILE.json','REGRESSION_ACCEPTANCE.json','PAIRED_COST_TUPLE.json']
    for name in evidence:assert s.vc.read_json(s.A/name)['status'].startswith('PASS'),name
    costs=s.vc.read_json(s.A/'PAIRED_COST_TUPLE.json');assert costs['plain_total_speed_ratio']>1.
    assert costs['plain_validate_calls']==42 and costs['profiled_validate_calls']==14
    for row in s.vc.read_json(s.A/'SEAM_SOURCE_MANIFEST_TUPLE.json')['files']:assert s.bind(s.P/row['path'])==row
    cfg=s.V/'configs/n4_p0h_structural_seam_v1.json';contract=s.V/'contracts/N4_P0H_0018_GATE_C_STRUCTURAL_SEAM_SCOPE_CN.md'
    doc=s.vc.read_json(cfg)
    assert all(x is None for x in doc['scientific_parameters'].values())
    assert all(x is None for x in doc['formal_control_parameters'].values())
    s.write('pre_implementation_verification.json',dict(status='PASS',revision_id='0017',revision_sha256=s.PARENT,
        version_record_sha256=s.ORIGIN,verified_file_count=6478,baseline_file_count=5810,excluded_file_count=202,
        source='Complete read-only verifier session 37827 exit0 before 0018 writes',undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[])))
    status='PASS_LIMITED_P0H_GATE_C_ENGINEERING_ONLY'
    s.write('acceptance_summary.json',dict(status=status,selected_runtime='runtime/n4_p0h_gate_c_final.py',
        synthetic_paired_cases=29,real160_paired_candidates=7,real160_paired_atomic_actions=5,
        isolated_terminal_lifecycle_energy_cases=6,rollback_and_tamper='PASS',
        plain_total_ratio=costs['plain_total_speed_ratio'],plain_original_s=costs['plain_original_total_s'],
        plain_optimized_s=costs['plain_optimized_total_s'],cold_install_s=costs['install_and_clone_s'],
        cold_install_batch_net_gain=False,full_catalog_under_300s=None,
        history_scope='ONE_ROOT_EXPLICIT_REBIND_REQUIRED_AFTER_LOG_CHANGE',
        full_N4_P0_engineering_pass=False,scientific_gate_pass=False,FIFO_optimized=False,
        full_catalog_enumerated=False,real160_MPC_forecast_branches=0,full_pilot_executed=False,
        frozen_source_changes=0,tests=s.vc.read_json(s.A/'REGRESSION_ACCEPTANCE.json')))
    files=sorted(p for p in s.A.rglob('*') if p.is_file())+[cfg,contract,s.V/'runtime/n4_p0h_gate_c.py',s.V/'runtime/n4_p0h_gate_c_final.py']
    s.write('manifest_final.json',dict(schema='dynamic_k_p0h_limited_gate_c_seam_manifest_v1',revision_id='0018',
        parent_revision=parent,version_origin=s.bind(s.V/'version_record.json'),files=[s.bind(p) for p in files],
        selected_runtime=s.bind(s.V/'runtime/n4_p0h_gate_c_final.py'),source_binding=s.bind(s.A/'SEAM_SOURCE_MANIFEST_TUPLE.json'),
        status=status,prototype_results_retained=True,full_N4_P0_engineering_pass=False,
        frozen_contracts_tests_results_sources_changed=False))
    actual,excluded=s.vc.inventory(s.P,progress=lambda p:print(p,flush=True))
    for p in reserved:actual.pop(p,None)
    diff=s.vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(x['path'].startswith('research_versions/dynamic_k_v1/') for x in diff['added'])
    audit=s.A/'preseal_change_audit.json'
    s.w.write(audit,dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded=excluded,excluded_count=len(excluded),old_assets_modified=[],old_assets_deleted=[],old_assets_renamed=[]))
    actual[audit.relative_to(s.P).as_posix()]=s.vc.file_info(audit);diff=s.vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0018',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0H explicit Gate C structural-copy seam with shared native immutable history values and independent views; all original physics/transactions/FIFO retained; bounded equivalence/rollback/tamper/lifecycle tests and upstream regressions pass; warm sample improvement observed, cold batch no net gain; no full catalog, true160 forecast or epoch',
        authorization=dict(actor='human_user',source='current_conversation_user_request',scope='N4_P0H_LIMITED_STRUCTURAL_COPY_EQUIVALENCE_AND_BOUNDED_PERFORMANCE',
            request='Verify 0017 chain/frozen assets; measure finite representative Gate C copy/log/transaction stages; isolated immutable-history structural-copy seam only; strict physical/state/log/ready/release/rollback/tamper equivalence; bounded same-root paired timings and regressions; no FIFO optimization/kernel edits/full catalog/epoch/pilot; append0018 and stop'),
        changes={k:diff[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=v['baseline_seal'],contract=s.bind(contract),configuration=s.bind(cfg),
            implementation_manifest=s.bind(s.A/'manifest_final.json'),result_report=s.bind(s.A/'RESULT_CN.md'),
            source_binding=s.bind(s.A/'SEAM_SOURCE_MANIFEST_TUPLE.json'),selected_runtime=s.bind(s.V/'runtime/n4_p0h_gate_c_final.py'),
            source_diff=s.bind(s.A/'MINIMAL_CONNECT_DIFF.patch'),sharing_audit=s.bind(s.A/'SHARING_AUDIT.json'),
            baseline_cost=s.bind(s.A/'BASELINE_COST.json'),paired_cost=s.bind(s.A/'PAIRED_COST_TUPLE.json'),
            stage_profile=s.bind(s.A/'DISJOINT_STAGE_PROFILE.json'),equivalence=s.bind(s.A/'CORRECTNESS_ACCEPTANCE_TUPLE.json'),
            rollback_tamper=s.bind(s.A/'ROLLBACK_AND_TAMPER_FINAL.json'),regressions=s.bind(s.A/'REGRESSION_ACCEPTANCE.json'),old_asset_audit=s.bind(audit)),
        status=status,full_N4_P0_engineering_pass=False,scientific_gate_pass=False,formal_experiments_executed=False,
        full_pilot_executed=False,production_code_modified=False,history_modified=False,
        full_catalog_enumerated=False,FIFO_optimized=False,retained_prior_status='STOP_CATALOG_300S_HARD_LIMIT')
    p=s.V/'revisions/0018/record.json';p.parent.mkdir(exist_ok=False);s.w.write(p,record)
    print(dict(revision=s.bind(p),added=len(diff['added']),modified=0,deleted=0,renamed=0),flush=True)
if __name__=='__main__':main()
