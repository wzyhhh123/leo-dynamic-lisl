# Gate F0：Topology Controller 合同

## 正式状态

**Gate F0 topology-controller contract = PASS_WITH_HUMAN_FREEZE_ITEMS**。

本 Gate 只冻结控制问题、接口、公平规则和实验边界。没有实现 B0–B5，没有运行 controller performance，也没有启动 F1/F2/F3 或 RL。

## 研究问题与控制层

研究问题冻结为：在 persistent dynamic LISL network 中，面对时变多 OD 聚合业务、有限 dynamic LCT、双端 terminal occupancy、非零且有状态的重构时间、有限 terminal-pair lifetime、persistent queues 与 shared-network congestion，控制器在统一 decision epoch 选择 HOLD 或一个合法 terminal-level topology reconfiguration，使

[
J=sum_fint N_f(t),dt,qquad
N_f(t)=A_f(t)-D_f(t)=sum_iQ_i^f(t)+sum_eI_e^f(t)
]

最小。

Gate F 控制 slow-layer persistent topology reconfiguration。packet next hop 继续由统一 fast router 决定，controller action 中禁止携带 next-hop。

## Action 合同

每个统一 decision epoch 最多输出一个动作：

- `HOLD(decision_time_s, absolute_time_frame_id)`；
- `REPLACE(decision_time_s, absolute_time_frame_id, old_physical_binding, new_terminal_pair)`。

`old_physical_binding` 和 `new_terminal_pair` 都必须给出两端 satellite ID 与具体 D1/D2 terminal ID。controller 不得声明 BBM 或 MBB：

- 新 terminal pair 复用 occupied terminal 时，Gate B 自然执行 terminal-level BBM；
- 新 terminal pair 双端真实 IDLE 且 `old_physical_binding` 可在 LINK_UP 后释放时，Gate B 才形成 genuine MBB；
- 同 peer 换 terminal 仍是新物理连接；
- controller 不能取消或改写正在 setup 的 target。

动作必须走同一因果链：

```mermaid
flowchart LR
    S[Current canonical state] --> P[Terminal-pair proposal]
    P --> C[Gate C legality]
    C --> D[Controller HOLD or SWITCH]
    D --> B[Gate B executor]
    B --> G[G_active / G_admit]
    G --> R[Common fast router]
    R --> V[Network service]
    V --> Q[Q / I / D]
```

Gate B/C 回答 **can build**；Gate F 回答 **worth building**。

## Controller-visible state

默认信息类别是 `CURRENT_STATE_ONLY`。controller 可见：

- 当前绝对时间、time-frame ID、(G_{m active})、(G_{m admit})、persistent dynamic bindings、当前 component/bridge；
- D1/D2 的 phase、current/target peer、reservation、event version、terminal free time、retarget/acquisition 时间、active start 与 visibility end；
- 当前时刻 Gate C 双边合法性、terminal-pair window、ready time、remaining/usable lifetime、plane gap、terminal conflict 与 genuine-MBB structural feasibility；
- 当前 (Q_i^f)、(I_e^f)、offered rate、service/utilization 和 current routes；
- 仅由上述当前信息计算的 (kappa_2)、当前 bottleneck、path/hop/propagation 与 conflict 特征。

每个 derived feature 必须能由相同 canonical current state 重放得到。

## Future-information policy

三个信息等级被冻结：

| 等级 | 允许范围 |
|---|---|
| `CURRENT_STATE_ONLY` | 当前状态与当前已知 Gate C window；不得读未来 traffic realization、未来 action、最终 J |
| `SHORT_HORIZON_FORECAST` | 使用所有相关 controller 共享的 forecast source 与 horizon；不得读真实未来 realization |
| `ORACLE_SMALL_FIXTURE_ONLY` | 只用于 tiny fixture 的 exhaustive legal action 与 short-horizon evaluation，不进入 160/240/720 主比较 |

forecast source 与 horizon 数值尚无冻结依据，进入人工决定清单。

## Decision epoch 合同

以下相对事件语义已经冻结：

1. 同一实验中的所有 controller 使用相同 decision epochs。
2. 在时间 (t)，先结算已承诺的 propagation-rate events，再处理 Gate B 同时刻 terminal events。
3. controller 观察 (t) 时刻右连续的 current traffic state。
4. 动作经过 Gate C、scenario safety policy 与 Gate B 后，才更新 (G_{m active}/G_{m admit})、route 和 service。
5. Gate B 同时刻优先级沿用：visibility expiry → TX completion → LINK_DOWN → retarget events → LINK_READY。
6. setup target 不可取消或改写。setup 期间只能 HOLD，或使用与所有现有 reservation 完全不相交、且 Gate C 合法的 terminal pair。
7. natural expiry 只触发物理 LINK_DOWN，不隐式替 controller 选择修复动作。

