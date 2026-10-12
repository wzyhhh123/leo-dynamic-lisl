"""Read-only synthesis of the stopped engineering gate; never reruns a worker."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    out=max((ROOT/'outputs').glob('b4_branch_multiprocessing_*/report.json')).parent
    report=json.loads((out/'report.json').read_text())
    assert report['status']=='B4_BRANCH_MULTIPROCESSING_GATE_FAIL'
    assert report['failure']=='WORKER_STARTUP_COUNT_MISMATCH'
    rows=json.loads((out/'worker_results.partial.json').read_text())
    assert [r['workers'] for r in rows]==[1,2] and all(r['exact'] for r in rows)
    base=rows[0]['wall_s']
    scaling=[{'workers':r['workers'],'wall_s':r['wall_s'],
        'speedup_vs_1worker':base/r['wall_s'],
        'efficiency':base/(r['workers']*r['wall_s']),
        'worker_observed_peak_rss_bytes':r['worker_observed_peak_rss_bytes'],
        'exact':True} for r in rows]
    serial=json.loads((out/'serial_reference.json').read_text())
    write(out/'equivalence_by_worker_count.json',{'label':'ENGINEERING_PROFILE_ONLY',
        'gate_status':'FAIL','serial_exact_reference':True,
        'completed':[{'workers':r['workers'],'exact':True,'live_unchanged':r['live_before']==r['live_after'],
            'branch_count':len(r['branch_results']),'full_final_evidence_equal':r['final_evidence']==serial['final_evidence'],
            'full_branch_result_equal':r['branch_results']==serial['branch_results'],
            'controller_decision_equal':r['decision']==serial['decision']} for r in rows],
        'four_worker':'NOT_EVALUATED_STARTUP_ASSERTION','eight_worker':'NOT_STARTED'})
    write(out/'scaling_summary.json',{'label':'ENGINEERING_PROFILE_ONLY','gate_status':'FAIL',
        'serial_production_wall_s':serial['wall_s'],'completed_rows':scaling,
        'four_worker':None,'eight_worker':None,
        'fastest_valid_worker_count_in_complete_grid':None,
        'fastest_among_completed_only':2})
    write(out/'branch_runtime_distribution.json',{'label':'ENGINEERING_PROFILE_ONLY',
        'serial':serial['branch_wall'],
        'completed_workers':{str(r['workers']):r['branch_runtime'] for r in rows}})
    write(out/'memory_ipc_summary.json',{'label':'ENGINEERING_PROFILE_ONLY',
        'completed_workers':[{k:r[k] for k in (
            'workers','pool_creation_s','worker_startup_s','root_serialization_s',
            'physical_serialization_s','task_dispatch_s','result_serialization_s',
            'result_deserialization_s','parent_merge_s','serialized_root_bytes',
            'per_task_payload_bytes','per_result_payload_bytes',
            'worker_observed_peak_rss_bytes','parent_observed_peak_rss_bytes',
            'worker_cpu_s','cpu_utilization_fraction','worker_idle_proxy_s')}
            for r in rows],
        'peak_ram_note':'observed RSS at startup/task return, not continuous peak'})
    state={'label':'ENGINEERING_PROFILE_ONLY','B4_BRANCH_MULTIPROCESSING_GATE':'FAIL',
        'failure':'WORKER_STARTUP_COUNT_MISMATCH at four-worker warm-up',
        'serial_wall_s':serial['wall_s'],'one_worker_wall_s':rows[0]['wall_s'],
        'two_worker_wall_s':rows[1]['wall_s'],
        'two_worker_speedup_vs_one':base/rows[1]['wall_s'],
        'two_worker_efficiency':base/(2*rows[1]['wall_s']),
        'four_worker_rollout_started':False,'eight_worker_started':False,
        'full_regression_after_change':'NOT_RUN_DUE_TO_STOP_RULE',
        'P1_preflight_at_gate_start':'PASS',
        'registered_P1_executed':False,'P2_started':False,'RL_started':False,
        'production_integration':False,'fastest_valid_worker_count':None,
        'evidence_dir':str(out.relative_to(ROOT)).replace('\\','/')}
    write(out/'failure_summary.json',state)
    artifacts={str(p.relative_to(out)):sha(p) for p in out.iterdir() if p.is_file() and p.name!='artifact_hashes.json'}
    write(out/'artifact_hashes.json',artifacts)
    write(ROOT/'configs/gate_f3_b4_branch_multiprocessing_status.json',state)
    doc=f'''# B4 分支级多进程工程 Gate：失败封存

**B4_BRANCH_MULTIPROCESSING_GATE = FAIL。** 本轮按“任何异常立即停止”规则停在4-worker启动检查，未运行4-worker分支，未启动8-worker，也未接入正式P1。

## 已完成结果

真实160星、Z_MODERATE、ρ=0.5、primary router、t=0、HOLD+8BBM+8MBB。真正串行B4耗时 **{serial['wall_s']:.3f}s**；1-worker进程池 **{rows[0]['wall_s']:.3f}s**；2-worker进程池 **{rows[1]['wall_s']:.3f}s**。2 worker相对1 worker加速 **{base/rows[1]['wall_s']:.3f}×**，并行效率 **{base/(2*rows[1]['wall_s']):.3f}**。1-worker相对真正串行多 **{rows[0]['wall_s']-serial['wall_s']:.3f}s**，该差异包含IPC、序列化和系统波动，不能全归因于单项开销。

1与2 worker都通过17/17分支精确比较：分支结果、Gate B动作、事件顺序、终端/预约/事件版本、active/admit图、Q/I/D、累计目标、outage和最终canonical状态一致；最终controller decision字典及tie处理一致。live前后hash相同。单worker观测RSS峰值分别约{rows[0]['worker_observed_peak_rss_bytes']/1e9:.3f}GB和{rows[1]['worker_observed_peak_rss_bytes']/1e9:.3f}GB；它们是采样RSS，不是连续峰值。

## 停止原因

4-worker池 warm-up 中，短小的ping任务返回的**不同PID少于4个**，触发 `WORKER_STARTUP_COUNT_MISMATCH`。ProcessPoolExecutor可以尚未把所有进程调度到这些很短的任务；因此这个断言失败尚不能证明4-worker的科学结果会错，也不能声称4-worker更慢或更快。用户合同要求异常即FAIL+STOP，故未调整warm-up、未重试、未改网格。

4 worker：未测；8 worker：未启动；完整1/2/4/8网格的最快worker数：**未知**。在已完成的1/2组中，2 worker较快，不能称为整个网格的最优。

## 审计状态

本轮使用 `ENGINEERING_PROFILE_ONLY` run_id，保留serial reference、逐支结果与状态、IPC/RSS/CPU指标和失败traceback。源程序未接入注册P1；历史frozen manifests与paused attempt证据未修改。

启动前P1 preflight = PASS；本轮focused Windows spawn测试 = PASS。失败后遵守STOP规则，**没有运行最终full repository regression或再次preflight**，所以不能报告本轮验收所需的“full regression 100% PASS”。上一轮299/299回归属于此前代码状态。

registered P1 executed（本轮）= false；P2 started=false；RL started=false。多进程生产接入=false。后续如继续，需要新的人工决定先修正warm-up进程计数的工程验收方法，再从独立新attempt重新验证；本轮不能标PASS。

证据目录：{out.relative_to(ROOT)}。
'''
    (ROOT/'docs/B4_BRANCH_MULTIPROCESSING_GATE_CN.md').write_text(doc,encoding='utf-8')
    print(json.dumps({'status':'FAIL','output':str(out),'serial_s':serial['wall_s'],
        'one_s':rows[0]['wall_s'],'two_s':rows[1]['wall_s'],
        'speedup_two_vs_one':base/rows[1]['wall_s']},ensure_ascii=False))
if __name__=='__main__':main()
