"""Seal all successful and failed P0R evidence, without rewriting old assets."""
import json
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
import workflow as w

ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='fa9564caf795279ce608cf7ff31c9a86693c7336238b285a52c95c7ffb66c897'
def bind(p):return w.vc.binding(w.P,p.relative_to(w.P).as_posix())
def text(name,value):
    p=w.A/name
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(value)
def reports():
    result=w.vc.read_json(w.A/'paired_cost_summary.json');failure=w.vc.read_json(w.A/'conservation_failure_comparison_attempt02.json')
    assert result['status']=='PASS_EXACT_EQUIVALENCE' and failure['rejected_measurement_and_state_every_field_equal']
    for n in ('original','handle'):assert w.vc.read_json(w.A/('p0_'+n+'.json'))['tests_run']==20 and w.vc.read_json(w.A/('p0_'+n+'.json'))['status']=='PASS'
    reader=w.vc.read_json(w.A/'final_reader_tests.json');eq=w.vc.read_json(w.A/'final_pre_post_all_action_equivalence.json')
    assert reader['status']=='PASS' and reader['tests_run']==8 and eq['status']=='PASS'
    regression={n:w.vc.read_json(w.A/('final_regression_'+n+'.json')) for n in ('N1a','N1b','N2','N3')}
    assert all(r['status']=='PASS' and not r['skipped'] for r in regression.values())
    hist=w.vc.read_json(w.A/'historical_regression.json');prior=w.vc.read_json(w.V/'acceptance/0010/historical_regression.json')
    assert hist['base']['failures']==prior['base']['failures'] and len(hist['base']['failures'])==1
    assert not hist['base']['errors'] and not hist['physical_gate_c']['errors'] and not hist['physical_gate_c']['failures']
    protect=w.vc.read_json(w.A/'version_protection_tests.json');assert protect['status']=='PASS' and protect['tests_run']==32
    w.write('regression_comparison.json',dict(status='PASS_NO_NEW_EXISTING_SUITE_REGRESSIONS',
        original_P0=20,final_P0=20,new_reader_tests=8,pre_post_actions=6,version_protection=32,
        upstream={n:r['tests_run'] for n,r in regression.items()},historical_passed=131,historical_total=132,
        known_old_F3_failure=hist['base']['failures'],N3_catalog='FROZEN_TEST_RETAINED_INDEPENDENT_EVIDENCE_PATH; all frozen assertions executed',
        separate_new_real_stress_case='PERSIST_ADD_REJECTED_BY_BOTH_ORIGINAL_AND_OPTIMIZED_N1A',new_reader_regression=False))
    w.write('catalog_cost_boundary.json',dict(status='NOT_EXECUTED_STOP_CONSERVATION_BEFORE_CATALOG',
        registered_catalog_rows=2742,complete_catalog_legal_counts=None,completed_catalog_validation_count=None,
        selected_global_action=None,completed_global_epoch_count=0,catalog_budget_truncation_performed=False,
        planned_test_only_wall_limit_s=60.,physical_catalog_shrunk=False,reason='Real PERSIST/ADD fails strict N1a conservation; subsequent cost phases stopped'))
    original=w.vc.read_json(w.A/'paired_original_instrumented.json');native=w.vc.read_json(w.A/'paired_handle_instrumented.json')
    reconciled=w.vc.read_json(w.A/'paired_trace_native_counter_reconciliation.json')['sections']['paired_handle_instrumented']
    trace=original['branch'];groups={}
    for path,row in trace['raw_files'].items():
        p=path.replace('\\','/');kind=('source' if p.endswith('.py') else 'contract_document' if '/contracts/' in p else 'configuration' if '/configs/' in p else 'physical_data' if '/data/' in p or '/outputs/' in p else 'manifest_version_evidence')
        group=groups.setdefault(kind,dict(unique_files=0,reads=0,raw_bytes_hashed=0));group['unique_files']+=1;group['reads']+=row['calls'];group['raw_bytes_hashed']+=row['bytes_hashed']
    w.write('cost_callchain_findings.json',dict(status='ACTUAL_CALLS_RECONCILED',original_raw_io_sha=groups,
        branch_immutable_guard_calls=dict(N1a=7,N1b=11,N2=8,P0=1),branch_dynamic_verify_calls=5,branch_physical_input_hash_calls=5,
        original_branch_raw_reads=3114,original_branch_distinct_files=156,original_branch_raw_bytes=40461106,
        optimized_branch_actual_reads=reconciled['branch']['actual_reads'],optimized_branch_actual_bytes=reconciled['branch']['actual_bytes_hashed'],
        original_json_dumps=25,original_json_loads=54,
        original_json_serialized_characters=sum(x['characters'] or 0 for x in trace['json_operations'] if x['kind']=='json_dumps'),
        original_json_parsed_characters=sum(x['characters'] or 0 for x in trace['json_operations'] if x['kind']=='json_loads'),
        original_profiler_callback_events=trace['profiler_callback_events'],native_profiler_callback_events=native['branch']['profiler_callback_events'],
        original_exclusive_instrumented_s=trace['exclusive_instrumented_s'],native_exclusive_instrumented_s=native['branch']['exclusive_instrumented_s'],
        raw_hash_time_includes_io_metadata_and_profiler=True,pure_sha_cpu_seconds_not_separately_measured=True,
        json_and_state_hash_results_not_cached=True,geometry_catalog_cost_not_measured_after_failure=True))
    raw_guard_error=failure['offered_bits']-(failure['delivered_bits']+failure['remaining_bits'])
    w.write('acceptance_summary.json',dict(status='STOP_EXISTING_CONSERVATION_BOUNDARY',N4_P0R_engineering_pass=False,
        exact_reader_interface_tests_pass=True,N4_P0_engineering_pass=False,restore_full_epoch_recommended=False,
        main_pilot_runs=0,completed_global_epochs=0,controlled_paired_hold_completed=4,ZERO_small_domain_completed=5,
        PERSIST_small_domain_failed=1,PERSIST_small_domain_unexecuted_after_failure=4,
        readonly_failure_reproductions=2,original_and_optimized_failure_same=True,
        scientific_gate_pass=False,formal_experiments_executed=False,conservation_residual_validator_bits=raw_guard_error,
        conservation_residual_sequential_subtraction_bits=failure['residual_bits'],business_tolerance_bits=1e-6))
    text('MINIMAL_NEXT_STEP_CN.md',"""# \u505c\u6b62\u539f\u56e0\u4e0e\u6700\u5c0f\u540e\u7eed\u65b9\u6848

\u672c\u8f6e\u8bfb\u53d6\u4f18\u5316\u4e0d\u9700\u8981\u4fee\u6539\u51bb\u7ed3\u5185\u6838\uff1b\u5df2\u901a\u8fc7\u539f\u4e13\u9879\u3001\u4e0a\u6e38\u56de\u5f52\u4e0e\u9010\u5b57\u6bb5\u7b49\u4ef7\u6d4b\u8bd5\u3002\u4f46\u65b0\u589e\u771f\u5b9e 160 \u661f PERSIST/ADD \u5206\u652f\u5728 t=6 \u88ab\u539f N1a \u4e25\u683c\u62d2\u7edd\u3002\u539f\u8bc4\u5206\u5668\u4e5f\u4ee5\u76f8\u540c\u7ed3\u679c\u62d2\u7edd\uff0c\u4e0d\u662f\u65b0\u8bfb\u53d6\u5668\u5f15\u5165\u3002

D2 \u5b9e\u9645\u5b9e\u4f8b\u5141\u8bb8\u7edd\u5bf9\u5b88\u6052\u8bef\u5dee 0.001 bit \u52a0\u76f8\u5bf9 1e-12\u00d7scale\uff1bstate_tol=1e-6\u3002N1a \u5de5\u7a0b fixture \u4f7f\u7528\u56fa\u5b9a business_bits=1e-6\u3002\u5df2\u786e\u8ba4\u4e24\u5c42\u7684\u5bb9\u5dee\u8fb9\u754c\u4e0d\u540c\uff0c\u4f46\u5c1a\u672a\u5b9a\u4f4d\u54ea\u4e2a\u5177\u4f53\u79ef\u5206\u3001\u961f\u5217\u66f4\u65b0\u6216\u4f20\u64ad\u95ed\u5408\u4ea7\u751f\u4e86\u6b8b\u5dee\u3002\u4e0d\u80fd\u4ec5\u51ed\u8fd9\u4e2a\u5dee\u5f02\u5224\u5b9a\u5e94\u653e\u5bbd N1a\uff0c\u4e5f\u4e0d\u80fd\u9759\u9ed8\u4fee\u8865 Q/I/D \u6216\u865a\u6784 cohort\u3002

\u6700\u5c0f\u4e0b\u4e00\u8f6e\u5e94\u5148\u79bb\u7ebf\u6838\u5bf9\u5df2\u4fdd\u5b58\u7684 INTERVAL/CLOSURE\u3001\u4e1a\u52a1 timeline\u3001\u961f\u5217/\u4f20\u64ad\u72b6\u6001\u4e0e\u80fd\u8017\u539f\u59cb\u8bb0\u5f55\uff0c\u8ba1\u7b97\u9010\u4e8b\u4ef6 delta A/Q/I/D \u548c\u820d\u5165/\u95ed\u5408\u8d21\u732e\uff0c\u9501\u5b9a\u9996\u6b21\u4ea7\u751f\u8d85\u989d\u6b8b\u5dee\u7684\u4f4d\u7f6e\u3002\u5fc5\u8981\u65f6\u63d0\u51fa\u53ea\u8bfb\u4e8b\u4ef6\u89c2\u5bdf\u63a5\u53e3\uff0c\u4ee5\u4e00\u6b21\u8c03\u7528\u539f\u65b9\u6cd5\u3001\u539f\u8fd4\u56de\u503c\u53ca\u786e\u5b9a\u6027\u91cd\u653e\u8bc1\u660e\u4e0d\u5f71\u54cd\u670d\u52a1\u3002\u5148\u63d0\u4ea4\u6570\u503c\u95ed\u5408\u8bbe\u8ba1\u53ca\u98ce\u9669\uff0c\u4e0d\u5148\u4fee\u6539\u4efb\u4f55\u51bb\u7ed3\u751f\u4ea7\u4ee3\u7801\u3001\u65e7\u5408\u540c\u3001\u6d4b\u8bd5\u6216\u5bb9\u5dee\u3002

\u82e5\u6b63\u786e\u4fee\u590d\u9700\u8981\u6539\u53d8\u51bb\u7ed3\u5185\u6838\uff0c\u987b\u53e6\u5916\u6388\u6743\u5e76\u5f62\u6210\u72ec\u7acb\u65b0\u7248\u672c\u63a5\u7f1d\u65b9\u6848\uff1b\u672c\u8f6e\u6ca1\u6709\u8fd9\u6837\u7684\u6388\u6743\uff0c\u4e0d\u5b9e\u65bd\u3002\u5f85\u65e2\u6709\u9ad8\u8d1f\u8f7d\u5b88\u6052\u8fb9\u754c\u89e3\u51b3\u3001\u540c\u52a8\u4f5c\u7cbe\u786e\u7b49\u4ef7\u901a\u8fc7\u540e\uff0c\u6062\u590d 60 \u79d2\u6709\u754c\u5b8c\u6574 catalog \u5206\u9636\u6bb5\u8bca\u65ad\uff0c\u518d\u636e\u5b9e\u63d0\u51fa\u5b8c\u6574\u5355 epoch \u7684\u8303\u56f4\u4e0e\u79bb\u7ebf\u8ba1\u7b97\u9884\u7b97\u3002\u5f53\u524d\u4e0d\u5efa\u8bae\u6062\u590d\u5b8c\u6574 epoch\uff0c\u4e5f\u4e0d\u5efa\u8bae\u6388\u6743 24 \u6b21\u914d\u5bf9\u77e9\u9635\u3002

\u53ef\u7528\u4f18\u5316\u63a5\u53e3\u4fdd\u6301 HandleReaderLease \u7684\u6bcf\u6b21\u539f\u59cb\u5b57\u8282\u91cd\u54c8\u5e0c\uff0c\u4e0d\u5173\u95ed\u52a8\u6001\u5408\u6cd5\u6027\u3001\u5b8c\u6574\u72b6\u6001/FIFO/\u80fd\u8017\u68c0\u67e5\u3002\u6f5c\u5728\u51e0\u4f55/\u4e8b\u52a1\u91cd\u590d\u4ec5\u80fd\u5728\u5b8c\u6574\u952e\u3001\u76f8\u540c\u7ed3\u679c\u53ca\u4e0d\u53d8\u5ba1\u8ba1\u8bc1\u636e\u88ab\u8bc1\u660e\u540e\u53e6\u884c\u4f18\u5316\uff1b\u672c\u8f6e\u6ca1\u6709\u6267\u884c\u6216\u7f13\u5b58\u8fd9\u4e9b\u8ba1\u7b97\u3002
""")
    m=result['measures'];zero=w.vc.read_json(w.A/'small_domain_ZERO.json')
    text('RESULT_CN.md',f"""# N4-P0R \u7cbe\u786e\u7b49\u4ef7\u6210\u672c\u4f18\u5316\u4e0e\u53d7\u63a7\u590d\u6d4b\u7ed3\u679c

\u7ed3\u8bba\uff1a**STOP_EXISTING_CONSERVATION_BOUNDARY\u3002N4-P0R \u5b8c\u6574 Engineering PASS \u672a\u83b7\u5f97\uff0cN4-P0 \u5b8c\u6574 Engineering PASS \u4ecd\u672a\u83b7\u5f97\u3002\u6682\u4e0d\u5efa\u8bae\u6062\u590d\u5b8c\u6574\u5355 epoch \u9a8c\u6536\u3002** \u8bfb\u53d6\u63a5\u7f1d\u672c\u8eab\u7684\u6b63\u786e\u6027\u4e0e\u7b49\u4ef7\u6d4b\u8bd5\u901a\u8fc7\uff1b\u771f\u5b9e\u5c0f\u57df PERSIST/ADD \u63ed\u793a\u539f\u5b9e\u73b0\u5df2\u6709\u7684\u4e25\u683c\u5b88\u6052\u62d2\u7edd\u3002\u672a\u4fee\u6539\u51bb\u7ed3\u5185\u6838\u3001\u65e7\u5408\u540c\u3001\u4fee\u8ba2 0001\u20130010\u3001\u5386\u53f2\u7ed3\u679c\u6216\u65e7\u6d4b\u8bd5\u9884\u671f\uff1b\u672a\u653e\u5bbd\u6570\u503c\u6761\u4ef6\u3002

## \u5b9e\u73b0\u4e0e\u5b9e\u9645\u8c03\u7528\u94fe

\u65b0\u589e `runtime/n4_p0r_reader.py` \u8def\u5f84\u9501\u5b9a\u539f\u578b\u4e0e `runtime/n4_p0r_handle_reader.py` \u6700\u7ec8 HandleReaderLease\uff1b\u63a5\u53e3\u4e3a\u4e0a\u4e0b\u6587\u7ba1\u7406\u53ca `lease.guard(original_binding)`\uff0c\u8fd4\u56de\u539f\u7c7b\u65b0\u5bf9\u8c61\u3002\u6700\u5c0f\u7528\u6cd5\uff1a\u53d6\u5f97\u5b8c\u6574\u4f9d\u8d56/\u8def\u5f84\u53e5\u67c4 \u2192 \u539f\u59cb\u5b8c\u6574\u6821\u9a8c \u2192 \u5728\u539f N1a/N1b/N2/P0 \u5bf9\u8c61\u4e0a\u660e\u786e\u7ed1\u5b9a\u65b0\u6821\u9a8c\u5165\u53e3 \u2192 \u76f4\u63a5\u8c03\u7528\u539f make_sanitized_root/score_action/score_candidates \u2192 \u5173\u95ed\u4e0a\u4e0b\u6587\u5931\u6548\u3002\u6ca1\u6709\u7b2c\u4e8c\u5957\u7269\u7406\u72b6\u6001\u673a\u3001\u7f51\u7edc\u670d\u52a1\u3001FIFO \u6216\u8bc4\u5206\u516c\u5f0f\u3002

\u6ca1\u6709\u7f13\u5b58\u6b63\u5411\u9a8c\u8bc1\u3001\u5185\u5bb9\u6216 SHA\u3002\u6700\u7ec8\u63a5\u7f1d\u6bcf\u6b21\u4ece\u9501\u5b9a\u53e5\u67c4\u5b8c\u6574\u8bfb\u53d6\u539f\u5b57\u8282\uff0c\u9a8c\u8bc1\u8eab\u4efd\u3001\u524d\u540e\u5143\u6570\u636e\u5e76\u91cd\u65b0 SHA-256\uff1b\u53ea\u51cf\u5c11\u91cd\u590d\u8def\u5f84\u904d\u5386\u3001\u91cd\u65b0\u6253\u5f00\u6587\u4ef6\u3001Path.stat \u53ca\u9a8c\u8bc1\u5668\u91cd\u590d\u88c5\u8f7d\u3002Windows WRITE/DELETE \u5206\u4eab\u9650\u5236\u3001\u975e reparse \u7956\u5148\u4fdd\u62a4\u3001\u5173\u95ed\u5931\u6548\u3001\u5df2\u6709 writer/\u672c\u673a writable mapping \u62d2\u7edd\u5728\u72ec\u7acb\u6d4b\u8bd5\u526f\u672c\u9a8c\u8bc1\u3002\u672a\u5b9e\u73b0\u4efb\u4f55 SGP4/LOS/FoR\u3001\u4e8b\u52a1\u6216\u72b6\u6001\u7ed3\u679c\u7f13\u5b58\u3002\u53e5\u67c4\u53ea\u5728\u540c\u4e00\u4e0a\u4e0b\u6587\u5185\u590d\u7528\uff0c\u4e0d\u63d0\u4f9b\u8de8\u8fdb\u7a0b\u5e8f\u5217\u5316\u80fd\u529b\u3002

\u539f\u771f\u5b9e HOLD \u5206\u652f\u5b9e\u9645\u8c03\u7528 N1a/N1b/N2/P0 \u4e0d\u53ef\u53d8\u4f9d\u8d56 verify 7/11/8/1 \u6b21\uff0c\u5171 27 \u6b21\uff1b\u539f\u59cb\u5b57\u8282\u8bfb\u53d6/\u54c8\u5e0c **3114 \u6b21\uff0c156 \u4e2a\u4e0d\u540c\u6587\u4ef6\uff0c40461106 \u5b57\u8282**\u3002\u4f18\u5316\u540e\u6b21\u6570\u53ca\u5b57\u8282\u91cf\u5b8c\u5168\u76f8\u540c\uff0c\u4e0e\u539f\u751f\u8bfb\u53d6\u8ba1\u6570\u5668\u95ed\u5408\u3002root \u53e6\u8bfb\u53d6 475 \u6b21 / 7247700 \u5b57\u8282\u30025 \u6b21 N2 \u52a8\u6001 `_verify` \u4e0e 5 \u6b21\u7269\u7406\u8f93\u5165\u6458\u8981\u4ecd\u6267\u884c\uff1b\u72b6\u6001/\u8bc1\u636e SHA\u3001\u8d44\u6e90\u548c\u7a97\u53e3\u6821\u9a8c\u4e5f\u4fdd\u7559\u3002\u8c03\u7528\u94fe\u3001\u9010\u6587\u4ef6\u6b21\u6570/\u5b57\u8282/SHA\u3001\u5404\u6587\u4ef6\u7c7b\u522b\u53ca\u539f\u65b9\u6cd5/\u9002\u914d AST \u89c1 actual_binding_callchain_*\u3001immutable_dependency_actual_leaf_counts\u3001paired_* \u548c cost_callchain_findings\u3002

\u539f\u5206\u652f JSON dumps/loads \u4e3a 25/54 \u6b21\uff0c\u5206\u522b\u5e8f\u5217\u5316 15942322 / \u89e3\u6790 636060 \u5b57\u7b26\u3002\u539f\u4eea\u5668\u5316 19556075 \u4e2a profiler callback\uff0c\u4f18\u5316\u540e\u4ecd\u6709 17732403 \u4e2a\u3002\u539f\u89c2\u6d4b\u4e2d N1a \u7684\u59d4\u6258 raw_info \u8fd4\u56de\u66fe\u88ab\u91cd\u590d\u8ba1\u6570\uff1b\u539f\u62a5\u544a\u539f\u6837\u4fdd\u7559\uff0cpaired_trace_native_counter_reconciliation \u72ec\u7acb\u5254\u9664\u8be5\u5305\u88c5\u8fd4\u56de\u5e76\u4e0e\u771f\u6b63\u8bfb\u53d6\u6b21\u6570\u3001\u5b57\u8282\u91cf\u5b8c\u5168\u95ed\u5408\uff0c\u672a\u6539\u52a8\u4efb\u4f55\u65f6\u95f4\u6570\u636e\u3002

## \u4e32\u884c\u914d\u5bf9\u6210\u672c\uff08\u540c\u4e00 160 \u661f t=3 PERSIST/HOLD\uff09

| \u6d4b\u91cf | \u539f\u51c0\u5316 root / s | \u65b0 root / s | \u539f HOLD \u5206\u652f / s | \u65b0\u5206\u652f / s |
|---|---:|---:|---:|---:|
| \u4e0d\u5e26 profiler | {m['original_plain']['root_wallclock_s']:.6f} | {m['handle_plain']['root_wallclock_s']:.6f} | {m['original_plain']['branch_wallclock_s']:.6f} | {m['handle_plain']['branch_wallclock_s']:.6f} |
| \u8c03\u7528\u94fe profiler | {m['original_instrumented']['root_wallclock_s']:.6f} | {m['handle_instrumented']['root_wallclock_s']:.6f} | {m['original_instrumented']['branch_wallclock_s']:.6f} | {m['handle_instrumented']['branch_wallclock_s']:.6f} |

\u4e24\u7248\u53ca\u4e24\u79cd\u4eea\u5668\u5316\u65b9\u5f0f\u7684\u7ed3\u679c\u9010\u5b57\u6bb5\u5b8c\u5168\u76f8\u540c\uff0c\u53ea\u6392\u9664 `timings`\u3002\u539f\u59cb\u6839\u548c\u5206\u652f\u4e0d\u662f\u65b0\u5b8c\u6574 epoch \u7684\u603b\u8017\u65f6\u3002\u8bfb\u53d6\u4e0a\u4e0b\u6587\u6784\u5efa\uff08\u539f\u59cb\u5168\u91cf\u6821\u9a8c\u53ca\u8def\u5f84\u51c6\u5907\uff09{result['reader_construction_original_full_checks_s']:.6f}s\uff0c\u9501\u83b7\u53d6\u548c\u9501\u540e\u539f\u59cb\u5168\u6821\u9a8c {result['lock_acquisition_and_original_postlock_full_checks_s']:.6f}s\uff1b\u65b0\u589e\u5b9e\u73b0\u7ed1\u5b9a\u68c0\u67e5 {result['new_binding_startup_s']:.6f}s\uff0c\u5168\u90e8\u51b7\u542f\u52a8\u5355\u72ec\u8ba1\u5165\uff0c\u4e0d\u9690\u85cf\u4e3a\u70ed\u5206\u652f\u6210\u672c\u3002

\u4eea\u5668\u5316\u539f/\u65b0\u8def\u5f84\u68c0\u67e5 11.701615/0.399270s\uff0c\u539f\u59cb\u6587\u4ef6 I/O\u3001\u5143\u6570\u636e\u4e0e SHA 10.798076/0.914184s\uff1b\u52a8\u6001\u68c0\u67e5 3.382951/3.474745s\uff0cFIFO 2.587844/2.367077s\uff0c\u7f51\u7edc 0.444345/0.479196s\uff0c\u80fd\u8017 0.400057/0.381984s\u3002\u4ee5\u4e0a\u4e3a\u542b callback \u5f00\u9500\u7684\u4e92\u65a5\u533a\u6bb5\uff0c\u4e0d\u80fd\u5f53\u6210\u4e0d\u5e26 profiler \u7684\u5206\u7c7b\u8017\u65f6\uff0c\u66f4\u4e0d\u80fd\u628a\u539f binding/hash \u5168\u90e8\u5f52\u56e0\u4e8e SHA \u8fd0\u7b97\u3002\u539f score_action \u8fd8\u4fdd\u7559 clone\u3001\u771f\u5b9e\u63d0\u4ea4\u3001\u63a8\u8fdb\u53ca\u80fd\u8017/\u4ee3\u4ef7\u8bc1\u636e\u7684\u7c97\u8ba1\u65f6\u3002

\u72ec\u7acb HOLD \u9884\u6d4b h=6s\uff1aJ_h=187306.60287934053 bit\u00b7s\uff0cN_end=31217.767146556987 bit\uff0cE_h=10080J\uff0cDeltaE_h=480J\uff0c\u4ee3\u4ef7 854613.2057586825 bit\u00b7s\u3002\u624b\u7b97\uff1a318\u00d75\u00d76 + 2\u00d745\u00d76=10080J\uff1b\u76f8\u5bf9 320\u00d75\u00d76=9600J \u7684\u589e\u91cf\u4e3a480J\u30027 \u6761\u670d\u52a1\u89c2\u5bdf\u300120 \u4e2a\u7ed3\u675f cohort\u30010 \u4e2a\u65b0\u589e\u7ec8\u7aef\u4e8b\u4ef6\u3002\u9884\u6d4b\u7ed3\u675f t9 \u4e0d\u7b49\u4e8e\u5168 T30 \u8bc4\u4ef7\u5b8c\u6210\u3002

\u5df2\u4fdd\u5b58\u6d4b\u91cf\u671f\u95f4\u8fdb\u7a0b\u5cf0\u503c\u5de5\u4f5c\u96c6 **{zero['memory']['process_peak_working_set_bytes']} \u5b57\u8282**\uff0c\u5cf0\u503c\u63d0\u4ea4 {zero['memory']['process_peak_commit_bytes']} \u5b57\u8282\u3002Windows \u6570\u503c\u4e3a\u8fdb\u7a0b\u751f\u547d\u5468\u671f\u9ad8\u6c34\u4f4d\uff0c\u542b fixture\u3001\u524d\u5e8f\u914d\u5bf9/profiler\u53ca ZERO \u4e94\u5206\u652f\uff1b\u4e0d\u662f\u5404\u5206\u652f\u53ef\u91cd\u7f6e\u7684\u72ec\u7acb\u5cf0\u503c\u3002\u8bca\u65ad\u590d\u73b0\u548c\u6700\u7ec8 20MB \u72b6\u6001\u8bc1\u636e\u5e8f\u5217\u5316\u4e0d\u5c5e\u4e8e\u8fd9\u6b21\u6210\u672c\u8ba1\u65f6\u30023 \u79d2\u4eff\u771f cadence \u4e0d\u4ee3\u8868 3 \u79d2\u5899\u949f\u5b9e\u65f6\u6027\u4fdd\u8bc1\u3002

## \u5c0f\u57df\u3001\u505c\u6b62\u8bc1\u636e\u4e0e catalog \u8fb9\u754c

\u5b8c\u6574\u8f93\u5165 catalog \u4e3a2742\u884c\uff0c\u4e94\u4e2a\u663e\u5f0f\u5019\u9009 HOLD/ADD/DROP/BBM/MBB \u9010\u4e2a\u7ecf\u8fc7\u539f N2\u7269\u7406\u68c0\u67e5\u3002ZERO \u4e94\u5206\u652f\u5b8c\u6210\uff0c\u517130 branch-s\uff0c\u5899\u949f {zero['wallclock_s']:.6f}s\uff1b\u4ec5\u8be5\u4e94\u52a8\u4f5c\u57df\u7684\u9009\u62e9\u4e3a DROP\uff0c\u672a\u628a\u5b83\u63d0\u4ea4\u5230\u771f\u5b9e live\u3002PERSIST \u6309\u539f\u6392\u5e8f\u9996\u5148\u8bc4\u4f30 ADD\uff0c\u5728 t6 \u9996\u4e2a\u9884\u6d4b\u68c0\u67e5\u70b9\u88ab\u62d2\u7edd\uff0c\u5269\u4f59\u56db\u9879\u672a\u7ee7\u7eed\u8bc4\u4f30\uff0c\u6574\u4e2a PERSIST \u5c0f\u57df\u9009\u62e9\u4e3a null\u3002

\u62d2\u7edd\u8f93\u5165\uff1aA={failure['offered_bits']!r}bit\uff0cD={failure['delivered_bits']!r}bit\uff0cQ+I={failure['remaining_bits']!r}bit\u3002\u987a\u5e8f A-D-N \u7684\u6b8b\u5dee\u4e3a {failure['residual_bits']!r}bit\uff1b\u9a8c\u6536\u51fd\u6570\u5b9e\u9645\u6d6e\u70b9\u8868\u8fbe\u5f0f A-(D+N) \u7684\u6b8b\u5dee\u4e3a {raw_guard_error!r}bit\uff0c\u5747\u8d85\u8fc7\u56fa\u5b9a1e-6bit\u3002\u539f\u7248\u548c\u65b0\u8bfb\u53d6\u5668\u7684\u62d2\u7edd\u6d4b\u91cf\u3001\u53ef\u5e8f\u5217\u5316\u72b6\u6001\u3001FIFO\u89c2\u5bdf\u53ca\u80fd\u8017\u72b6\u6001\u5b8c\u5168\u76f8\u540c\u3002\u539f D2\u5b9e\u9645 abs_tol=0.001\u3001rel_tol=1e-12\u3001state_tol=1e-6\uff1b\u76ee\u524d\u4ec5\u786e\u8ba4\u5c42\u95f4\u5bb9\u5dee\u8fb9\u754c\u4e0d\u540c\uff0c\u5c1a\u672a\u9501\u5b9a\u5177\u4f53\u54ea\u6b21\u820d\u5165/\u95ed\u5408\u4ea7\u751f\u6b8b\u5dee\u3002\u5931\u8d25\u524d\u80fd\u8017\u8bb0\u5f55\u4e0d\u88ab\u5f53\u4f5c\u901a\u8fc7\u9a8c\u6536\u7684\u5b8c\u6574\u9884\u6d4b\u7ed3\u679c\u3002

\u539f\u521d\u8bca\u65ad\u6b63\u786e\u6355\u83b7\u76f8\u540c\u62d2\u7edd\u8f93\u5165\uff0c\u4f46\u989d\u5916\u65e5\u5fd7\u4e0d\u80fd\u76f4\u63a5\u5e8f\u5217\u5316 native Satrec\uff0c\u4ea7\u751f\u4e8c\u6b21\u89c2\u5bdf\u5668\u9519\u8bef\uff1b\u4e24\u4efd\u5c1d\u8bd5\u539f\u6837\u4fdd\u7559\u3002attempt02 \u53ea\u6392\u9664 delay/native model \u548c router \u5b9e\u73b0\u5bf9\u8c61\uff0c\u4fdd\u7559\u7269\u7406\u8f93\u5165 SHA\u53ca\u5168\u90e8\u4e1a\u52a1/\u89c2\u5bdf/\u80fd\u8017\u6570\u636e\uff0c\u518d\u6b21\u5f97\u5230\u76f8\u540c BUSINESS_CONSERVATION_MISMATCH\uff0c\u672a\u6539\u53d8\u670d\u52a1\u4e0e\u5bb9\u5dee\u3002

\u6210\u672c\u6267\u884c\u5230\u6b64 STOP\u3002**\u65b0\u7684\u5b8c\u6574 catalog \u679a\u4e3e/SGP4/\u4e8b\u52a1/320\u7ec8\u7aef\u5feb\u7167\u6210\u672c\u8bca\u65ad\u6ca1\u6709\u542f\u52a8**\uff1b\u5b8c\u6574\u5408\u6cd5\u6570\u3001\u5168\u57df\u9009\u62e9\u548c\u5b8c\u6574 epoch \u6210\u672c\u5747 null\uff0c\u5b8c\u6574 epoch \u6570\u4e3a0\u3002\u4e0d\u80fd\u7528\u5386\u53f22742\u884c\u8bc1\u636e\u6216\u4e94\u4e2a\u5408\u6cd5\u52a8\u4f5c\u5192\u79f0\u672c\u8f6e\u5168 catalog \u8986\u76d6\u3002\u540e\u7eed\u53ef\u80fd\u7684\u91cd\u590d\u8ba1\u7b97\u8c03\u7528\u94fe\u5df2\u5728\u539f\u4ee3\u7801\u4e2d\u53ef\u8bfb\uff0c\u4f46\u672c\u8f6e\u6ca1\u6709\u65b0\u7684\u679a\u4e3e\u8017\u65f6\u548c\u91cd\u590d\u51e0\u4f55\u6d4b\u91cf\uff0c\u4e0d\u80fd\u636e\u51fd\u6570\u540d\u63a8\u5b9a\u74f6\u9888\u3002

## \u6d4b\u8bd5\u3001\u4fdd\u62a4\u53ca\u540e\u7eed\u6761\u4ef6

\u6700\u7ec820\u9879 N4-P0\u4e13\u9879\u5168\u8dd1PASS\uff0c\u5305\u542b\u5165\u53e3\u62d2\u7edd\u3001\u672a\u6765\u6e90\u9694\u79bb\u3001ZERO/PERSIST\u3001HOLD/ADD/DROP/BBM/MBB\u3001\u8fde\u7eedFIFO\u3001\u90e8\u5206\u670d\u52a1\u3001\u72b6\u6001/\u80fd\u8017\u3001\u5019\u9009\u987a\u5e8f\u3001clone/checkpoint/restore/replay\u3002\u539f\u8bc4\u5206\u5668\u6700\u7ec820\u9879\u4e5f\u5b8c\u6574PASS\uff1b\u6700\u7ec8reader8\u9879PASS\uff1b6\u7c7b\u52a8\u4f5c\u539f/\u65b0\u5168\u90e8\u5b57\u6bb5\u7cbe\u786e\u7b49\u4ef7\u3002N1a/N1b/N2/N3\u4e3a25/24/27/20 PASS\u3002N3 catalog\u56de\u5f52\u6267\u884c\u51bb\u7ed3\u6d4b\u8bd5\u81ea\u5e26\u7684\u72ec\u7acb\u5386\u53f2\u8bc1\u636e\u590d\u6838\u5206\u652f\uff0c\u5e76\u9a8c\u8bc1\u5168\u90e8\u8bb0\u5f55\u6620\u5c04\u53ca\u6e90\u7801/\u8f93\u5165\u7ed1\u5b9a\uff0c\u4e0d\u662f\u65b0\u7684\u5b8c\u6574\u7269\u7406\u626b\u63cf\u3002\u5386\u53f2132\u9879131PASS\uff0c\u539f\u65e7F3\u5931\u8d25\u53catraceback\u5b8c\u5168\u76f8\u540c\uff0c\u672a\u6539\u6d4b\u8bd5\u3002\u7248\u672c\u4fdd\u62a432\u9879PASS\u3002

\u771f\u5b9e\u65b0\u589ePERSIST/ADD\u4e0d\u662f\u901a\u8fc7\u9879\uff0c\u5df2\u4f5c\u4e3a\u4e24\u7248\u90fd\u590d\u73b0\u7684\u539f\u6709\u6a21\u578b\u8fb9\u754c\u767b\u8bb0\uff1b\u4e0d\u80fd\u628a\u201c\u5df2\u77e5\u5957\u4ef6\u65e0\u65b0\u56de\u5f52\u201d\u6362\u6210\u5b8c\u6574N4-P0 PASS\u3002\u6700\u5c0f\u540e\u7eed\u65b9\u6848\u89c1 MINIMAL_NEXT_STEP_CN.md\uff1b\u5148\u89e3\u91ca\u6570\u503c\u95ed\u5408\uff0c\u4efb\u4f55\u5fc5\u8981\u5185\u6838\u6539\u52a8\u53e6\u884c\u6388\u6743\uff0c\u4e0d\u80fd\u589e\u52a0\u5bb9\u5dee\u3001\u6e05\u9664cohort\u6216\u4f2a\u9020\u4e1a\u52a1\u3002

\u524d\u7f6e\u7528\u72ec\u7acb\u8d77\u70b9 ce3fe1df\u2026\u53ca0010 fa9564ca\u2026\u6838\u9a8c6023\u53d7\u4fdd\u62a4\u6587\u4ef6\u30015810\u65e7\u57fa\u7ebf\u6587\u4ef6\u53ca\u5b8c\u6574\u7236\u94fePASS\u3002\u5c01\u5b58\u524d\u5c06\u518d\u6b21\u5168\u91cf\u6838\u5bf9\u539f\u59cb\u5b57\u8282\uff0c\u6240\u6709\u65b0\u589e/\u4fee\u6539/\u5220\u9664\u90fd\u8fdb\u51650011\uff1b\u672c\u8f6e\u9884\u671f\u4ec5\u65b0\u589e\uff0c\u65e7\u8d44\u4ea7\u548c\u65e7\u7248\u672c\u6587\u4ef6\u4fee\u6539/\u5220\u9664\u57470\u3002\u5c01\u5b58\u8bb0\u5f55\u4e0d\u81ea\u5f15\u7528\uff0c\u6700\u7ec8\u72ec\u7acb0011 SHA\u53ca\u5c01\u5b58\u540e\u5b8c\u6574\u6821\u9a8c\u7ed3\u679c\u7531\u4ea4\u4ed8\u5de5\u5177\u8f93\u51fa\u786e\u8ba4\uff0c\u4e0d\u80fd\u4ee5\u54c8\u5e0cPASS\u66ff\u4ee3\u79d1\u5b66\u6216\u5de5\u7a0bGate\u3002

PILOT_ONLY T30/TA20/H6/cadence3/setup1/\u5355\u539f\u5b50\u52a8\u4f5c\u53calambda6/1000\u4fdd\u6301\uff1b\u6b63\u5f0fT_A\u3001T\u3001tau_res\u3001R_min\u3001alpha\u3001D_ref\u3001E_ref\u53ca\u6b63\u5f0f\u5468\u671f/\u641c\u7d22\u9884\u7b97\u5747null\u3002\u672a\u8fd0\u884c24\u6b21\u4e3b\u9884\u5b9e\u9a8c\u3001840\u5206\u652f\u77e9\u9635\u3001\u654f\u611f\u6027\u3001GNN\u6216MAPPO\u3002Gate B TX\u4e0eD2\u5728\u9014\u4e1a\u52a1\u5206\u79bb\u3001\u53f3\u5220\u5931\u7a97\u53e3\u3001\u5206\u6bb5\u4f20\u64ad/FIFO\u53ca\u6570\u503c\u8bef\u5dee\u754c\u4ecd\u662f\u539f\u6a21\u578b\u89e3\u91ca\u8fb9\u754c\uff0c\u672c\u8f6e\u4e0d\u6539\u5199\u3002\u5b8c\u6210\u540e\u505c\u6b62\u7b49\u5f85\u5ba1\u6838\u3002
""")

