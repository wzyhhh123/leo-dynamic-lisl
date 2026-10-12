# B4 轻量精确克隆：依赖审计

## 范围与实现

本轮只优化 F3 B4 根动作预测分支的克隆，不运行 registered P1，不改变预测时域、候选集、路由、事件排序、服务分配、传播闭合或容差。最终接入只在 F3 的 ObservationalE2Engine.clone() 中进行；D2 基类和 B4 evaluator 保持原文件哈希。F3 新增 clone_legacy_reference() 仅供测试对照。独立 helper 也通过小型 D2 fixture 测试。

原始 `TransitionAwareNetworkServiceEngine.clone()` 递归复制整个执行器。真实 F3 使用 `ObservationalE2Engine.clone()`，也是先递归复制整个对象，再把分支 reporting_enabled 设为 false、reporting_samples 置空。新增方法必须保留这项子类行为。

最小优化采用 deepcopy 的局部 memo：只将已审计的历史记录自身登记为共享对象，其外层列表仍独立复制。所有记录、顺序、游标、长度都保留，不清空终端日志，不改变 canonical state/hash 的定义。共享仅限当前代码中创建后不再修改的历史记录；这与现有 TerminalExecutor transaction clone 的只读历史约定相同。它不是任意外部写入历史记录时仍保持隔离的通用 deepcopy 替代品。

## 字段依赖与复制策略

| 字段 | 作用及后续读写 | 本轮策略 |
|---|---|---|
| nodes, fixed_edges, capacity_bit_s, commodities, by_id | 拓扑节点、链路容量及 OD 定义；参与路由与流守恒 | 保留原 deepcopy 行为 |
| trace, boundaries, boundary_index | 当前外生流量及游标；克隆校验后安装 forecast | 保留原 deepcopy；不提前替换流量 |
| delay, router | 几何时延与路由状态；delay 有 cache，load-aware router 会更新状态 | 保留原 deepcopy；不引入跨分支缓存共享 |
| executor | 全部终端、绑定、预约、事件及序列号 | 深复制；只有 executor.log 中旧记录共享 |
| actions, action_index | 已执行和未来脚本动作，未来动作防火墙 | 深复制，不截断；保留现有防火墙 |
| abs_tol, rel_tol, state_tol | 守恒与状态阈值 | 原值复制 |
| geometry_refresh_s, now, next_refresh | 几何更新与绝对时间 | 原值复制 |
| queues, in_flight | Q/I、到达速率及其内部状态 | 全部深复制 |
| arrived, arrived_compensation | 累计到达与补偿求和 | 全部深复制 |
| delivered, delivered_compensation | 累计交付与补偿求和 | 全部深复制 |
| objective_by_commodity, objective_compensation | 累计 J 与补偿项；分支使用终值减初值 | 全部深复制，不重置累计 J |
| transmitted, transmitted_by_commodity | 累计服务统计 | 全部深复制 |
| queue_area, max_queue, max_capacity_violation, max_abs_conservation, max_relative_conservation, conservation_samples | 积分、最大值与校验统计 | 原值复制，不清零 |
| service_rates, service_delays | 当前服务段与传播时延 | 全部深复制 |
| propagation_agenda, sequence | 尚未发生的传播事件及稳定顺序 | 全部深复制 |
| routes, next_hop, graph | 当前路径、下一跳、active/admit 图 | 全部深复制 |
| terminal_log_cursor | 终端日志读取游标 | 原值复制；日志长度不变 |
| route_changes | `_recompute_routes` 创建并 append，后续只读取统计 | 独立列表，共享旧记录 |
| route_state_events | `_recompute_routes` 创建并 append；outage 计算只读 | 独立列表，共享旧记录 |
| terminal_event_sequence | `_microstep` 深复制 details 后追加；outage 与分支事件输出只读 | 独立列表，共享旧记录 |
| timeline | `_record` 创建标量快照并 append | 独立列表，共享旧记录 |
| propagation_closure_events | 闭合后创建结果记录并 append | 独立列表，共享旧记录 |
| executor.log | `_log` 创建终端历史快照并 append；现有 transaction clone 也共享旧记录 | 独立列表，共享旧记录；不使用清空日志的 profiler clone |
| action_results | 嵌套 proposal 可能与脚本动作引用相关 | 保守深复制 |
| graph_event_sequence | 嵌套图数据可能存在别名 | 保守深复制 |
| BBM_count, MBB_count, switch_count | 累计动作分类 | 原值复制 |
| outage_duration_s, no_route_duration_by_commodity, partition_duration_s, partition_node_time_s | 累计断路/分区统计 | 原值或深复制，不重置 |
| backlog_added_during_transition_bits, peak_transition_backlog_bits | 累计重构积压 | 原值复制 |
| transition_episodes, _transition_open, _pending_clearance, _last_transition_active | episode 的 end/peak/clearance 仍可能更新；pending 与 episodes 含同一对象 | 同一 deepcopy memo 深复制，保持分支内别名、隔离分支与 live |
| reporting_enabled, reporting_samples | F3 observational 子类的插值报告 | 原克隆策略仍是分支 false/空列表 |
| 其他/未来新增字段 | 未审计依赖 | 默认 deepcopy，绝不自动省略或共享 |

无字段因“看起来不重要”而置空；只有 reporting 子类继续执行原有的 false/空列表处理。SGP4 provider 原先的 `__deepcopy__` 共享只读模型并独立复制 cache，本轮不改。

## 证明边界与验证

对照路径保留原 deepcopy 实现；测试仅在隔离上下文中替换 clone。对比完整 branch result、canonical state、日志、Q/I/D、累计积分与补偿项、服务状态和事件队列，而非仅比较选中动作。

必须覆盖 BBM、MBB、自然 expiry、零业务 exact tie、非零时刻/积压、过渡中克隆、pending-clearance 别名及两端独立状态。共享历史要求前缀在 live 和 branch 推进后都不被修改，新增记录写入各自列表。

工程工具仅对真实 160 星、rho=0.5、初始时刻生产候选执行 HOLD/首个 BBM/首个 MBB 的新旧 10 秒预测对照，按结构顺序选择，不读取 J 选案例。它不是完整 17 分支/多 epoch final pre-P1 验收，也不重新授权 P1。

后续若有代码开始原地修改以上只读历史，必须重新审计并将对应字段恢复深复制。当前不做 hash 复用、历史报告增量化、多进程或路由优化。
