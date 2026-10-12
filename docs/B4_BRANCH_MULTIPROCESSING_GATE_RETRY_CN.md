# Gate F3 / B4 多进程 worker-liveness 修复与完整重测

**B4_BRANCH_MULTIPROCESSING_GATE = PASS（ENGINEERING_PROFILE_ONLY）。** 上一次 FAIL attempt 原样保留；本轮结果全部来自新目录 `outputs\b4_branch_multiprocessing_retry_20261002T114610_676786Z`。未执行 registered P1，未接入 production controller。

## 修复与 Windows 进程验收

上一轮的短 ping 任务不能保证覆盖每个 worker，因此不能作为 `unique PID == N` 的依据。本轮使用 Windows `spawn`：每档提交 N 个可 pickle 的工程任务，任务进入 worker 后向父进程发送 READY，并一直阻塞到父进程确认 N 个不同 PID 同时占用后才统一释放。任务不调用科学仿真 API，不读取或修改科学状态。1/2/4/8 档均 PASS，所有任务正常完成、进程池正常 shutdown，未观察到 orphan process。顶层 worker 函数、`if __name__ == '__main__'` 入口和异常向父进程传递均经专项目测试验证。

## 固定状态与精确等价

真实 160 星、Z_MODERATE、ρ=0.5、primary shortest-propagation router；同一根状态、forecast 与 proposal 顺序，HOLD + 8 BBM + 8 MBB 共 17 分支。串行和 1/2/4/8-worker 使用现有 Gate B/C、routing、service、Q/I/D、目标函数及原控制器选择逻辑。父进程按 HOLD、P1…P16 的原顺序归并，worker 完成顺序不参与选优。

每档 17/17 `RolloutBranchResult` 和最终分支证据均与串行逐字段精确相等，包括合法性及原因、J_H、Gate B 接受/拒绝、transition、terminal/reservation/event 顺序及版本、G_active/G_admit、Q/I/D、累积目标、outage/no-route 诊断和 final canonical state。最终 controller result dict 完全一致；所有模式 live_before_hash == live_after_hash。没有改容差或作近似比较。

## 同一新 attempt 的性能测量

| mode | wall time | speedup vs serial | speedup vs 1w | efficiency | estimated peak RAM | exact |
|---|---:|---:|---:|---:|---:|---|
| serial | 246.870 s | 1.00× | N/A | N/A | 未采样 | reference |
| 1 worker | 265.911 s | 0.93× | 1.00× | 1.00 | 0.272 GB | YES |
| 2 workers | 118.528 s | 2.08× | 2.24× | 1.12 | 0.409 GB | YES |
| 4 workers | 69.259 s | 3.56× | 3.84× | 0.96 | 0.652 GB | YES |
| 8 workers | 40.746 s | 6.06× | 6.53× | 0.82 | 1.064 GB | YES |

**FASTEST_VALID_WORKER_COUNT = 8**；**BEST_MEASURED_WALL_TIME = 40.746 s**；**BEST_SPEEDUP_VS_SERIAL = 6.06×**。2-worker 的效率大于 1 反映单次测量波动，不能解读为稳定的超线性加速。结果只对当前代表性 B4 决策有效，不外推到整场 P1。

内存列为“父进程观测 RSS 峰值 + N × 单 worker 观测最大 RSS”的保守估计，非同步采样的精确峰值；串行模式没有单独采样 RSS，因此明确记为未采样。每 task 约 2.17 MB，每 result 约 0.41–0.45 MB；纯传输延迟未被单独隔离，现有计时仅分别记录了序列化、反序列化和提交时间。

- 1 worker：pool 创建 0.002 s，startup 1.472 s，task dispatch 0.0074 s，result 序列化+反序列化 0.128 s；CPU 利用率 97.5%。
- 2 worker：pool 创建 0.004 s，startup 1.768 s，task dispatch 0.0061 s，result 序列化+反序列化 0.070 s；CPU 利用率 95.3%。
- 4 worker：pool 创建 0.004 s，startup 2.179 s，task dispatch 0.0005 s，result 序列化+反序列化 0.143 s；CPU 利用率 93.5%。
- 8 worker：pool 创建 0.002 s，startup 3.162 s，task dispatch 0.0005 s，result 序列化+反序列化 0.172 s；CPU 利用率 89.7%。

branch 最快/最慢、负载不均衡代理、CPU 时间、parent/worker RSS、完整 payload 大小及归并时间见本次 `branch_runtime_distribution.json` 与 `memory_ipc_summary.json`。

## 完整性与停止

focused multiprocessing 测试 **3/3 PASS**；完整仓库回归 **302/302 PASS**；当前 P1 preflight **PASS**；源代码和 config 哈希在计时过程前后相同；上一 FAIL attempt 文件哈希前后相同。production multiprocessing integration = false，registered P1 executed = false，P2 started = false，RL started = false。本 Gate 到此停止，等待人工审查。
