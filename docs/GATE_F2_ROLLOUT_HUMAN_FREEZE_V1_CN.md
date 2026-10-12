# Gate F2-0：Rollout / MPC 合同 Human Freeze v1

## 状态与边界

本文件只冻结 B4 rollout/MPC 的科学语义。Gate F1 infrastructure、Scoring Human Freeze v2、B0–B3 科学实现和 Gate F1 closure 均已通过；F2 readiness 为 `READY`。本轮不实现 B4，不运行性能比较，不启动 F2/F3/RL，也不修改 A–E2、F0、F1、Scoring v1/v2、Z_SPARSE 或 Z_MODERATE 的冻结资产。

## 冻结输入

- 真实控制决策周期为 2 s。
- 共同 proposal budget 为 top-K=16，结构配额为 MBB 可行 8 个、BBM 必需 8 个，spillover 和排序沿用 F0 Human Freeze v1。
- 相同状态、决策时刻和 topology regime 下，B1/B2/B3/B4 必须获得相同 proposal set。
- B4 信息级别为 `SHORT_HORIZON_FORECAST`，交通预测为 `CURRENT_RATE_PERSISTENCE`，预测长度 10 s、每个真实 2 s 决策时刻重建。
- 分支只读取当前 `lambda_f(t)`，并令整个分支内 `lambda_hat_f(t+tau)=lambda_f(t)`。禁止读取 immutable trace 中尚未实现的未来业务段。
- 可以使用确定可知的 SGP4/Gate C 几何、候选窗口、自然到期和 Gate B 已承诺事件。

## 分支与克隆

每个真实决策时刻恰好评估 HOLD 和冻结 proposal set 中每个候选，正常分支数不超过 17。B4 内部不得新增候选，也不得先用 rollout 分数重排或剪枝。

所有分支从同一个决策时刻的右连续 canonical state 精确克隆。克隆内容包括 terminal、reservation、Gate B pending events、`G_active/G_admit`、`Q/I`、arrival-rate events、守恒所需累计量、router、时间、Gate C 几何、候选窗口和确定性物理事件。分支不能修改 live engine，彼此不能共享可变对象；执行顺序不能改变分数。clone isolation 与 branch-order invariance 是后续实现必须通过的正确性测试。

## Root-action-only MPC

B4 冻结为 root-action-only receding-horizon controller。HOLD 分支在根时刻不发出重构；candidate 分支只在根时刻通过真实 Gate C、安全层和 Gate B 执行该 REPLACE。之后 10 s 内不允许新的自愿拓扑动作；内部的 2、4、6、8、10 s 决策点对新重构一律 HOLD。

物理与网络过程仍须完整推进：传播事件、Gate B 状态迁移、DRAINING/LINK_DOWN/RETARGETING/ACQUIRING/LINK_UP、自然到期、Gate C 窗口变化、`G_active/G_admit` 变化、共同路由、服务分配以及 `Q/I/D`。B4 不能在 rollout 中递归调用自身，不能用 B1/B2/B3 充当未来策略，也不能构造指数动作树。下一个真实 2 s 决策点再基于 live state 重新求解。

## 目标与边界

每个合法分支最小化

\[
J_H(a;t)=\sum_f\int_t^{t+10s}N_f^a(\tau)d\tau,
\qquad
N_f=A_f-D_f=\sum_iQ_i^f+\sum_eI_e^f.
\]

这是显式网络动力学 rollout。setup 代价只通过真实 transition 对 routing、service 和 `Q/I/D` 的影响进入目标。禁止加入 `V_v2` terminal penalty、拓扑分、setup/switch/outage/hysteresis penalty、学习 value function 或 alpha/beta/gamma 权重。

rollout 在 `t+10 s` 精确结束，不继续 drain，不加 terminal backlog penalty，也不追加 `V_v2`。末端 backlog 只作为诊断量。该有限截断是 B4 的固定性质，10 s 不被宣称为最优。

## 非法分支与选择

HOLD 总是评估。候选仅在根 REPLACE 无法依据冻结 Gate C、regime safety 和 Gate B 从克隆状态合法执行时判为非法，记 `J_H=+infinity` 并保存精确拒绝原因。若共同 proposer 已做 hard prune，这一情况同时是 proposer/executor 一致性诊断。

后续自然到期、暂时无路、积压上升或 delivery 下降都是合法物理后果，不能把分支判为非法。

选择最小 `J_H`。HOLD 与 REPLACE 精确同分时 HOLD 胜；多个 REPLACE 精确同分时按冻结 proposer canonical order；无 deadband、无随机打破平局。

## 路由与安全公平性

同一实验中所有分支及 B0–B4 使用同一个共同 router。主 router 为 `DeterministicShortestPropagationDelayRouter`，robustness router 为冻结的 `DeterministicCurrentStateLoadAwareRouter`。

`Z_SPARSE_REFERENCE` 使用 2 s 的 controller-induced transition outage 上界；`Z_MODERATE` 要求 controller-induced transition 全程在 `G_admit` 上严格连通。安全层只拒绝，不替换候选。自然到期后的无路是 rollout 后果，不计入 controller transition outage。

## Live action 与科学解释

B4 最终只返回根动作 `HOLD` 或 `REPLACE(old binding, new concrete terminal pair)`。live system 通过共同真实 Gate B/C 路径执行；所有假想分支状态在评分后丢弃，不得覆盖 live state。

B3 是 setup-aware current-state greedy；B4 是在共同 10 s current-rate-persistence 预测下显式模拟 transition、routing、service、queue 后果的短时预测控制器。B4 不被描述为全局最优。

## 冻结结论

该合同唯一固定了 branch set、same-state clone、预测、防止未来泄漏、10 s horizon、root-only action、真实 Gate B/C 与网络演化、精确 `J_H`、非法分支、tie、router 公平性、安全语义、live-state 隔离和 receding-horizon 解释。B4 实现仍不存在；下一步仅能在另行授权后从 correctness fixtures 开始。

