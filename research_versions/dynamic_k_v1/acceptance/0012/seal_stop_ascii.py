"""Seal a mandatory input-root STOP. Never reruns the failing constructor."""
import json
from datetime import datetime,timezone,timedelta
import audit_workflow as w

def bind(path):return w.vc.binding(w.P,path.relative_to(w.P).as_posix())
def md(name,text):
    with (w.A/name).open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
def main():
    scan=w.vc.read_json(w.A/'offline_saved_evidence_scan.json');first=scan['first_interval_over_N1a_threshold_exact_IEEE_state']
    # These are observations of the already-completed command, not a retry.
    w.write('stop_binding_evidence.json',dict(status='STOP_ROOT_BINDING_MISMATCH',expected_root_sha256=scan['root_sha256'],
        actual_root_sha256=None,actual_hash_capture='not persisted before assertion; do not invent it',
        command='D:/Program_Files/anaconda3/envs/pytorch/python.exe -B research_versions/dynamic_k_v1/acceptance/0012/run_diagnosis.py',
        exit_code=1,observed_assertion='ROOT_BINDING_MISMATCH',source_file='acceptance/0012/run_diagnosis.py',source_line=41,
        failure_at='run_case before writing root snapshot, cloning prediction branch or submitting action',
        fresh_failure_branch_replays=0,hold_controls=0,zero_controls=0,analytic_controls=0,
        frozen_inputs_modified=False,tolerances_modified=False,assertions_bypassed=False,reruns_after_mismatch=0))
    w.write('pre_implementation_verification.json',dict(status='PASS',scope='N0_FILE_INTEGRITY_AND_VERSION_BINDINGS_ONLY',
        version_record_sha256=w.ORIGIN,revision_record_sha256=w.PARENT,verified_file_count=6090,baseline_file_count=5810,
        excluded_file_count=202,undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
        source='actual complete independent verifier output before 0012 file creation'))
    cfg=w.vc.read_json(w.V/'configs/n4_p0r_engineering_v1.json')
    cfg.update(schema='dynamic_k_n4_p0c_diagnostic_v1',stage='N4_P0C',status='STOP_ROOT_BINDING_MISMATCH',
        diagnosis_only=True,kernel_modifications_authorized=False,tolerance_changes_authorized=False,
        full_epoch_authorized=False,formal_experiments_authorized=False)
    dest=w.V/'configs/n4_p0c_diagnostic_v1.json'
    with dest.open('x',encoding='utf-8',newline='\n') as f:json.dump(cfg,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n')
    w.write('acceptance_summary.json',dict(status='STOP_ROOT_BINDING_MISMATCH',root_cause='UNRESOLVED',
        full_version_precheck_pass=True,stored_original_handle_failure_records_exactly_equal=True,
        bound_saved_state_intervals_scanned=scan['interval_count'],first_threshold_interval=first,
        fresh_bound_failure_reproduction_pass=False,observer_runtime_validated=False,
        numeric_reference='exact Fraction of IEEE-754 binary values, not printed decimal as exact physical real',
        additional_kernel_authorization_needed='No implementation proposed until valid root and actual cause are established',
        N4_P0_engineering_pass=False,N4_P0R_engineering_pass=False,scientific_gate_pass=False,
        full_catalog_runs=0,main_pilot_runs=0,simulation_controls_executed=0))
    md('RESULT_CN.md',f'''# N4-P0C \u4e13\u9879\u8bca\u65ad\uff1aUNRESOLVED / STOP_ROOT_BINDING_MISMATCH

0011\u5b8c\u6574\u7248\u672c\u3001\u72ec\u7acb\u8d77\u70b9\u53ca\u7236\u94fe\u6821\u9a8cPASS\uff086090\u6587\u4ef6\uff0c\u65e7\u57fa\u7ebf5810\u6587\u4ef6\uff0c\u6392\u9664202\uff0c\u672a\u767b\u8bb0\u5dee\u5f020\uff09\u30020011\u539f\u8def\u5f84\u4e0eHandleReaderLease\u8def\u5f84\u4fdd\u5b58\u7684\u5931\u8d25\u72b6\u6001records\u5b8c\u5168\u76f8\u540c\uff0c\u539f\u6587\u4ef6\u539f\u59cb\u5b57\u8282\u7ed1\u5b9a\u5339\u914d\u3002

\u4f46\u672c\u8f6e\u91cd\u6784t=3 root\u65f6\uff0c\u5728run_diagnosis.py\u7b2c41\u884c\u672a\u5339\u914d\u5c01\u5b58root\u6307\u7eb9 `{scan['root_sha256']}`\uff0c\u62a5ROOT_BINDING_MISMATCH\u3002\u4e25\u683c\u6309\u4eba\u5de5\u505c\u6b62\u89c4\u5219\u505c\u6b62\uff0c\u6ca1\u6709\u63d0\u4ea4ADD\uff0c\u6ca1\u6709\u63a8\u8fdb\u65b0\u9884\u6d4b\u5206\u652f\uff0c\u6ca1\u6709\u6267\u884cHOLD/ZERO/\u89e3\u6790\u5bf9\u7167\u6216\u5b8c\u6574catalog\u3002\u8be5\u65ad\u8a00\u672a\u5728\u5931\u8d25\u524d\u4fdd\u5b58actual root SHA\uff0c\u672c\u8f6e\u4e0d\u586b\u9020\u8be5\u503c\uff1b\u65b0\u589e\u89c2\u5bdf\u5668\u4ee3\u7801\u5c1a\u672a\u5728\u6709\u6548\u6839\u4e0a\u8fd0\u884c\uff0c\u4e0d\u80fd\u6807\u8bb0\u4e3a\u901a\u8fc7\u3002\u672a\u7ed5\u8fc7\u3001\u66ff\u6362\u951a\u6216\u91cd\u8bd5\u3002

## \u5df2\u5b8c\u6210\u7684\u72ec\u7acb\u79bb\u7ebf\u6838\u7b97

\u4f7f\u75280011\u7ecf\u7ed1\u5b9a\u6838\u5bf9\u7684\u4e24\u4efd\u539f\u59cb\u5931\u8d25\u8bc1\u636e\uff08original/handle attempt02\uff09\uff0crecords\u9010\u5b57\u6bb5\u76f8\u540c\u3002\u53ea\u5bf9\u5df2\u6709INTERVAL before/after\u7684IEEE\u6d6e\u70b9\u72b6\u6001\u505aFraction\u7cbe\u786e\u6838\u7b97\uff0c\u4ecet3\u5230t6\u5171{scan['interval_count']}\u533a\u95f4\u3002\u8f93\u5165\u5341\u8fdb\u5236JSON\u7ecf\u5f80\u8fd4\u6062\u590d\u539f\u59cb\u4e8c\u8fdb\u5236\u6d6e\u70b9\uff0c\u53c2\u8003\u4f7f\u7528\u5176\u6574\u6570\u6bd4\uff0c\u4e0d\u628a\u6253\u5370\u5341\u8fdb\u5236\u5f53\u4f5c\u6570\u5b66\u4e0a\u7684\u7cbe\u786e\u5b9e\u6570\uff1b\u672a\u5199\u56de\u751f\u4ea7\u72b6\u6001\u3002

\u7b2c\u4e00\u4e2a\u5df2\u5b9a\u4f4d\u7684\u201c\u8d85\u51faN1a\u56fa\u5b9a\u9608\u503c\u201d\u7684\u533a\u95f4\uff1a

- \u8d77\u70b9 `{first['start_s']}` \u79d2\uff0chex `{first['start_hex']}`\u3002
- \u7ec8\u70b9 `{first['end_s']}` \u79d2\uff0chex `{first['end_hex']}`\u3002
- \u4e4b\u524d\u7cbe\u786e\u6b8b\u5dee `{first['exact_before']}` bit\u3002
- \u4e4b\u540e\u7cbe\u786e\u6b8b\u5dee `{first['exact_after']}` bit\uff0c\u7ea6 `{first['residual_bits']}` bit\u3002
- \u533a\u95f4\u53d8\u5316 `{first['exact_change']}` bit\uff0c\u7ea6 `{first['change_bits']}` bit\u3002

\u8fd9\u662f\u5df2\u6709\u72b6\u6001\u4e2d\u9996\u6b21\u8d8a\u8fc71e-6\u9608\u503c\u7684\u533a\u95f4\uff0c\u540c\u65f6\u662f\u6b64\u6b21\u626b\u63cf\u4e2d\u6b8b\u5dee\u53d8\u5316\u6700\u5927\u7684\u533a\u95f4\u3002\u5b83\u4e0d\u662f\u9996\u6b21\u4ea7\u751f\u4efb\u610f\u820d\u5165\u8bef\u5dee\u7684\u4e8b\u4ef6\uff0c\u4e5f\u4e0d\u80fd\u636e\u6b64\u5b9a\u4f4d\u5177\u4f53\u961f\u5217\u6263\u51cf\u3001\u5230\u8fbe\u3001clamp\u6216\u7d2f\u52a0\u64cd\u4f5c\u3002\u5b8c\u6574144\u884c\u53c2\u8003\u89c1offline_saved_evidence_scan.json\uff1b\u539f\u59cb\u6bcfcommodity/node/edge\u53caFIFO\u72b6\u6001\u4ecd\u57280011\u539f\u8bc1\u636e\u4e2d\u3002\u672c\u8f6e\u65b0\u7684\u9010\u66f4\u65b0\u660e\u7ec6\u3001\u6c42\u548c\u987a\u5e8f\u3001\u7d2f\u8ba1\u820d\u5165\u754c\u4e0ecommodity/edge\u8bef\u5dee\u5206\u89e3\u672a\u6267\u884c\uff0c\u4e0d\u7528\u8ba1\u5212\u4e2d\u7684\u89c2\u5bdf\u5668\u8f93\u51fa\u5192\u5145\u5b9e\u6d4b\u3002

## \u539f\u9a8c\u6536\u5931\u8d25\u4e0e\u6570\u503c\u5206\u7c7b

0011\u5df2\u5c01\u5b58\u5931\u8d25t6\uff1aA=3600000.0\uff0cD=3598758.711573384\uff0cQ+I=1241.2884277067496 bit\u3002\u987a\u5e8fA-D-N\u6b8b\u5dee\u7ea6-1.0905205272138119e-6\uff1b\u9a8c\u6536\u8868\u8fbe\u5f0fA-(D+N)\u7ea6-1.0905787348747253e-6\u3002\u539f\u7248\u4e0e\u4f18\u5316\u7248\u5747\u62d2\u7edd\uff0cN1a\u56fa\u5b9abusiness_bits=1e-6\u6ca1\u6709\u53d8\u5316\u3002

D2\u6e90\u7801_record\u9010commodity\u68c0\u67e5(((A-D)-Q)-I)\uff0c\u9650\u989dabs_tol + rel_tol*scale\uff1b\u5b9e\u4f8babs_tol=0.001 bit\u3001rel_tol=1e-12\u3002N1a\u5168\u5c40\u7528fsum\u805a\u5408A/D/Q/I\u540e\uff0cQ+I\u548cD+N\u4ecd\u7528\u666e\u901a\u4e8c\u5143\u52a0\u6cd5\uff0c\u6bd4\u8f83\u56fa\u5b9a1e-6\u3002\u5c42\u95f4\u8868\u8fbe\u5f0f\u53ca\u5bb9\u5dee\u4e0d\u540c\u662f\u6e90\u7801/\u65e7\u72b6\u6001\u5df2\u8bc1\u5b9e\u7684\u4e8b\u5b9e\uff0c\u4e0d\u8bc1\u660e\u5e94\u8c03\u6574\u5bb9\u5dee\u3002

\u5206\u7c7bA\u6d6e\u70b9\u7d2f\u8ba1\u3001B\u6d88\u53bb\u8bef\u5dee\u3001C\u6c42\u548c\u987a\u5e8f\u3001D\u4e8b\u4ef6\u65f6\u5e8f\u3001E\u91cd\u590d/\u4e22\u5931/\u771f\u5b9e\u5b88\u6052\u7834\u574f\uff1a\u672c\u8f6e\u5747UNRESOLVED\uff0c\u4e0d\u80fd\u6309\u91cf\u7ea7\u5224\u5b9a\u3002F\u5c42\u95f4\u5bb9\u5dee\u5b9a\u4e49\u4e0d\u540c\uff1a\u786e\u8ba4\uff0c\u4f46\u4e0d\u662f\u5df2\u5b8c\u6210\u7684\u6839\u56e0\u8bc1\u660e\u3002\u7f3a\u5c11\u6709\u6548\u6839\u4e0b\u9010\u64cd\u4f5c\u8d26\u672c\uff0c\u56e0\u6b64\u4e0d\u80fd\u7ed9\u51fa\u53ef\u8bc1\u660e\u7684\u7d2f\u8ba1\u8bef\u5dee\u754c\uff0c\u4e0d\u80fd\u7533\u8bf7\u76f4\u63a5\u653e\u5bbd\u5bb9\u5dee\u3002

## \u6709\u9650\u5bf9\u7167\u53ca\u771f\u5b9e\u4e22\u5931\u8d1f\u5411\u8bbe\u8ba1

\u539f\u8def\u5f84/Handle\u590d\u73b0\u3001\u540c\u6839HOLD\u3001\u540c\u6839ZERO/ADD\u53ca\u6700\u5c0f\u89e3\u6790fixture\u90fd\u5728\u7ed1\u5b9a\u505c\u6b62\u540e\u672a\u6267\u884c\u3002\u8d1f\u5411\u8bbe\u8ba1\u4ec5\u8bb0\u5f55\uff1a\u5728\u72ec\u7acb\u53c2\u8003\u8d26\u672c\u4e2d\u663e\u5f0f\u6263\u96641 bit\u771f\u5b9e\u5728\u9014\u4e1a\u52a1\u4e14\u4e0d\u5411D\u6216Q\u8f6c\u79fb\uff0cA\u4fdd\u6301\u4e0d\u53d8\uff0c\u4ea7\u751f1 bit\u5b88\u6052\u6b8b\u5dee\uff1b\u539fN1a\u68c0\u67e5\u4e0e\u4efb\u4f55\u62df\u8bae\u8bef\u5dee\u754c\u5e94\u62d2\u7edd\u3002\u4e0d\u53ef\u5728\u672c\u8f6e\u751f\u4ea7clone\u4e0a\u4fee\u6539I\u6765\u6267\u884c\u8be5\u8bbe\u8ba1\uff1b\u672a\u5ba3\u79f0\u5b83\u5df2\u7ecf\u901a\u8fc7\u3002

## \u6700\u5c0f\u540e\u7eed\u65b9\u6848\u4e0e\u8fb9\u754c

\u9996\u5148\u53d6\u5f97\u80fd\u5339\u914d0011\u6307\u7eb9\u7684\u6839\uff0c\u6216\u5b9a\u4f4d\u91cd\u6784\u5dee\u5f02\u5e76\u63d0\u4ea4\u4eba\u5de5\u5ba1\u6838\uff1b\u65e7\u6839\u53ea\u6709\u54c8\u5e0c\u53ca\u90e8\u5206\u5931\u8d25\u5feb\u7167\uff0c\u4e0d\u628a\u5b83\u63cf\u8ff0\u4e3a\u53ef\u53cd\u5e8f\u5217\u5316\u7684\u5b8c\u6574native checkpoint\u3002\u9700\u8981\u6bd4\u8f83\u539f\u7ed1\u5b9a\u6784\u9020\u6e90\u7801\u3001\u989d\u5916\u8bfb\u53d6\u7684\u6b21\u5e8f\u3001\u539fage\u5ba1\u8ba1\u5217\u8868\u53ca\u5f53\u524d\u91cd\u6784\u7684state_json\u3002\u82e5\u5dee\u5f02\u4ec5\u5728\u5ba1\u8ba1\u987a\u5e8f\uff0c\u4e5f\u4e0d\u80fd\u672c\u8f6e\u5077\u5077\u6392\u5e8f\u6216\u7528\u65b0\u54c8\u5e0c\u66ff\u4ee3\u951a\u3002\u82e5\u65e0\u6cd5\u5fe0\u5b9e\u6062\u590d\u539f\u6839\uff0c\u5e94\u7531\u4eba\u5de5\u51b3\u5b9a\u662f\u5426\u6388\u6743\u65b0\u7684\u3001\u72ec\u7acb\u4fdd\u5b58\u7684\u53ef\u91cd\u653e\u6839\uff0c\u800c\u975e\u4f2a\u79f0\u5df2\u590d\u75280011\u6839\u3002

\u53d6\u5f97\u6709\u6548\u6839\u540e\u624d\u53ef\u6267\u884cevent_auditor.py\u7684\u53ea\u8bfb\u89c2\u5bdf\u8bbe\u8ba1\uff1a\u8bb0\u5f55\u64cd\u4f5c\u524d\u540e\u7cbe\u786e\u4e8c\u8fdb\u5236\u503c\u3001\u8c03\u7528\u6b21\u5e8f\u3001\u670d\u52a1/\u5230\u8fbe\u4e58\u79ef\u4e0e\u6b8b\u5dee\uff0c\u5e76\u5c06\u5b9e\u9645\u8d28\u91cf\u53d8\u5316\u4e0e\u9010\u64cd\u4f5c\u8bef\u5dee\u7cbe\u786e\u95ed\u5408\u3002\u8be5\u4ee3\u7801\u672c\u8f6e\u672a\u8fd0\u884c\u9a8c\u6536\u3002\u53ea\u6709\u8bc1\u660e\u95ee\u9898\u4e3a\u89c2\u6d4b/\u805a\u5408\u8868\u8fbe\u5f0f\u65f6\uff0c\u624d\u63d0\u51fa\u9002\u914d\u5668\u5185\u7684\u7a33\u5b9a\u6c42\u548c\uff1b\u82e5\u6765\u81eaQ/I\u6570\u503c\u66f4\u65b0\uff0c\u5e94\u63d0\u51fa\u6700\u5c0f\u51bb\u7ed3\u5185\u6838\u5dee\u5f02\u53ca\u8bed\u4e49\u5f71\u54cd\uff0c\u518d\u7b49\u5f85\u6388\u6743\u3002\u5f53\u524d\u672a\u63d0\u51fa\u6216\u5b9e\u65bd\u5177\u4f53\u5185\u6838\u4fee\u590d\uff0c\u4e0d\u8c03\u6574\u5bb9\u5dee\u3002

\u4fdd\u75590011 STOP_EXISTING_CONSERVATION_BOUNDARY\u53ca\u4e0d\u6388\u4e88\u5b8c\u6574N4-P0/N4-P0R PASS\u7684\u5ba1\u6838\u7ed3\u8bba\u3002\u672c\u8f6e\u8ffd\u52a00012\uff0c\u65e7\u751f\u4ea7\u6e90\u7801\u3001\u5408\u540c\u3001\u6d4b\u8bd5\u3001\u7ed3\u679c\u30010001\u20130011\u4e0d\u4fee\u6539\u3002\u6b63\u5f0f\u79d1\u5b66\u53c2\u6570\u7ee7\u7eednull\uff1b\u4e0d\u8fd0\u884cGNN/MAPPO\u30012742catalog\u3001840\u77e9\u9635\u6216\u81ea\u52a8\u4fee\u590d\u3002\u5c01\u5b58\u524d\u5168\u91cf\u65e7\u8d44\u4ea7\u539f\u59cb\u5b57\u8282\u5ba1\u8ba1\u4e0e\u5c01\u5b58\u540e\u7684\u72ec\u7acb\u6821\u9a8c\u5206\u522b\u4ea4\u4ed8\uff1b\u54c8\u5e0cPASS\u4e0d\u662f\u79d1\u5b66Gate\u3002

\u5b8c\u6210\u540e\u505c\u6b62\u7b49\u5f85\u5ba1\u6838\u3002
''')
    version,baseline,expected,latest,parent,reserved=w.vc.load_expected(w.P,w.ORIGIN,w.PARENT)
    paths=list(w.A.glob('*'))+[dest,w.V/'contracts/N4_P0C_DIAGNOSTIC_STOP_SCOPE_CN.md']
    w.write('manifest_final.json',dict(schema='dynamic_k_n4_p0c_diagnostic_manifest_v1',revision_id='0012',
        files=[bind(p) for p in sorted(paths) if p.is_file()],parent_revision=parent,version_origin=bind(w.V/'version_record.json'),
        stored_failure_inputs=[w.bound(w.V/'acceptance/0011'/n) for n in ('conservation_failure_original_attempt02.json','conservation_failure_handle_attempt02.json','conservation_failure_comparison_attempt02.json')],
        status='STOP_ROOT_BINDING_MISMATCH',root_cause='UNRESOLVED',scientific_gate_pass=False))
    actual,excluded=w.vc.inventory(w.P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for r in reserved:actual.pop(r,None)
    diff=w.vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(x['path'].startswith('research_versions/dynamic_k_v1/') for x in diff['added'])
    w.write('preseal_change_audit.json',dict(status='PASS_COMPLETE_RAW_BYTE_OLD_ASSET_AUDIT',changes_before_audit_creation=diff,
        excluded_count=len(excluded),excluded=excluded,old_assets_modified=[],old_assets_deleted=[],reserved_records_not_overwritten=True))
    actual[(w.A/'preseal_change_audit.json').relative_to(w.P).as_posix()]=w.vc.file_info(w.A/'preseal_change_audit.json')
    final=w.vc.differences(expected,actual);now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0012',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0C diagnostic only; bound saved-state high precision scan; immediate STOP at reconstructed root SHA mismatch, root cause UNRESOLVED',
        authorization=dict(actor='human_user',scope='N4_P0C_READ_ONLY_CONSERVATION_DIAGNOSIS_ONLY',source='current_conversation_user_request',
            request='Verify independent 0011/origin/full assets; strictly reuse bound failure root/forecast/action, diagnose first residual with high precision references only; stop any binding mismatch; no frozen core/tolerance changes, no full pilot'),
        changes={k:final[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(w.V/'contracts/N4_P0C_DIAGNOSTIC_STOP_SCOPE_CN.md'),configuration=bind(dest),
            diagnostic_manifest=bind(w.A/'manifest_final.json'),result_report=bind(w.A/'RESULT_CN.md'),
            stop_evidence=bind(w.A/'stop_binding_evidence.json'),saved_state_reference=bind(w.A/'offline_saved_evidence_scan.json'),old_asset_audit=bind(w.A/'preseal_change_audit.json')),
        status='STOP_ROOT_BINDING_MISMATCH',root_cause='UNRESOLVED',N4_P0_engineering_pass=False,N4_P0R_engineering_pass=False,
        scientific_gate_pass=False,formal_experiments_executed=False,full_pilot_executed=False)
    path=w.V/'revisions/0012/record.json';path.parent.mkdir(exist_ok=False)
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(dict(revision=bind(path),added=len(final['added']),modified=0,deleted=0)),flush=True)
if __name__=='__main__':main()
