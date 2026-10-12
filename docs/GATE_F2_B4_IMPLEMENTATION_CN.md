# Gate F2 B4 Rollout/MPC 实现

## 实现范围

本实现严格对应 Gate F2-0 Human Freeze v1，并且只完成 B4 correctness infrastructure。核心类为 `RootActionRolloutMPCController`，分支执行器为 `ExactRootActionRolloutEvaluator`，业务预测为 `CurrentRatePersistenceForecast`。

B4 在每个真实决策时刻接收与 B1–B3 相同的冻结 proposal set，评估 HOLD 和其中每个 concrete terminal-pair proposal。正常分支数不超过 17。候选源绑定器只把原 `MultiEpochControllerRunner` 已交给共同 proposer 的 `CandidateSpec` 按 ID 提供给 B4，不产生、重排或剪枝候选。

## Clone 与预测

每个分支调用现有 `TransitionAwareNetworkServiceEngine.clone()`。该接口保留 terminal/reservation/event、`G_active/G_admit`、`Q/I/D`、累计守恒量、路由器、物理时间、窗口和所有已承诺事件。clone 后才挂接 branch-local current-rate-persistence trace；live engine 和其他分支不共享可变状态。

预测只读取根时刻的 `lambda_f(t)`，并在 `[t,t+10s]` 内保持不变。所有分支使用同一个 forecast hash。branch trace 不读取 live immutable trace 后续 segment。

## Root action 与真实网络动力学

HOLD 分支不提交重构。REPLACE 分支通过原 `TerminalPairPhysicalFeasibility → OperationalPolicy → ScriptedProposal → TerminalExecutor` 路径执行，并保留真实 BBM/MBB、DRAINING、LINK_DOWN、RETARGETING、ACQUIRING、LINK_UP 和自然到期。

根动作后不再产生自愿 topology action。传播、TX、路由、fair-share service 和 `Q/I/D` 仍由原 D2 事件引擎推进。假想分支状态在评分后丢弃；live runner 只接收最终的根 `ControllerAction`，再通过原 Gate B/C 路径执行。

## 精确目标

分支分数直接复用 D0/D1/D2 的事件驱动 unfinished-work accumulator：

\[
J_H=J_{engine}(t+10)-J_{engine}(t).
\]

因此历史 `J` 自动抵消，且没有新增数值积分。rollout 精确停在 `t+10s`，不 drain，不追加 `V_v2`、末端 backlog、setup、switch、outage 或其他人工 penalty。自然到期和暂时无路仍是合法分支后果，通过真实 `Q/I/D` 进入 `J_H`。

## 选择与安全

选择最小 `J_H`。HOLD 与 REPLACE 精确同分时 HOLD 胜；REPLACE 同分时使用共同 proposer 原始 canonical order。非法根 REPLACE 记为 `+infinity` 并保存 Gate C、安全层或 Gate B 的精确拒绝原因。

`Z_SPARSE_REFERENCE` 使用 2 s controller-induced transition outage 上界；`Z_MODERATE` 在 `G_admit` 上执行严格全程连通。安全层只拒绝，不替换候选。

## 科学边界

该实现与测试只证明接口和因果语义正确，不比较 B0–B4 性能，不选择控制器参数，不宣称 10 s horizon 最优，也不启动 F3、RL/PPO 或主规模 sweep。

