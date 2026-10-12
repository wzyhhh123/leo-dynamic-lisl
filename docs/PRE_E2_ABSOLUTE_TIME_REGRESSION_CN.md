# Pre-E2 绝对时间 / 延迟动作专项回归合同

## 1. 目的与边界

本专项回归验证：当整个合成物理世界的所有绝对时间戳统一平移时，相对动力学、合法性、状态迁移、服务、队列与评价结果保持一致。它是时间坐标一致性测试，不是轨道物理不变性测试，也不在真实 SGP4 160 星轨迹上要求时间平移不变。

专项回归贯穿完整调用链：Gate C terminal-pair 合法性与 transition profiler → Gate B 双端 terminal 状态机 → Gate D2 服务积分 → Gate E0 paired-counterfactual harness。孤立 helper 的测试不能替代这条端到端路径。

## 2. 冻结合成 fixture

- 时间基准标识：`PRE_E2_SYNTHETIC_ABSOLUTE_TIME_V1`。
- 全局平移量：`0 s`、`7.25 s`、`100 s`。
- decision time：`5 + Δ s`。
- delayed offset：`2.5 s`，所以 action time 为 `7.5 + Δ s`。
- terminal-pair window：`[6 + Δ, 15 + Δ) s`。
- setup：`2 s`，其中双端 retarget 为 `0.8 s / 1.4 s`，acquisition 为 `0.6 s`，因此并行双端 ready offset 为 `max(0.8, 1.4) + 0.6 = 2 s`。
- profiler horizon：`action time + setup + 1e-7 s`。
- traffic phases：`[5 + Δ, 9 + Δ)` 与 `[9 + Δ, 15 + Δ)`。
- drain horizon：`75 + Δ s`。

所有 duration、业务率、容量、传播时延、delayed offset 保持不变。decision/action、profiler horizon、terminal window、visibility end、Gate B future events、traffic phase boundaries、arrival horizon 和 drain horizon 全部加同一个 `Δ`。

## 3. 必须保持一致的结果

每个平移 replay 必须满足：

1. `t_action - t0 = 2.5 s`；
2. `t_ready - t_action = 2 s`；
3. `L_remain = t_end - t_exec = 7.5 s`；
4. `L_usable = t_end - t_ready = 5.5 s`；
5. Gate C accept/reject、reject reason 与 transition classification 一致；
6. BBM/MBB 类型、相对时间下的 terminal/graph/route/queue/in-flight 轨迹一致；
7. delivered work、transition backlog、J、mean-bit delay、reversal 与 censor 状态一致；
8. work conservation、非负队列和容量约束通过。

事件与轨迹先把绝对时间减去各自 `Δ`，再规范化比较。业务量只消除低于既有 `0.01 bit` 状态容差的浮点噪声，不放宽任何科学验收阈值。原始 JSON 和原始 traffic hash 因绝对时间戳不同而允许不同；`relative_time_canonical_hash` 与 `relative_traffic_trace_hash` 必须完全相同。

## 4. DELAYED 专项语义

DELAYED action 必须在 `t_exec = t0 + δ` 执行，并在该执行时刻重新调用 Gate C。`L_remain` 使用 `t_end - t_exec`，不得使用 `t_end - t0`。

若执行时刻已经越过 terminal-pair feasible window，分支状态必须为 `INFEASIBLE_AT_EXECUTION_TIME`，并保留原 target，不得自动替换 candidate。

adapter、Gate C profiler、terminal window 和 scenario timeline 必须声明同一个 `absolute_time_frame_id`。若 action 已平移但 profiler horizon 保留旧绝对时间，validation 必须抛出 `ABSOLUTE_TIME_FRAME_MISMATCH_STALE_PROFILER_HORIZON`，不得静默运行。

## 5. 冻结与停止规则

正式运行前冻结 Gate A–E1 文件 hash，并复验 Gate E1 正式证据仍为 PASS。专项回归同时执行专用测试、重复 replay 和 A–E1 全回归。

只有全部 acceptance checks 通过时，状态才可写为：

`PRE_E2_ABSOLUTE_TIME_REGRESSION_PASS`

任一检查失败时写为：

`PRE_E2_ABSOLUTE_TIME_REGRESSION_FAIL / STOP CONDITION`

FAIL 后不得启动 Gate E2，不得通过改 E0/E1 manifest、删除 fixture 或放宽 tolerance 获得 PASS。

正式入口：

```powershell
python tools/check_pre_e2_absolute_time.py
```
