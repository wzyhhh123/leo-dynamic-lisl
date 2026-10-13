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
    md('RESULT_CN.md',f'''# N4-P0C 专项诊断：UNRESOLVED / STOP_ROOT_BINDING_MISMATCH

0011完整版本、独立起点及父链校验PASS（6090文件，旧基线5810文件，排除202，未登记差异0）。0011原路径与HandleReaderLease路径保存的失败状态records完全相同，原文件原始字节绑定匹配。

但本轮重构t=3 root时，在run_diagnosis.py第41行未匹配封存root指纹 `{scan['root_sha256']}`，报ROOT_BINDING_MISMATCH。严格按人工停止规则停止，没有提交ADD，没有推进新预测分支，没有执行HOLD/ZERO/解析对照或完整catalog。该断言未在失败前保存actual root SHA，本轮不填造该值；新增观察器代码尚未在有效根上运行，不能标记为通过。未绕过、替换锚或重试。

## 已完成的独立离线核算

使用0011经绑定核对的两份原始失败证据（original/handle attempt02），records逐字段相同。只对已有INTERVAL before/after的IEEE浮点状态做Fraction精确核算，从t3到t6共{scan['interval_count']}区间。输入十进制JSON经往返恢复原始二进制浮点，参考使用其整数比，不把打印十进制当作数学上的精确实数；未写回生产状态。

第一个已定位的“超出N1a固定阈值”的区间：

- 起点 `{first['start_s']}` 秒，hex `{first['start_hex']}`。
- 终点 `{first['end_s']}` 秒，hex `{first['end_hex']}`。
- 之前精确残差 `{first['exact_before']}` bit。
- 之后精确残差 `{first['exact_after']}` bit，约 `{first['residual_bits']}` bit。
- 区间变化 `{first['exact_change']}` bit，约 `{first['change_bits']}` bit。

这是已有状态中首次越过1e-6阈值的区间，同时是此次扫描中残差变化最大的区间。它不是首次产生任意舍入误差的事件，也不能据此定位具体队列扣减、到达、clamp或累加操作。完整144行参考见offline_saved_evidence_scan.json；原始每commodity/node/edge及FIFO状态仍在0011原证据中。本轮新的逐更新明细、求和顺序、累计舍入界与commodity/edge误差分解未执行，不用计划中的观察器输出冒充实测。

## 原验收失败与数值分类

0011已封存失败t6：A=3600000.0，D=3598758.711573384，Q+I=1241.2884277067496 bit。顺序A-D-N残差约-1.0905205272138119e-6；验收表达式A-(D+N)约-1.0905787348747253e-6。原版与优化版均拒绝，N1a固定business_bits=1e-6没有变化。

D2源码_record逐commodity检查(((A-D)-Q)-I)，限额abs_tol + rel_tol*scale；实例abs_tol=0.001 bit、rel_tol=1e-12。N1a全局用fsum聚合A/D/Q/I后，Q+I和D+N仍用普通二元加法，比较固定1e-6。层间表达式及容差不同是源码/旧状态已证实的事实，不证明应调整容差。

分类A浮点累计、B消去误差、C求和顺序、D事件时序、E重复/丢失/真实守恒破坏：本轮均UNRESOLVED，不能按量级判定。F层间容差定义不同：确认，但不是已完成的根因证明。缺少有效根下逐操作账本，因此不能给出可证明的累计误差界，不能申请直接放宽容差。

## 有限对照及真实丢失负向设计

原路径/Handle复现、同根HOLD、同根ZERO/ADD及最小解析fixture都在绑定停止后未执行。负向设计仅记录：在独立参考账本中显式扣除1 bit真实在途业务且不向D或Q转移，A保持不变，产生1 bit守恒残差；原N1a检查与任何拟议误差界应拒绝。不可在本轮生产clone上修改I来执行该设计；未宣称它已经通过。

## 最小后续方案与边界

首先取得能匹配0011指纹的根，或定位重构差异并提交人工审核；旧根只有哈希及部分失败快照，不把它描述为可反序列化的完整native checkpoint。需要比较原绑定构造源码、额外读取的次序、原age审计列表及当前重构的state_json。若差异仅在审计顺序，也不能本轮偷偷排序或用新哈希替代锚。若无法忠实恢复原根，应由人工决定是否授权新的、独立保存的可重放根，而非伪称已复用0011根。

取得有效根后才可执行event_auditor.py的只读观察设计：记录操作前后精确二进制值、调用次序、服务/到达乘积与残差，并将实际质量变化与逐操作误差精确闭合。该代码本轮未运行验收。只有证明问题为观测/聚合表达式时，才提出适配器内的稳定求和；若来自Q/I数值更新，应提出最小冻结内核差异及语义影响，再等待授权。当前未提出或实施具体内核修复，不调整容差。

保留0011 STOP_EXISTING_CONSERVATION_BOUNDARY及不授予完整N4-P0/N4-P0R PASS的审核结论。本轮追加0012，旧生产源码、合同、测试、结果、0001–0011不修改。正式科学参数继续null；不运行GNN/MAPPO、2742catalog、840矩阵或自动修复。封存前全量旧资产原始字节审计与封存后的独立校验分别交付；哈希PASS不是科学Gate。

完成后停止等待审核。
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
