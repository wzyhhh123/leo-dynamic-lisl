# Gate F3 Runtime Phase 2A 审计

审计范围仅包括 `CURRENT_STATE_ONLY` snapshot routing 的重复计算。未运行 registered P1，未修改任何 frozen manifest，未开始 Phase 2B、P2 或 RL。

## 1. `routes_to_destinations()` 的调用结构

`DeterministicShortestPropagationDelayRouter.routes_to_destinations()` 按 commodity、node 两层确定性循环，对每个 `(node, commodity)` 调用一次 `path()`。160 星、16 个 OD commodity 因而每个 topology snapshot 产生：

```text
160 × 16 = 2560 path() calls
```

该结构及 Dijkstra、全路径字典序 tie-breaking 均未修改。

## 2. edge delay provider 的确定性

当前 E2 SGP4 delay provider 在固定 directed edge `(u,v)` 和精确 `time_s` 下是纯确定计算：先使用同一时刻的 SGP4 位置，再计算该有向边端点的欧氏距离和传播时延。只读审计对同一 key 重复调用得到 exact-equal float。

Phase 2A 没有修改 SGP4、坐标系、距离、edge weight 或时间值。

## 3. 重复调用规模

在 160 星初始 epoch 的 HOLD topology 上，一次 legacy `routes_to_destinations()` 的观察值为：

| 指标 | 观察值 |
|---|---:|
| directed edges | 328 |
| route entries / `path()` calls | 2,560 |
| delay-provider calls | 470,077 |
| unique exact `(directed edge, time)` keys | 328 |
| repeated calls | 469,749 |
| mean calls / unique key | 1,433.16 |
| max calls / key | 1,980 |

重复来自 2,560 次独立 Dijkstra 对相同 topology、同一时刻反复读取相同边权。

## 4. proposal topology 去重审计

初始 epoch：raw candidate 64，final proposal 16。把每个 proposal 通过 `candidate_edges(proposal)` 映射为 canonical satellite topology 后：

- unique satellite topologies：16；
- duplicate topology count：0；
- proposal-set SHA-256：`3791664971e36a1f0d9c48535e6b1e0b6cf90c4ace1cc9733723f9ddae0e46b6`。

结论为 `NO_APPLICABLE_DUPLICATES`。本阶段没有实现 identical-topology evaluation reuse；proposal ID、顺序、ready/remaining/usable lifetime 和 B3 eta 均保持逐 proposal 计算。

## 5. 允许的最小实现边界

新增 `ExactEvaluationEdgeDelayMemo`，由 `ScientificSnapshotEvaluator.evaluate_edges()` 在每次 topology evaluation 开始时新建。key 精确为：

```text
(tuple(directed_edge), float(exact_evaluation_time))
```

第一次请求调用原 provider，后续完全相同 key 返回第一次的 exact float。缓存不跨 simulation time、topology evaluation、engine clone 或 real network advance。`legacy_no_cache_reference()` 保留给测试和工程对照。

审计证据：`outputs/gate_f3_runtime_phase2a_audit_20260925T134051_381202Z/audit.json`。
