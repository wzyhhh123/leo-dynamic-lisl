# Gate F3 Runtime Phase 2B-2 审计

审计目标是证明 exact same-destination route reuse 的适用边界。本阶段没有引入 reverse-Dijkstra、destination-tree、多源/全对最短路、近似、跨 topology cache 或 Dijkstra 改写。

## Frozen traffic 结构

冻结的 16-OD manifest 包含 14 个 unique destinations：

- `X3_21` 被 `f00`、`f08` 共享；
- `X2_30` 被 `f02`、`f10` 共享；
- 其余 12 个 destinations 各对应一个 commodity。

因此每 topology 的理论查询数为：

```text
legacy:    160 × 16 = 2560
optimized: 160 × 14 = 2240
reduction: 320 / 2560 = 12.5%
```

预审计判定为 `SAME_DESTINATION_REUSE_APPLICABLE`。traffic、commodity 和 manifest 未修改。

## Routing dependency audit

`DeterministicShortestPropagationDelayRouter._path_with_adjacency()` 的参数只有：

```text
source, destination, adjacency, propagation_delay_s, exact time_s
```

代码审计确认它不读取：

- commodity ID；
- commodity source metadata（path 的 source node 除外）；
- traffic rate；
- queue；
- allocation；
- controller identity。

Dijkstra 冻结语义仍在同一 helper 内：

```python
heap = [(0.0, (source,), source)]
candidate = (distance + weight, route + (neighbor,))
candidate < current
```

因此在同一次 `routes_to_destinations()`、同一 adjacency、同一 delay provider 和 exact time 下，`path(node, destination)` 与 commodity identity 无关。

## 实现边界

内部先为每个 exact destination 和每个 sorted node 调用当前冻结的 `_path_with_adjacency()` 一次。随后仍按：

```python
for commodity in sorted(commodities):
    for node in sorted(nodes):
```

写入 routes dict，保持 key insertion order。复用键严格等价于 `(node, destination, current topology evaluation, exact time)`；缓存不跨 topology evaluation。

依赖审计证据：`outputs/gate_f3_runtime_phase2b2_audit_20260925T144943_355836Z/audit.json`。