现有 A–E2 没有唯一给出 periodic cadence、event-trigger policy、expiry 后是否立即决策和 minimum reaction interval。这些数值/规则不在 F0 中臆造，集中列入 human-freeze 文档。

## Candidate proposal 合同

proposal 输出单位必须是 concrete terminal pair，并包含 proposal ID、current-state hash、old binding、new terminal pair、Gate C 结论与原因、ready/remaining/usable lifetime、plane gap、terminal conflicts、genuine-MBB structural feasibility 和 deterministic tie key。

proposal 必须：

- 尊重 Gate C bilateral feasibility、terminal occupancy 与 reservation；
- 排除已经失效的 binding；
- 相同 canonical state 下确定性一致；
- 不读取最终 J、未来真实 performance 或 controller identity；
- 在主规模禁止无界 exhaustive terminal-pair search。

接口采用 top-K 形式，但 K、ranking 和 pruning 尚无依据，留待人工冻结。

## Common routing、公平性与目标

Primary router 固定为 `DeterministicShortestPropagationDelayRouter`。Robustness 合同名为 `DeterministicCurrentStateLoadAwareRouter`，当前实现类为 `DeterministicLoadAwareRouter`。同一个 controller 比较中必须先完整运行 primary；robustness 使用完全相同的 topology scenario、traffic trace、controller parameters、initial state、decision epochs 和 candidates，只替换 common router。

主目标只使用 unfinished-work (J)。禁止向主目标加入 switch/setup/outage penalty 或手工 reward。transition cost 通过 service loss、rerouting、queue buildup、delayed benefit、natural expiry 和 shared congestion 自然进入 (J)。

## Secondary metrics

冻结的指标包括 mean bit delay、delivery、residual backlog、peak/area queue、link utilization、route/switch/BBM/MBB count、transition backlog、partition node-time、active-dynamic-link time、controller runtime、candidate count 和 rollout count。

从 Gate F 起必须分开：

- `transition_period_outage_s` 与逐 commodity 版本；
- `post_expiry_no_route_s` 与逐 commodity 版本。

旧的累计 `forced_outage_duration` 只能作为诊断值，不能再承担主要机制解释。

## Traffic、censor 与公平实验

复用 D0 的 aggregate OD、persistent queue、immutable external trace、reference (alpha^*)、(ho) scaling 和 stable → hotspot → migration → recovery，不重新设计 traffic semantics。

`CENSORED_AT_DRAIN_LIMIT` 必须保留并报告 residual backlog、delivery 与 censor 状态。不得用 truncated J 排名，不得删除，也不得解释为 packet loss。完整 run 可按 J 比较；混合 complete/censored 的总体 controller ranking 尚无冻结依据，当前只按注册 stratum 报告 censor 数和 residual-backlog distribution。

所有 controller 共享 initial topology/terminal state、traffic、geometry、Gate B/C、capacity、scheduler、router、decision epochs、candidate universe/budget、forecast source 和 drain rule。确定性算法要求 canonical replay 一致；若以后启用 stochastic sanity baseline，seed policy 必须先冻结。

## Safety boundary

Safety layer 只可拒绝 Gate C illegal action、terminal conflict、无法在 window end 前 ready 的 setup、违反 scenario-frozen connectivity policy 的 transition，并维护 Gate B atomicity。

Safety layer不得依据 J 替换 action、替 Ignore-Setup 规避经济性差但物理合法的动作、替某算法挑更好 terminal，或用未来信息修复决策。

## Topology regimes 与规模

`Z_SPARSE_REFERENCE` 正式保留：160 星、3 条跨轨 dynamic links、三条全为 bridge，动态端口占用 6/320=1.875%。它适合 bridge/outage 机制，但不能单独支撑一般 controller 结论，也不能自然提供 connected-BBM。

`Z_MODERATE` 的流量无关、结果盲原则已经冻结：只用 Gate C legality、terminal resources、connectedness、non-bridge presence、plane coverage 和 deterministic tie-break；禁止使用 J、delay、reversal 或 controller result。三个结构候选为最小 plane-cycle closure、balanced plane-pair redundancy、terminal-occupancy band。最终方案和密度需要人工冻结。

规模 registry：160 为主开发，240 为泛化，720 保留给后续 scalability/representative evaluation。F0 不运行任何规模实验。

## 停止条件

F1/F2/F3 与 RL 均保持未启动。所有 human-freeze 项解决前，不得开始公平 controller 实现与比较。
