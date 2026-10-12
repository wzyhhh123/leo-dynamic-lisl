# Gate D2 动态重构—网络服务耦合合同

## 唯一目标

Gate D2 只验证预注册的 Gate B/C terminal transition 是否真实改变 Gate D1 的 routing、service、queue、in-flight 和 delivery。它不回答何时切换，也不比较 topology controller。

因果链冻结为：

\[
\text{scripted terminal proposal}\rightarrow
\text{Gate C legality/policy}\rightarrow
\text{Gate B events}\rightarrow
(G_{active},G_{admit})\rightarrow
\text{CommonRouter}\rightarrow\text{service}\rightarrow(Q,I,D).
\]

## 图与业务准入

固定边始终同时属于 `G_active` 和 `G_admit`。ACTIVE dynamic link 同时属于两者；DRAINING dynamic link 只属于 `G_active`。routing 和新的 queue work admission 只能使用 `G_admit`。LINK_DOWN 后边不属于任何图；LINK_UP 后新边才进入 `G_admit`。

已经离开发送队列的 work 属于 `I_e^f`。即使边随后 DRAINING 或 LINK_DOWN，这些 bit 仍按原传播事件抵达下游。拓扑事件本身不得修改 A/Q/I/D。

## 统一事件时钟

执行器不使用固定数值步长。下一时刻取所有真实事件的最小值：traffic rate boundary、传播 rate-change、queue-empty、Gate B event、scripted proposal、visibility/FoR expiry 和可选 geometry refresh。

同一时刻的微步顺序为：

1. 结算 `t` 前已经承诺并在 `t` 成熟的网络 work；
2. Gate B 按冻结 priority 处理既有事件，再评估并提交该时刻的 scripted Gate C proposal；
3. 应用 `t` 起生效的外生 rate；
4. 只对更新后的 `G_admit(t)` 重算路由；
5. 为 `t` 之后分配服务。

Gate B 内部相同时刻 priority 不变。scripted proposal 在执行时只获得当前 executor、当前 Gate C 窗口和当前 operational policy，不读取未来流量或未来动作。

## no-route 与恢复

若 commodity 的 source 到 destination 在当前 `G_admit` 中无路，状态为 `NO_ROUTE_TEMPORARY`，新服务为 0，work 留在 per-node/per-commodity queue，外生到达继续，且没有 drop、teleport 或 fake delivery。图恢复后使用同一 `CommonRouter` 确定性重算并继续服务 backlog。

## 守恒与容量

所有事件前后必须满足冻结恒等式：

\[
A_f=D_f+\sum_iQ_i^f+\sum_eI_e^f.
\]

误差阈值沿用 D0/D1：每 commodity 为 1 bit 绝对误差或 \(10^{-12}\) 相对误差。每条有向边容量为 10 Gbit/s；full duplex 两方向容量独立。不得出现负队列或超过 0.01 bit/s 的数值容量越界。

## 状态克隆

same-state 分支深拷贝 terminal/executor event heap、Q、I、传播事件堆、traffic cursor、future trace、routes、计数器和 scripted-action cursor。正常 traffic loop 无 RNG。HOLD 与 scripted SWITCH 分支的 future traffic hash 必须相同；该 fixture 只证明因果隔离，不形成策略优劣结论。

## 指标

D2 填充 `BBM_count`、`MBB_count`、`route_change_count`、`no_route_duration_s`、`outage_duration_s`、`partition_duration_s`、`partition_node_time_s`、`backlog_added_during_transition_bits`、`peak_transition_backlog_bits`、`backlog_clearance_time_s`、`max_queue_bits`、`delivered_bits`、`residual_backlog_bits`、`J_bit_s` 和 `mean_bit_delay_s`。setup 不加入人工 penalty；代价只通过服务变化、积压和 J 自然体现。

## 边界

D2 不包含 automatic HOLD/SWITCH、topology scoring、matching/b-matching、greedy、hysteresis、MPC、RL/PPO、参数扫描或 720 星实验。160 星只运行 manifest 中的两个 deterministic scripted correctness case，动作不按最终 J 选择。
