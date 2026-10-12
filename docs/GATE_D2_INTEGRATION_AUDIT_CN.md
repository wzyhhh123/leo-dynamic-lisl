# Gate D2 集成审计

## 审计范围与结论

本审计只检查 Gate B/C 的终端与拓扑事件能否接入 Gate D1 的网络服务语义。审计没有发现需要修改历史 Gate B/C/D1 证据的 blocker bug。现有模块可以作为冻结依赖，但 D1 的 `NetworkServiceEngine.run()` 把固定边集、路由和仿真状态封装在一次调用内部，不能在运行途中接收拓扑事件。因此 Gate D2 需要新增一个编排适配层；该层复用现有 `TerminalExecutor`、`graph_state`、`CommonRouter`、`QueueState`、`InFlightState` 和公平服务调度器，不修改冻结模块，也不建立另一套终端状态机、流量生成器或路由器。

## Gate B 事件推进

`TerminalExecutor` 使用最小堆 `events`，元素为 `(time, priority, sequence, kind, payload)`。`advance(until)` 依次处理所有 `time <= until` 的事件。相同时刻的 Gate B 优先级被冻结为：可见性/setup expiry（0）、`TX_DONE`（1）、`LINK_DOWN`（2）、retarget 事件（3）、`LINK_READY`（4），同优先级再按单调递增 `sequence` 排序。`submit()` 先在深拷贝上原子执行命令，再调用 `advance(now)` 清算同一时刻的 Gate B 事件，最后整体提交试运行状态。

## Gate D1 事件推进

D1 是事件驱动的分段仿射流体执行器。真实事件包括流量 rate boundary、延迟服务段在下游开始或结束的 `RateArrivalEvent`、队列清空时刻以及可选的几何 refresh。每段内外生到达率、服务率和传播到达率保持常数，状态按解析式推进；observation grid 只插值观测，不改变状态。

D1 当前将 `directed_edges`、`capacity`、`routes` 和 `next_hop` 在构造时固定，并把 `QueueState`、`InFlightState`、traffic cursor、传播事件堆等放在 `run()` 的局部变量中。这不会破坏 D1 的固定拓扑合同，但意味着 D2 不能简单在 D1 外部替换一个边列表。

## 统一时钟与同时间微步

两套系统都使用以秒为单位的单调浮点仿真时钟，可以由同一个 orchestrator 统一。D2 冻结以下跨层顺序：

1. 将此前已承诺的连续服务、传播到达和队列变化精确积分到时刻 `t`；处理恰好在 `t` 成熟的传播 rate-change；
2. 先让 Gate B 按其既有 priority 完成 `t` 时刻已有事件，再处理预注册且已通过 Gate C/operational-policy 的 scripted proposal；命令引发的同时间 Gate B 事件仍由 `TerminalExecutor` 自己排序；
3. 应用 `t` 时刻开始生效的外生 traffic rate；
4. 从更新后的 `G_admit(t)` 重新计算确定性路由；
5. 为开区间 `(t,t_next)` 分配新服务。

这个顺序保证：旧服务在 `t` 之前已经序列化的 bit 不会消失；`DRAINING` 在 `t` 发生后，不会为 `t` 之后的新 work 分配旧边；与 `LINK_DOWN` 同时开始的新流量只看到更新后的图。

## DRAINING 时 queue 与 in-flight 的语义

Gate D1 的“已经 committed”不是 Gate B 的 synthetic `tx_end` 项，而是已经从发送端 `Q_i^f` 扣除并加入 `I_e^f` 的 bit。到达 DRAINING 时刻前已序列化的 bit 继续留在 `I_e^f`，并按照建立该服务段时冻结的 propagation delay 到达下游。尚在 queue 中的 bit 没有被承诺，DRAINING 开始后必须通过新的 `G_admit` 重新路由，或者在 `NO_ROUTE_TEMPORARY` 状态下等待。

Gate B 的 synthetic nonpreemptive TX 只决定物理 link 何时能从 DRAINING 进入 LINK_DOWN；D2 不把它当作第二份业务量，也不据此增减 Q/I/D。

## G_active、G_admit 与路由

冻结的 `transition_profiler.graph_state()` 已给出唯一图语义：fixed edges 同时属于 active/admit；非 draining dynamic link 同时属于 active/admit；draining dynamic link 仅属于 active。D2 直接调用该接口生成图快照。

`CommonRouter.routes_to_destinations()` 接收显式 `directed_edges`，因此它能直接接收每次更新后的 `G_admit`。D2 不保留跨拓扑版本的隐藏路径缓存；每当 admit edge set 改变时，用当前图、当前时间和既有确定性 tie-break 全量重算 route/next-hop。几何 refresh 可以更新权重，但不会添加未来信息。路由器看不到 future traffic、future transition、controller identity 或 fixture 后续脚本。

## natural expiry 的传播

自然到期仍由 Gate B 的 `LINK_EXPIRE` 产生 `LINK_DOWN`。编排层比较事件前后的 active/admit edge set；若变化，则走与 scripted removal 完全相同的 graph update、route invalidation、service-rate termination、reroute/NO_ROUTE 流程，不建立自然到期专用的业务逻辑。

## 状态克隆

D2 可克隆状态必须包含：

- `TerminalExecutor` 全状态，包括 terminals、links、reservations、Gate B future event heap、event versions 和 log cursor；
- `QueueState` 与 `InFlightState`，包括 delayed arrival rates；
- arrived/delivered/objective/transmitted 计数；
- traffic boundary cursor 与 immutable future trace/hash；
- 当前 active/admit 图、route/next-hop 和 route history；
- D2 propagation event heap、scripted-action cursor、同序列计数器以及 metric episode 状态。

采用 `deepcopy` 后会核对上述字段的 canonical snapshot。正常 traffic loop 不使用 RNG；因此 RNG state 为 `None`，两个分支必须具有相同 future trace hash。

## link removal 与固定图硬编码审计

现有 D1 没有“link down”路径，也没有删除 `I_e^f` 的代码。`InFlightState` 只在传播到达时按同量扣除；因此 D2 只要保留旧 edge 的 delayed arrival events，就不会因边移除丢失 work。

D1 构造时固定的 `routes`、`next_hop`、`directed_edges` 和 `capacity` 会阻碍动态图直接接入，但这些是 D1 合同的一部分，不是需要回写修复的 bug。D2 adapter 将 physical edge universe 与当前 admitted subset 分开：capacity 对可能出现的边定义，service/routing 只遍历当前 `G_admit`。旧边的 in-flight key 即使已不在当前图中也继续合法存在，直至归零。

## 实现边界

D2 adapter 只编排预注册 scripted fixtures。它不产生候选、不打分、不选择动作，不实现 HOLD/SWITCH policy、matching、MPC 或 RL。Gate C legality 与 operational-policy 只负责接受或拒绝脚本中指定的 proposal；fixture 不能按最终 J 反向挑选。
