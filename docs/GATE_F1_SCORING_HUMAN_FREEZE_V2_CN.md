# Gate F1 Scoring Human Freeze v2

## Scheduler-Consistent Current-Service Snapshot

## 1. 状态与版本边界

本文件是新的不可变评分 overlay。它承接 Gate F1 Scoring Human Freeze v1 及其 semantic audit，只替换 v1 的以下定义：

- 全局 `F_active(t)`；
- `n_e(G,t)`；
- `r_{e,f}(G,t)=C_e/n_e(G,t)`；
- 由上述三项形成的 `R_f` service-participation semantics。

以下内容保持不变：B1 在 HOLD 与全部 candidate 中选择最小拓扑价值；B2 使用 `DeltaV_c=V_H-V_c`；B3 使用 `eta_c=L_usable,c/L_remaining,c` 和 `S_c=DeltaV_c*eta_c`。所有 tie rule、真实 Gate B/C setup、proposer、cadence、router fairness 和 safety boundary 均不变。

本 overlay 不修改 B1/B2/B3 scientific implementation，不推进仿真时间，不调用 rollout，不运行 controller performance，也不启动 F2、F3 或 RL。

## 2. 保留的路径、传播与未完成工作定义

对每个候选拓扑 `G`，使用当前实验所选的同一个冻结 common router 重新计算 admitted route。流 `f` 的 source-to-destination 路径为 `P_f(G,t)`，传播代价为

\[
C_f^{prop}(G,t)=\sum_{e\in P_f(G,t)}\frac{d_e(t)}{c}.
\]

未完成工作保持为

\[
N_f(t)=A_f(t)-D_f(t)=\sum_iQ_i^f(t)+\sum_eI_e^f(t).
\]

## 3. 与现有 scheduler 一致的节点局部 demand

不定义全局 active commodity set。对每个当前 `(node i, commodity f)`，在候选拓扑 `G` 上重新计算合法 admitted next hop `h_{i,f}(G,t)`。

本地输入 `u_{i,f}(t)` 完全沿用 D1/D2：

- 在 commodity source，加入当前外生 `lambda_f(t)`；
- 对所有当前到达节点 `i` 的传播流，加入对应 `in_flight.arrival_rates`；
- aggregate `I_f` 只参与 unfinished-work accounting，不作为 service-demand 指示器。

数值边界沿用执行器：backlog 判定使用当前 engine 的冻结 `state_tolerance_bits`，本项目 Gate D0 正式值为 `0.01 bit`；正 input 判定使用现有 `1e-15 bit/s`；实现中的 queue-key scan `1e-12 bit` 只负责建立候选 key，不改变最终正 demand 判定。

节点局部 demand 冻结为：

\[
d_{i,f}(G,t)=
\begin{cases}
0, & i=d_f,\\
\text{invalid}, & \text{存在必须转发的正 demand，但无合法 admitted next hop},\\
+\infty, & Q_i^f(t)>\epsilon_Q,\\
u_{i,f}(t), & Q_i^f(t)\le\epsilon_Q,\ u_{i,f}(t)>\epsilon_u,\\
0, & \text{otherwise}.
\end{cases}
\]

其中 `epsilon_Q=engine.state_tolerance_bits`，`epsilon_u=1e-15 bit/s`。

对每条 directed edge，收集 next hop 为该边的全部正本地 demand，并调用现有：

`dynamic_lisl.service_scheduler.equal_weight_fair_share(capacity_bit_s, demands_bit_s)`。

禁止复制或重新实现第二套 fair-share allocator。其输出中 `(i,f)` 对应的当前分配记为 `mu_{i,f}(G,t)`。

## 4. 当前 demand 集合与服务快照代理

定义节点局部集合

\[
\mathcal D_f(G,t)=\{i:d_{i,f}(G,t)>0\ \text{且存在合法 admitted next hop}\}.
\]

若该集合非空，定义

\[
R_f^{snap}(G,t)=\min_{i\in\mathcal D_f(G,t)}\mu_{i,f}(G,t).
\]

