# Gate F3 Runtime Phase 2B-1 审计

审计范围仅为 `SAME-TOPOLOGY ADJACENCY REUSE`。未实施 destination-tree、reverse-Dijkstra、多源/全对最短路、路径缓存、近似或剪枝。

## 实现前结论

以 160 星 Z_MODERATE 初始 admit graph 为审计对象：

- `directed_edges` 是含 328 条边的 tuple；审计前后 canonical SHA-256 相同；
- 使用 legacy 表达式三次构造 adjacency，keys、neighbor lists 和 neighbor 顺序完全一致；
- adjacency 含 160 个 source keys；
- Dijkstra 主循环只通过 `adjacency.get(node, ())` 读取，没有 `setdefault`、`append` 或 subscript 写入；
- `propagation_delay_s` 和 `time_s` 不进入 adjacency，adjacency 只编码有向 connectivity。

因此同一次 `routes_to_destinations()` 内复用一份 canonical adjacency 不会共享可变搜索状态，也不会缓存权重。

## 冻结语义

canonical adjacency helper 逐字保持原逻辑：

```python
adjacency = {}
for a, b in sorted(set(tuple(edge) for edge in directed_edges)):
    adjacency.setdefault(a, []).append(b)
```

Dijkstra 仍逐 route query 独立执行，并保持：

```python
heap item = (distance, full_path_tuple, node)
candidate = (distance + weight, route + (neighbor,))
candidate < current
```

public `path()` 仍保留逐调用构图行为。`legacy_no_adjacency_reuse_reference()` 使 `routes_to_destinations()` 显式走历史逐 path 构图路径，供测试和工程对照。

审计证据：`outputs/gate_f3_runtime_phase2b1_audit_20260925T141645_111997Z/audit.json`。
