# Gate F1 科学评分实现

## 实现范围

本实现只落地已冻结的 Gate F1 Scoring Human Freeze v2，不改变公式、参数、候选预算、决策周期、路由公平性或 Gate B/C 执行语义。

共享实现位于 `src/dynamic_lisl/scientific_snapshot.py`。`ScientificSnapshotEvaluator` 对 HOLD 或 candidate 的 admitted topology 在当前时刻重算 source-to-destination route 与所有 node-local next hop；它从现有 D2 engine 读取当前 queue、source lambda 和 `in_flight.arrival_rates`，不使用 aggregate `I_f` 判断 service demand，不推进时间，也不运行 rollout。

每条 directed edge 的正 demand 直接交给现有 `dynamic_lisl.service_scheduler.equal_weight_fair_share`。没有实现第二套 allocator，也没有恢复 v1 的 global `F_active`、`n_e` 或 `C_e/n_e`。

## V_v2

对 commodity `f`：

\[
N_f=\sum_iQ_i^f+\sum_eI_e^f,
\qquad
C_f^{prop}=\sum_{e\in P_f}d_e/c.
\]

当 node-local current-demand set 非空时，`R_f_snap` 是这些节点当前 fair-share allocation 的最小值，并使用 `Psi_f=N_f^2/(2R_f_snap)`。当 unfinished bits 仅处于传播中且没有当前本地 demand 时，不虚构 service rate，使用 `Psi_f=0`。无 source-to-destination route、正 demand 无 admitted next hop、或正 demand 获得非正 allocation 时，目标拓扑价值为 `+infinity`。

最终共享函数返回：

\[
V_{v2}(G,t)=\sum_{f:N_f>0}[N_fC_f^{prop}+\Psi_f].
\]

该值仍是 `CURRENT_STATE_ONLY` snapshot proxy，不是精确 `J`、精确 delay 或精确 residual-work cost。

## B0–B3

- B0 继续使用既有 `StaticHoldController`，永远不主动重构。
- B1 使用 `IgnoreSetupDynamicController`，比较 HOLD 与全部 candidate 的同一个 `V_v2`。精确并列时 HOLD 胜出，candidate 并列按 proposer 顺序。零 setup 只存在于评分；选中的动作仍由 `MultiEpochControllerRunner` 送入真实 Gate B/C。
- B2 继续使用既有参数化 `HysteresisMinimumHoldController` 包装 scientific B1，并直接消费 metadata 中的 `DeltaV=V_H-V_c`。本 Gate 未冻结或搜索 F3 参数网格。
- B3 使用 `SetupAwareGreedyController`，先计算 `DeltaV`，再按冻结的 `eta=L_usable/L_remaining` 和 `S=DeltaV*eta` 选择最大正值。它不读取 forecast、未来 traffic、最终 J，也不调用 rollout。

B1 与 B3 都调用同一个 `ScientificSnapshotEvaluator`；B2 的 base signal 来自同一个 scientific B1。

## 验证边界

新增 25 项 deterministic scientific-scoring tests，逐项覆盖用户合同 A–Y。另有 160 星自然 Gate C candidate 的限定语义 sanity：B1/B2/B3 使用同一冻结 proposer 和 current-state scoring；一个单独标注的 `TEST_ONLY_NATURAL_GATE_B_C_EXECUTION_PROBE` 只验证同一自然候选能经过真实 Gate B/C，不参与科学评分或性能比较。

本实现未加入 B4/MPC、B5 main-scale oracle、matching、RL/PPO、训练、参数搜索或 controller performance ranking。