def seal():
    reports()
    version,baseline,expected,latest,parent,reserved=w.vc.load_expected(w.P,ORIGIN,PARENT)
    # Final implementation manifest additionally binds read-only diagnostics,
    # all raw reports and final code; initial cost binding remains unchanged.
    paths=[w.V/'runtime/n4_p0r_reader.py',w.V/'runtime/n4_p0r_handle_reader.py',w.V/'tests/test_n4_p0r_reader.py',
        w.V/'contracts/N4_P0R_EXACT_READER_AND_COST_CN.md',w.V/'configs/n4_p0r_engineering_v1.json']+list(w.A.glob('*'))
    paths=[p for p in paths if p.is_file()]
    w.write('manifest_final.json',dict(schema='dynamic_k_n4_p0r_final_evidence_v1',candidate_revision_id='0011',
        formal_experiments_authorized=False,files=[bind(p) for p in sorted(set(paths))],
        anchors=dict(version_origin=bind(w.V/'version_record.json'),parent_revision=parent,
            initial_implementation_manifest=bind(w.A/'implementation_manifest.json'))))
    actual,excluded=w.vc.inventory(w.P,progress=lambda p:print(json.dumps(dict(progress=p)),flush=True))
    for r in reserved:actual.pop(r,None)
    diff=w.vc.differences(expected,actual)
    assert not diff['modified'] and not diff['deleted'] and not diff['possible_renames'],diff
    assert all(r['path'].startswith(w.old.NS) for r in diff['added'])
    assert w.vc.load_expected(w.P,ORIGIN,PARENT)[-2]==parent
    w.write('preseal_change_audit.json',dict(status='PASS_COMPLETE_OLD_ASSET_RAW_BYTE_AUDIT',
        protected_parent_revision='0010',protected_parent_sha256=PARENT,old_assets_modified=[],old_assets_deleted=[],
        registered_0010_and_older_assets_modified=[],raw_bytes_and_file_set_checked=True,
        changes_before_audit_creation=diff,excluded_count=len(excluded),excluded=excluded,includes_gitignored_assets=True,
        scientific_gate_pass=False))
    actual[(w.A/'preseal_change_audit.json').relative_to(w.P).as_posix()]=w.vc.file_info(w.A/'preseal_change_audit.json')
    final=w.vc.differences(expected,actual);now=datetime.now(timezone.utc)
    record=dict(schema='dynamic_k_revision_record_v1',version_id='dynamic_k_v1',revision_id='0011',parent_record=parent,
        created_utc=now.isoformat(),created_beijing=now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        reason='N4-P0R exact-equivalent fresh-handle dependency reader and controlled retest; STOP at inherited PERSIST/ADD conservation failure',
        authorization=dict(actor='human_user',scope='N4_P0R_EXACT_COST_OPTIMIZATION_AND_BOUNDED_RETEST_ONLY',source='current_conversation_user_request',
            request='Verify origin and independently anchored 0010 chain; retain exact physical/FIFO/energy behavior and all guards; implement exact-equivalent independent cost seam and bounded paired diagnostics; do not change frozen kernels, tolerances, histories or run full pilot'),
        changes={k:final[k] for k in ('added','modified','deleted')},
        bindings=dict(baseline_seal=version['baseline_seal'],contract=bind(w.V/'contracts/N4_P0R_EXACT_READER_AND_COST_CN.md'),
            configuration=bind(w.V/'configs/n4_p0r_engineering_v1.json'),implementation_manifest=bind(w.A/'manifest_final.json'),
            result_report=bind(w.A/'RESULT_CN.md'),acceptance_summary=bind(w.A/'acceptance_summary.json'),
            paired_cost=bind(w.A/'paired_cost_summary.json'),blocking_evidence=bind(w.A/'conservation_failure_comparison_attempt02.json'),
            catalog_boundary=bind(w.A/'catalog_cost_boundary.json'),old_asset_audit=bind(w.A/'preseal_change_audit.json')),
        status='STOP_EXISTING_CONSERVATION_BOUNDARY',N4_P0R_engineering_pass=False,N4_P0_engineering_pass=False,
        exact_reader_interface_tests_pass=True,full_pilot_executed=False,scientific_gate_pass=False,formal_experiments_executed=False)
    p=w.V/'revisions/0011/record.json';p.parent.mkdir(exist_ok=False)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(revision=bind(p),added=len(final['added']),modified=len(final['modified']),deleted=len(final['deleted']))),flush=True)
if __name__=='__main__':seal()
