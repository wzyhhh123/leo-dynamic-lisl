# Gate F1 Scoring Human Freeze v1

## 状态与边界

本文件是 Gate F1 scoring contract 的不可变人工冻结 overlay。它解决 B1、B2、B3 的标量评分歧义，但本轮不修改控制器实现、不运行性能实验，也不启动 F2、F3 或 RL。

所有 HOLD 与 candidate topology 都使用当前实验选择的同一个冻结 common router 重新计算路径。这里的路径重算只是时刻 \(t\) 的解析快照，不推进仿真时间，也不调用多步 rollout。

## 公共解析量

对候选拓扑 \(G\)，流 \(f\) 的重算路径记为 \(P_f(G,t)\)。其传播代价为

\[
C_f^{\mathrm{prop}}(G,t)=\sum_{e\in P_f(G,t)}\frac{d_e(t)}{c}.
\]

活跃业务集合冻结为

\[
\mathcal F_{\mathrm{active}}(t)=
\left\{f:\sum_iQ_i^f(t)>0\ \text{or}\ \lambda_f(t)>0\right\}.
\]

对每条有向边，令

\[
n_e(G,t)=
\left|\left\{f\in\mathcal F_{\mathrm{active}}(t):e\in P_f(G,t)\right\}\right|.
\]

按照已冻结的 equal-weight snapshot sharing rule，路径使用该边的业务获得

\[
r_{e,f}(G,t)=\frac{C_e}{n_e(G,t)}.
\]

由此定义流的路径瓶颈快照服务率

\[
R_f(G,t)=\min_{e\in P_f(G,t)}r_{e,f}(G,t).
\]

未完成工作仍为

\[
N_f(t)=A_f(t)-D_f(t).
\]

公共拓扑价值冻结为

\[
V(G,t)=\sum_{f:N_f(t)>0}
\left[
N_f(t)C_f^{\mathrm{prop}}(G,t)
+\frac{N_f(t)^2}{2R_f(G,t)}
\right].
\]

控制器最小化 \(V\)。\(V\) 是 `CURRENT_STATE_ONLY` 的解析快照代理，不是最终 \(J\)，也不是 rollout。项 \(N_f^2/(2R_f)\) 是恒定当前服务率下的 queue-area proxy，不表示精确的多跳队列演化。

## B1：Ignore-Setup Dynamic

定义

\[
V_H=V(G_{\mathrm{current}},t),\qquad
V_c=V(G_{c}^{\mathrm{ideal}},t).
\]

B1 只在决策评价时令 candidate setup 为 0，并在 HOLD 与全部候选中选择 \(V\) 最小者。真实选中的 REPLACE 仍必须经过真实 Gate B/C setup。零 setup 假设不得进入物理执行。

## B2：Hysteresis / Minimum-Hold

B2 的基础信号冻结为

\[
\Delta V_c=V_H-V_c.
\]

本 overlay 不冻结 F3 的 minimum-hold 或 hysteresis 数值网格，也不授权依据性能选择这些数值。

## B3：Setup-Aware Greedy

若 \(\Delta V_c\le0\)，candidate 在经济性上直接拒绝。否则定义

\[
\eta_c=\frac{L_{\mathrm{usable},c}}{L_{\mathrm{remaining},c}},
\qquad
S_c=\Delta V_c\eta_c.
\]

B3 选择正 \(S_c\) 最大的 candidate；若不存在则 HOLD。

## 边界规则

- 总未完成工作为 0 时，必须 HOLD；
- 若任意 \(N_f>0\) 的业务在目标拓扑下无路，令 \(V=+\infty\)；
- 若 \(R_f\le0\)，令 \(V=+\infty\)；
- 若 \(L_{\mathrm{remaining},c}\le0\) 或 \(L_{\mathrm{usable},c}\le0\)，B3 candidate 不可选；
- HOLD 与 REPLACE 精确相等时 HOLD 胜出；
- REPLACE 之间精确相等时使用冻结 proposer canonical order；
- 不存在 trainable coefficient，也不引入 alpha/beta/gamma 权重；
- 禁止读取 realized future traffic；
- 禁止 performance-based tuning。

## 冻结结果

- `B1_scalar_score_resolved = true`
- `B2_base_signal_resolved = true`
- `B3_scalar_score_resolved = true`
- `Gate F1 scientific implementation readiness = READY`
- `F2/F3/RL started = false`

机器合同及 parent hashes 位于 `configs/gate_f1_scoring_human_freeze_v1.json`，正式验收入口为 `python tools/check_gate_f1_scoring_human_freeze.py`。

