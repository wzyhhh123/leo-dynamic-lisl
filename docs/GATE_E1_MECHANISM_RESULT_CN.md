# Gate E1 小规模可解释机制实验结果

正式状态：`Gate E1 small-scale mechanism experiments = PASS`。

正式证据目录：`outputs/gate_e1_20260923T024344_227121Z`。

## 1. 执行范围与正确性

冻结 execution manifest 共包含 3,856 个注册点：四个机制模板、两个 router、3,840 个 positive-setup core points、8 个 zero-setup correctness points和 8 个 delayed-anchor points。另执行 8 个 fixed-timescale break-even families。

Gate A–E1 全回归为 `128/128 PASS`。全部注册点满足 paired state/trace identity、work conservation、nonnegative queue 和 capacity constraint；primary 与 robustness router 各重放完全相同的 1,928 个参数点。完整 3,856 点和 8 个 break-even families 第二次重放的 canonical SHA-256 与第一次逐字一致。

8 个 zero-setup points 的 REAL/IDEAL `J` 和 network signature 全部一致。Gate A–E0 的 75 个冻结文件以及 E0/E1 manifest hashes 全部未改变。正式证据目录 15 个文件的 SHA-256 已独立复核一致。

## 2. 注册域结果

3,856 个 point 的分类如下：

| 状态 | 数量 |
|---|---:|
| `SETUP_INDUCED_DECISION_REVERSAL` | 926 |
| `REVERSE_DIRECTION_REVERSAL` | 72 |
| `NO_REVERSAL` | 2,050 |
| `NUMERICALLY_TIED` | 192 |
| `NOT_EVALUABLE_CENSORED` | 616 |

因此本 Gate 的注册域结论是：

```text
SETUP_INDUCED_DECISION_REVERSAL_OBSERVED_IN_REGISTERED_DOMAIN
```

四个模板中的 setup-induced reversal 数量分别为：E-A 348、E-B 530、E-C 24、E-D 24。shortest-propagation 与 load-aware router 各观察到 463 个 setup-induced reversal；这说明 reversal 并非只在其中一个 router 配置下出现，但不等于每个参数点的两种路由行为完全相同。

所有 998 个正向或反向 reversal 均在 `reversal_details.jsonl` 中逐点记录：absolute Delta J、relative effect、REAL/IDEAL 相对 HOLD 的 mean-bit-delay difference、transition backlog、no-route duration、route-change count、focus 与 third-party Delta J。数值 deadband 只用于分类，明细明确标记不得据此推断工程显著性。

setup-induced reversal 的 `r_real` 范围约为 `8.32e-5` 到 `319.5`，中位数约 `8.5`；REAL 相对 HOLD 的 mean-bit-delay 增量范围约 `0.00067 s` 到 `15.975 s`，中位数约 `0.1093 s`。相对效应很大时常伴随很小的 HOLD 分母，因此论文解释必须同时引用绝对 Delta J 和 mean delay，不能只引用比例。

## 3. 四类机制

- **E-A BBM/no-route**：真实 LINK_DOWN 到 LINK_UP 产生 zero-route interval。616 个 censored points 全部保留，并强制 `NOT_EVALUABLE_CENSORED`、`break_even_use=false`；未用截断 `J` 判断 reversal。
- **E-B BBM/connected reroute**：transition 期间始终有 fixed alternate path，但 setup/reroute 仍产生 530 个 setup-induced reversals，说明 reversal 不依赖完整 partition。
- **E-C genuine MBB**：真实空闲 D2/D2 建链后再释放 D1/D1；大多数点为 no-reversal 或 tied，但仍有 24 个 setup-induced reversals，说明“全程连通”不等于“无重构代价”。
- **E-D shared-congestion externality**：962 个 core/zero points 中，485 个 third-party Delta J 为正；其中 92 个同时满足 focus 改善、third-party 变差。该 trade-off 在 shortest router 有 8 点、load-aware router 有 84 点，表明非局部耦合存在，但强度对 routing rule 敏感。

## 4. Delayed anchor

四模板、两 router、三个 delay ratios 共 24 个 delayed branches：18 个执行并完成，6 个在 common drain limit 仍有 residual backlog，按合同记为 `CENSORED_AT_DRAIN_LIMIT`。没有替换任何 candidate，也没有因执行结果重新选点。delayed study 保存在独立的 `delayed_results.jsonl` 中。

## 5. Break-even families

每个 family 固定 `rho=0.8`、`T_demand=20s`、`L_remain=120s`、S0、target、traffic trace 与 router，只改变冻结的 setup grid。

| Template | Router | 注册 bracket | refinement |
|---|---|---|---|
| E-A | shortest | `[0,0.5] s` | `[0.4453125,0.453125] s` |
| E-A | load-aware | `[0,0.5] s` | `[0.4453125,0.453125] s` |
| E-B | shortest | `[1,2] s` | `[1.0234375,1.03125] s` |
| E-B | load-aware | `[1,2] s` | `[1.0234375,1.03125] s` |
| E-C | 两 router | 无 crossing | `NO_BREAK_EVEN_IN_SCANNED_RANGE` |
| E-D | 两 router | 无 crossing | `NO_BREAK_EVEN_IN_SCANNED_RANGE` |

所有 refinement 宽度为 `0.0078125s <= 0.01s`。没有假设单调，没有扩大 setup 范围；每个 family 的 grid points 使用同一 traffic trace hash。

## 6. 结论边界

Gate E1 证明的是：在预注册的小规模、确定性 fluid-workload、等容量链路和 synthetic terminal-window 场景中，忽略真实 transition time 确实会改变 HOLD/SWITCH 判断；这种现象既可由 zero-route outage 引起，也可在保持连通、genuine MBB 或共享拥塞情况下出现。

这些结果还不能直接外推到 160/720 星、真实业务统计或最终 topology controller 性能。E2、matching、MPC、RL 均未启动。当前状态为：

```text
Gate E1 = PASS
Gate E2 started = false
Gate F started = false
```

按合同在此停止，等待人工审查后再决定是否进入 E2。
