"""Seal accepted P0 evidence with complete old-file audit, append-only 0010."""
import json
from datetime import datetime,timezone,timedelta
def seal(manifest,sha,attempt):
    from workflow import A,V,P,vc,ORIGIN,PARENT,NS,write,bind,dependencies
    from runtime.n4_p0 import P0EvidenceBinding
    guard=P0EvidenceBinding(P,NS+'acceptance/0010/'+manifest,sha);guard.verify();dependencies()
    tests=vc.read_json(A/attempt/'p0_tests.json');assert tests['status']=='PASS'
    coverage=vc.read_json(A/'entry_guard_change_audit.json');assert coverage['status']=='PASS' and coverage['unique_test_cases_passed']==20
    protection=vc.read_json(A/'version_protection_tests.json');assert protection['status']=='PASS' and protection['tests_run']==32
    regress={n:vc.read_json(A/('regression_'+n+'.json')) for n in ('N1a','N1b','N2','N3')}
    assert all(r['status']=='PASS' and not r['errors'] and not r['failures'] and not r['skipped'] for r in regress.values())
    hist=vc.read_json(A/'historical_regression.json');old=vc.read_json(V/'acceptance/0007/historical_regression.json')
    assert hist['base']['tests_run']==97 and hist['physical_gate_c']['tests_run']==35
    assert hist['base']['failures']==old['base']['failures'] and len(hist['base']['failures'])==1
    assert not hist['base']['errors'] and not hist['physical_gate_c']['errors'] and not hist['physical_gate_c']['failures']
    cost=vc.read_json(A/'one_epoch_cost.json');assert cost['registered_catalog_rows']==2742 and cost['branch_count']>1
    write(A/'regression_comparison.json',dict(status='PASS_NO_NEW_REGRESSIONS',P0_unique_cases=20,P0_full_suite=19,P0_targeted_reexecutions=5,version_protection_tests=32,
        upstream_counts={n:r['tests_run'] for n,r in regress.items()},historical_tests=132,historical_passed=131,
        known_failure=hist['base']['failures'],new_regressions=0))
    state='Engineering PASS' if tests['status']=='PASS' else 'FAIL'
    write(A/'RESULT_CN.md','# N4-P0 \u6700\u5c0f\u52a8\u6001 K MPC \u8bc4\u5206\u63a5\u7f1d\u5de5\u7a0b\u7ed3\u679c\n\n'+state+'\uff0c\u4ec5\u5de5\u7a0b\u6b63\u786e\u6027\u4e0e\u6700\u5c0f\u6210\u672c\u8bc1\u636e\uff1b\u4e0d\u662fMPC\u4f18\u8d8a\u6027\u3001N4\u5168\u90e8\u5b8c\u6210\u6216\u79d1\u5b66Gate PASS\u3002\n\n'
        '\u63a5\u53e3\uff1aruntime/n4_p0.py \u7684 CausalRootView\u3001ForecastInput ZERO/PERSIST\u3001make_sanitized_root\u3001SanitizedRoot clone/checkpoint/restore\u3001PilotCost\u3001score_action\u3001retain_small_domain\u3001score_candidates\u3002\n'
        '\u5386\u53f2\u524d\u7f00\u7531\u53ea\u8bfb\u89c2\u5bdf\u8bb0\u5f55\u6784\u9020\uff0c\u590d\u5236\u65f6\u51c0\u5316\u672a\u6765trace/\u8fb9\u754c\u53ca\u65e7\u7f13\u5b58\uff0c\u4fdd\u7559\u539fN1a/N1b/N2\u5bf9\u8c61\u4e0e\u627f\u8bfa\u4e8b\u4ef6\u3002\u6570\u636e\u5bf9\u8c61\u9694\u79bb\u4e0d\u662f\u6076\u610fPython\u5b89\u5168\u6c99\u7bb1\uff1b\u539fN3 observation\u4e0d\u662f\u7cbe\u786e\u9884\u6d4b\u72b6\u6001\u3002\n\n'
        f'\u65b0\u589e\u4e13\u9879\u6d4b\u8bd5 {19} + {5} (unique {20}) PASS\uff1bN1a/N1b/N2/N3 '+str({n:r['tests_run'] for n,r in regress.items()})+'\u5168\u90e8PASS\u3002\u5386\u53f2131/132\uff0c\u539f\u65e7F3\u5931\u8d25\u4e0e\u5b8c\u6574traceback\u76f8\u540c\uff0c\u65b0\u589e\u56de\u5f520\uff1b\u4e0d\u5220\u9664\u6216\u6539\u65e7\u6d4b\u8bd5\u3002\u5177\u4f53\u89e3\u6790/\u53cc\u751f/\u540c\u52a8\u4f5c\u7b49\u4ef7/checkpoint\u8bc1\u636e\u89c1\u4e13\u9879\u6d4b\u8bd5JSON\u53ca\u6d4b\u8bd5\u6e90\u3002\n\n'
        f'\u771f\u5b9e160\u661f\u3001\u5b8c\u65742742\u884ccatalog\u3001t=3\u7684\u4e00\u6b21epoch\u5b9e\u9645\u5899\u949f {cost["total_decision_wallclock_s"]:.6f} s\uff0c\u9884\u6d4b\u5206\u652f {cost["branch_count"]}\uff0cbranch-s {cost["branch_seconds"]}\u3002\u8be6\u89c1 one_epoch_cost.json \u548c standalone_branch_cost.json \u7684\u9636\u6bb5\u62c6\u5206\u3001\u539f\u59cb\u56de\u6267\u3001\u4e8b\u4ef6/cohort\u53ca\u5185\u5b58\u3002\n'
        f'\u8fdb\u7a0b\u5cf0\u503c\u5de5\u4f5c\u96c6 {cost["peak_memory"]["process_peak_working_set_bytes"]} byte\uff1b\u5cf0\u503c\u542bfixture\u521d\u59cb\u5316\u4e0e\u524d\u4e00\u72ec\u7acb\u5206\u652f\uff0cOS\u9ad8\u6c34\u4f4d\u4e0d\u80fd\u5206\u9636\u6bb5\u91cd\u7f6e\u3002\u8ba1\u65f6\u5305\u542bsys.setprofile\u5f00\u9500\uff0c\u5206\u9879exclusive\u907f\u514d\u53cc\u91cd\u8ba1\u6570\uff1b\u52a8\u4f5c\u4e0e\u63a8\u8fdb\u7c97\u8ba1\u65f6\u542b\u539f\u7ed1\u5b9a\uff0c\u7ec6\u5206\u4ee5exclusive\u5206\u7c7b\u4e3a\u51c6\u3002\n\n'
        '\u82e5epoch\u8d85\u8fc73\u79d2\uff0c\u4e0d\u6ee1\u8db3\u771f\u5b9e3\u79d2\u8ba1\u7b97\u9884\u7b97\uff0c\u6210\u672c\u95e8\u69db\u672a\u8fc7\uff0cSTOP\u7b49\u5f85\u65b0\u6388\u6743\u3002\u4f18\u5148\u8bc4\u4f30\u5b8c\u6574\u7269\u7406\u9a8c\u8bc1/\u4e8b\u52a1clone\u3001\u539f\u59cb\u7ed1\u5b9ahash\u3001\u5386\u53f2clone/Fraction\u589e\u957f\uff1b\u4f18\u5316\u987b\u4fdd\u6301\u5168\u5408\u6cd5\u8ba1\u6570\u3001\u5b8c\u6574\u8f93\u5165\u54c8\u5e0c\u9a8c\u8bc1\u3001\u539f\u72b6\u6001\u4e0e\u4e8b\u4ef6\u9010\u5b57\u6bb5\u7b49\u4ef7\uff0c\u4e0d\u80fd\u5173\u9a8c\u8bc1\u3001\u7f29catalog\u6216\u52a0worker\u63a9\u76d6\u6210\u672c\u3002\n'
        '\u672c\u8f6e\u4e0d\u5efa\u8bae\u76f4\u63a5\u6388\u674324\u6b21\u914d\u5bf9\u9884\u5b9e\u9a8c\uff1b\u5148\u5ba1\u6838\u6b63\u786e\u6027\u3001\u6210\u672c\u548c\u7cbe\u786e\u4f18\u5316\u65b9\u6848\uff0c\u518d\u51b3\u5b9a\u3002\u4e3b\u9884\u5b9e\u9a8c\u9884\u7b97\u73b0\u4e3a840\u5206\u652f\uff0c\u672b\u7aeft27\u7684h3\uff1b\u65e71\u79d2\u8349\u6848\u4e0e\u54c8\u5e0c\u5df2\u4fdd\u7559\uff0c\u56db\u4efd\u65b03\u79d2\u526f\u672c\u4f4d\u4e8epilot_review_3s\u3002\n\n'
        'Current-State Greedy\u8bbe\u8ba1\u5efa\u8bae\uff08\u672a\u5b9e\u73b0\uff09\uff1a\u4e0eMPC\u5171\u4eab\u5f53\u524d\u5c0f\u57df\u548c\u7269\u7406\u5408\u6cd5\u6027\uff0c\u53ea\u7528\u5f53\u524d\u5b9e\u9645\u961f\u5217/\u7387\u3001\u8def\u7531\u74f6\u9888\u7684\u5bb9\u91cf\u5360\u7528\u3001\u5f53\u524d\u65b0\u589e/\u66ff\u6362\u53ef\u964d\u4f4e\u7684\u74f6\u9888\u538b\u529b\u53ca\u4f20\u64ad\u957f\u5ea6\u4f5c\u786e\u5b9a\u6027\u6392\u5e8f\uff1b\u4e0d\u6267\u884c6\u79d2rollout\u3001\u4e0d\u8bfb\u53d6\u672a\u6765trace\uff0c\u4fdd\u7559\u80fd\u8017/setup\u6210\u672c\u7684\u5355\u6b65\u516c\u5f00\u4ee3\u7406\u53ca\u5b57\u5178\u5e8f\u3002\u4e0d\u80fd\u53eb\u539fN3 Reactive\uff0c\u4e5f\u4e0d\u5148\u51bb\u7ed3\u9608\u503c\uff1b\u53e6\u6388\u6743\u540e\u7528\u540c\u4e00\u521d\u6001\u548c3\u79d2epoch\u516c\u5e73\u6bd4\u8f83\u3002\n\n'
        '\u6b63\u5f0f\u4e03\u53c2\u6570\u53ca\u6b63\u5f0f\u5468\u671f/\u9884\u7b97\u5747null\u3002\u751f\u4ea7\u6838\u30010001\u20130009\u3001\u539fN1a/b/N2/N3\u53ca\u65e7\u5408\u540c/\u6d4b\u8bd5/\u7ed3\u679c\u4e0d\u4fee\u6539\u3002\u672c\u8f6e\u53ea\u65b0\u589e\uff0c\u5b8c\u6574\u539f\u5b57\u8282\u65e7\u8d44\u4ea7\u5ba1\u8ba1\u89c1preseal_change_audit.json\uff1b\u6700\u7ec8\u8bb0\u5f55\u72ec\u7acbSHA\u7531\u5c01\u5b58\u5de5\u5177\u8f93\u51fa\uff0c\u6700\u7ec8\u5b8c\u6574\u6821\u9a8c\u5355\u72ec\u6267\u884c\u3002\n')
    loaded=vc.load_expected(P,ORIGIN,PARENT);version,baseline,expected,latest,parent,reserved=loaded
    actual,excluded=vc.inventory(P,progress=lambda x:print(json.dumps(dict(progress=x)),flush=True))
    for r in reserved:actual.pop(r,None)
    diff=vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(x['path'].startswith(NS) for x in diff['added']),diff
    guard.verify();assert vc.load_expected(P,ORIGIN,PARENT)==loaded
    write(A/'preseal_change_audit.json',dict(status='PASS',old_assets_changed=[],existing_version_assets_changed=[],
        changes_before_audit_creation=diff,excluded_file_count=len(excluded),excluded=excluded,scope='COMPLETE_RAW_BYTE_AUDIT',
        includes_gitignored_research_assets=True,scientific_gate_pass=False))
    actual[A.joinpath('preseal_change_audit.json').relative_to(P).as_posix()]=vc.file_info(A/'preseal_change_audit.json')
    final=vc.differences(expected,actual)
    now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0010',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0\u72ec\u7acb\u56e0\u679c\u52a8\u6001K\u8bc4\u5206\u63a5\u7f1d\u5de5\u7a0b\u5b9e\u73b0\u4e0e\u9a8c\u6536\uff1bPILOT_ONLY\u5468\u671f\u4eba\u5de5\u4fee\u8ba2\u4e3a3\u79d2\uff1b\u4ec5\u6700\u5c0f\u6210\u672c\u68c0\u67e5\uff0c\u4e0d\u8fd0\u884c\u914d\u5bf9\u9884\u5b9e\u9a8c\u3002',
        authorization=dict(actor='human_user',scope='N4_P0_ENGINEERING_AND_THREE_SECOND_PILOT_DRAFT_ONLY',
            source='current_conversation_user_request',request='\u6388\u6743N4-P0\u6700\u5c0f\u65b0\u7248MPC\u8bc4\u5206\u63a5\u7f1d\u53ca\u9a8c\u6536\u3002\u590d\u7528\u51bb\u7ed3N1a/N1b/N2/N3\uff0c\u5b8c\u6574\u672a\u6765\u5916\u751f\u9694\u79bb\u4e0e\u5386\u53f2\u4fdd\u6301\u3002\u4e00\u4e2abranch\u4e0e\u4e00\u4e2aepoch\u6210\u672c\u6d4b\u91cf\u3002\u4eba\u5de5\u4fee\u8ba2decision_cadence_s\u4ece1\u52303\uff0c\u65e7\u8349\u6848\u53ca\u54c8\u5e0c\u4fdd\u7559\uff0c\u4e3b\u9884\u7b97840\u3002\u6b63\u5f0f\u53c2\u6570null\uff0c\u4e0d\u6267\u884c24\u6b21/\u654f\u611f\u6027/GNN/\u6b63\u5f0f\u5b9e\u9a8c\u3002'),
        changes={k:final[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(V/'contracts/N4_P0_CAUSAL_ROOT_SCORING_CN.md'),
            configuration=bind(V/'configs/n4_p0_pilot_semantics_v1.json'),implementation_manifest=bind(A/manifest),
            acceptance=bind(A/attempt/'p0_tests.json'),result_report=bind(A/'RESULT_CN.md'),cost=bind(A/'one_epoch_cost.json'),
            old_asset_audit=bind(A/'preseal_change_audit.json')),
        N4_P0_engineering_pass=True,full_pilot_executed=False,scientific_gate_pass=False,formal_experiments_executed=False)
    dest=V/'revisions/0010/record.json';write(dest,record);print(json.dumps(bind(dest)),flush=True);return 0
