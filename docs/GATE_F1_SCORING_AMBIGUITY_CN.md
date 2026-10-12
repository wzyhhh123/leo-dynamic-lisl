# Gate F1 B1/B3 评分合同歧义

## 审计结论

现有冻结合同没有给出 B1 或 B3 唯一、可执行的标量评分公式。因此 Gate F1 可以完成公共执行基础设施和测试注入评分下的状态迁移验证，但不能把测试注入评分称为科学 baseline。

## 已冻结内容

### B1

- 信息边界为 `CURRENT_STATE_ONLY`；
- 决策评价假设 setup 为 0；
- 被选动作仍通过真实 Gate B/C setup 执行；
- safety 只能拒绝物理非法动作，不能替换经济性较差的合法动作；
- 不能读取最终 J、未来真实业务或使用多步 rollout。

### B3

- 信息边界为 `CURRENT_STATE_ONLY`；
- 可以读取当前拓扑、终端、实际 setup、ready time、remaining/usable lifetime、队列、当前 offered load、利用率和路由；
- 只能做 myopic 决策；
- 不能读取 10 秒 B4 forecast、未来真实业务、最终 J 或性能标签。

## 缺失内容

两者均未冻结以下决定，因此无法从合同唯一推出动作：

- HOLD 与各 REPLACE 候选的标量价值定义；
- 多 OD 业务之间如何聚合；
- queue、path service、hop/propagation 和 link utilization 的使用方式；
- 数值归一化、比较方向和量纲；
- 精确 tie/deadband 规则；
- B3 如何把 setup 和 usable lifetime 转化为与当前网络收益可比较的量。

F0 主目标 J 不能直接解决该问题，因为 B1/B3 禁止读取最终 J，B3 又禁止通过真实多步仿真 rollout 计算候选 J。

## 需要人工冻结的最小备选定义

以下定义彼此不等价，必须在科学版 B1/B3 实现前择一冻结。

1. **瞬时 queue-weighted service drift**：在当前 Q、当前 arrival 和当前路由下，比较 HOLD 与零 setup 目标拓扑的瞬时 unfinished-work 导数。需要冻结不可达流、空队列、共享容量和 tie 的处理。
2. **当前路径瓶颈服务增益**：按 OD 当前队列权重聚合目标拓扑对各路径 bottleneck service 的改变。需要冻结路径重算、共享边竞争和多路径不存在时的定义。
3. **解析 break-even proxy**：用当前服务状态估计 usable lifetime 内的服务增益，并扣除真实 transition service loss。需要冻结具体公式、截断方式与多流外部性的计算；不能暗中变成 rollout。

B1 还需明确其“instantaneous target-topology value”采用第 1 项还是第 2 项。B3 需在相同基础信号上明确 setup/lifetime 修正。B2 的 base signal 随 B1 一并待冻结；F1 中的 B2 只作为参数化逻辑验证。

## Gate F1 边界

`IgnoreSetupDynamicScaffold` 与 `SetupAwareGreedyScaffold` 只有显式 `test_only=True` 并注入 deterministic fixture scores 时才能构造。未提供该标志会抛出 `SCORING_CONTRACT_UNRESOLVED_REQUIRES_HUMAN_FREEZE`，从代码层阻止把测试评分误用于科学实验。

