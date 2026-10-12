# Gate E2：160 星自然几何机制验证结果

## 正式状态

**Gate E2 160-star natural-geometry mechanism validation = PASS**。

本轮执行 80 个 logical paired points，对应 50 个 unique physical execution scenarios 和 120 个唯一 branch tasks。E-C/E-D 重复物理动作只执行一次，再映射回两个逻辑类别。正式结果完整重放第二遍，canonical result 一致。

证据目录：`outputs/gate_e2_20260923T073629_059828Z`。

## 总体结果

- reversal 状态：`{"NOT_EVALUABLE_CENSORED": 52, "NO_REVERSAL": 22, "SETUP_INDUCED_DECISION_REVERSAL": 6}`；
- censor 状态：`{"CENSORED_AT_DRAIN_LIMIT": 52, "COMPLETE": 28}`；
- router reversal-status 一致/不一致：32 / 8；
- 所有完整性检查、冻结 hash 和全回归均通过。

这些计数只描述冻结的结构化机制案例，不是现实 LEO 网络中的 reversal 概率。

## 分机制结果

### E-A：BBM temporary partition

执行 20 个 logical points。所有 REAL 分支均记录 `BBM_count=1, MBB_count=0`，2 s setup 阶段均产生正 transition backlog。低 κ₂ 场景的 setup partition 为 2 s；中 κ₂ 场景报告的 54.026 s 是“2 s setup outage + 新链路随后自然到期后的持续无路由时间”的全评价窗累计量，不能把 54.026 s 全部解释成 setup outage。逐点 affected commodities、backlog、recovery 和 drain 记录在 `case_details.jsonl`。

### E-B：connected BBM reroute

正式结果为 `NOT_NATURALLY_AVAILABLE_UNDER_CURRENT_SPARSE_ZREF`，四个 κ₂ bin 均保留原始 `NO_ELIGIBLE_CASE`。这只说明当前三 bridge 的稀疏 Z_ref 没有自然 E-B case。

### E-C：genuine MBB

执行 30 个 logical points。所有 REAL 分支都满足 `action_accepted=true, MBB_count=1, BBM_count=0`，因此 terminal transition 确实按 genuine MBB 执行。低 κ₂ 场景在全评价窗内无 forced outage；中、高 κ₂ 场景在 LINK_UP 后先保持连续，但目标链路分别在剩余 6.970 s 和 3.713 s 后自然到期，之后稀疏 Z_ref 失去路由并被 censor。

机器结果中的 `MBB_continuity=false` 和 `forced_outage_duration>0` 按**整个评价窗**的 no-route duration 定义，包含链路自然到期后的 outage；它不表示 2 s MBB setup 期间发生了 BBM。E-C 的可解释结论应同时查看 `MBB_count/BBM_count`、natural expiry 和 censor 状态。setup opportunity cost 和 κ₂ 分层结果见逐点记录。

### E-D：shared-congestion externality

执行 30 个 logical points，其中 9 个未 censor。focus 改善且 third party 恶化的点数为 5；shared-link utilization 与两个 router 的逐点差异记录在 `case_details.jsonl`。

## 解释边界

setup=2 s 是 Gate C simplified parametric audit fixture，不是真实商业 LCT 硬件测量值。自然 κ₂、candidate 和 Z_ref 均未因结果修改。Gate F、matching、MPC、RL、240/720 星实验及 setup sensitivity 均未启动。

52–55 s 的 `temporary_partition_duration` / `forced_outage_duration` 是全评价窗累计指标，主要对应短寿命候选自然到期后的无路由区间。setup 本身的过渡效应由 `transition_backlog`、`BBM_count/MBB_count` 与 setup 区间事件单独判读。
