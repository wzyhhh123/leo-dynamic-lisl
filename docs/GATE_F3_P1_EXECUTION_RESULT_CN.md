# Gate F3 P1 新授权执行结果

## 正式状态

`Gate F3 P1 execution = BLOCKED`

`P1 result seal = NO`

`P1 registered runs executed = 0/12`

`P1 COMPLETE = 0, CENSORED = 0, FAILED = 1`

P2、R1--R4 和 RL/PPO 均未启动。

## 已完成的执行前检查

执行前确认了 F3、execution manifest 和 F3-0.1 overlay 的 canonical SHA-256，复验了全部冻结 parent hash、148 项 A--E2 hash、历史阻塞证据以及 12 个 P1 manifest 行。执行前检查全部通过，traffic identity 的三档 hash 也与 manifest 完全一致。

## 阻塞位置

按冻结顺序启动的首项为：

`F3V1-P1-Z_MODERATE-SHORTEST_PROPAGATION_DELAY-TRAFFIC_HOTSPOT_MIGRATION_V1-RHO0p5-B0`

该模拟到达运行后封存阶段时，新增 P1 执行适配器的 aggregate invariant check 返回失败并抛出：

`P1_RUN_INVARIANT_FAILURE ... RHO0p5-B0`

适配器在写出 `invariant_report.json` 之前执行了 aggregate `pass` 断言，因此失败子项没有被持久化；现有证据无法可靠区分失败来自 conservation、capacity、queue nonnegative、drain/status 或 reporting-only candidate-cap 检查。为避免把执行层问题误报成科学模型问题，本次 blocker 记录为：

`GATE_F3_P1_EXECUTION_BLOCKED_BY_POST_RUN_INVARIANT_AGGREGATE_FAILURE_WITH_UNPERSISTED_SUBCHECKS`

这是本次新建执行/报告层的可观测性缺陷。目前没有证据证明冻结的 B0 或服务引擎违反了哪一项科学不变量，也不能在缺少证据时宣布它们通过。

## Stop rule 执行情况

异常发生后立即停止。没有跳过首项，没有启动后续 11 项，也没有重跑首项。冻结的 controller、Gate B/C、router、service、traffic 和 manifest 均未修改；运行前后科学文件 hash 一致。旧的 `GATE_F3_P1_EXECUTION_BLOCKED_BY_CANDIDATE_SOURCE_NOT_FROZEN` 文档、状态、checker 和 evidence 目录保持不变。

若要再次启动 P1，需要新的人工授权。下一次尝试前应只修复执行层的失败证据写出顺序：先持久化每个 invariant 子项和 partial run artifacts，再根据结果 STOP；不得借此修改科学算法或放宽 tolerance。
