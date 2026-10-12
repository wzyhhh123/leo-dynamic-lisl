"""Render the completed engineering-only profile; no simulation is run."""
from pathlib import Path
import json
import io
import pstats
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=max((ROOT/'outputs').glob('b4_rollout_kernel_profile_*/report.json')).parent
    report=json.loads((out/'report.json').read_text())
    agg=json.loads((out/'aggregate_timing.json').read_text())
    rows=json.loads((out/'branch_timing.json').read_text())
    stream=io.StringIO()
    stats=pstats.Stats(*[str(p) for p in sorted(out.glob('branch_*.prof'))],stream=stream)
    stats.sort_stats('cumulative').print_stats(50)
    (out/'cprofile_top50.txt').write_text('ENGINEERING_PROFILE_ONLY\n'+stream.getvalue(),encoding='utf-8')
    table='\n'.join(f"| {key} | {v:.4f} | {agg['share_of_instrumented_observe'][key]*100:.2f}% |" for key,v in agg['exclusive_seconds'].items())
    branches='\n'.join(f"| {i+1} | {r['branch_type']} | {r['total_s']:.3f} | {r['event_count']} | {r['route_evaluation_count']} | {r['delay_provider_call_count']} | {r['service_allocation_count']} |" for i,r in enumerate(rows))
    text=f'''# B4 Rollout Kernel Profiling

ENGINEERING_PROFILE_ONLY。只执行一个真实160星、Z_MODERATE、rho=0.5、primary router初始decision epoch。HOLD + 16有效候选，10秒forecast。OFF/ON使用同一根状态、同一候选、同一顺序。没有执行registered P1/P2/RL，也没有实施新性能优化。

## 先决条件

lightweight clone seal = PASS；decision-local hash reuse seal = PASS；current P1 preflight = PASS；full regression = 299/299 PASS。新增runtime chain通过现有工程报告绑定当前源码哈希，原frozen manifest与历史attempt不变。

暂停attempt只有在原归档清单、ZIP、原attempt文件集/逐文件hash、telemetry文件集/逐文件hash、5项ledger和无result seal均验证后才被识别为PAUSED_INCOMPLETE。ledger时间戳 .588120Z 与 .58812Z 按精确时刻相等比较，不使用数值容差。原始归档仍保留MANUAL_AUDIT_REQUIRED，不把暂停结果改成PASS或恢复执行授权。

## 等价性

17/17 branch：J_H、validity、Gate B action_result、完整terminal event sequence、完整final canonical state精确一致。最终decision字典、proposal、tie handling和decision hash精确一致。live状态未被修改。所有配置和scientific source hash在profiling前后相同。

## 耗时

OFF observe：{agg['observe_wall_s']['OFF']:.3f} s；ON observe：{agg['observe_wall_s']['ON']:.3f} s。
17支ON总耗时：{agg['branch_total_s']:.3f} s；mean {agg['branch_mean_s']:.3f} s；median {agg['branch_median_s']:.3f} s；max {agg['branch_max_s']:.3f} s。

各类分支统计：{json.dumps(agg['by_type'],ensure_ascii=False)}。

下表是扣除嵌套计时的exclusive wall time；inclusive stage timing另存JSON，不能直接相加。

| 项 | 总秒数 | 占ON observe |
|---|---:|---:|
{table}

root hash前后检查、forecast hash只发生于decision层，JSON的global_hash_timing_s单独保留它们。每支forecast hash为零不表示遗漏，而是当前冻结优化已将它移到分支外复用。

objective项测量补偿累加器调用；objective公式计算与循环开销仍归qid，因此它是objective部分耗时的下界，不能独立断言“完整目标积分很便宜”。service/QID/event整体分组不受这种内部归属影响。cProfile与Python计时hook会产生开销，ON占比用于诊断，不当作未经instrumentation的真实生产占比。finish含为精确对照捕获canonical state的额外开销；other含harness和profile保存开销。

| 分支序号 | 类别 | ON总秒数 | _step次数 | route evaluation | delay调用 | allocation次数 |
|---|---|---:|---:|---:|---:|---:|
{branches}

完整proposal ID、J_H、final hash、inclusive/exclusive秒数及每支结尾队列/事件/历史规模见branch_timing.json。

## 历史增长性

根状态proxy：{json.dumps(report['root_state_proxy'],ensure_ascii=False)}。
每支结尾proxy也已记录，包括terminal log、transition、route/history、timeseries、pending events、I对象数与queue大小。本轮只有t=0，不能据此拟合T_clone(t)或断言后期历史增长无影响；没有额外跑晚期epoch。

## 结论与停止

PRIMARY_RUNTIME_BOTTLENECK = {report['PRIMARY_RUNTIME_BOTTLENECK']}

NEXT_OPTIMIZATION_CANDIDATE = {report['NEXT_OPTIMIZATION_CANDIDATE']}

上述候选只用于下一轮讨论，尚未实施。若routing/delay与service/event都显著，应结合OFF总时长和instrumentation开销确定次序，不能仅凭ON单项差异预测加速倍数。

registered P1 executed = false（本轮）；P2 started = false；RL started = false。历史P1曾执行并暂停，证据如实保留。preflight PASS不构成新P1人工授权。

证据目录：{out.relative_to(ROOT)}。
'''
    (ROOT/'docs/B4_ROLLOUT_KERNEL_PROFILE_CN.md').write_text(text,encoding='utf-8')
    print(json.dumps({'output':str(out),'OFF':agg['observe_wall_s']['OFF'],'ON':agg['observe_wall_s']['ON'],'bottleneck':report['PRIMARY_RUNTIME_BOTTLENECK'],'next':report['NEXT_OPTIMIZATION_CANDIDATE'],'totals':agg['exclusive_seconds']},ensure_ascii=False))
if __name__=='__main__':main()
