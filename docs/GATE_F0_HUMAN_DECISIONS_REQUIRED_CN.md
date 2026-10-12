# Gate F0：需要人工冻结的决定

## 状态

以下项目没有足够的冻结证据，F0 不填写默认数值。**在开始 F1 controller 实现前，应至少解决 1–5；在开始 F3 performance 前，必须全部解决。**

## 1. Decision epoch

需要决定：

- periodic cadence (T_{m decision})；
- topology event、LINK_UP/LINK_DOWN 与 natural expiry 后是否触发额外 epoch；
- minimum controller reaction interval；
- periodic 与 event-trigger 同时发生时是否合并为一个 epoch。

已冻结的相对 priority 是：先结算 propagation 与 Gate B terminal events，controller 再观察 current state 并提交一个动作，随后更新 graph/route/service。

**不得**让不同 controller 使用不同 epoch schedule。

## 2. Candidate top-K、ranking 与 pruning

需要决定：

- 统一 K；
- structural/current-state ranking rule；
- pruning 是否按 plane gap、lifetime、terminal conflict 或 redundancy；
- B0/B5 等不使用普通 proposer 时如何记录公平 proposal budget。

K 不能根据最终 J 调优。主规模禁止无界 exhaustive search。

## 3. Forecast source 与 MPC horizon

需要决定：

- shared forecast source；
- forecast horizon；
- forecast 更新节拍；
- forecast error/replay trace 的冻结方式；
- rollout evaluation budget。

普通 baseline 和 proposed 若使用 forecast，必须看到同一个 forecast，不能读取 actual future realization。

## 4. Z_MODERATE 方案与密度

共同规则已冻结，但需要从以下方案选择并冻结数值：

1. `ZM_A_MINIMAL_PLANE_CYCLE_CLOSURE`：最小 plane-level cycle closure。机制清楚，但 occupancy 可能仍过低。
2. `ZM_B_BALANCED_PLANE_PAIR_REDUNDANCY`：每个选定 plane pair 固定相同 link count。需要冻结 count。
3. `ZM_C_TERMINAL_OCCUPANCY_BAND`：达到目标 dynamic-terminal occupancy band。需要冻结 occupancy band。

同时需要冻结 construction epoch/scenario-time policy、目标 link/occupancy、plane-pair coverage 和 infeasible 时的报告方式。构造过程禁止读取 traffic、J、delay、reversal 或 controller result。

## 5. Scenario hard-connectivity policy

需要明确各 topology regime 的安全策略：

- `STRICT_CONNECTED`；或
- 预注册的 `BOUNDED_OUTAGE(T_max)`。

同一 scenario 中所有 controller 必须使用相同 policy。Safety 只能拒绝，不得替换 action。

## 6. Hysteresis/minimum-hold grid

需要冻结：

- minimum-hold candidate values；
- improvement-threshold definition 与 values；
- B2 的 base signal 是 B1 instantaneous value 还是另一个注册的 current-state signal。

数值不能根据 B2 performance 结果后选。

## 7. Controller evaluation grid

F3 轴已经注册为：

- (ho)；
- traffic regime；
- topology regime；
- common router；
- system scale。

需要冻结 cross-product、replicate/seed policy 和哪些轴属于 primary/robustness。E2 的 (ho) grid 不能自动当作 F3 grid，因为 D0 主 grid 原本 deferred，E2 grid 是机制验证注册域。

## 8. Mixed censor ranking

当前只允许：

- COMPLETE run 用完整 J 比较；
- CENSORED run 报 residual backlog、delivery ratio 与 censor status；
- 按注册 stratum 报完成率与 residual-backlog distribution。

需要人工决定 controller-level mixed-censor ranking/统计方法。冻结前禁止构造 scalar penalty，也禁止使用 truncated J 排名。

## 9. Stochastic seed policy

只有启用 optional random baseline 或未来 stochastic controller 时才需要。必须在首次运行前冻结 seed list、replicate count 与 aggregation rule。

## F1 blocker

仿真器接口没有 blocker。当前阻止进入 F1 的是第 1–5 项尚未人工冻结：它们决定 controller callback 的时间、proposal budget、forecast interface、moderate topology asset 和 safety policy。解决后才应开始 baseline/proposed controller 实现。
