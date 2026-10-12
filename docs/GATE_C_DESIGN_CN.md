# Gate C core framework 设计

Gate C 将 Gate A 的连续可见窗口与 Gate B 的双动态终端执行器接起来，形成四层只判定接口：

`geometry feasibility → terminal/hardware feasibility → transition consequence profile → operational policy`

它只返回 `ACCEPT / REJECT + reason + profile`，不修复、不改写、不排序上层 proposal。临时分区只在 policy 层判断，不属于 physical rejection。

## 模块边界

| 模块 | 职责 |
|---|---|
| `geometry_interface.py` | 半开可见窗口 `[start,end)`、剩余有效期、跨面候选、保守 expiry 接入 Gate B |
| `physical_feasibility.py` | 明确 terminal pair、端口/预约/setup检查和 hardware hooks；确定性 allocator |
| `transition_profiler.py` | 克隆同一个 Gate B executor，按真实事件组回放 active/admit 图 |
| `operational_policy.py` | STRICT_CONNECTED 或参数化 BOUNDED_OUTAGE；不冻结 T_max |
| `reference_topology.py` | traffic-agnostic 的三种 Z_ref 构造与结构统计；不选择最终方案 |

Gate C 不复制 setup lifecycle。CONNECT、DRAINING、TX completion、LINK_DOWN、RETARGETING、ACQUIRING、LINK_UP、MBB release-after、expiry、abort 和 stale-event 都由 `TerminalExecutor` 执行。

## Geometry 和物理层

上游候选是当前窗口内全部 inter-plane pair，不限定 adjacent plane。连接要求当前时刻满足 `[start,end)` 且 Gate B 计算出的 `t_ready < end`。右截断的 600 s 端点仅是当前资产的 prediction horizon；执行器可保守地在该端点释放链，但报告不得把它当成真实自然寿命。

hardware contract 独立于 5000 km geometry cutoff。参数表记录 value、unit、source、status、notes，状态支持 `literature_calibrated / provisional / sensitivity_only / unresolved`。当前只用 provisional fixtures 测接口，正式 calibration 为 PENDING。

物理拒绝原因包括 `NOT_VISIBLE`、`INSUFFICIENT_LIFETIME`、`TERMINAL_BUSY`、`RESERVATION_CONFLICT`、`HARDWARE_RANGE_FAIL`、`FOV_FAIL`、`TRACKING_FAIL`、`SETUP_NOT_COMPLETABLE`。`NETWORK_PARTITION` 不在这一层。

## Transition consequence

Profiler 在执行器副本上合并已有 pending 事件和新 command batch。相同时间的全部 Gate B 事件由 `advance(t)` 完整执行后才采样一次图，避免人为事件排序产生零时连通。

- ACTIVE link 同时进入 active/admit 图。
- DRAINING link 保留在 active 图，从 admit 图移除。
- setup/pending 在 LINK_UP 前不进入任何图。
- fixed intra edge 是图输入，不占 dynamic terminal。

输出包含分区起止、持续时间、components、affected nodes、active/admit断开标志、恢复事件、恢复计划和分类。分类为 `no_partition`、`temporary_recoverable_partition` 或 `unrecoverable_partition`；超过 T_max 在 policy 结果中标 `bounded_but_long_partition`。

## Operational policy

`STRICT_CONNECTED`：active 或 admit 任一图出现非零常值区间分区即拒绝。

`BOUNDED_OUTAGE(T_max)`：只有确定恢复且最大连续 outage `≤ T_max` 才接受，等号明确接受。无恢复、预测范围内没有恢复、自然 expiry 后不恢复分别返回机器原因。当前不冻结 T_max。

所有非 HOLD proposal 都失败时返回 `hold_only=true, fallback=HOLD`；validator 不生成替代动作。

## 已知限制

本 Gate 没有 traffic、queue、routing、packet service、business-aware matching、MPC、RL 或性能比较。Z_ref 内部贪心只是 deterministic 初始化构造。全局结论限定于4-plane pilot study；FOV、姿态、slew、tracking 和真实 hardware range 尚未完成文献标定。
