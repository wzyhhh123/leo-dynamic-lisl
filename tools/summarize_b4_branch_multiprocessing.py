"""Write a report from a completed engineering gate; never run a branch."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def main():
    reports=sorted((ROOT/'outputs').glob('b4_branch_multiprocessing_*/report.json'))
    if not reports:raise SystemExit('NO_GATE_REPORT')
    out=reports[-1].parent
    report=json.loads(reports[-1].read_text())
    if report['status']!='B4_BRANCH_MULTIPROCESSING_GATE_PASS':
        raise SystemExit('GATE_NOT_PASS_REPORT_REMAINS_FAILURE_EVIDENCE')
    scaling=json.loads((out/'scaling_summary.json').read_text())
    mem=json.loads((out/'memory_ipc_summary.json').read_text())
    rows=[]
    for scale,detail in zip(scaling['rows'],mem['workers']):
        rows.append(f"| {scale['workers']} | {scale['wall_s']:.3f} | "
          f"{scale['speedup_vs_1worker']:.2f} | {scale['parallel_efficiency']:.2f} | "
          f"{detail['worker_observed_peak_rss_bytes']/1e9:.2f} | PASS |")
    overhead=mem['workers'][0]
    text=f'''# B4 分支级多进程工程 Gate

**B4_BRANCH_MULTIPROCESSING_GATE = PASS**。本轮只在独立工程工具中实现与验证；尚未接入正式 P1。执行对象为真实160星、Z_MODERATE、ρ=0.5、primary shortest propagation router 的单个 t=0 决策，HOLD+8 BBM+8 MBB，原封不动的10秒rollout。所有 case 从相同 canonical 根状态与相同 frozen proposal set 出发。

## 进程与语义

Windows使用spawn和安全main入口。每个worker进程保留已冻结的synthetic-TLE/SGP4轨道模型，原始manifest/TLE/hashes组合经哈希验证；轨道模型只读。每个branch task单独反序列化当前根状态，terminal、Q/I/D、route、provider cache、future events均属于该task。进程池可长期存在，但本Gate只测一个decision；无跨decision保留的可变科学状态。

worker直接调用现有ExactRootActionRolloutEvaluator和Gate B/C/D2内核。父进程按冻结的HOLD、P1…P16顺序取结果，再调用原RootActionRolloutMPCController.evaluate_root_actions完成排序、argmin和exact tie规则。完成回调顺序只用于诊断，不能改变选择。

原始Satrec不能被pickle；传输层只把SGP4模型映射到已验证的冻结资产引用，worker加载该模型。其余完整根状态（包含事件游标和历史）仍逐task传输，没有共享branch可变状态或跨branch缓存。

## 精确等价

serial、1、2、4、8 worker均通过17/17分支逐项精确比较：所有RolloutBranchResult字段（包含J_H、合法性、原因、Gate B结果、BBM/MBB、终端事件顺序、outage）、终端状态/预约/事件版本、active/admit图、Q/I/D、累积目标与final canonical state。最终controller decision字典、proposal顺序、tie metadata和decision hash完全一致。各模式live前后hash相等；没有容差或rounding。详细证据见equivalence_by_worker_count.json与完整serial/worker结果。

## Production-like scaling

真正串行B4：**{scaling['serial_production_wall_s']:.3f}秒**。下表speedup和efficiency以**1-worker process pool**为分母；串行基准另列，以免混淆IPC开销。

| workers | observe wall/s | speedup vs 1 worker | efficiency | 单worker观测峰值RSS/GB | exact |
|---:|---:|---:|---:|---:|---|
{chr(10).join(rows)}

最快有效worker数：**{scaling['fastest_valid_worker_count']}**。1-worker pool相对串行的额外耗时：**{scaling['rows'][0]['wall_s']-scaling['serial_production_wall_s']:.3f}秒**。该差额包含传输、worker进程行为和系统波动，不能完全归因于pickle。

1-worker传输/启动诊断：pool创建 {overhead['pool_creation_s']:.3f}s，启动 {overhead['worker_startup_s']:.3f}s，根状态序列化 {overhead['root_serialization_s']:.3f}s，task提交 {overhead['task_dispatch_s']:.3f}s，worker结果序列化 {overhead['result_serialization_s']:.3f}s，parent反序列化 {overhead['result_deserialization_s']:.3f}s，归并 {overhead['parent_merge_s']:.3f}s。根状态 {overhead['serialized_root_bytes']} bytes；每task/每result bytes逐支存于memory_ipc_summary.json。worker RSS为启动/任务完成时的可复测观测值，未宣称捕捉连续时间精确峰值。

各worker的CPU时间/利用率、parent RSS、branch fastest/slowest、load imbalance和idle proxy都存于scaling与memory/IPC报告。idle proxy为 p×wall 减各branch compute累积值，包含任务排队/传输/进程调度，不能视作精确空闲时间。

## 完整性和停止

focused spawn test、serial-vs-parallel exact tests、既有runtime优化测试及完整回归：见本Gate最终status。current P1 preflight保持PASS；全部历史frozen manifest和暂停归档不变。所有输出标记ENGINEERING_PROFILE_ONLY。

**NEXT_OPTIMIZATION_CANDIDATE = {scaling['NEXT_OPTIMIZATION_CANDIDATE']}**。本轮没有把多进程接入registered P1，也没有实施其他缓存、内核优化或参数裁剪。registered P1本轮执行=false；P2 started=false；RL started=false。历史暂停的P1 attempt仍作为不可变证据保存。

证据：{out.relative_to(ROOT)}。
'''
    (ROOT/'docs/B4_BRANCH_MULTIPROCESSING_GATE_CN.md').write_text(text,encoding='utf-8')
    print(json.dumps({'status':report['status'],'fastest':scaling['fastest_valid_worker_count'],
                      'serial_s':scaling['serial_production_wall_s'],'rows':scaling['rows']},ensure_ascii=False))
if __name__=='__main__':main()
