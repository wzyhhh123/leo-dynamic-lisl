# Gate F1 多时刻控制基础设施

## 复用边界

Gate F1 没有建立第二套网络仿真器。`MultiEpochControllerRunner` 是 `TransitionAwareNetworkServiceEngine` 外的一层薄适配器，继续复用 Gate B terminal executor、Gate C terminal-pair legality、`G_active/G_admit`、common router 和 D1/D2 的 Q/I/D 服务与守恒逻辑。

## 时间语义

控制器只在 `t_k = t0 + 2k s` 被调用。每个 epoch 先由既有引擎结算已承诺传播事件和 Gate B 同时刻事件，再暴露 right-continuous 当前状态。LINK_UP、LINK_DOWN、natural expiry 和普通 topology event 不触发额外 callback；它们在两个 epoch 之间仍按精确时间改变 terminal、graph、routing 和 service。

控制器可见快照包含当前 `G_active/G_admit`、terminal、Q、I、当前业务率、当前服务率和当前路由。快照不包含 future traffic trace、future action、forecast、最终 J 或性能标签。

## 候选与安全

`FrozenTerminalPairProposer` 只执行冻结的物理/资源/安全 hard pruning。合法候选按 `MBB_STRUCTURALLY_FEASIBLE` 和 `BBM_REQUIRED` 分层，使用 8/8 配额与不足一侧的确定性 spillover，总数不超过 16。类内排序严格为 usable lifetime 降序、plane gap 升序、old/new binding 和 proposal ID 字典序。

proposer 不接收 queue、J、未来业务、controller identity 或下游结果。相同 executor state、epoch 和 regime 生成相同 canonical proposal-set SHA。

安全层按 regime 固定：

- `Z_SPARSE_REFERENCE`：controller-induced transition outage 不超过 2 秒，等号允许；
- `Z_MODERATE`：整个 transition 的 `G_admit` 必须连通；
- 两者都只允许 reject，不能替换 terminal、改成 MBB 或选择第二候选。

## 动作记录

每个 epoch 记录 controller ID、epoch、current-state SHA、proposal-set SHA、HOLD/REPLACE、具体 proposal ID、Gate C/safety 拒绝原因、Gate B 实际 BBM/MBB 类型和 action canonical SHA。控制器只能引用公共 proposal set 中的具体 terminal-pair action，不能指定 packet next hop。

## Baseline 状态

- B0 已实现：每个 epoch 返回 HOLD；不阻止自然 expiry。
- B1 已实现接口、setup=0 决策标记和真实 setup 执行链；科学评分公式未冻结。
- B2 已实现 parameterized minimum-hold / improvement-threshold wrapper；F3 参数 grid 未冻结，测试数值仅用于逻辑验证。
- B3 已实现 CURRENT_STATE_ONLY 防火墙和真实 setup metadata 接口；科学评分公式未冻结。
- B4/B5、matching、MPC、RL/PPO 均未实现。

## Outage 指标

`derive_separated_outage_metrics` 从既有 Gate B 和 route-state 日志派生：

- `transition_period_outage_s`；
- `transition_period_no_route_by_commodity_s`；
- `post_expiry_no_route_s`；
- `post_expiry_no_route_by_commodity_s`。

transition 与 post-expiry 使用不重叠时间交集，避免双重计数。旧 `forced_outage_duration` 只作为 diagnostic；底层网络动力学未改变。

