# Gate F3 Runtime Phase 1 Clone Dependency Audit

状态：PASS。范围仅为 proposer/counterfactual clone/deepcopy；没有修改候选上限、排序、Gate C、safety、BBM/MBB、setup、事件优先级、decision cadence、candidate source、proposal identity/hash 或 router。

## 调用链与旧复制行为

FrozenTerminalPairProposer.propose() 本身不直接复制 executor。每个候选先调用 Gate C physical_layer.evaluate()；其 connect_command() 对整个 TerminalExecutor 做一次 deepcopy，随后 trial.submit() 再做一次 deepcopy。物理合法后，RegimeSafetyAdapter.evaluate() 调用 profile_transition()；旧实现再次复制整个 executor，随后 trial.submit() 再复制一次。因此一个进入 safety 的候选最多触发四次递归复制。

旧 profile_transition() 复制整个对象：卫星与固定端口 inventory、320 个动态终端对象、links、reservations、future-event heap、序列号、不变量计数，以及从场景初始化起累计的完整 log。其中 log 的每条记录还包含当时全部 terminal snapshots，是递归复制的主要来源。

## TerminalExecutor 顶层字段审计

| 字段 | 未来 transition 依赖 | Phase 1 克隆规则 | 依据 |
|---|---|---|---|
| satellite_ids | 是 | 共享 immutable tuple | 决定合法终端 inventory 与图节点 |
| terminals | 是 | 新 dict；逐个浅复制 Terminal | phase、peer、reservation、version、时间戳会在反事实中改变 |
| fixed_ports | 是（不变量） | 共享 immutable frozenset | 用于 inventory invariant；不会被执行器修改 |
| now | 是 | 复制 float | 决定事件合法性、ready time 和 horizon |
| links | 是 | 新 dict；逐个复制 Link；tx_end 单独复制 | active/admit 图、drain、free time、expiry 均依赖 |
| reservations | 是 | 新 dict；逐个复制 Reservation | 双端原子预约、版本、MBB release ownership 均依赖 |
| events | 是 | 新 heap list；共享 immutable event tuples/payloads | event pop/push 必须隔离；payload 只由 tuple/string/number 组成 |
| log | 否，属于 historical/audit | transaction clone：新 list、共享追加后只读的旧记录；counterfactual clone：置空 | 所有写操作只有 _log().append()；profiler 只需要 clone 后的新 suffix |
| _sequence | 是 | 复制 int | 保持同时间事件稳定排序与后续 event IDs |
| _reservation_sequence | 是 | 复制 int | 保持 reservation/link ID 完全一致 |
| invariant_checks | 不影响物理转移，属于 audit counter | 仍复制 int | 保留以避免可观察状态差异 |

实现有 _CLONE_AUDITED_FIELDS 精确白名单。未来新增或删除顶层字段时，克隆会以 TERMINAL_EXECUTOR_CLONE_AUDIT_REQUIRED 明确失败，不能静默遗漏。

## 嵌套字段审计

### Terminal

terminal_id, phase, current_peer, target_peer, reservation_id, event_version, orientation, orientation_frame, terminal_free_time, retarget_start/end, acquisition_start/end, active_link_start, visibility_end 全部保留。它们分别参与端口身份、占用/预约冲突、stale-event guard、指向完成、ready time、setup 生命周期、active 状态和自然到期；没有一个可置空。字段值是字符串、数字、None 或 tuple，因此复制 Terminal 对象后可安全共享其 immutable 值。

### Link

link_id, endpoints, start, visibility_end, draining, tx_end, release_owner 全部保留。tx_end 是唯一嵌套 mutable dict，必须独立复制；其余值为 scalar/tuple。它们共同决定 active/admit graph、DRAINING、新 TX admission、LINK_DOWN 时间、MBB release ownership 和 expiry。

### Reservation

reservation_id, endpoints, versions, durations, orientations, acquisition, visibility_end, release_after, acquiring 全部保留。它们决定双边绑定、retarget/acquisition 时间、stale event、可见期 abort 与 MBB 后释放。字段值均为 scalar/tuple，因此复制 Reservation 对象即可。

## 可省略历史与严格边界

只有 counterfactual clone 的既有 log 可以置空。它不参与 physical feasibility、BBM/MBB classification、ready time、remaining/usable lifetime、outage duration、active/admit graph、safety result、proposal order 或 proposal_set_sha256。

counterfactual 中新产生的记录仍完整保留，transition_log 与 legacy reference 完全一致。final_executor.snapshot() 也一致；只有不属于 snapshot 的旧日志前缀被省略。

Gate C 源码没有修改。其外层 deepcopy 保留；其内部 submit() 现在使用 exact structural transaction clone，从而避免第二次递归复制历史。无法严格证明可省略的字段全部保留。
