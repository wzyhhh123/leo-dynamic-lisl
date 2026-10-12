"""Format a completed engineering retry; does not run any scientific branch."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/b4_branch_multiprocessing_retry_20261002T114610_676786Z'


def load(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    report = load('report.json')
    if report['status'] != 'B4_BRANCH_MULTIPROCESSING_GATE_PASS':
        raise AssertionError('RETRY_GATE_NOT_PASS')
    scale = load('scaling_summary.json')
    memory = load('memory_ipc_summary.json')
    live = load('worker_liveness.json')
    if live['status'] != 'PASS' or len(live['rows']) != 4:
        raise AssertionError('WORKER_LIVENESS_INCOMPLETE')
    regression = (OUT / 'full_regression.txt').read_text(encoding='utf-8')
    focused = (OUT / 'focused_tests.txt').read_text(encoding='utf-8')
    if 'Ran 302 tests' not in regression or 'OK' not in regression:
        raise AssertionError('FULL_REGRESSION_NOT_PASS')
    if 'Ran 3 tests' not in focused or 'OK' not in focused:
        raise AssertionError('FOCUSED_TESTS_NOT_PASS')
    table = ['| mode | wall time | speedup vs serial | speedup vs 1w | efficiency | estimated peak RAM | exact |',
             '|---|---:|---:|---:|---:|---:|---|',
             f"| serial | {scale['serial_production_wall_s']:.3f} s | 1.00× | N/A | N/A | 未采样 | reference |"]
    detail_rows = []
    for row, detail in zip(scale['rows'], memory['workers']):
        if row['workers'] != detail['workers'] or not row['exact']:
            raise AssertionError('SCALING_MEMORY_ROW_MISMATCH')
        total = detail['parent_observed_peak_rss_bytes'] + row['workers'] * detail['worker_observed_peak_rss_bytes']
        detail['estimated_peak_total_ram_bytes'] = total
        detail['result_ipc_processing_s'] = detail['result_serialization_s'] + detail['result_deserialization_s']
        table.append(f"| {row['workers']} worker{'s' if row['workers']>1 else ''} | {row['wall_s']:.3f} s | "
                     f"{row['speedup_vs_serial']:.2f}× | {row['speedup_vs_1worker']:.2f}× | "
                     f"{row['parallel_efficiency']:.2f} | {total/1e9:.3f} GB | YES |")
        detail_rows.append(f"- {row['workers']} worker：pool 创建 {detail['pool_creation_s']:.3f} s，"
                           f"startup {detail['worker_startup_s']:.3f} s，task dispatch {detail['task_dispatch_s']:.4f} s，"
                           f"result 序列化+反序列化 {detail['result_ipc_processing_s']:.3f} s；"
                           f"CPU 利用率 {detail['cpu_utilization_fraction']:.1%}。")
    save('memory_ipc_summary.json', memory)
    report['full_regression_test_count'] = 302
    report['focused_test_count'] = 3
    report['estimated_peak_ram_definition'] = 'observed parent RSS peak + N times observed maximum single-worker RSS; conservative estimate, not synchronized process peak'
    report['pure_result_ipc_transport_latency_measured'] = False
    save('report.json', report)
    save('status.json', report)
    doc = f"""# Gate F3 / B4 多进程 worker-liveness 修复与完整重测

**B4_BRANCH_MULTIPROCESSING_GATE = PASS（ENGINEERING_PROFILE_ONLY）。** 上一次 FAIL attempt 原样保留；本轮结果全部来自新目录 `{OUT.relative_to(ROOT)}`。未执行 registered P1，未接入 production controller。

## 修复与 Windows 进程验收

上一轮的短 ping 任务不能保证覆盖每个 worker，因此不能作为 `unique PID == N` 的依据。本轮使用 Windows `spawn`：每档提交 N 个可 pickle 的工程任务，任务进入 worker 后向父进程发送 READY，并一直阻塞到父进程确认 N 个不同 PID 同时占用后才统一释放。任务不调用科学仿真 API，不读取或修改科学状态。1/2/4/8 档均 PASS，所有任务正常完成、进程池正常 shutdown，未观察到 orphan process。顶层 worker 函数、`if __name__ == '__main__'` 入口和异常向父进程传递均经专项目测试验证。

## 固定状态与精确等价

真实 160 星、Z_MODERATE、ρ=0.5、primary shortest-propagation router；同一根状态、forecast 与 proposal 顺序，HOLD + 8 BBM + 8 MBB 共 17 分支。串行和 1/2/4/8-worker 使用现有 Gate B/C、routing、service、Q/I/D、目标函数及原控制器选择逻辑。父进程按 HOLD、P1…P16 的原顺序归并，worker 完成顺序不参与选优。

每档 17/17 `RolloutBranchResult` 和最终分支证据均与串行逐字段精确相等，包括合法性及原因、J_H、Gate B 接受/拒绝、transition、terminal/reservation/event 顺序及版本、G_active/G_admit、Q/I/D、累积目标、outage/no-route 诊断和 final canonical state。最终 controller result dict 完全一致；所有模式 live_before_hash == live_after_hash。没有改容差或作近似比较。

## 同一新 attempt 的性能测量

{chr(10).join(table)}

**FASTEST_VALID_WORKER_COUNT = 8**；**BEST_MEASURED_WALL_TIME = {scale['rows'][-1]['wall_s']:.3f} s**；**BEST_SPEEDUP_VS_SERIAL = {scale['rows'][-1]['speedup_vs_serial']:.2f}×**。2-worker 的效率大于 1 反映单次测量波动，不能解读为稳定的超线性加速。结果只对当前代表性 B4 决策有效，不外推到整场 P1。

内存列为“父进程观测 RSS 峰值 + N × 单 worker 观测最大 RSS”的保守估计，非同步采样的精确峰值；串行模式没有单独采样 RSS，因此明确记为未采样。每 task 约 2.17 MB，每 result 约 0.41–0.45 MB；纯传输延迟未被单独隔离，现有计时仅分别记录了序列化、反序列化和提交时间。

{chr(10).join(detail_rows)}

branch 最快/最慢、负载不均衡代理、CPU 时间、parent/worker RSS、完整 payload 大小及归并时间见本次 `branch_runtime_distribution.json` 与 `memory_ipc_summary.json`。

## 完整性与停止

focused multiprocessing 测试 **3/3 PASS**；完整仓库回归 **302/302 PASS**；当前 P1 preflight **PASS**；源代码和 config 哈希在计时过程前后相同；上一 FAIL attempt 文件哈希前后相同。production multiprocessing integration = false，registered P1 executed = false，P2 started = false，RL started = false。本 Gate 到此停止，等待人工审查。
"""
    (ROOT / 'docs/B4_BRANCH_MULTIPROCESSING_GATE_RETRY_CN.md').write_text(doc, encoding='utf-8')
    print(json.dumps({'status': report['status'], 'output': str(OUT),
                      'fastest_valid_worker_count': scale['fastest_valid_worker_count'],
                      'full_regression_tests': 302}, ensure_ascii=False))


if __name__ == '__main__':
    main()
