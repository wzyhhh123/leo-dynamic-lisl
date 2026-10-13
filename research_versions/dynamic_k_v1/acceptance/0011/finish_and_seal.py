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
    text('MINIMAL_NEXT_STEP_CN.md',"""# 停止原因与最小后续方案

本轮读取优化不需要修改冻结内核；已通过原专项、上游回归与逐字段等价测试。但新增真实 160 星 PERSIST/ADD 分支在 t=6 被原 N1a 严格拒绝。原评分器也以相同结果拒绝，不是新读取器引入。

D2 实际实例允许绝对守恒误差 0.001 bit 加相对 1e-12×scale；state_tol=1e-6。N1a 工程 fixture 使用固定 business_bits=1e-6。已确认两层的容差边界不同，但尚未定位哪个具体积分、队列更新或传播闭合产生了残差。不能仅凭这个差异判定应放宽 N1a，也不能静默修补 Q/I/D 或虚构 cohort。

最小下一轮应先离线核对已保存的 INTERVAL/CLOSURE、业务 timeline、队列/传播状态与能耗原始记录，计算逐事件 delta A/Q/I/D 和舍入/闭合贡献，锁定首次产生超额残差的位置。必要时提出只读事件观察接口，以一次调用原方法、原返回值及确定性重放证明不影响服务。先提交数值闭合设计及风险，不先修改任何冻结生产代码、旧合同、测试或容差。

若正确修复需要改变冻结内核，须另外授权并形成独立新版本接缝方案；本轮没有这样的授权，不实施。待既有高负载守恒边界解决、同动作精确等价通过后，恢复 60 秒有界完整 catalog 分阶段诊断，再据实提出完整单 epoch 的范围与离线计算预算。当前不建议恢复完整 epoch，也不建议授权 24 次配对矩阵。

可用优化接口保持 HandleReaderLease 的每次原始字节重哈希，不关闭动态合法性、完整状态/FIFO/能耗检查。潜在几何/事务重复仅能在完整键、相同结果及不变审计证据被证明后另行优化；本轮没有执行或缓存这些计算。
""")
    m=result['measures'];zero=w.vc.read_json(w.A/'small_domain_ZERO.json')
    text('RESULT_CN.md',f"""# N4-P0R 精确等价成本优化与受控复测结果

结论：**STOP_EXISTING_CONSERVATION_BOUNDARY。N4-P0R 完整 Engineering PASS 未获得，N4-P0 完整 Engineering PASS 仍未获得。暂不建议恢复完整单 epoch 验收。** 读取接缝本身的正确性与等价测试通过；真实小域 PERSIST/ADD 揭示原实现已有的严格守恒拒绝。未修改冻结内核、旧合同、修订 0001–0010、历史结果或旧测试预期；未放宽数值条件。

## 实现与实际调用链

新增 `runtime/n4_p0r_reader.py` 路径锁定原型与 `runtime/n4_p0r_handle_reader.py` 最终 HandleReaderLease；接口为上下文管理及 `lease.guard(original_binding)`，返回原类新对象。最小用法：取得完整依赖/路径句柄 → 原始完整校验 → 在原 N1a/N1b/N2/P0 对象上明确绑定新校验入口 → 直接调用原 make_sanitized_root/score_action/score_candidates → 关闭上下文失效。没有第二套物理状态机、网络服务、FIFO 或评分公式。

没有缓存正向验证、内容或 SHA。最终接缝每次从锁定句柄完整读取原字节，验证身份、前后元数据并重新 SHA-256；只减少重复路径遍历、重新打开文件、Path.stat 及验证器重复装载。Windows WRITE/DELETE 分享限制、非 reparse 祖先保护、关闭失效、已有 writer/本机 writable mapping 拒绝在独立测试副本验证。未实现任何 SGP4/LOS/FoR、事务或状态结果缓存。句柄只在同一上下文内复用，不提供跨进程序列化能力。

原真实 HOLD 分支实际调用 N1a/N1b/N2/P0 不可变依赖 verify 7/11/8/1 次，共 27 次；原始字节读取/哈希 **3114 次，156 个不同文件，40461106 字节**。优化后次数及字节量完全相同，与原生读取计数器闭合。root 另读取 475 次 / 7247700 字节。5 次 N2 动态 `_verify` 与 5 次物理输入摘要仍执行；状态/证据 SHA、资源和窗口校验也保留。调用链、逐文件次数/字节/SHA、各文件类别及原方法/适配 AST 见 actual_binding_callchain_*、immutable_dependency_actual_leaf_counts、paired_* 和 cost_callchain_findings。

原分支 JSON dumps/loads 为 25/54 次，分别序列化 15942322 / 解析 636060 字符。原仪器化 19556075 个 profiler callback，优化后仍有 17732403 个。原观测中 N1a 的委托 raw_info 返回曾被重复计数；原报告原样保留，paired_trace_native_counter_reconciliation 独立剔除该包装返回并与真正读取次数、字节量完全闭合，未改动任何时间数据。

## 串行配对成本（同一 160 星 t=3 PERSIST/HOLD）

| 测量 | 原净化 root / s | 新 root / s | 原 HOLD 分支 / s | 新分支 / s |
|---|---:|---:|---:|---:|
| 不带 profiler | {m['original_plain']['root_wallclock_s']:.6f} | {m['handle_plain']['root_wallclock_s']:.6f} | {m['original_plain']['branch_wallclock_s']:.6f} | {m['handle_plain']['branch_wallclock_s']:.6f} |
| 调用链 profiler | {m['original_instrumented']['root_wallclock_s']:.6f} | {m['handle_instrumented']['root_wallclock_s']:.6f} | {m['original_instrumented']['branch_wallclock_s']:.6f} | {m['handle_instrumented']['branch_wallclock_s']:.6f} |

两版及两种仪器化方式的结果逐字段完全相同，只排除 `timings`。原始根和分支不是新完整 epoch 的总耗时。读取上下文构建（原始全量校验及路径准备）{result['reader_construction_original_full_checks_s']:.6f}s，锁获取和锁后原始全校验 {result['lock_acquisition_and_original_postlock_full_checks_s']:.6f}s；新增实现绑定检查 {result['new_binding_startup_s']:.6f}s，全部冷启动单独计入，不隐藏为热分支成本。

仪器化原/新路径检查 11.701615/0.399270s，原始文件 I/O、元数据与 SHA 10.798076/0.914184s；动态检查 3.382951/3.474745s，FIFO 2.587844/2.367077s，网络 0.444345/0.479196s，能耗 0.400057/0.381984s。以上为含 callback 开销的互斥区段，不能当成不带 profiler 的分类耗时，更不能把原 binding/hash 全部归因于 SHA 运算。原 score_action 还保留 clone、真实提交、推进及能耗/代价证据的粗计时。

独立 HOLD 预测 h=6s：J_h=187306.60287934053 bit·s，N_end=31217.767146556987 bit，E_h=10080J，DeltaE_h=480J，代价 854613.2057586825 bit·s。手算：318×5×6 + 2×45×6=10080J；相对 320×5×6=9600J 的增量为480J。7 条服务观察、20 个结束 cohort、0 个新增终端事件。预测结束 t9 不等于全 T30 评价完成。

已保存测量期间进程峰值工作集 **{zero['memory']['process_peak_working_set_bytes']} 字节**，峰值提交 {zero['memory']['process_peak_commit_bytes']} 字节。Windows 数值为进程生命周期高水位，含 fixture、前序配对/profiler及 ZERO 五分支；不是各分支可重置的独立峰值。诊断复现和最终 20MB 状态证据序列化不属于这次成本计时。3 秒仿真 cadence 不代表 3 秒墙钟实时性保证。

## 小域、停止证据与 catalog 边界

完整输入 catalog 为2742行，五个显式候选 HOLD/ADD/DROP/BBM/MBB 逐个经过原 N2物理检查。ZERO 五分支完成，共30 branch-s，墙钟 {zero['wallclock_s']:.6f}s；仅该五动作域的选择为 DROP，未把它提交到真实 live。PERSIST 按原排序首先评估 ADD，在 t6 首个预测检查点被拒绝，剩余四项未继续评估，整个 PERSIST 小域选择为 null。

拒绝输入：A={failure['offered_bits']!r}bit，D={failure['delivered_bits']!r}bit，Q+I={failure['remaining_bits']!r}bit。顺序 A-D-N 的残差为 {failure['residual_bits']!r}bit；验收函数实际浮点表达式 A-(D+N) 的残差为 {raw_guard_error!r}bit，均超过固定1e-6bit。原版和新读取器的拒绝测量、可序列化状态、FIFO观察及能耗状态完全相同。原 D2实际 abs_tol=0.001、rel_tol=1e-12、state_tol=1e-6；目前仅确认层间容差边界不同，尚未锁定具体哪次舍入/闭合产生残差。失败前能耗记录不被当作通过验收的完整预测结果。

原初诊断正确捕获相同拒绝输入，但额外日志不能直接序列化 native Satrec，产生二次观察器错误；两份尝试原样保留。attempt02 只排除 delay/native model 和 router 实现对象，保留物理输入 SHA及全部业务/观察/能耗数据，再次得到相同 BUSINESS_CONSERVATION_MISMATCH，未改变服务与容差。

成本执行到此 STOP。**新的完整 catalog 枚举/SGP4/事务/320终端快照成本诊断没有启动**；完整合法数、全域选择和完整 epoch 成本均 null，完整 epoch 数为0。不能用历史2742行证据或五个合法动作冒称本轮全 catalog 覆盖。后续可能的重复计算调用链已在原代码中可读，但本轮没有新的枚举耗时和重复几何测量，不能据函数名推定瓶颈。

## 测试、保护及后续条件

最终20项 N4-P0专项全跑PASS，包含入口拒绝、未来源隔离、ZERO/PERSIST、HOLD/ADD/DROP/BBM/MBB、连续FIFO、部分服务、状态/能耗、候选顺序、clone/checkpoint/restore/replay。原评分器最终20项也完整PASS；最终reader8项PASS；6类动作原/新全部字段精确等价。N1a/N1b/N2/N3为25/24/27/20 PASS。N3 catalog回归执行冻结测试自带的独立历史证据复核分支，并验证全部记录映射及源码/输入绑定，不是新的完整物理扫描。历史132项131PASS，原旧F3失败及traceback完全相同，未改测试。版本保护32项PASS。

真实新增PERSIST/ADD不是通过项，已作为两版都复现的原有模型边界登记；不能把“已知套件无新回归”换成完整N4-P0 PASS。最小后续方案见 MINIMAL_NEXT_STEP_CN.md；先解释数值闭合，任何必要内核改动另行授权，不能增加容差、清除cohort或伪造业务。

前置用独立起点 ce3fe1df…及0010 fa9564ca…核验6023受保护文件、5810旧基线文件及完整父链PASS。封存前将再次全量核对原始字节，所有新增/修改/删除都进入0011；本轮预期仅新增，旧资产和旧版本文件修改/删除均0。封存记录不自引用，最终独立0011 SHA及封存后完整校验结果由交付工具输出确认，不能以哈希PASS替代科学或工程Gate。

PILOT_ONLY T30/TA20/H6/cadence3/setup1/单原子动作及lambda6/1000保持；正式T_A、T、tau_res、R_min、alpha、D_ref、E_ref及正式周期/搜索预算均null。未运行24次主预实验、840分支矩阵、敏感性、GNN或MAPPO。Gate B TX与D2在途业务分离、右删失窗口、分段传播/FIFO及数值误差界仍是原模型解释边界，本轮不改写。完成后停止等待审核。
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