`R_f_snap` 只解释为 **current-service bottleneck snapshot proxy**，不是精确端到端吞吐率。如果任一必须转发的正本地 demand 无合法 admitted next hop，或任一正 demand 得到的 `mu<=0`，则目标拓扑价值为 `+infinity`。

## 5. in-flight-only 显式边界

可达状态可能满足 `N_f>0`，但所有 bit 都处于纯传播阶段，因而 `D_f(G,t)` 为空。此时不令 `R_f=0`，不令 `V=+infinity`，也不虚构 service rate，而是冻结：

\[
\Psi_f(G,t)=0.
\]

当 `D_f(G,t)` 非空时：

\[
\Psi_f(G,t)=\frac{N_f(t)^2}{2R_f^{snap}(G,t)}.
\]

“source-to-destination route 不存在”与“route 存在但当前没有节点局部 demand”是不同状态。前者对任意 `N_f>0` 仍令目标拓扑价值为 `+infinity`；后者使用 `Psi_f=0`。

## 6. v2 拓扑价值

\[
V_{v2}(G,t)=\sum_{f:N_f(t)>0}
\left[N_f(t)C_f^{prop}(G,t)+\Psi_f(G,t)\right].
\]

优化方向保持 `MINIMIZE`。

`V_v2` 是 source-to-destination aggregate unfinished-work 的 `CURRENT_STATE_ONLY` 解析快照代理。`N_f` 同时包含 queue 与 in-flight bits，一些 in-flight bits 已经走完部分路径。因此 `N_f*C_f_prop` 不是精确的剩余传播 work；当当前 service demand 存在时，`N_f^2/(2R_f_snap)` 也只是恒定当前 service 假设下的 queue-area proxy，不是精确多跳 residual-work area 或未来 queue evolution。该近似是有意保留的。

## 7. B1/B2/B3 保持不变

### B1 — Ignore-Setup Dynamic

\[
V_H=V_{v2}(G_{current},t),\qquad V_c=V_{v2}(G_c^{ideal},t).
\]

在 HOLD 与全部 candidate 中取最小值。candidate setup 只在决策评价时视为零；真实 REPLACE 仍经过真实 Gate B/C setup。

### B2 — Hysteresis / Minimum-Hold

\[
\Delta V_c=V_H-V_c.
\]

本 overlay 不冻结 F3 的 minimum-hold 或 hysteresis 数值网格。

### B3 — Setup-Aware Greedy

若 `DeltaV_c<=0`，经济性拒绝该 candidate。否则：

\[
\eta_c=\frac{L_{usable,c}}{L_{remaining,c}},\qquad
S_c=\Delta V_c\eta_c.
\]

选择正 `S_c` 最大的 candidate；不存在则 HOLD。

HOLD 与 REPLACE 精确并列时 HOLD 胜出；REPLACE 之间并列时使用冻结 proposer canonical order。仍禁止 trainable coefficient、alpha/beta/gamma 权重、realized future traffic 和 performance-based tuning。

## 8. 兼容性验收与冻结结果

验收器必须用未修改的 D2 engine 重现两个 `Q=0, lambda=0, I>0` 状态：

- 纯传播空档：本地 demand 为空，`D_f` 为空，`Psi_f=0`，有路时 `V_v2` 有限；
- 下游 arrival stream：下游 `u_i,f>0`，`D_f` 非空，直接使用现有 fair-share allocation，`R_f_snap` 有定义。

同时要求无除零、确定性重放一致、不需要全局 `F_active`，所有父 hash 不变。

冻结状态：

- `Gate F1 Scoring Human Freeze v2 = PASS`；
- `scheduler_semantics_aligned = true`；
- `inflight_only_edge_case_resolved = true`；
- `B1_B2_B3_scientific_implementation_readiness = READY`；
- `F2/F3/RL started = false`。

机器合同位于 `configs/gate_f1_scoring_human_freeze_v2.json`，正式验收入口为 `python tools/check_gate_f1_scoring_human_freeze_v2.py`。
