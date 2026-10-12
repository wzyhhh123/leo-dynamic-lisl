# Gate F1 正确性结果

## 结论

- `Gate F1 infrastructure = PASS`
- `Gate F1 baseline-scoring contract = BLOCKED_REQUIRES_HUMAN_FREEZE`
- `Gate F1 overall = BLOCKED_BEFORE_SCIENTIFIC_B1_B3_IMPLEMENTATION`
- Gate F2/F3/RL 均未启动。

基础设施阻塞并非实现失败。B1/B3 的信息边界已经冻结，但标量决策公式没有冻结；合同明确禁止在此处发明权重或使用最终 J。因此当前结果在完成执行与正确性验证后停在科学评分合同边界。

## 已验证机制

小规模 deterministic fixtures 覆盖：

- 2 秒 periodic callbacks；
- epoch 同时、前一瞬和后一瞬的物理事件顺序；
- 7.3 秒自然到期立即改变物理图、8 秒才再次调用 controller；
- proposer hard pruning、8/8 配额、spillover、确定性排序和 replay；
- sparse 的 2 秒 outage 等号允许及超限拒绝；
- moderate 的 strict-connected 拒绝；
- safety reject-only；
- B0 全 HOLD；
- B1 决策 setup=0、执行真实 setup；
- B2 minimum-hold 与 threshold equality；
- B3 current-state-only 防火墙；
- transition/post-expiry outage 三种组合；
- 多 epoch 下 work conservation、capacity 和 nonnegative queue。

160 星 sanity 使用冻结自然几何，仅检查三个周期 callback、自然 Gate C candidate 经过 proposer/Gate B/C、两种 topology regime 可执行及 Q/I/D 不变量。该 sanity 明确不输出 J、平均时延、交付率、相对提升或 controller 排名。

机器验收、测试数和 evidence 目录由 `python tools/check_gate_f1.py` 生成并写入 `configs/gate_f1_status.json`。

