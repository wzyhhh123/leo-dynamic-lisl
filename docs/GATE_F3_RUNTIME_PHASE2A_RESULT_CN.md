# Gate F3 Runtime Phase 2A 结果

正式状态：`GATE_F3_RUNTIME_PHASE2A_PASS`

## 实现

只对 `ScientificSnapshotEvaluator.evaluate_edges()` 内的一次 topology route evaluation 使用精确局部 edge-delay memo。未改 shortest-path algorithm、edge weight、tie-breaking、V_v2、allocator、candidate universe、proposal order/hash、Gate B/C、setup、事件顺序、decision cadence、traffic、queue 或 drain。

16 个 final proposal 对应 16 个不同 topology，因此 Phase 2A-2 记录为 `NO_APPLICABLE_DUPLICATES`，没有添加复用分支。

## 严格等价

小型 deterministic fixtures 验证：

- directed edge 和 exact time key；
- 不同方向、不同时间和不同 topology evaluation 不共享缓存；
- 每个 `(node, commodity)` 的 route、None pattern、path node sequence、传播 cost 和 deterministic tie 完全一致；
- HOLD 与每个 candidate 的 V_v2、N_f、C_prop、current demand/allocation、R_snap、Psi、贡献值和 invalid reason 完全一致；
- B1/B3 proposal IDs、顺序、hash、动作、score metadata 和 exact-tie 行为一致；
- 未启用 duplicate-topology shortcut。

160 星 `ENGINEERING_PROFILE_ONLY`、`sim_end_s=0` legacy/optimized 对照验证：

- B1 state SHA 两边均为 `c83dbea43f270b4a859f9df62c35fba0b79d8bcc2cac10a811ba9db8a72b4e69`；
- B1 与 B3 全部捕获状态逐项相等；
- route tables/costs、snapshot evaluations、selected action、terminal/graph events、G_active/G_admit、Q/I/D 和 canonical live state 相等；
- final proposals：16；unique satellite topologies：16。

## 性能

B1 首个 epoch 工程对照：

| 指标 | Legacy | Optimized |
|---|---:|---:|
| `routes_to_destinations()` calls | 18 | 18 |
| `path()` calls | 46,080 | 46,080 |
| prefix delay-provider calls | 8,711,757 | 475,669 |
| sum unique snapshot edge/time keys | 5,576 | 5,576 |
| max provider calls / same key within topology | 2,140 | 1 |
| B1 observe wall time | 37.612 s | 7.553 s |
| total epoch wall time | 50.344 s | 17.478 s |

- delay-provider calls 减少 8,236,088，即 94.54%；
- B1 observe speedup：4.980×；
- total epoch speedup：2.881×。

总 prefix 中剩余的 475,669 次 provider 调用包括 snapshot 之外的 candidate/profiler 工作。本轮不改这些路径。

## 剩余热点

`path()` 调用数仍为 46,080；每个 path 仍重建 adjacency 并独立运行 Dijkstra。destination-tree / reverse-Dijkstra 可作为 Phase 2B 候选，但它会改变 shortest-path implementation，必须单独证明完整路径序列和 lexicographic full-path tie semantics，因此本阶段未实施。

## 完整性

- registered P1 executed = false；
- Phase 2B started = false；
- P2 started = false；
- RL started = false；
- frozen manifests 未修改；
- Phase 1 exact live-state clone 保持不变；
- P1 preflight 通过 Phase 1 + Phase 2A sealed overlay 核验。

机器证据：`outputs/gate_f3_runtime_phase2a_20260925T134746_379320Z/report.json`。
